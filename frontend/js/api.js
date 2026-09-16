// Cliente de la API: peticiones asíncronas y traducción del cuerpo de error uniforme.
import { API_BASE } from "./config.js";

export class ErrorApi extends Error {
  constructor(status, { error, mensaje, detalle }) {
    super(mensaje);
    this.status = status;
    this.codigo = error;
    this.detalle = detalle ?? {};
  }
}

async function pedir(ruta, opciones) {
  let respuesta;
  try {
    respuesta = await fetch(`${API_BASE}${ruta}`, opciones);
  } catch {
    throw new ErrorApi(0, {
      error: "SIN_CONEXION",
      mensaje: `No se pudo contactar la API en ${API_BASE}. Revise que el backend esté corriendo.`,
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

export function obtenerEspecies() {
  return pedir("/especies");
}

export function pedirDiagnostico(datos) {
  return pedir("/diagnosticos", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(datos),
  });
}
