// El front se sirve desde otro origen que el backend (RA2), por eso la URL va completa.
// La API se busca en el mismo equipo desde el que se abrió el front: en el PC es localhost, y desde un
// celular de la misma red es la IP del PC (con el backend arrancado con MATERA_HOST=0.0.0.0).
const EQUIPO = globalThis.location?.hostname || "127.0.0.1";
export const API_BASE = `http://${EQUIPO}:5000/api/v1`;

// Con el front abierto en este mismo PC, la API sigue respondiendo aunque el PC cambie de WiFi.
export const API_EN_ESTE_EQUIPO = esLoopback(EQUIPO);

// La API local de la placa: solo responde en su propia red WiFi (Matera-…), mientras se conecta.
const PLACA_POR_DEFECTO = "http://192.168.4.1";

// Para probar sin la placa: ?placa=http://127.0.0.1:8099 en la dirección del front. Solo se acepta una
// dirección de este equipo o de la red de la placa (192.168.4.x): la clave del WiFi viaja a ella, y un
// enlace con ?placa= no debe poder llevársela a otro equipo de la red.
export const PLACA_BASE = placaPedida() ?? PLACA_POR_DEFECTO;

// Verdadero si la placa no está en su dirección de siempre (una prueba): el asistente lo avisa.
export const PLACA_DE_PRUEBA = PLACA_BASE !== PLACA_POR_DEFECTO;

function placaPedida() {
  try {
    const pedida = new URLSearchParams(globalThis.location?.search ?? "").get("placa");
    if (!pedida) return null;
    const url = new URL(pedida);
    return url.protocol === "http:" && (esLoopback(url.hostname) || esRedDeLaPlaca(url.hostname)) ? url.origin : null;
  } catch {
    return null;
  }
}

function esLoopback(nombre) {
  return nombre === "localhost" || nombre === "[::1]" || /^127\.\d+\.\d+\.\d+$/.test(nombre);
}

function esRedDeLaPlaca(nombre) {
  return /^192\.168\.4\.\d{1,3}$/.test(nombre);
}
