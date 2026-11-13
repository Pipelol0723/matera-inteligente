// Adaptador «BluetoothNativo» del puerto CanalPlaca: el Bluetooth LE de la placa desde la app Android, con
// el plugin @capacitor-community/bluetooth-le (por ble-nativo.js, que tiene los métodos de su BleClient). Es el
// mismo contrato que BluetoothWeb (pedazos de 20 bytes, trozos con cabecera, la clave y mantener la conexión,
// todo en CanalBluetooth): aquí solo va el transporte. El asistente no cambia; canales-placa.js lo pone primero
// cuando corre dentro de la app, donde la WebView no tiene navigator.bluetooth.
//
// Android pide el permiso «Dispositivos cercanos» (BLUETOOTH_SCAN, con neverForLocation, y BLUETOOTH_CONNECT)
// la primera vez que se busca la placa, desde el toque de la persona; nunca la ubicación (salvo Android 11 o
// menos, que la exige para buscar por Bluetooth).
import { CONEXION_CANCELADA, fallaDelCanal } from "./canal-placa.js";
import { CanalBluetooth, CARACTERISTICA_RESPUESTA, CARACTERISTICA_PEDIDO, SERVICIO_PLACA } from "./canal-bluetooth.js";
import { crearClienteBle } from "./ble-nativo.js";

const INTENTOS_DE_CONEXION = 2; // el plugin ya espera hasta 10 s por intento
const ESPERA_ENTRE_INTENTOS_MS = 500;

// La lista de placas la muestra Android con los textos del plugin, que vienen en inglés.
const TEXTOS_DEL_SELECTOR = {
  scanning: "Buscando placas Matera…",
  cancel: "Cancelar",
  availableDevices: "Placas encontradas",
  noDeviceFound: "No se encontró ninguna placa",
};

const esperar = (ms) => new Promise((listo) => setTimeout(listo, ms));
const detalleDe = (error) => {
  const mensaje = String(error?.message ?? error ?? "").trim();
  return mensaje ? ` (${mensaje})` : "";
};

export class BluetoothNativo extends CanalBluetooth {
  // ble: un cliente con los métodos de BleClient. Las pruebas pasan uno falso.
  constructor({ ble = crearClienteBle() } = {}) {
    super({
      id: "bluetooth-nativo",
      nombre: "Bluetooth",
      descripcion: "El celular no deja su WiFi: la app le habla a la placa por Bluetooth, con la clave de su pantalla.",
      icono: "bluetooth",
      motivoNoDisponible: "Por Bluetooth: esta instalación de la app no trae el Bluetooth. Vuelva a instalarla.",
    });
    this.ble = ble;
    this.iniciado = false;
    this.dispositivo = null; // { deviceId, name }: la placa elegida
    this.abierto = false; // conectado y con las notificaciones de la respuesta activas
    this.alDesconectarse = (deviceId) => {
      if (deviceId !== this.dispositivo?.deviceId) return; // una desconexión pedida por la app, o de otra placa
      this.abierto = false;
      this.alCortarse();
    };
  }

  disponible() {
    return this.ble?.disponible !== false;
  }

  get placa() {
    return this.dispositivo?.name ?? "";
  }

  get conectado() {
    return this.abierto;
  }

  async abrirTransporte({ elegir }) {
    await this.iniciar();
    if (!this.dispositivo) {
      if (!elegir) throw fallaDelCanal("BLUETOOTH_CORTADO", "Se perdió la placa elegida. Vuelva a buscarla.");
      await this.revisarEncendido();
      let elegida;
      try {
        // Por el servicio, que va en el anuncio. Android muestra la lista y la persona elige.
        elegida = await this.ble.requestDevice({ services: [SERVICIO_PLACA], optionalServices: [SERVICIO_PLACA] });
      } catch (error) {
        throw this.traducir(error);
      }
      if (!elegida?.deviceId) throw fallaDelCanal(CONEXION_CANCELADA, "No eligió ninguna placa.");
      this.dispositivo = { deviceId: elegida.deviceId, name: elegida.name ?? "" };
    }
    const { deviceId } = this.dispositivo;
    let ultimo = null;
    for (let intento = 1; intento <= INTENTOS_DE_CONEXION; intento += 1) {
      try {
        await this.ble.connect(deviceId, this.alDesconectarse);
        // Antes del primer pedido: si no, la placa no tiene por dónde responder.
        await this.ble.startNotifications(deviceId, SERVICIO_PLACA, CARACTERISTICA_RESPUESTA, (valor) => this.alNotificar(valor));
        if (this.dispositivo?.deviceId !== deviceId) break; // se desconectó a propósito mientras tanto
        this.abierto = true;
        return;
      } catch (error) {
        ultimo = error;
        if (this.dispositivo?.deviceId !== deviceId) break;
        try {
          await this.ble.disconnect(deviceId);
        } catch {
          // No estaba conectada.
        }
        if (intento < INTENTOS_DE_CONEXION) await esperar(ESPERA_ENTRE_INTENTOS_MS * intento);
      }
    }
    const nombre = this.placa ? `«${this.placa}»` : "la placa";
    throw fallaDelCanal("BLUETOOTH_CORTADO", `No se pudo conectar con ${nombre} por Bluetooth${detalleDe(ultimo)}. Acérquese a la matera y vuelva a intentarlo; si sigue igual, apague y encienda el Bluetooth del celular.`);
  }

  async escribirPedazo(bytes) {
    const deviceId = this.dispositivo?.deviceId;
    if (!this.abierto || !deviceId) throw fallaDelCanal("BLUETOOTH_CORTADO", "Se cortó la conexión por Bluetooth con la placa.");
    try {
      // Escritura con respuesta, de a un pedazo: nunca una escritura larga.
      await this.ble.write(deviceId, SERVICIO_PLACA, CARACTERISTICA_PEDIDO, new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength));
    } catch (error) {
      throw fallaDelCanal("BLUETOOTH_CORTADO", `Se cortó la conexión por Bluetooth con la placa${detalleDe(error)}.`);
    }
  }

  cerrarTransporte() {
    const deviceId = this.dispositivo?.deviceId;
    this.dispositivo = null; // antes de desconectar: así su aviso no cuenta como un corte
    this.abierto = false;
    if (deviceId) this.ble.disconnect(deviceId).catch(() => {});
  }

  // La primera vez: pide los permisos de Bluetooth (con neverForLocation) y pone los textos de la lista.
  async iniciar() {
    if (this.iniciado) return;
    if (!this.disponible()) throw fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", this.motivoNoDisponible);
    try {
      await this.ble.initialize({ androidNeverForLocation: true });
    } catch (error) {
      throw this.traducir(error);
    }
    try {
      await this.ble.setDisplayStrings(TEXTOS_DEL_SELECTOR);
    } catch {
      // Quedan los textos en inglés: la lista igual sirve.
    }
    this.iniciado = true;
  }

  // Con el Bluetooth apagado, Android pregunta si lo enciende. Si la persona dice que no, es BLUETOOTH_APAGADO.
  async revisarEncendido() {
    try {
      if (await this.ble.isEnabled()) return;
    } catch {
      return; // no se pudo saber: lo dirá la búsqueda
    }
    try {
      await this.ble.requestEnable();
    } catch {
      // Dijo que no.
    }
    let encendido = false;
    try {
      encendido = await this.ble.isEnabled();
    } catch {
      encendido = false;
    }
    if (!encendido) {
      throw fallaDelCanal("BLUETOOTH_APAGADO", "El Bluetooth del celular está apagado. Enciéndalo y vuelva a buscar la placa.");
    }
  }

  // Los mensajes del plugin (en inglés), en los errores del puerto.
  traducir(error) {
    const mensaje = String(error?.message ?? error ?? "");
    if (/cancel|no device found/i.test(mensaje)) return fallaDelCanal(CONEXION_CANCELADA, "No eligió ninguna placa.");
    if (/permission/i.test(mensaje)) {
      return fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", "La app no tiene permiso para buscar dispositivos cercanos. Permítalo en Ajustes > Aplicaciones > Matera > Permisos y vuelva a intentarlo.");
    }
    if (/not (enabled|turned on)|disabled|is off/i.test(mensaje)) {
      return fallaDelCanal("BLUETOOTH_APAGADO", "El Bluetooth del celular está apagado. Enciéndalo y vuelva a buscar la placa.");
    }
    if (/not supported|not available/i.test(mensaje)) {
      return fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", "Este celular no tiene Bluetooth LE: use la red de la placa.");
    }
    return fallaDelCanal("BLUETOOTH_NO_DISPONIBLE", `No se pudo usar el Bluetooth${detalleDe(error)}.`);
  }
}
