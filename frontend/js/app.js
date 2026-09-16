// Arranque del front: carga los catálogos de la API, navega entre pantallas y muestra
// el estado de la conexión. Las reglas de negocio viven en el backend.
import { obtenerEspecies, obtenerParametros } from "./api.js";
import { crearPantallaDiagnostico } from "./diagnostico.js";
import { crearPantallaEspecies } from "./especies.js";
import { crearPrototipos } from "./prototipos.js";

const PANTALLAS = ["diagnostico", "especies", "historial", "materas", "vincular"];
const PANTALLA_INICIAL = "diagnostico";
const REINTENTO_MS = 5000;

const contexto = {
  especies: [],
  parametros: [],
  navegar: (pantalla) => {
    location.hash = pantalla;
  },
  marcarConexion,
  diagnosticarEspecie: (nombre) => {
    diagnostico.seleccionarEspecie(nombre);
    contexto.navegar("diagnostico");
  },
};

const diagnostico = crearPantallaDiagnostico(contexto);
const especies = crearPantallaEspecies(contexto);
const prototipos = crearPrototipos(contexto);

function pantallaActual() {
  const pedida = location.hash.slice(1);
  return PANTALLAS.includes(pedida) ? pedida : PANTALLA_INICIAL;
}

function mostrarPantalla() {
  const actual = pantallaActual();
  for (const nombre of PANTALLAS) {
    document.getElementById(`pantalla-${nombre}`).hidden = nombre !== actual;
  }
  for (const pestana of document.querySelectorAll("[data-pantalla]")) {
    const activa = pestana.dataset.pantalla === actual;
    pestana.classList.toggle("pestana--activa", activa);
    if (activa) pestana.setAttribute("aria-current", "page");
    else pestana.removeAttribute("aria-current");
  }
  window.scrollTo(0, 0);
}

function marcarConexion(conectada) {
  const indicador = document.getElementById("conexion");
  indicador.classList.remove("conexion--pendiente");
  indicador.classList.toggle("conexion--caida", !conectada);
  document.getElementById("conexion-texto").textContent = conectada
    ? `API conectada · ${contexto.especies.length} especies`
    : "Sin conexión con la API";
}

async function cargarCatalogos() {
  try {
    [contexto.parametros, contexto.especies] = await Promise.all([obtenerParametros(), obtenerEspecies()]);
  } catch (error) {
    marcarConexion(false);
    diagnostico.mostrarErrorDeCarga(error);
    setTimeout(cargarCatalogos, REINTENTO_MS);
    return;
  }
  marcarConexion(true);
  diagnostico.alCargarCatalogos();
  especies.pintar();
  prototipos.alCargarCatalogos();
}

document.querySelector(".pestanas").addEventListener("click", (evento) => {
  const pestana = evento.target.closest("[data-pantalla]");
  if (pestana) contexto.navegar(pestana.dataset.pantalla);
});
window.addEventListener("hashchange", mostrarPantalla);

mostrarPantalla();
cargarCatalogos();
