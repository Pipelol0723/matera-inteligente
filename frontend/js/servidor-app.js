// App Android: a qué servidor le habla la app. En la web no hace nada (la API se deduce del equipo, config.js).
// - La primera vez pide la dirección de la API, la prueba contra la API y la guarda en el celular
//   (direccion-api.js). Sin dirección, el diálogo no se puede cerrar.
// - Después se ve y se cambia en Ingresar y en Mi cuenta. Cambiarla cierra la sesión (el token es de otra API)
//   y recarga la página, para que todo el front use la dirección nueva.
// - Recibe el enlace del QR de Mi cuenta en la web (co.edu.usergioarboleda.matera://servidor?api=...), con el
//   plugin @capacitor/app. Un enlace solo propone el servidor: la persona lo revisa y lo confirma, porque a ese
//   servidor la app le mandará su correo y su contraseña. Cualquier página o QR podría traer un enlace así.
import { cerrarSesion, ErrorApi } from "./api.js";
import { API_BASE } from "./config.js";
import { direccionDelEnlace, guardarDireccion, normalizarDireccion } from "./direccion-api.js";
import { mostrarError, ocupado } from "./formularios.js";
import { EN_APP, pluginNativo } from "./plataforma.js";
import { sesion } from "./sesion.js";

const PRUEBA_MAXIMO_MS = 8000;
const ENLACES_VISTOS = "matera.app.enlaces-vistos"; // en sessionStorage: el enlace con que se abrió la app

const TEXTO_NORMAL = "Escriba la dirección de la API que muestra Mi cuenta en la web, o escanee su QR con la cámara " +
  "del celular. El celular y el PC tienen que estar en la misma red (por ejemplo, el PC unido al hotspot del celular).";
const TEXTO_DEL_ENLACE = "Un QR o un enlace propone este servidor. Revise que sea el suyo antes de guardarlo: la app " +
  "le mandará a esa dirección su correo y su contraseña.";

export function iniciarServidorApp() {
  if (!EN_APP) return;
  const $ = (id) => document.getElementById(id);
  const dialogo = $("dialogo-servidor");
  const formulario = $("form-servidor");
  const campo = $("servidor-direccion");
  const error = $("error-servidor");
  const cancelar = $("servidor-cancelar");
  let obligatorio = false;

  $("acceso-servidor").hidden = false;
  $("cuenta-servidor").hidden = false;
  $("acceso-servidor-direccion").textContent = API_BASE || "sin elegir";
  $("cuenta-servidor-direccion").textContent = API_BASE;
  $("acceso-servidor-cambiar").addEventListener("click", () => abrir());
  $("cuenta-servidor-cambiar").addEventListener("click", () => abrir());
  cancelar.addEventListener("click", () => dialogo.close());
  // Sin dirección no hay app: el diálogo no se cierra con Escape ni con el botón atrás del navegador.
  dialogo.addEventListener("cancel", (evento) => {
    if (obligatorio) evento.preventDefault();
  });

  function abrir({ propuesta = "" } = {}) {
    obligatorio = !API_BASE;
    cancelar.hidden = obligatorio;
    $("servidor-texto").textContent = propuesta ? TEXTO_DEL_ENLACE : TEXTO_NORMAL;
    campo.value = propuesta || API_BASE;
    mostrarError(error, null);
    if (!dialogo.open) dialogo.showModal();
    if (!propuesta) campo.focus();
  }

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    mostrarError(error, null);
    const direccion = normalizarDireccion(campo.value);
    if (!direccion) {
      mostrarError(error, new ErrorApi(0, {
        error: "DIRECCION_INVALIDA",
        mensaje: "Escriba la IP del PC (por ejemplo, 10.34.101.124) o la dirección completa de la API (http://10.34.101.124:5000/api/v1).",
      }));
      campo.focus();
      return;
    }
    // El campo no se reescribe con la forma completa: con el teclado de Android abierto, cambiar su valor
    // por código lo dejaba a medias. La dirección completa sale en los mensajes.
    try {
      await ocupado($("servidor-guardar"), () => probar(direccion));
    } catch (fallo) {
      mostrarError(error, fallo);
      return;
    }
    if (direccion === API_BASE) {
      dialogo.close();
      return;
    }
    try {
      guardarDireccion(direccion);
    } catch {
      mostrarError(error, new ErrorApi(0, { error: "SIN_ALMACENAMIENTO", mensaje: "El celular no dejó guardar la dirección." }));
      return;
    }
    if (sesion.activa()) {
      try {
        await cerrarSesion(); // en la API de antes
      } catch {
        // Si ya no responde, la sesión igual se cierra en el celular.
      }
      sesion.cerrar();
    }
    location.reload();
  });

  escucharEnlaces((propuesta) => abrir({ propuesta }));
  if (!API_BASE) abrir();
}

// ¿Es la API de Matera? Sin token, toda ruta privada responde 401 con el cuerpo de error de siempre (R7 y RA1):
// así se prueba sin cuenta y sin escribir nada.
async function probar(direccion) {
  const control = new AbortController();
  const reloj = setTimeout(() => control.abort(), PRUEBA_MAXIMO_MS);
  let respuesta;
  try {
    respuesta = await fetch(`${direccion}/parametros`, { cache: "no-store", signal: control.signal });
  } catch {
    throw new ErrorApi(0, {
      error: "SIN_CONEXION",
      mensaje: `No respondió nada en ${direccion}. Revise la IP, que el backend esté corriendo con MATERA_HOST=0.0.0.0 y que el celular esté en la misma red que el PC.`,
    });
  } finally {
    clearTimeout(reloj);
  }
  let cuerpo = null;
  try {
    cuerpo = await respuesta.json();
  } catch {
    cuerpo = null;
  }
  if (respuesta.status === 401 && typeof cuerpo?.error === "string") return;
  throw new ErrorApi(respuesta.status, {
    error: "NO_ES_LA_API",
    mensaje: `En ${direccion} respondió algo, pero no la API de Matera. Revise el puerto (el del backend es 5000) y que termine en /api/v1.`,
  });
}

// El enlace con que se abrió la app (getLaunchUrl) se ofrece una vez por sesión de la app; uno que llega con la
// app abierta (appUrlOpen: se volvió a escanear el QR), siempre.
function escucharEnlaces(proponer) {
  const app = pluginNativo("App");
  if (!app) return;
  const ofrecer = (url, { unaVez }) => {
    const propuesta = direccionDelEnlace(url);
    if (!propuesta || propuesta === API_BASE) return;
    if (unaVez) {
      const vistos = leerVistos();
      if (vistos.includes(url)) return;
      guardarVistos([...vistos, url]);
    }
    proponer(propuesta);
  };
  try {
    app.addListener("appUrlOpen", (evento) => ofrecer(evento?.url ?? "", { unaVez: false }));
  } catch {
    // Sin el plugin, el enlace solo abre la app.
  }
  Promise.resolve(app.getLaunchUrl?.())
    .then((lanzamiento) => {
      if (lanzamiento?.url) ofrecer(lanzamiento.url, { unaVez: true });
    })
    .catch(() => {});
}

function leerVistos() {
  try {
    const lista = JSON.parse(sessionStorage.getItem(ENLACES_VISTOS));
    return Array.isArray(lista) ? lista.filter((x) => typeof x === "string") : [];
  } catch {
    return [];
  }
}

function guardarVistos(lista) {
  try {
    sessionStorage.setItem(ENLACES_VISTOS, JSON.stringify(lista.slice(-10)));
  } catch {
    // Sin almacenamiento: se puede volver a ofrecer al recargar, nada más.
  }
}
