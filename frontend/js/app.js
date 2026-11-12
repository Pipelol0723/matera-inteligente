// Arranque del front: carga los catálogos de la API, navega entre pantallas y muestra
// el estado de la conexión, de la sesión y de la conexión en vivo. Las reglas de negocio viven en el backend.
import { avisarAlVencerSesion, obtenerEspecies, obtenerMiCuenta, obtenerParametros } from "./api.js";
import { crearPantallaAcceso } from "./acceso.js";
import { crearPantallaAdmin } from "./admin.js";
import { crearPantallaCuenta } from "./cuenta.js";
import { crearPantallaDiagnostico } from "./diagnostico.js";
import { crearPantallaEspecies } from "./especies.js";
import { crearPantallaHistorial } from "./historial.js";
import { crearJuego } from "./juego.js";
import { crearPantallaMateras } from "./materas.js";
import { sesion } from "./sesion.js";
import { crearTiempoReal } from "./tiempo-real.js";

const PUBLICAS = ["acceso"];
// Exigen sesión (R7), también Diagnóstico y Especies. Ocultarlas no protege nada: la API
// responde 401 sin token, y 403 en administración si el usuario no es ADMIN.
const PRIVADAS = ["diagnostico", "especies", "materas", "historial", "juego", "cuenta", "admin"];
const PANTALLAS = [...PUBLICAS, ...PRIVADAS];
const PANTALLA_INICIAL = "diagnostico";
const DESPUES_DE_INGRESAR = "materas";
const REINTENTO_MS = 5000;

// La pantalla privada que se pidió antes de ingresar: se vuelve a ella después.
let destino = null;

// Mientras haya sesión, un WebSocket trae cada medición nueva de las plantas del usuario.
const tiempoReal = crearTiempoReal({
  alCambiarEstado: pintarEnVivo,
  alSesionInvalida: () => {
    sesion.cerrar();
    sesionVencida();
  },
});

const contexto = {
  especies: [],
  parametros: [],
  tiempoReal,
  // La planta que se eligió en una pantalla, para abrir otra con esa misma planta.
  plantaElegida: null,
  navegar: (pantalla) => {
    location.hash = pantalla;
  },
  verPlanta(pantalla, plantaId) {
    contexto.plantaElegida = plantaId;
    contexto.navegar(pantalla);
  },
  marcarConexion,
  diagnosticarEspecie: (nombre) => {
    diagnostico.seleccionarEspecie(nombre);
    contexto.navegar("diagnostico");
  },
  alIniciarSesion() {
    pintarSesion();
    cargarCatalogos();
    contexto.juego.iniciar();
    contexto.navegar(destino ?? DESPUES_DE_INGRESAR);
    destino = null;
  },
  alCerrarSesion() {
    pintarSesion();
    contexto.navegar(PANTALLA_INICIAL);
  },
  alCambiarUsuario: pintarSesion,
  // Después de que el admin agrega una especie: Diagnóstico, Especies y Mis materas la ven.
  recargarCatalogos: () => cargarCatalogos(),
  // Mientras el asistente «Conectar sensor» tiene al equipo en la red de la placa, no hay API.
  sinApi: () => pantallas.materas.sinApi(),
};

// El juego (corte 3): los puntos de la cabecera y los avisos se ven en todas las pantallas con sesión,
// y Mis materas dibuja cada matera con lo que trae.
contexto.juego = crearJuego(contexto);

const diagnostico = crearPantallaDiagnostico(contexto);
const especies = crearPantallaEspecies(contexto);
const pantallas = {
  diagnostico,
  acceso: crearPantallaAcceso(contexto),
  cuenta: crearPantallaCuenta(contexto),
  materas: crearPantallaMateras(contexto),
  historial: crearPantallaHistorial(contexto),
  juego: contexto.juego,
  admin: crearPantallaAdmin(contexto),
};

function pantallaPedida() {
  const pedida = location.hash.slice(1);
  return PANTALLAS.includes(pedida) ? pedida : PANTALLA_INICIAL;
}

function mostrarPantalla() {
  const pedida = pantallaPedida();
  if (PRIVADAS.includes(pedida) && !sesion.activa()) {
    destino = pedida;
    location.replace("#acceso");
    return;
  }
  if ((pedida === "acceso" && sesion.activa()) || (pedida === "admin" && !sesion.esAdmin())) {
    location.replace(`#${DESPUES_DE_INGRESAR}`);
    return;
  }
  for (const nombre of PANTALLAS) {
    document.getElementById(`pantalla-${nombre}`).hidden = nombre !== pedida;
    if (nombre !== pedida) pantallas[nombre]?.ocultar?.();
  }
  for (const pestana of document.querySelectorAll("[data-pantalla]")) {
    const activa = pestana.dataset.pantalla === pedida;
    pestana.classList.toggle("pestana--activa", activa);
    if (activa) pestana.setAttribute("aria-current", "page");
    else pestana.removeAttribute("aria-current");
  }
  // Si las pestañas de arriba se desplazan de lado, la de la pantalla actual queda a la vista.
  document.querySelector(`.pestana[data-pantalla="${pedida}"]`)?.scrollIntoView({ block: "nearest", inline: "nearest" });
  window.scrollTo(0, 0);
  pantallas[pedida]?.mostrar?.();
}

function pintarSesion() {
  const boton = document.getElementById("boton-cuenta");
  const usuario = sesion.usuario();
  document.getElementById("boton-cuenta-texto").textContent = usuario ? usuario.nombre : "Ingresar";
  boton.title = usuario ? `${usuario.nombre}: Mi cuenta` : "";
  boton.dataset.pantalla = usuario ? "cuenta" : "acceso";
  boton.classList.toggle("boton-cuenta--activa", Boolean(usuario));
  document.querySelector('.pestana[data-pantalla="admin"]').hidden = !sesion.esAdmin();
  ajustarBarra();
  if (sesion.activa()) {
    tiempoReal.conectar();
  } else {
    tiempoReal.desconectar();
    diagnostico.reiniciar();
    pantallas.materas.reiniciar();
    pantallas.historial.reiniciar();
    pantallas.cuenta.reiniciar();
    contexto.juego.reiniciar();
    contexto.plantaElegida = null;
    marcarSinSesion();
  }
}

// En el PC, la cabecera pasa a dos filas cuando las pestañas no caben al lado de la marca, los indicadores, el
// puntaje y la cuenta. En el celular las pestañas van en la barra de abajo y siempre caben. Se mide en el
// cuadro siguiente: así el cambio de filas no vuelve a disparar la medición en el mismo.
const barra = document.querySelector(".cabecera");
const pestanas = barra.querySelector(".pestanas");
let ajuste = 0;

function ajustarBarra() {
  cancelAnimationFrame(ajuste);
  ajuste = requestAnimationFrame(() => {
    barra.classList.remove("cabecera--dos-filas");
    barra.classList.toggle("cabecera--dos-filas", pestanas.scrollWidth > pestanas.clientWidth + 1);
  });
}

// Cambia el ancho de las pestañas al cambiar la ventana, el puntaje, el nombre de la cuenta o los indicadores.
new ResizeObserver(ajustarBarra).observe(pestanas);

const TEXTOS_EN_VIVO = {
  conectando: "Conectando en vivo…",
  "en-vivo": "En vivo",
  caido: "En vivo: reconectando…",
};

function pintarEnVivo(estado) {
  const indicador = document.getElementById("en-vivo");
  indicador.hidden = estado === "apagado";
  indicador.classList.toggle("en-vivo--activo", estado === "en-vivo");
  indicador.classList.toggle("en-vivo--caido", estado === "caido");
  ponerTexto(indicador, "en-vivo-texto", TEXTOS_EN_VIVO[estado] ?? "");
}

// En pantallas angostas los indicadores muestran solo su punto: el texto también va en su título.
function ponerTexto(indicador, id, texto) {
  document.getElementById(id).textContent = texto;
  indicador.title = texto;
}

function sesionVencida() {
  pintarSesion();
  destino = pantallaPedida();
  location.replace("#acceso");
}

function marcarConexion(conectada) {
  const indicador = document.getElementById("conexion");
  indicador.classList.remove("conexion--pendiente");
  indicador.classList.toggle("conexion--caida", !conectada);
  ponerTexto(indicador, "conexion-texto", conectada
    ? `API conectada · ${contexto.especies.length} especies`
    : "Sin conexión con la API");
}

// Sin sesión no hay ruta que consultar: los catálogos también exigen el token.
function marcarSinSesion() {
  const indicador = document.getElementById("conexion");
  indicador.classList.remove("conexion--caida");
  indicador.classList.add("conexion--pendiente");
  ponerTexto(indicador, "conexion-texto", "Ingrese para usar la API");
}

let reintento = null;

async function cargarCatalogos() {
  clearTimeout(reintento);
  if (!sesion.activa()) {
    marcarSinSesion();
    return;
  }
  try {
    [contexto.parametros, contexto.especies] = await Promise.all([obtenerParametros(), obtenerEspecies()]);
  } catch (error) {
    if (!sesion.activa()) return; // un 401 cerró la sesión y ya llevó a Ingresar
    marcarConexion(false);
    diagnostico.mostrarErrorDeCarga(error);
    reintento = setTimeout(cargarCatalogos, REINTENTO_MS);
    return;
  }
  marcarConexion(true);
  diagnostico.alCargarCatalogos();
  especies.pintar();
  pantallas.materas.alCargarCatalogos();
  pantallas.admin.alCargarCatalogos();
}

// Si había una sesión guardada, se pregunta a la API quién es: el rol pudo cambiar. Después arranca el
// juego, que pregunta si participa a quien todavía no lo decidió.
async function confirmarSesion() {
  if (!sesion.activa()) return;
  try {
    const { plantas, ...usuario } = await obtenerMiCuenta();
    sesion.actualizarUsuario(usuario);
  } catch {
    // Un 401 ya cerró la sesión; sin conexión, se conserva la que había.
  }
  pintarSesion();
  if (sesion.activa()) contexto.juego.iniciar();
}

document.querySelector(".cabecera").addEventListener("click", (evento) => {
  const destinoClic = evento.target.closest("[data-pantalla]");
  if (destinoClic) contexto.navegar(destinoClic.dataset.pantalla);
});
window.addEventListener("hashchange", mostrarPantalla);
avisarAlVencerSesion(sesionVencida);

pintarSesion();
mostrarPantalla();
cargarCatalogos();
confirmarSesion();
