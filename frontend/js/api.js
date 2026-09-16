// Cliente de la API: peticiones asíncronas y traducción del cuerpo de error uniforme.
import { API_BASE } from "./config.js";

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

function enviarDiagnostico(base, datos, signal) {
  return pedir(base, "/diagnosticos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
    signal,
  });
}

export function obtenerParametros() {
  return pedir(API_BASE, "/parametros");
}

export function obtenerEspecies() {
  return pedir(API_BASE, "/especies");
}

export function pedirDiagnostico(datos, { signal } = {}) {
  return enviarDiagnostico(API_BASE, datos, signal);
}

export function pedirDiagnosticoSinConexion(datos, { signal } = {}) {
  return enviarDiagnostico(API_INALCANZABLE, datos, signal);
}
