// Arranque del front: carga los catálogos de la API, navega entre pantallas y muestra
// el estado de la conexión y de la sesión. Las reglas de negocio viven en el backend.
import { avisarAlVencerSesion, obtenerEspecies, obtenerMiCuenta, obtenerParametros } from "./api.js";
import { crearPantallaAcceso } from "./acceso.js";
import { crearPantallaAdmin } from "./admin.js";
import { crearPantallaCuenta } from "./cuenta.js";
import { crearPantallaDiagnostico } from "./diagnostico.js";
import { crearPantallaEspecies } from "./especies.js";
import { crearPantallaHistorial } from "./historial.js";
import { crearPantallaMateras } from "./materas.js";
import { sesion } from "./sesion.js";
import { crearSimulador } from "./simulador.js";
import { crearPantallaVincular } from "./vincular.js";

const PUBLICAS = ["diagnostico", "especies", "acceso"];
// Exigen sesión. Ocultarlas no protege nada: la API responde 401 sin token, y 403 en
// administración si el usuario no es ADMIN.
const PRIVADAS = ["materas", "vincular", "historial", "cuenta", "admin"];
const PANTALLAS = [...PUBLICAS, ...PRIVADAS];
const PANTALLA_INICIAL = "diagnostico";
const DESPUES_DE_INGRESAR = "materas";
const REINTENTO_MS = 5000;

// La pantalla privada que se pidió antes de ingresar: se vuelve a ella después.
let destino = null;

const contexto = {
  especies: [],
  parametros: [],
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
};

const diagnostico = crearPantallaDiagnostico(contexto);
const especies = crearPantallaEspecies(contexto);
const simulador = crearSimulador(contexto);
const pantallas = {
  acceso: crearPantallaAcceso(contexto),
  cuenta: crearPantallaCuenta(contexto),
  materas: crearPantallaMateras(contexto),
  vincular: crearPantallaVincular(contexto, simulador),
  historial: crearPantallaHistorial(contexto),
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
  }
  for (const pestana of document.querySelectorAll("[data-pantalla]")) {
    const activa = pestana.dataset.pantalla === pedida;
    pestana.classList.toggle("pestana--activa", activa);
    if (activa) pestana.setAttribute("aria-current", "page");
    else pestana.removeAttribute("aria-current");
  }
  window.scrollTo(0, 0);
  pantallas[pedida]?.mostrar?.();
}

function pintarSesion() {
  const boton = document.getElementById("boton-cuenta");
  const usuario = sesion.usuario();
  boton.textContent = usuario ? usuario.nombre : "Ingresar";
  boton.dataset.pantalla = usuario ? "cuenta" : "acceso";
  boton.classList.toggle("boton-cuenta--activa", Boolean(usuario));
  document.querySelector('.pestana[data-pantalla="admin"]').hidden = !sesion.esAdmin();
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
  pantallas.materas.alCargarCatalogos();
  pantallas.admin.alCargarCatalogos();
  simulador.alCargarCatalogos();
}

// Si había una sesión guardada, se pregunta a la API quién es: el rol pudo cambiar.
async function confirmarSesion() {
  if (!sesion.activa()) return;
  try {
    const { plantas, ...usuario } = await obtenerMiCuenta();
    sesion.actualizarUsuario(usuario);
  } catch {
    // Un 401 ya cerró la sesión; sin conexión, se conserva la que había.
  }
  pintarSesion();
}

document.querySelector(".navegacion").addEventListener("click", (evento) => {
  const destinoClic = evento.target.closest("[data-pantalla]");
  if (destinoClic) contexto.navegar(destinoClic.dataset.pantalla);
});
window.addEventListener("hashchange", mostrarPantalla);
avisarAlVencerSesion(() => {
  pintarSesion();
  destino = pantallaPedida();
  location.replace("#acceso");
});

pintarSesion();
mostrarPantalla();
cargarCatalogos();
confirmarSesion();
