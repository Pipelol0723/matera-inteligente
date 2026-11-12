// Avisos del juego. Cuando GET /juego/materas trae el aviso de una matera (PASO_A_CRITICO o SE_MARCHITO:
// lo decide el dominio con la última lectura), la app avisa una sola vez por esa lectura. Las ya avisadas
// (planta, momento de la lectura y tipo de aviso) se guardan en localStorage, por usuario: la consulta cada
// 10 s no repite el aviso, ni al recargar, ni al volver a ingresar, ni en otra pestaña.
//
// Cómo avisa:
// - Con contexto seguro (por ejemplo, el front en http://localhost) y el permiso concedido: una notificación
//   del navegador (Notification API). El permiso se pide con un botón, nunca al cargar la página.
// - Si no (por ejemplo, el celular que abre el front por la red local, en http): un aviso dentro de la
//   página, y el celular vibra si el navegador lo permite.
import { dibujoDeMatera, globoDe } from "./dibujo-planta.js";
import { crear, rotuloDeEstado } from "./formato.js";
import { sesion } from "./sesion.js";

const GUARDADO = "matera.juego.avisados";
const clave = () => `${GUARDADO}.${sesion.usuario()?.id ?? "nadie"}`;
const MAXIMO_GUARDADOS = 200;
const MAXIMO_EN_PAGINA = 3;
const VIBRACION = [200, 100, 200];

const TEXTOS = {
  PASO_A_CRITICO: (apodo) => `${apodo} pasó a ${rotuloDeEstado("CRITICO")}`,
  SE_MARCHITO: (apodo) => `${apodo} se marchitó`,
};

const HORA = new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" });

// «sin-contexto» (http fuera de este equipo), «no-soportado», «pendiente», «concedido» o «bloqueado».
export function estadoPermiso() {
  if (!globalThis.isSecureContext) return "sin-contexto";
  if (!("Notification" in globalThis)) return "no-soportado";
  if (Notification.permission === "granted") return "concedido";
  if (Notification.permission === "denied") return "bloqueado";
  return "pendiente";
}

function leer() {
  try {
    const lista = JSON.parse(localStorage.getItem(clave()));
    return Array.isArray(lista) ? lista.filter((x) => typeof x === "string").slice(-MAXIMO_GUARDADOS) : [];
  } catch {
    return [];
  }
}

function escribir(lista) {
  try {
    if (lista.length) localStorage.setItem(clave(), JSON.stringify(lista.slice(-MAXIMO_GUARDADOS)));
    else localStorage.removeItem(clave());
  } catch {
    // Sin almacenamiento: los avisos se recuerdan mientras dure la página.
  }
}

// raiz: donde van los avisos dentro de la página. alVer: llevar a Mis materas. alCambiarPermiso: repintar
// lo que dependa del permiso (la pantalla Juego).
export function crearAvisos({ raiz, alVer, alCambiarPermiso }) {
  let avisados = null;
  let dueno = null; // el usuario de la lista en memoria

  // La lista es de la cuenta con sesión; si cambió la cuenta, se vuelve a leer. Otra pestaña pudo avisar
  // desde la última vez: se relee siempre y se mezcla.
  function lista() {
    const id = sesion.usuario()?.id ?? null;
    const guardados = leer();
    avisados = id === dueno && avisados ? [...new Set([...guardados, ...avisados])] : guardados;
    dueno = id;
    return avisados;
  }

  // materas: las de GET /juego/materas. apodoDe(plantaId): el apodo, que viene en GET /juego/puntaje.
  function revisar(materas, apodoDe) {
    if (!sesion.activa()) return;
    const vistos = lista();
    let nuevos = false;
    for (const matera of materas) {
      const texto = TEXTOS[matera.aviso];
      if (!texto) continue;
      const llave = `${matera.plantaId}|${matera.ultimaLectura ?? ""}|${matera.aviso}`;
      if (vistos.includes(llave)) continue;
      vistos.push(llave);
      nuevos = true;
      avisar(matera, texto(apodoDe(matera.plantaId)), llave);
    }
    if (nuevos) escribir(vistos);
  }

  function avisar(matera, titulo, clave) {
    const detalle = [globoDe(matera.necesidad), matera.ultimaLectura && HORA.format(new Date(matera.ultimaLectura))]
      .filter(Boolean)
      .join(" · ");
    if (estadoPermiso() === "concedido" && notificar(titulo, detalle, clave)) return;
    enPagina(matera, titulo, detalle);
    // El navegador solo deja vibrar después de que la persona tocó la página (por ejemplo, al ingresar).
    if (navigator.userActivation?.hasBeenActive === false) return;
    try {
      navigator.vibrate?.(VIBRACION);
    } catch {
      // Sin vibración: el aviso igual se ve.
    }
  }

  function notificar(titulo, cuerpo, clave) {
    try {
      const notificacion = new Notification(titulo, { body: cuerpo, tag: clave, lang: "es" });
      notificacion.addEventListener("click", () => {
        window.focus();
        notificacion.close();
        alVer();
      });
      return true;
    } catch {
      // Chrome para Android solo notifica desde un service worker: entonces se avisa dentro de la página.
      return false;
    }
  }

  function enPagina(matera, titulo, detalle) {
    const nodo = crear("div", { clase: `aviso aviso--${matera.aviso === "SE_MARCHITO" ? "marchita" : "critica"}` });
    nodo.setAttribute("role", "alert");
    const quitar = () => nodo.remove();
    const acciones = [boton("Ver materas", "boton-contorno", () => {
      quitar();
      alVer();
    })];
    if (estadoPermiso() === "pendiente") {
      acciones.push(boton("Avisarme con notificaciones", "boton-contorno", async () => {
        await pedirPermiso();
        quitar();
      }));
    }
    const cerrar = boton("×", "aviso__cerrar", quitar);
    cerrar.setAttribute("aria-label", "Cerrar el aviso");
    const textos = [crear("p", { clase: "aviso__titulo", texto: titulo })];
    if (detalle) textos.push(crear("p", { clase: "aviso__detalle", texto: detalle }));
    nodo.append(
      dibujoDeMatera(matera, { sinGlobo: true, clase: "aviso__dibujo" }),
      crear("div", { clase: "aviso__cuerpo" }, ...textos, crear("div", { clase: "aviso__acciones" }, ...acciones)),
      cerrar);
    raiz.prepend(nodo);
    while (raiz.children.length > MAXIMO_EN_PAGINA) raiz.lastElementChild.remove();
  }

  // Solo con un clic de la persona: el navegador muestra su propia pregunta.
  async function pedirPermiso() {
    if (estadoPermiso() === "pendiente") {
      try {
        await Notification.requestPermission();
      } catch {
        // Un navegador viejo que no responde con una promesa: el estado se lee igual abajo.
      }
    }
    const estado = estadoPermiso();
    alCambiarPermiso?.(estado);
    return estado;
  }

  // Al cerrar la sesión: se quitan los avisos de la pantalla y la lista en memoria. Lo ya avisado sigue
  // guardado para esa cuenta (clave por usuario), así que al volver a ingresar no se repite.
  function reiniciar() {
    avisados = null;
    dueno = null;
    raiz.replaceChildren();
  }

  return { revisar, pedirPermiso, reiniciar };
}

function boton(texto, clase, accion) {
  const nodo = crear("button", { clase, texto });
  nodo.type = "button";
  nodo.addEventListener("click", accion);
  return nodo;
}
