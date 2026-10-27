// Cliente de la API: peticiones asíncronas y traducción del cuerpo de error uniforme.
import { API_BASE } from "./config.js";
import { sesion } from "./sesion.js";

// Dirección en la que no escucha ningún servidor: sirve para ver el error real de "sin conexión".
const API_INALCANZABLE = "http://127.0.0.1:5999/api/v1";

export class ErrorApi extends Error {
  constructor(status, { error, mensaje, detalle }) {
    super(mensaje);
    this.status = status;
    this.codigo = error;
    this.detalle = detalle ?? {};
  }
}

// Quien quiera enterarse de que la sesión dejó de servir (la app lleva a Ingresar).
let alVencerSesion = () => {};
export function avisarAlVencerSesion(funcion) {
  alVencerSesion = funcion;
}

async function pedir(base, ruta, opciones = {}) {
  let respuesta;
  try {
    respuesta = await fetch(`${base}${ruta}`, opciones);
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new ErrorApi(0, {
      error: "SIN_CONEXION",
      mensaje: `No se pudo contactar la API en ${base}. Revise que el backend esté corriendo.`,
    });
  }

  let cuerpo;
  try {
    cuerpo = await respuesta.json();
  } catch {
    throw new ErrorApi(respuesta.status, {
      error: "RESPUESTA_INVALIDA",
      mensaje: "La API respondió algo que no es JSON.",
    });
  }

  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, cuerpo);
  }
  return cuerpo;
}

function conJson(metodo, datos, cabeceras = {}) {
  return {
    method: metodo,
    headers: { "Content-Type": "application/json", ...cabeceras },
    body: JSON.stringify(datos),
  };
}

// Todas las rutas del front exigen sesión (R7), menos crear cuenta e ingresar: llevan el token,
// y un 401 SESION_INVALIDA cierra la sesión local.
async function privada(ruta, opciones = {}, base = API_BASE) {
  const cabeceras = { ...opciones.headers, Authorization: `Bearer ${sesion.token()}` };
  try {
    return await pedir(base, ruta, { ...opciones, headers: cabeceras });
  } catch (error) {
    if (error.codigo === "SESION_INVALIDA") {
      sesion.cerrar();
      alVencerSesion();
    }
    throw error;
  }
}

function enviarDiagnostico(base, datos, signal) {
  return privada("/diagnosticos", { ...conJson("POST", datos), signal }, base);
}

// ---- corte 1: desde la fase 2 también exigen sesión ----

export function obtenerParametros() {
  return privada("/parametros");
}

export function obtenerEspecies() {
  return privada("/especies");
}

export function pedirDiagnostico(datos, { signal } = {}) {
  return enviarDiagnostico(API_BASE, datos, signal);
}

export function pedirDiagnosticoSinConexion(datos, { signal } = {}) {
  return enviarDiagnostico(API_INALCANZABLE, datos, signal);
}

// ---- cuenta ----

export const registrarse = (datos) => pedir(API_BASE, "/usuarios", conJson("POST", datos));
export const iniciarSesion = (datos) => pedir(API_BASE, "/sesiones", conJson("POST", datos));
export const cerrarSesion = () => privada("/sesiones/actual", { method: "DELETE" });
export const obtenerMiCuenta = () => privada("/usuarios/yo");

// ---- plantas, sensores e historial ----

// Una matera nace con su sensor: POST /plantas lleva apodo, especie y código, y responde la clave una vez.
export const obtenerPlantas = () => privada("/plantas");
export const registrarPlanta = (datos) => privada("/plantas", conJson("POST", datos));
export const eliminarPlanta = (id) => privada(`/plantas/${id}`, { method: "DELETE" });
export const cambiarSensor = (id, codigo) => privada(`/plantas/${id}/sensor`, conJson("PUT", { codigo }));

// Las mediciones no se escriben desde el front: llegan del sensor y se ven aquí en vivo (tiempo-real.js).
export const obtenerHistorial = (id, limite) => privada(`/plantas/${id}/historial?limite=${limite}`);

// ---- administración ----

export const obtenerUsuarios = () => privada("/admin/usuarios");
export const cambiarUsuario = (id, cambio) => privada(`/admin/usuarios/${id}`, conJson("PATCH", cambio));
export const eliminarUsuario = (id) => privada(`/admin/usuarios/${id}`, { method: "DELETE" });
export const agregarEspecie = (datos) => privada("/admin/especies", conJson("POST", datos));
