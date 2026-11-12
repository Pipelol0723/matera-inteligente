// «CanalBluetooth»: lo común de los adaptadores Bluetooth LE del puerto CanalPlaca. Es el contrato de la
// sección «Bluetooth LE» de firmware/README.md, igual desde Chrome (BluetoothWeb) que desde la app Android
// (BluetoothNativo, fase 17):
//   - cada pedido es un JSON {"op","clave","id",...} que se escribe en pedazos de 20 bytes, uno detrás de
//     otro y esperando cada escritura: nunca una escritura larga (la placa corta la conexión);
//   - la respuesta {"op","id","http","cuerpo"} llega en trozos, uno por notificación, con 3 bytes de
//     cabecera (número de respuesta, índice y total). Se juntan los bytes y recién ahí se lee el UTF-8;
//   - las notificaciones se activan antes del primer pedido (lo hace el transporte al abrirse);
//   - la placa corta la conexión si en 2 minutos no llega un pedido con la clave: mientras la clave sirve,
//     se le pide «estado» cada 45 s sin uso.
// Un pedido a la vez: la placa junta los bytes en orden y el navegador no acepta dos escrituras juntas.
// Cada adaptador solo pone su transporte: abrirTransporte, escribirPedazo, cerrarTransporte y conectado.
import { CanalPlaca, CONEXION_CANCELADA, errorDeLaPlaca, fallaDelCanal } from "./canal-placa.js";

export const SERVICIO_PLACA = "4d540001-d5b8-499f-bad6-c70b14aebec3";
export const CARACTERISTICA_PEDIDO = "4d540002-d5b8-499f-bad6-c70b14aebec3";
export const CARACTERISTICA_RESPUESTA = "4d540003-d5b8-499f-bad6-c70b14aebec3";
export const PREFIJO_DEL_NOMBRE = "Matera-"; // la placa se anuncia con el nombre de su red

const PEDAZO = 20; // bytes por escritura: así nunca hay escritura larga, con cualquier MTU
const CABECERA = 3; // número de respuesta, índice del trozo y total de trozos
const RESPUESTA_MAXIMA_MS = 15000; // si en este tiempo no llegan todos los trozos, se vuelve a pedir
const MANTENER_MS = 45000; // menos que los 2 minutos sin pedidos que corta la placa

// El pedido en pedazos de hasta `tamano` bytes. Se parte por bytes, sin cuidar los caracteres: la placa
// junta los bytes antes de leer el UTF-8.
export function partirPedido(pedido, tamano = PEDAZO) {
  const bytes = new TextEncoder().encode(JSON.stringify(pedido));
  const pedazos = [];
  for (let inicio = 0; inicio < bytes.length; inicio += tamano) pedazos.push(bytes.slice(inicio, inicio + tamano));
  return pedazos;
}

// Junta los trozos de cada respuesta, por su número. agregar() devuelve el objeto JSON cuando ya llegaron
// todos los trozos de esa respuesta, y null mientras falten.
export class JuntadorDeRespuestas {
  constructor() {
    this.enCamino = new Map(); // número de respuesta -> { total, partes }
  }

  agregar(valor) {
    const bytes = valor instanceof Uint8Array ? valor : new Uint8Array(valor.buffer, valor.byteOffset, valor.byteLength);
    if (bytes.length < CABECERA) return null;
    const [numero, indice, total] = bytes;
    if (total === 0 || indice >= total) return null;
    let respuesta = this.enCamino.get(numero);
    if (!respuesta || respuesta.total !== total) {
      respuesta = { total, partes: new Array(total), llegaron: 0 };
      this.enCamino.set(numero, respuesta);
    }
    if (!respuesta.partes[indice]) respuesta.llegaron += 1;
    respuesta.partes[indice] = bytes.slice(CABECERA); // copia: el transporte puede reutilizar su buffer
    if (respuesta.llegaron < total) return null;
    this.enCamino.delete(numero);
    const todo = new Uint8Array(respuesta.partes.reduce((largo, parte) => largo + parte.length, 0));
    let posicion = 0;
    for (const parte of respuesta.partes) {
      todo.set(parte, posicion);
      posicion += parte.length;
    }
    // fatal: un UTF-8 roto es una respuesta inválida, no texto con caracteres de reemplazo.
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(todo));
  }

  vaciar() {
    this.enCamino.clear();
  }
}

const cortado = (mensaje = "Se cortó la conexión por Bluetooth con la placa. Acérquese a la matera y vuelva a intentarlo.") =>
  fallaDelCanal("BLUETOOTH_CORTADO", mensaje);

// Con 429, la placa dice en su mensaje cuántos segundos faltan («... espera 60 s ...»). Solo se lee para
// mostrar la cuenta atrás: el bloqueo lo decide la placa.
const SEGUNDOS_EN_EL_MENSAJE = /(\d+)\s*s\b/;

export class CanalBluetooth extends CanalPlaca {
  constructor(opciones) {
    super({ ...opciones, dejaLaRed: false, pideClave: true });
    this.clave = ""; // la de la pantalla: solo en memoria
    this.juntador = new JuntadorDeRespuestas();
    this.cola = Promise.resolve(); // los pedidos, uno detrás de otro
    this.pendiente = null; // { id, resolver, rechazar }: el pedido que espera su respuesta
    this.contador = 0;
    this.claveAceptada = false; // la placa respondió algo que no es 401 ni 429: se puede mantener la conexión
    this.relojMantener = null;
    // Los plazos, en milisegundos (las pruebas los acortan).
    this.tiempos = { respuesta: RESPUESTA_MAXIMA_MS, mantener: MANTENER_MS };
  }

  // ---- el transporte: lo pone cada adaptador ----

  // Verdadero si hay conexión y las notificaciones de la respuesta están activas.
  get conectado() {
    return false;
  }

  // Abre la conexión con la placa y activa las notificaciones de la respuesta. Con elegir, puede mostrar el
  // selector de placas; sin él, solo vuelve a la placa ya elegida. Cada notificación va a alNotificar(valor),
  // y un corte, a alCortarse(). Los errores son fallaDelCanal (status 0), o CONEXION_CANCELADA.
  async abrirTransporte() {
    throw this.sinImplementar("abrirTransporte");
  }

  // Una escritura con respuesta (write request) de hasta 20 bytes en la característica del pedido.
  async escribirPedazo() {
    throw this.sinImplementar("escribirPedazo");
  }

  // Cierra la conexión y suelta la placa elegida: la próxima vez se vuelve a elegir.
  cerrarTransporte() {
  }

  // ---- lo que llama el transporte ----

  alNotificar(valor) {
    let respuesta;
    try {
      respuesta = this.juntador.agregar(valor);
    } catch {
      this.pendiente?.rechazar(fallaDelCanal("RESPUESTA_INVALIDA", "La placa respondió por Bluetooth algo que no es JSON."));
      return;
    }
    if (!respuesta || !this.pendiente) return;
    // Sin id es que la placa no pudo leer el pedido (SOLICITUD_INVALIDA): es la respuesta del que espera.
    // Con otro id, es la respuesta tardía de un pedido que ya se volvió a mandar.
    if (respuesta.id !== undefined && respuesta.id !== this.pendiente.id) return;
    this.pendiente.resolver(respuesta);
  }

  alCortarse() {
    this.juntador.vaciar();
    clearTimeout(this.relojMantener);
    this.pendiente?.rechazar(cortado());
  }

  // ---- el puerto ----

  async conectar({ clave } = {}) {
    if (typeof clave === "string") {
      this.clave = clave;
      this.claveAceptada = false;
    }
    if (!this.conectado) await this.abrir({ elegir: true });
  }

  info() {
    return this.pedir("info");
  }

  configurar({ red, claveRed, servidores }) {
    return this.pedir("configurar", { red, claveRed, servidores });
  }

  estado() {
    return this.pedir("estado");
  }

  async cerrar() {
    await this.pedir("cerrar");
    // La placa apaga su Bluetooth medio segundo después: ya no hay nada que mantener.
    this.claveAceptada = false;
    clearTimeout(this.relojMantener);
  }

  desconectar() {
    clearTimeout(this.relojMantener);
    this.claveAceptada = false;
    this.clave = "";
    this.juntador.vaciar();
    this.pendiente?.rechazar(cortado());
    try {
      this.cerrarTransporte();
    } catch {
      // Ya estaba cerrado.
    }
  }

  // ---- pedidos ----

  async abrir({ elegir }) {
    this.juntador.vaciar();
    await this.abrirTransporte({ elegir });
  }

  pedir(op, datos = {}) {
    const turno = this.cola.then(() => this.pedirAhora(op, datos, true));
    this.cola = turno.catch(() => {});
    return turno;
  }

  async pedirAhora(op, datos, reintentar) {
    let respuesta;
    try {
      if (!this.conectado) await this.abrir({ elegir: false }); // la misma placa, sin selector
      this.contador += 1;
      respuesta = await this.mandar({ op, clave: this.clave, id: String(this.contador), ...datos });
    } catch (fallo) {
      // Un corte o una respuesta que no llegó: se vuelve a mandar una vez (todos los pedidos se pueden repetir).
      if (reintentar && fallo?.status === 0 && fallo.codigo !== CONEXION_CANCELADA) return this.pedirAhora(op, datos, false);
      throw fallo;
    }
    const http = Number(respuesta?.http);
    const cuerpo = respuesta?.cuerpo ?? null;
    if (!Number.isInteger(http) || http < 200) {
      throw fallaDelCanal("RESPUESTA_INVALIDA", "La placa respondió por Bluetooth sin su código HTTP.");
    }
    if (http === 401 || http === 429 || cuerpo?.error === "SOLICITUD_INVALIDA") {
      // La placa no aceptó la clave (o no leyó el pedido): no hay conexión que mantener.
      this.claveAceptada = false;
      clearTimeout(this.relojMantener);
    } else {
      this.mantener(); // la clave sirvió, aunque el error sea de los datos (400 PARAMETRO_INVALIDO, 409 SIN_RED)
    }
    if (http >= 300) throw this.errorDe(http, cuerpo);
    return http === 204 ? null : cuerpo;
  }

  async mandar(pedido) {
    const espera = new Promise((resolver, rechazar) => {
      this.pendiente = { id: pedido.id, resolver, rechazar };
    });
    espera.catch(() => {}); // si falla mientras se escribe, el error sale de la escritura
    const reloj = setTimeout(() => {
      this.pendiente?.rechazar(fallaDelCanal("PLACA_SIN_RESPUESTA", `La placa no respondió por Bluetooth en ${Math.round(this.tiempos.respuesta / 1000)} s. Acérquese a la matera y vuelva a intentarlo.`));
    }, this.tiempos.respuesta);
    try {
      for (const pedazo of partirPedido(pedido)) await this.escribirPedazo(pedazo);
      return await espera;
    } finally {
      clearTimeout(reloj);
      this.pendiente = null;
    }
  }

  // Mientras la clave sirve, un «estado» cada 45 s sin pedidos: así la placa no corta la conexión mientras
  // la persona escribe la clave del WiFi.
  mantener() {
    this.claveAceptada = true;
    clearTimeout(this.relojMantener);
    this.relojMantener = setTimeout(() => {
      if (this.conectado && this.claveAceptada) this.estado().catch(() => {});
    }, this.tiempos.mantener);
  }

  errorDe(http, cuerpo) {
    if (http === 429 && cuerpo?.error === "DEMASIADOS_INTENTOS") {
      const segundos = Number(SEGUNDOS_EN_EL_MENSAJE.exec(cuerpo.mensaje ?? "")?.[1]) || null;
      return errorDeLaPlaca(http, {
        error: cuerpo.error,
        mensaje: segundos
          ? `Hubo demasiadas claves equivocadas y la placa no atiende pedidos por ${segundos} s. Revise la clave de su pantalla y vuelva a intentarlo después.`
          : "Hubo demasiadas claves equivocadas y la placa no atiende pedidos por un momento. Revise la clave de su pantalla y vuelva a intentarlo después.",
        detalle: segundos ? { segundos } : {},
      });
    }
    return errorDeLaPlaca(http, cuerpo);
  }
}
