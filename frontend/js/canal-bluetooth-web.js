// Adaptador «BluetoothWeb» del puerto CanalPlaca: el Bluetooth LE de la placa desde Chrome o Edge, con Web
// Bluetooth (navigator.bluetooth, que solo existe con HTTPS o en localhost). El equipo no deja su WiFi, así
// que la app sigue alcanzando la API todo el tiempo. Solo pone el transporte: el contrato (pedazos de 20
// bytes, trozos con cabecera, la clave y mantener la conexión) está en CanalBluetooth.
import { CONEXION_CANCELADA, fallaDelCanal } from "./canal-placa.js";
import {
  CanalBluetooth, CARACTERISTICA_PEDIDO, CARACTERISTICA_RESPUESTA, PREFIJO_DEL_NOMBRE, SERVICIO_PLACA,
} from "./canal-bluetooth.js";

const INTENTOS_DE_CONEXION = 3; // en Windows, la primera conexión GATT a veces falla y la segunda entra
const CONEXION_MAXIMA_MS = 8000; // un intento que no termina en este tiempo se da por fallido

const esperar = (ms) => new Promise((listo) => setTimeout(listo, ms));

// La promesa, o un error si no termina en ms milisegundos.
function antesDe(ms, promesa) {
  let reloj;
  const vencida = new Promise((_, rechazar) => {
    reloj = setTimeout(() => rechazar(new Error(`sin respuesta en ${ms / 1000} s`)), ms);
  });
  return Promise.race([promesa, vencida]).finally(() => clearTimeout(reloj));
}

export class BluetoothWeb extends CanalBluetooth {
  constructor() {
    super({
      id: "bluetooth",
      nombre: "Bluetooth",
      descripcion: "Este equipo no deja su WiFi: la app le habla a la placa por Bluetooth, con la clave de su pantalla.",
      icono: "bluetooth",
      motivoNoDisponible: "Por Bluetooth: este navegador no lo permite aquí. Se necesita Chrome o Edge, con la app abierta en localhost o con HTTPS.",
    });
    this.dispositivo = null;
    this.pedidoGatt = null; // la característica del pedido
    this.respuestaGatt = null; // la característica de la respuesta
    this.alDesconectarse = () => {
      this.pedidoGatt = null;
      this.alCortarse();
    };
    this.alCambiarRespuesta = (evento) => this.alNotificar(evento.target.value);
  }

  // Se lee cada vez: así también sirve un navigator.bluetooth puesto después de cargar (las pruebas).
  get bluetooth() {
    return globalThis.navigator?.bluetooth ?? null;
  }

  disponible() {
    return Boolean(this.bluetooth) && globalThis.isSecureContext !== false;
  }

  get placa() {
    return this.dispositivo?.name ?? "";
  }

  get conectado() {
    return Boolean(this.dispositivo?.gatt?.connected && this.pedidoGatt && this.respuestaGatt);
  }

  async abrirTransporte({ elegir }) {
    if (!this.bluetooth) {
      throw fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", this.motivoNoDisponible);
    }
    if (!this.dispositivo) {
      if (!elegir) throw fallaDelCanal("BLUETOOTH_CORTADO", "Se perdió la placa elegida. Vuelva a buscarla.");
      let dispositivo;
      try {
        // Por el servicio (va en el anuncio) o por el nombre (va en la respuesta al escaneo).
        dispositivo = await this.bluetooth.requestDevice({
          filters: [{ services: [SERVICIO_PLACA] }, { namePrefix: PREFIJO_DEL_NOMBRE }],
          optionalServices: [SERVICIO_PLACA],
        });
      } catch (error) {
        throw await this.errorDelSelector(error);
      }
      dispositivo.addEventListener("gattserverdisconnected", this.alDesconectarse);
      this.dispositivo = dispositivo;
    }
    let ultimo = null;
    for (let intento = 1; intento <= INTENTOS_DE_CONEXION; intento += 1) {
      try {
        await antesDe(CONEXION_MAXIMA_MS, this.abrirGatt());
        return;
      } catch (error) {
        ultimo = error;
        if (!this.dispositivo) break; // se desconectó a propósito mientras tanto
        if (intento < INTENTOS_DE_CONEXION) await esperar(400 * intento);
      }
    }
    const nombre = this.placa ? `«${this.placa}»` : "la placa";
    throw fallaDelCanal("BLUETOOTH_CORTADO", `No se pudo conectar con ${nombre} por Bluetooth${ultimo?.message ? ` (${ultimo.message})` : ""}. Acérquese a la matera y vuelva a intentarlo; si sigue igual, apague y encienda el Bluetooth del equipo.`);
  }

  async abrirGatt() {
    const servidor = await this.dispositivo.gatt.connect();
    const servicio = await servidor.getPrimaryService(SERVICIO_PLACA);
    const pedido = await servicio.getCharacteristic(CARACTERISTICA_PEDIDO);
    const respuesta = await servicio.getCharacteristic(CARACTERISTICA_RESPUESTA);
    this.respuestaGatt?.removeEventListener("characteristicvaluechanged", this.alCambiarRespuesta);
    respuesta.addEventListener("characteristicvaluechanged", this.alCambiarRespuesta);
    await respuesta.startNotifications(); // antes del primer pedido: si no, la placa no tiene por dónde responder
    this.respuestaGatt = respuesta;
    this.pedidoGatt = pedido;
  }

  async escribirPedazo(bytes) {
    const pedido = this.pedidoGatt;
    if (!pedido || !this.dispositivo?.gatt?.connected) throw fallaDelCanal("BLUETOOTH_CORTADO", "Se cortó la conexión por Bluetooth con la placa.");
    try {
      // Escritura con respuesta, de a un pedazo: nunca una escritura larga.
      if (typeof pedido.writeValueWithResponse === "function") await pedido.writeValueWithResponse(bytes);
      else await pedido.writeValue(bytes);
    } catch (error) {
      throw fallaDelCanal("BLUETOOTH_CORTADO", `Se cortó la conexión por Bluetooth con la placa${error?.message ? ` (${error.message})` : ""}.`);
    }
  }

  cerrarTransporte() {
    const dispositivo = this.dispositivo;
    this.respuestaGatt?.removeEventListener("characteristicvaluechanged", this.alCambiarRespuesta);
    this.respuestaGatt = null;
    this.pedidoGatt = null;
    this.dispositivo = null;
    if (!dispositivo) return;
    dispositivo.removeEventListener("gattserverdisconnected", this.alDesconectarse);
    if (dispositivo.gatt?.connected) dispositivo.gatt.disconnect();
  }

  // Lo que respondió el selector de Chrome, en los errores del puerto.
  async errorDelSelector(error) {
    if (error?.name === "NotFoundError") {
      // «User cancelled the requestDevice() chooser.»: la persona cerró la lista sin elegir.
      if (/cancel/i.test(error.message ?? "")) {
        return fallaDelCanal(CONEXION_CANCELADA, "No eligió ninguna placa.");
      }
      let hayBluetooth = true;
      try {
        hayBluetooth = await this.bluetooth.getAvailability();
      } catch {
        // Sin getAvailability: se queda con el mensaje general.
      }
      if (!hayBluetooth) {
        return fallaDelCanal("BLUETOOTH_APAGADO", "El Bluetooth de este equipo está apagado o no está disponible. Enciéndalo y vuelva a buscar la placa.");
      }
      return fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", `No se pudo buscar la placa por Bluetooth${error.message ? ` (${error.message})` : ""}. Revise que el Bluetooth del equipo esté encendido.`);
    }
    if (error?.name === "SecurityError" || error?.name === "NotAllowedError") {
      return fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", "El navegador no dejó usar el Bluetooth en esta página. Revise los permisos del sitio o abra la app en localhost o con HTTPS.");
    }
    return fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", `No se pudo usar el Bluetooth${error?.message ? ` (${error.message})` : ""}.`);
  }
}
