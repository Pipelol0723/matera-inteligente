// Conexión en vivo: un WebSocket con la API que avisa cada medición nueva de las plantas del usuario.
// El navegador no deja poner la cabecera Authorization en un WebSocket, así que el token va en el
// primer mensaje. Si la conexión se cae, se reintenta con esperas cada vez más largas y, al volver,
// las pantallas piden de nuevo sus datos para no perder lo que llegó mientras tanto.
import { API_BASE } from "./config.js";
import { sesion } from "./sesion.js";

const URL_EN_VIVO = `${API_BASE.replace(/^http/, "ws")}/tiempo-real`;
const ESPERAS_MS = [1000, 2000, 4000, 8000, 16000, 30000];

// Estados para el indicador de la barra: "apagado" (sin sesión), "conectando", "en-vivo" y "caido".
export function crearTiempoReal({ alCambiarEstado, alSesionInvalida }) {
  const oyentes = new Set();
  let socket = null;
  let encendido = false;
  let intentos = 0;
  let reintento = null;

  function conectar() {
    if (!sesion.activa() || (encendido && socket)) return;
    encendido = true;
    clearTimeout(reintento);
    abrir(sesion.token());
  }

  function abrir(token) {
    const actual = new WebSocket(URL_EN_VIVO);
    socket = actual;
    alCambiarEstado("conectando");
    actual.addEventListener("open", () => actual.send(JSON.stringify({ tipo: "autenticar", token })));
    actual.addEventListener("message", (evento) => recibir(actual, evento.data));
    actual.addEventListener("close", () => alCerrarse(actual));
  }

  function recibir(actual, texto) {
    let mensaje;
    try {
      mensaje = JSON.parse(texto);
    } catch {
      return;
    }
    if (mensaje.tipo === "listo") {
      const volvio = intentos > 0;
      intentos = 0;
      alCambiarEstado("en-vivo");
      if (volvio) avisar({ tipo: "reconectado" });
    } else if (mensaje.tipo === "error") {
      // La sesión ya no sirve (se cerró, venció o desactivaron la cuenta): no se reintenta.
      if (mensaje.error === "SESION_INVALIDA") {
        apagar();
        alSesionInvalida();
      }
    } else {
      avisar(mensaje);
    }
  }

  function alCerrarse(actual) {
    if (actual !== socket) return; // ya se reemplazó o se apagó a propósito
    socket = null;
    if (!encendido) return;
    alCambiarEstado("caido");
    const espera = ESPERAS_MS[Math.min(intentos, ESPERAS_MS.length - 1)];
    intentos += 1;
    reintento = setTimeout(() => {
      if (encendido && sesion.activa()) abrir(sesion.token());
    }, espera);
  }

  function apagar() {
    encendido = false;
    intentos = 0;
    clearTimeout(reintento);
    const anterior = socket;
    socket = null;
    anterior?.close();
    alCambiarEstado("apagado");
  }

  function avisar(mensaje) {
    for (const oyente of oyentes) oyente(mensaje);
  }

  return {
    conectar,
    desconectar: apagar,
    // oyente(mensaje): {tipo: "medicion", planta, medicion, diagnostico} o {tipo: "reconectado"}.
    alRecibir: (oyente) => oyentes.add(oyente),
  };
}
