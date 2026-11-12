// El puerto «CanalPlaca»: lo que el asistente «Conectar sensor» necesita de la placa mientras se conecta, sin
// saber por dónde le llega. Son puertos y adaptadores, ahora del lado del cliente: el asistente
// (conectar-sensor.js) solo conoce esta clase, y cada adaptador la hereda y traduce a su transporte las cuatro
// operaciones de la API local de la placa (firmware/README.md):
//   - RedDeLaPlaca (canal-red-placa.js): HTTP en la red propia de la placa, en http://192.168.4.1.
//   - BluetoothWeb (canal-bluetooth-web.js): Bluetooth LE desde Chrome o Edge, con navigator.bluetooth.
//   - BluetoothNativo (fase 17): el mismo Bluetooth desde la app Android, con @capacitor-community/bluetooth-le.
//     Hereda de CanalBluetooth (canal-bluetooth.js), que ya parte los pedidos y junta las respuestas, y solo
//     pone su transporte. Se agrega en canales-placa.js y el asistente no cambia.
//
// Lo que devuelve cada operación es el cuerpo JSON de la API local, y un error es un ErrorApi con su código
// HTTP y el cuerpo de error de la placa: {error, mensaje, detalle}. Si el canal no llega a la placa (no hay
// red, se cortó el Bluetooth, nadie respondió), el ErrorApi tiene status 0.
// Aquí no hay reglas de negocio: el código, la huella, las etapas y la validación de cada dato los decide la placa.
import { ErrorApi } from "./api.js";

// La persona cerró el selector sin elegir una placa: no es una falla, solo hay que volver a ofrecerlo.
export const CONEXION_CANCELADA = "CONEXION_CANCELADA";

// Un error del canal, no de la placa: status 0, como un fetch que no llegó.
export const fallaDelCanal = (error, mensaje) => new ErrorApi(0, { error, mensaje });

// Verdadero si el pedido no llegó a la placa (o su respuesta no volvió): se puede probar por otro canal.
export const esFallaDelCanal = (fallo) => fallo?.status === 0 && fallo?.codigo !== CONEXION_CANCELADA;

// El error que respondió la placa, con su código HTTP. Igual por los dos canales.
export function errorDeLaPlaca(http, cuerpo) {
  return new ErrorApi(http, {
    error: typeof cuerpo?.error === "string" ? cuerpo.error : "ERROR_DE_LA_PLACA",
    mensaje: typeof cuerpo?.mensaje === "string" ? cuerpo.mensaje : `La placa respondió ${http}.`,
    detalle: cuerpo?.detalle && typeof cuerpo.detalle === "object" ? cuerpo.detalle : {},
  });
}

export class CanalPlaca {
  // id: se guarda con el avance del asistente.
  // nombre, descripcion e icono ("bluetooth" o "wifi"): para ofrecerlo. El nombre va después de «por»
  // («Seguir por Bluetooth», «Seguir por la red de la placa»).
  // dejaLaRed: el equipo tiene que dejar su WiFi para usarlo (mientras tanto no alcanza la API).
  // pideClave: cada pedido lleva la clave que muestra la pantalla de la placa, y la escribe la persona.
  // motivoNoDisponible: por qué no se ofrece en este navegador, si disponible() es falso.
  constructor({ id, nombre, descripcion = "", icono = "", dejaLaRed = false, pideClave = false, motivoNoDisponible = "" }) {
    if (new.target === CanalPlaca) throw new TypeError("CanalPlaca es un puerto: se usa uno de sus adaptadores.");
    Object.assign(this, { id, nombre, descripcion, icono, dejaLaRed, pideClave, motivoNoDisponible });
  }

  // ¿Se puede usar en este navegador?
  disponible() {
    return true;
  }

  // Un aviso para mostrar mientras se usa (por ejemplo, que es una placa de prueba), o "".
  get aviso() {
    return "";
  }

  // El nombre con el que se anuncia la placa, si el canal lo sabe (por ejemplo, «Matera-7518JP»), o "".
  get placa() {
    return "";
  }

  // Abre el canal. Con pideClave, recibe la clave de la pantalla (y la cambia si ya estaba abierto).
  // Puede mostrar un selector del navegador: se llama desde un clic.
  async conectar() {
  }

  // {codigo, huella, redes: [{nombre, senal, segura}]}
  async info() {
    throw this.sinImplementar("info");
  }

  // {red, claveRed, servidores} -> {etapa, detalle}
  async configurar() {
    throw this.sinImplementar("configurar");
  }

  // {etapa, detalle}
  async estado() {
    throw this.sinImplementar("estado");
  }

  // La placa apaga su red (y su Bluetooth). No devuelve nada.
  async cerrar() {
    throw this.sinImplementar("cerrar");
  }

  // Suelta el canal y borra la clave de la memoria. Nunca falla.
  desconectar() {
  }

  sinImplementar(operacion) {
    return new TypeError(`${this.constructor.name} no implementa ${operacion}().`);
  }
}
