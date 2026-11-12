// La pregunta de participar en la tabla de posiciones. La primera vez que entra alguien que todavía no
// decidió (GET /juego/participacion responde SIN_DECIDIR), un diálogo de la propia página le pregunta si
// quiere aparecer en la tabla. Si dice que sí, pide su apodo de jugador; si la API lo rechaza
// (400 APODO_JUGADOR_INVALIDO o 409 APODO_JUGADOR_REPETIDO), muestra el error tal como llega. Si dice que
// no, queda NO_PARTICIPA y no se vuelve a preguntar. Cerrar el diálogo no es decidir: no se pregunta otra
// vez en esta sesión, pero sí la próxima vez que entre. En Mi cuenta se puede cambiar cuando quiera.
import { mostrarError, ocupado } from "./formularios.js";

const POSPUESTA = "matera.juego.pregunta-pospuesta";

function pospuestaPara() {
  try {
    return sessionStorage.getItem(POSPUESTA);
  } catch {
    return null;
  }
}

function posponer(usuarioId) {
  try {
    if (usuarioId === null) sessionStorage.removeItem(POSPUESTA);
    else sessionStorage.setItem(POSPUESTA, String(usuarioId));
  } catch {
    // Sin almacenamiento: la pregunta puede volver al recargar la página.
  }
}

// elegir(participa, apodo): el PUT /juego/participacion del juego, que además guarda la respuesta.
export function crearDialogoParticipar({ elegir }) {
  const $ = (id) => document.getElementById(id);
  const dialogo = $("dialogo-participar");
  const formulario = $("form-participar");
  let usuario = null;

  function paso(nombre) {
    const pidiendoApodo = nombre === "apodo";
    $("participar-paso-apodo").hidden = !pidiendoApodo;
    $("participar-acciones-pregunta").hidden = pidiendoApodo;
    $("participar-acciones-apodo").hidden = !pidiendoApodo;
    mostrarError($("error-participar"), null);
    if (pidiendoApodo) $("participar-apodo").focus();
  }

  $("participar-si").addEventListener("click", () => paso("apodo"));
  $("participar-volver").addEventListener("click", () => paso("pregunta"));

  $("participar-no").addEventListener("click", async (evento) => {
    try {
      await ocupado(evento.currentTarget, () => elegir(false));
    } catch (error) {
      mostrarError($("error-participar"), error);
      return;
    }
    cerrar();
  });

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      await ocupado($("participar-enviar"), () => elegir(true, $("participar-apodo").value));
    } catch (error) {
      mostrarError($("error-participar"), error);
      $("participar-apodo").focus();
      return;
    }
    cerrar();
  });

  // «Decidir después» y la tecla Escape: no se responde a la API.
  $("participar-despues").addEventListener("click", () => {
    posponer(usuario);
    cerrar();
  });
  dialogo.addEventListener("cancel", () => posponer(usuario));

  function preguntar(usuarioId) {
    const quien = String(usuarioId ?? "?");
    if (dialogo.open || pospuestaPara() === quien) return;
    usuario = quien;
    formulario.reset();
    paso("pregunta");
    dialogo.showModal();
  }

  function cerrar() {
    if (dialogo.open) dialogo.close();
  }

  // Al cerrar la sesión.
  function reiniciar() {
    cerrar();
    posponer(null);
    usuario = null;
    formulario.reset();
    mostrarError($("error-participar"), null);
  }

  return { preguntar, cerrar, reiniciar };
}
