// Ayudas para los formularios: mostrar lo que respondió la API y bloquear el botón mientras se espera.
// Ningún formulario valida por su cuenta: se envía lo escrito y la API decide (como en Diagnóstico).
import { crear, textoDetalle } from "./formato.js";

export const datosDe = (formulario) => Object.fromEntries(new FormData(formulario));

export function mostrarError(caja, error) {
  if (!error) {
    caja.hidden = true;
    caja.replaceChildren();
    return;
  }
  const codigo = error.status ? `${error.status} · ${error.codigo}` : error.codigo ?? "ERROR";
  caja.replaceChildren(
    crear("p", { clase: "tarjeta-error__codigo", texto: codigo }),
    crear("p", { clase: "tarjeta-error__mensaje", texto: error.message }),
    crear("p", { clase: "tarjeta-error__detalle", texto: textoDetalle(error.detalle) }),
  );
  caja.hidden = false;
}

export function mostrarExito(caja, texto) {
  caja.textContent = texto ?? "";
  caja.hidden = !texto;
}

export async function ocupado(boton, accion) {
  boton.disabled = true;
  try {
    return await accion();
  } finally {
    boton.disabled = false;
  }
}

// Fecha y hora locales de un momento ISO que entrega la API.
const FECHA = new Intl.DateTimeFormat("es-CO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
export const fechaCorta = (iso) => FECHA.format(new Date(iso));
