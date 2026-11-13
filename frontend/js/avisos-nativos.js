// Los avisos de la matera (PASO_A_CRITICO y SE_MARCHITO) como notificaciones de Android, dentro de la app,
// con @capacitor/local-notifications: la WebView no tiene la Notification API del navegador. avisos.js le
// pregunta aquí si está en la app; en el navegador todo esto queda apagado (disponible es falso).
// - Las notificaciones son inmediatas, nunca programadas (isExactNotification: false: sin alarmas exactas).
// - Van en un canal propio, «Avisos de las materas», que la persona puede ajustar en los ajustes de Android.
// - El permiso (POST_NOTIFICATIONS, Android 13 o más) se pide solo cuando la persona activa los avisos.
// - Tocar la notificación abre la app en Mis materas.
// MagicOS (y otros Android) cierran las apps en segundo plano: los avisos llegan mientras la app está abierta.
import { pluginNativo } from "./plataforma.js";

const plugin = pluginNativo("LocalNotifications");
const CANAL = "avisos-materas";

let estado = "pendiente"; // «concedido», «pendiente» o «bloqueado», como estadoPermiso() de avisos.js
let alTocar = null;
const alCambiar = new Set();

function estadoDe(respuesta) {
  if (respuesta?.display === "granted") return "concedido";
  if (respuesta?.display === "denied") return "bloqueado";
  return "pendiente"; // «prompt» o «prompt-with-rationale»
}

function cambiarEstado(nuevo) {
  if (nuevo === estado) return;
  estado = nuevo;
  for (const oyente of alCambiar) oyente(estado);
}

async function revisarPermiso() {
  try {
    cambiarEstado(estadoDe(await plugin.checkPermissions()));
  } catch {
    // Se queda con el que tenía.
  }
}

// Un número de 31 bits por aviso (planta, lectura y tipo), con FNV-1a: el mismo aviso reemplaza su
// notificación en vez de repetirla.
function numeroDe(clave) {
  let n = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(clave)) n = Math.imul(n ^ byte, 0x01000193) >>> 0;
  return (n & 0x7fffffff) || 1;
}

async function iniciar() {
  await revisarPermiso();
  try {
    await plugin.createChannel({
      id: CANAL,
      name: "Avisos de las materas",
      description: "Cuando una matera pasa a CRÍTICO o se marchita.",
      importance: 4, // alta: se ve aunque la app esté abierta
      visibility: 1,
      vibration: true,
    });
  } catch {
    // Sin canal propio, Android usa el de la app.
  }
  try {
    await plugin.addListener("localNotificationActionPerformed", () => alTocar?.());
  } catch {
    // Tocarla igual abre la app, aunque no lleve a Mis materas.
  }
  // Al volver a la app: la persona pudo cambiar el permiso en los ajustes de Android.
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) revisarPermiso();
  });
}

const listo = plugin ? iniciar() : Promise.resolve();

const TEXTOS = {
  concedido: "Cuando una matera pasa a CRÍTICO o se marchita, la app le avisa con una notificación del celular.",
  pendiente: "Cuando una matera pasa a CRÍTICO o se marchita, la app avisa dentro de la pantalla. " +
    "Si quiere, también puede avisarle con una notificación del celular.",
  bloqueado: "Las notificaciones de la app están desactivadas: los avisos se ven dentro de la pantalla. " +
    "Puede activarlas en Ajustes > Aplicaciones > Matera > Notificaciones.",
};

// Una línea para dejarla «sin optimizar»: MagicOS cierra las apps en segundo plano.
const SEGUNDO_PLANO = "Los avisos llegan mientras la app está abierta: el celular la cierra en segundo plano. " +
  "Para que aguante minimizada, déjela sin optimizar en Ajustes > Batería > Inicio de aplicaciones > Matera (gestionar manualmente).";

export const notificacionesNativas = {
  disponible: Boolean(plugin),

  estado: () => estado,

  // oyente(estado) cuando el permiso cambia (al iniciar, al pedirlo o al volver de los ajustes).
  alCambiar: (oyente) => alCambiar.add(oyente),

  // Solo desde un toque de la persona («Activar notificaciones»): Android muestra su pregunta.
  async pedir() {
    await listo;
    try {
      cambiarEstado(estadoDe(await plugin.requestPermissions()));
    } catch {
      await revisarPermiso();
    }
    return estado;
  },

  // Muestra la notificación si hay permiso. Devuelve falso si no lo hay (entonces avisos.js avisa dentro de
  // la pantalla); si Android la rechaza después, llama a siFalla.
  mostrar(titulo, cuerpo, clave, { alVer, siFalla }) {
    if (estado !== "concedido") return false;
    alTocar = alVer;
    plugin.schedule({
      notifications: [{
        id: numeroDe(clave),
        title: titulo,
        body: cuerpo,
        channelId: CANAL,
        isExactNotification: false,
        autoCancel: true,
      }],
    }).catch(() => {
      revisarPermiso();
      siFalla?.();
    });
    return true;
  },

  // El texto de la pantalla Juego para cada estado del permiso.
  texto: (actual) => [TEXTOS[actual] ?? TEXTOS.pendiente, SEGUNDO_PLANO].join(" "),
};
