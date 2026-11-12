// Adaptador «RedDeLaPlaca» del puerto CanalPlaca: la API local de la placa por HTTP, en su red propia
// (Matera-…). Es el camino del QR: el equipo se une a esa red, y mientras tanto no alcanza la API.
// La dirección es http://192.168.4.1, o la de ?placa= para probar sin la placa (config.js solo acepta este
// equipo o la red de la placa).
import { PLACA_BASE, PLACA_DE_PRUEBA } from "./config.js";
import { CanalPlaca, errorDeLaPlaca, fallaDelCanal } from "./canal-placa.js";
import { ErrorApi } from "./api.js";

const PLACA_MAXIMO_MS = 3000; // una petición a la placa que no termina en este tiempo se corta
const CONFIGURAR_MAXIMO_MS = 6000;

// Un AbortSignal que se dispara a los ms milisegundos (AbortSignal.timeout no está en todos los navegadores).
function senalCon(ms) {
  const control = new AbortController();
  setTimeout(() => control.abort(), ms);
  return control.signal;
}

export class RedDeLaPlaca extends CanalPlaca {
  constructor() {
    super({
      id: "red",
      nombre: "la red de la placa",
      descripcion: "Este equipo se une un momento a la red WiFi de la matera, con el QR o con la clave de su pantalla. Sirve en cualquier navegador.",
      icono: "wifi",
      dejaLaRed: true,
      pideClave: false,
    });
  }

  get aviso() {
    // Solo con ?placa= (pruebas): la clave del WiFi viaja a esa dirección, no a la placa de verdad.
    return PLACA_DE_PRUEBA
      ? `Prueba: este asistente habla con ${PLACA_BASE} y no con la placa real (http://192.168.4.1). La clave del WiFi se enviará a esa dirección.`
      : "";
  }

  get direccion() {
    return PLACA_BASE;
  }

  info() {
    return this.pedir("/info");
  }

  configurar(datos) {
    return this.pedir("/configurar", { metodo: "POST", datos, ms: CONFIGURAR_MAXIMO_MS });
  }

  estado() {
    return this.pedir("/estado");
  }

  async cerrar() {
    await this.pedir("/cerrar", { metodo: "POST" });
  }

  // La API local responde JSON con CORS abierto, y solo la alcanza quien está en su red.
  async pedir(ruta, { metodo = "GET", datos, ms = PLACA_MAXIMO_MS } = {}) {
    const opciones = { method: metodo, cache: "no-store", signal: senalCon(ms) };
    if (datos !== undefined) {
      // Petición simple (text/plain, con el cuerpo en JSON): así el navegador no necesita la consulta
      // previa de CORS (OPTIONS) y basta con que la placa responda Access-Control-Allow-Origin.
      opciones.headers = { "Content-Type": "text/plain;charset=UTF-8" };
      opciones.body = JSON.stringify(datos);
    }
    let respuesta;
    let cuerpo = null;
    try {
      respuesta = await fetch(`${PLACA_BASE}${ruta}`, opciones);
      const texto = await respuesta.text();
      if (texto) cuerpo = JSON.parse(texto);
    } catch (error) {
      if (!respuesta || error.name === "AbortError") {
        throw fallaDelCanal("PLACA_INALCANZABLE", `No se pudo contactar la placa en ${PLACA_BASE}. Revise que este equipo siga unido a la red Matera-… de la matera.`);
      }
      if (respuesta.ok) {
        throw new ErrorApi(respuesta.status, { error: "RESPUESTA_INVALIDA", mensaje: "La placa respondió algo que no es JSON." });
      }
    }
    if (!respuesta.ok) {
      // Un detalle de texto (otra versión de la placa) se usa como mensaje.
      const mensaje = cuerpo?.mensaje ?? (typeof cuerpo?.detalle === "string" ? cuerpo.detalle : undefined);
      throw errorDeLaPlaca(respuesta.status, { ...cuerpo, mensaje });
    }
    return cuerpo;
  }
}
