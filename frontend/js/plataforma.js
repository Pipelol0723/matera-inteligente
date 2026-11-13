// Dónde corre el front: en un navegador (la web) o dentro de la app Android (Capacitor). Es el mismo front;
// la app solo cambia algunos adaptadores (el Bluetooth, las notificaciones y la dirección del servidor), y
// cada uno pregunta aquí. En el navegador no existe window.Capacitor, así que todo esto queda apagado.
//
// La app no usa un empaquetador: los plugins nativos se usan por el puente que Capacitor inyecta en la
// página antes de cargarla (window.Capacitor.Plugins.<nombre>, con los mismos métodos que sus paquetes npm).

const capacitor = globalThis.Capacitor;

// Verdadero dentro de la app Android.
export const EN_APP = typeof capacitor?.isNativePlatform === "function" && capacitor.isNativePlatform() === true;

// El plugin nativo con ese nombre («BluetoothLe», «LocalNotifications», «App»), o null fuera de la app.
export function pluginNativo(nombre) {
  return EN_APP ? capacitor?.Plugins?.[nombre] ?? null : null;
}

// En la app, CapacitorHttp cambia fetch por uno nativo (sin CORS ni contenido mixto), pero ese fetch no
// respeta la señal de cancelación en POST, PUT y DELETE: una API que no responde dejaba el botón esperando
// sin fin, porque los plazos de api.js (15 s) y de la placa (3 y 6 s) se cumplen cancelando la señal. Aquí se
// envuelve una sola vez para que, al cancelarse la señal, la promesa termine con AbortError como en el
// navegador (la petición nativa sigue sola hasta su fin, y su respuesta se descarta).
if (EN_APP && typeof globalThis.fetch === "function") {
  const nativo = globalThis.fetch;
  globalThis.fetch = (recurso, opciones) => {
    const senal = opciones?.signal;
    if (!senal) return nativo(recurso, opciones);
    const cancelada = () => new DOMException("La petición se canceló.", "AbortError");
    if (senal.aborted) return Promise.reject(cancelada());
    return new Promise((resolver, rechazar) => {
      const alCancelar = () => rechazar(cancelada());
      senal.addEventListener("abort", alCancelar, { once: true });
      nativo(recurso, opciones).then(resolver, rechazar).finally(() => senal.removeEventListener("abort", alCancelar));
    });
  };
}

// El esquema de los enlaces que abren la app (el mismo nombre del paquete Android). El QR de Mi cuenta lleva
// co.edu.usergioarboleda.matera://servidor?api=<dirección de la API>.
export const ESQUEMA_APP = "co.edu.usergioarboleda.matera";
