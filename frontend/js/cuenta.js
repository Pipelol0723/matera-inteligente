// Mi cuenta: los datos de GET /usuarios/yo, el botón para cerrar sesión y la tabla de posiciones del juego:
// participar con un apodo de jugador, cambiarlo o dejar de participar (PUT /juego/participacion). Si el
// apodo sirve lo decide la API; aquí se muestra su respuesta, también los errores.
import { cerrarSesion, obtenerMiCuenta } from "./api.js";
import { crear } from "./formato.js";
import { botonDe, mostrarError, mostrarExito, ocupado } from "./formularios.js";
import { sesion } from "./sesion.js";

const ROLES = { USUARIO: "Usuario", ADMIN: "Administrador" };

export function crearPantallaCuenta(contexto) {
  const $ = (id) => document.getElementById(id);
  const formularioJugador = $("form-jugador");

  $("cerrar-sesion").addEventListener("click", async () => {
    try {
      await cerrarSesion();
    } catch {
      // Si la API no responde, la sesión igual se cierra en este navegador.
    }
    sesion.cerrar();
    contexto.alCerrarSesion();
  });

  formularioJugador.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const yaParticipaba = formularioJugador.dataset.estado === "PARTICIPA";
    await cambiarParticipacion(botonDe(evento), true, $("jugador-apodo").value,
      (p) => (yaParticipaba ? `Listo: su apodo de jugador ahora es «${p.apodo}».` : `Listo: aparece en la tabla como «${p.apodo}».`));
  });

  $("jugador-salir").addEventListener("click", (evento) =>
    cambiarParticipacion(evento.currentTarget, false, null, () => "Listo: ya no aparece en la tabla de posiciones."));

  async function cambiarParticipacion(boton, participa, apodo, textoExito) {
    mostrarError($("error-jugador"), null);
    mostrarExito($("exito-jugador"), null);
    let respuesta;
    try {
      respuesta = await ocupado(boton, () => contexto.juego.elegir(participa, apodo));
    } catch (error) {
      mostrarError($("error-jugador"), error);
      return;
    }
    pintarJugador(respuesta);
    mostrarExito($("exito-jugador"), textoExito(respuesta));
  }

  async function mostrar() {
    mostrarError($("error-cuenta"), null);
    mostrarJugador();
    let cuenta;
    try {
      cuenta = await obtenerMiCuenta();
    } catch (error) {
      mostrarError($("error-cuenta"), error);
      return;
    }
    const { plantas, ...usuario } = cuenta;
    sesion.actualizarUsuario(usuario);
    contexto.alCambiarUsuario();
    const filas = [
      ["Nombre", usuario.nombre],
      ["Correo", usuario.correo],
      ["Rol", ROLES[usuario.rol] ?? usuario.rol],
      ["Plantas", String(plantas)],
    ];
    $("datos-cuenta").replaceChildren(...filas.map(([nombre, valor]) =>
      crear("div", { clase: "resumen__fila" },
        crear("span", { clase: "resumen__nombre", texto: nombre }),
        crear("span", { clase: "cuenta__valor", texto: valor }))));
  }

  async function mostrarJugador() {
    mostrarError($("error-jugador"), null);
    mostrarExito($("exito-jugador"), null);
    let participacion;
    try {
      participacion = await contexto.juego.cargarParticipacion();
    } catch (error) {
      mostrarError($("error-jugador"), error);
      return;
    }
    if (participacion) pintarJugador(participacion);
  }

  const ESTADOS = {
    PARTICIPA: (p) => `Participa en la tabla de posiciones como «${p.apodo}». Puede cambiar el apodo o dejar de participar.`,
    NO_PARTICIPA: () => "No participa: no aparece en la tabla de posiciones ni la ve. Sus materas suman y restan puntos igual.",
    SIN_DECIDIR: () => "Todavía no ha decidido si quiere aparecer en la tabla de posiciones.",
  };

  function pintarJugador(participacion) {
    const participa = participacion.estado === "PARTICIPA";
    formularioJugador.dataset.estado = participacion.estado;
    $("jugador-estado").textContent = (ESTADOS[participacion.estado] ?? ESTADOS.SIN_DECIDIR)(participacion);
    $("jugador-apodo").value = participa ? participacion.apodo : "";
    $("jugador-guardar").textContent = participa ? "Cambiar apodo" : "Participar";
    $("jugador-salir").hidden = !participa;
  }

  // Al cerrar la sesión: nada de esta cuenta queda en la pantalla.
  function reiniciar() {
    $("datos-cuenta").replaceChildren();
    $("jugador-estado").textContent = "";
    formularioJugador.reset();
    delete formularioJugador.dataset.estado;
    $("jugador-salir").hidden = true;
    $("jugador-guardar").textContent = "Participar";
    mostrarError($("error-cuenta"), null);
    mostrarError($("error-jugador"), null);
    mostrarExito($("exito-jugador"), null);
  }

  return { mostrar, reiniciar };
}
