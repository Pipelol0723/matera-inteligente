// Juego (corte 3): la matera Tamagotchi, los puntos y la tabla de posiciones.
// Todo lo decide la API (GET /juego/...): cuánto vale cada lectura, la etapa, la condición, la cara, la
// necesidad, el aviso y quién ve la tabla. Este módulo pide esos datos, los guarda para las otras pantallas
// (Mis materas dibuja cada matera con mascotaDe) y pinta la pantalla Juego y el puntaje de la cabecera.
// Se actualiza solo, como Mis materas: con la consulta cada 10 s (consulta-periodica.js), mientras haya
// sesión y en cualquier pantalla, porque el puntaje de la cabecera y los avisos se ven en todas; y con cada
// mensaje del WebSocket (tiempo-real.js). El backend guarda los puntos antes de avisar por el WebSocket.
import { elegirParticipacion, obtenerMascotas, obtenerParticipacion, obtenerPuntaje, obtenerTabla } from "./api.js";
import { pintarRelojEnJuego } from "./reloj-juego.js";
import { crearAvisos, estadoPermiso, textoDelPermisoEnLaApp } from "./avisos.js";
import { consultarCadaRato, textoConsulta } from "./consulta-periodica.js";
import { dibujoDeMatera, macetaVacia } from "./dibujo-planta.js";
import { capitalizar, crear, puntos, puntosConSigno, rotuloDeEstado, signoDe } from "./formato.js";
import { mostrarError } from "./formularios.js";
import { crearDialogoParticipar } from "./participacion.js";
import { sesion } from "./sesion.js";

// Con segundos: con el reloj del juego acelerado llegan varias lecturas por minuto.
const HORA = new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit", hourCycle: "h23" });
const DIA_Y_HORA = new Intl.DateTimeFormat("es-CO", {
  day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", hourCycle: "h23",
});
// En el celular, la pantalla Juego muestra estos movimientos y un «Ver más» para el resto (css/estilos.css).
const MOVIMIENTOS_CORTOS = 10;

const PERMISOS = {
  concedido: "Cuando una matera pasa a CRÍTICO o se marchita, el navegador le avisa con una notificación.",
  pendiente: "Cuando una matera pasa a CRÍTICO o se marchita, la app avisa dentro de la página. " +
    "Si quiere, el navegador también puede avisarle con una notificación.",
  bloqueado: "El navegador tiene bloqueadas las notificaciones de esta página: los avisos se ven dentro de la " +
    "página. Puede permitirlas en la configuración del sitio.",
  "sin-contexto": "Esta dirección no es segura (http desde otro equipo), así que el navegador no permite " +
    "notificaciones: los avisos se ven dentro de la página y, en el celular, vibra.",
  "no-soportado": "Este navegador no tiene notificaciones: los avisos se ven dentro de la página.",
};

export function crearJuego(contexto) {
  const $ = (id) => document.getElementById(id);
  const oyentes = new Set();
  let materas = new Map(); // plantaId -> la matera Tamagotchi, tal como la mandó la API
  let puntaje = null; // GET /juego/puntaje
  let participacion = null; // GET /juego/participacion
  let tabla = null; // las posiciones, solo mientras participa
  let error = null; // el último error al consultar, para la pantalla Juego
  let consultado = null; // cuándo respondió la API por última vez
  let generacion = 0; // cambia al cerrar la sesión: una respuesta de la sesión anterior se descarta
  let enCurso = null;
  let otraVez = false;
  let todosLosMovimientos = false; // en el celular se ven los primeros MOVIMIENTOS_CORTOS hasta «Ver más»

  const avisos = crearAvisos({
    raiz: $("avisos"),
    alVer: () => contexto.navegar("materas"),
    alCambiarPermiso: pintarPermiso,
  });
  const dialogo = crearDialogoParticipar({ elegir });
  const aLaVista = () => !$("pantalla-juego").hidden;

  consultarCadaRato(() => sesion.activa(), refrescar);
  contexto.tiempoReal.alRecibir((mensaje) => {
    if (mensaje.tipo === "medicion" || mensaje.tipo === "reconectado") refrescar();
  });
  $("activar-notificaciones").addEventListener("click", () => avisos.pedirPermiso());
  $("juego-ver-mas").addEventListener("click", () => {
    todosLosMovimientos = !todosLosMovimientos;
    pintarVerMas();
  });

  // Si llega un mensaje mientras otra consulta está en curso, al terminar se consulta otra vez: así lo
  // último que se pinta salió después del mensaje.
  function refrescar() {
    if (enCurso) {
      otraVez = true;
      return enCurso;
    }
    enCurso = (async () => {
      try {
        do {
          otraVez = false;
          await consultar();
        } while (otraVez);
      } finally {
        enCurso = null;
      }
    })();
    return enCurso;
  }

  async function consultar() {
    // Mientras el equipo está en la red de la placa (asistente «Conectar sensor») no hay API que consultar.
    if (!sesion.activa() || contexto.sinApi?.()) return;
    const mia = generacion;
    const conTabla = aLaVista() && participacion?.estado === "PARTICIPA";
    let respuesta;
    try {
      respuesta = await Promise.all([obtenerMascotas(), obtenerPuntaje(), conTabla ? pedirTabla() : null]);
    } catch (fallo) {
      if (mia !== generacion) return;
      error = fallo;
      pintarPantalla();
      return;
    }
    if (mia !== generacion) return; // se cerró la sesión mientras tanto
    const [mascotas, nuevoPuntaje, posiciones] = respuesta;
    const antes = puntaje?.puntos;
    error = null;
    consultado = new Date();
    puntaje = nuevoPuntaje;
    if (conTabla) tabla = posiciones;
    guardarMateras(mascotas.materas);
    pintarCabecera(antes);
    pintarPantalla();
    avisos.revisar(mascotas.materas, apodoDe);
  }

  async function pedirTabla() {
    try {
      return (await obtenerTabla()).posiciones;
    } catch (fallo) {
      if (fallo.codigo !== "PARTICIPACION_REQUERIDA") throw fallo;
      // Dejó de participar desde otra pestaña: se pregunta otra vez cómo está.
      cargarParticipacion().catch(() => {});
      return null;
    }
  }

  // Avisa a Mis materas qué plantas cambiaron, para que vuelva a dibujar solo esas.
  function guardarMateras(lista) {
    const nuevas = new Map(lista.map((matera) => [matera.plantaId, matera]));
    const cambiadas = [];
    for (const [id, matera] of nuevas) {
      if (JSON.stringify(matera) !== JSON.stringify(materas.get(id))) cambiadas.push(id);
    }
    for (const id of materas.keys()) if (!nuevas.has(id)) cambiadas.push(id);
    materas = nuevas;
    if (cambiadas.length) for (const oyente of oyentes) oyente(cambiadas);
  }

  const apodoDe = (plantaId) =>
    puntaje?.materas.find((matera) => matera.planta.id === plantaId)?.planta.apodo ?? "Una matera";

  // ---- participación ----

  async function cargarParticipacion() {
    const mia = generacion;
    const respuesta = await obtenerParticipacion();
    if (mia !== generacion) return null;
    ponerParticipacion(respuesta);
    return respuesta;
  }

  async function elegir(participa, apodo) {
    const mia = generacion;
    const respuesta = await elegirParticipacion(participa, apodo);
    if (mia === generacion) ponerParticipacion(respuesta);
    return respuesta;
  }

  function ponerParticipacion(nueva) {
    const empiezaAParticipar = nueva.estado === "PARTICIPA" && participacion?.estado !== "PARTICIPA";
    participacion = nueva;
    if (nueva.estado !== "PARTICIPA") tabla = null;
    pintarTabla();
    if (empiezaAParticipar && aLaVista()) refrescar();
  }

  // ---- cabecera ----

  function pintarCabecera(antes) {
    const boton = $("puntaje");
    boton.hidden = !puntaje;
    boton.classList.remove("puntaje--sube", "puntaje--baja");
    if (!puntaje) return;
    const total = puntos(puntaje.puntos);
    $("puntaje-valor").textContent = total;
    boton.setAttribute("aria-label", `Sus puntos: ${total}. Ver el juego`);
    if (antes !== undefined && antes !== puntaje.puntos) {
      void boton.offsetWidth; // vuelve a empezar la animación
      boton.classList.add(puntaje.puntos > antes ? "puntaje--sube" : "puntaje--baja");
    }
  }

  // ---- pantalla Juego ----

  function pintarPantalla() {
    mostrarError($("error-juego"), error);
    $("juego-consulta").textContent = consultado ? textoConsulta(consultado) : "";
    pintarPuntos();
    pintarTabla();
    pintarPermiso();
  }

  function pintarPuntos() {
    const total = $("juego-total");
    total.textContent = puntaje ? puntos(puntaje.puntos) : "—";
    total.className = `juego__total juego__valor--${puntaje ? signoDe(puntaje.puntos) : "cero"}`;
    // Sin sesión no queda nada; con sesión y sin respuesta todavía, se dice que se está consultando.
    const sinDatos = (conDatos, esperando) => (puntaje ? [vacio(conDatos)] : sesion.activa() ? [vacio(esperando)] : []);
    const porMatera = puntaje?.materas ?? [];
    $("juego-materas").replaceChildren(...(porMatera.length
      ? porMatera.map(filaMatera)
      : sinDatos("Todavía no tiene materas. Agréguelas en Mis materas.", "Consultando sus puntos…")));
    const movimientos = puntaje?.movimientos ?? [];
    $("juego-movimientos").replaceChildren(...(movimientos.length
      ? movimientos.map(filaMovimiento)
      : sinDatos("Todavía no llega ninguna lectura de sus sensores.", "Consultando sus movimientos…")));
    pintarVerMas();
  }

  // El botón solo aparece si hay más de MOVIMIENTOS_CORTOS; en el PC lo esconde el CSS y la lista va entera.
  function pintarVerMas() {
    const cuantos = puntaje?.movimientos?.length ?? 0;
    const boton = $("juego-ver-mas");
    boton.hidden = cuantos <= MOVIMIENTOS_CORTOS;
    $("juego-movimientos").classList.toggle("juego__movimientos--cortos", !todosLosMovimientos);
    boton.textContent = todosLosMovimientos ? "Ver menos" : `Ver más (${cuantos - MOVIMIENTOS_CORTOS})`;
    boton.setAttribute("aria-expanded", String(todosLosMovimientos));
  }

  function filaMatera({ planta, puntos: valor }) {
    const matera = materas.get(planta.id);
    return crear("li", { clase: "juego__fila" },
      matera ? dibujoDeMatera(matera, { sinGlobo: true, clase: "juego__mini" }) : macetaVacia({ sinGlobo: true, clase: "juego__mini" }),
      crear("span", { clase: "juego__nombre" },
        crear("span", { clase: "juego__apodo", texto: planta.apodo }),
        crear("span", { clase: "juego__especie", texto: capitalizar(planta.especie) })),
      crear("span", { clase: `juego__valor juego__valor--${signoDe(valor)}`, texto: puntosConSigno(valor) }));
  }

  // «+10» y «sala · SALUDABLE · 14:03:15». Una matera borrada conserva sus puntos, pero ya no tiene apodo.
  function filaMovimiento(movimiento) {
    const cuando = new Date(movimiento.momento);
    const hora = cuando.toDateString() === new Date().toDateString() ? HORA.format(cuando) : DIA_Y_HORA.format(cuando);
    const detalle = `${movimiento.planta ?? "matera borrada"} · ${rotuloDeEstado(movimiento.estado)} · ${hora}`;
    return crear("li", { clase: "juego__fila juego__fila--movimiento" },
      crear("span", {
        clase: `juego__valor juego__valor--${signoDe(movimiento.puntos)}`,
        texto: puntosConSigno(movimiento.puntos),
      }),
      crear("span", { clase: "juego__detalle", texto: detalle }));
  }

  function pintarTabla() {
    const caja = $("juego-tabla");
    if (!participacion) {
      caja.replaceChildren(nota(sesion.activa() ? "Consultando si participa…" : ""));
      return;
    }
    if (participacion.estado !== "PARTICIPA") {
      const ir = crear("button", { clase: "boton-primario", texto: "Participar desde Mi cuenta" });
      ir.type = "button";
      ir.addEventListener("click", () => contexto.navegar("cuenta"));
      caja.replaceChildren(
        nota(participacion.estado === "NO_PARTICIPA"
          ? "Usted eligió no aparecer en la tabla de posiciones, así que tampoco la ve."
          : "Todavía no ha decidido si quiere aparecer en la tabla de posiciones."),
        nota("En la tabla se compite con un apodo de jugador, nunca con su nombre ni su correo. " +
          "Sus materas suman y restan puntos igual, participe o no."),
        ir);
      return;
    }
    const encabezado = nota(`Participa como «${participacion.apodo}».`);
    if (!tabla) {
      caja.replaceChildren(encabezado, nota("Consultando la tabla…"));
      return;
    }
    caja.replaceChildren(encabezado, crear("ol", { clase: "juego__lista juego__posiciones" }, ...tabla.map(filaPosicion)));
  }

  function filaPosicion(fila) {
    const nodo = crear("li", { clase: `juego__fila juego__fila--posicion${fila.soyYo ? " juego__fila--yo" : ""}` },
      crear("span", { clase: "juego__posicion", texto: String(fila.posicion) }),
      crear("span", { clase: "juego__apodo", texto: fila.soyYo ? `${fila.apodo} (usted)` : fila.apodo }),
      crear("span", { clase: `juego__valor juego__valor--${signoDe(fila.puntos)}`, texto: puntos(fila.puntos) }));
    if (fila.soyYo) nodo.setAttribute("aria-current", "true");
    // Solo para el color de la medalla (los tres primeros); la posición la decide la API.
    nodo.dataset.posicion = String(fila.posicion);
    return nodo;
  }

  function pintarPermiso() {
    const estado = estadoPermiso();
    $("juego-permiso").textContent = textoDelPermisoEnLaApp?.(estado) ?? PERMISOS[estado];
    $("activar-notificaciones").hidden = estado !== "pendiente";
  }

  const nota = (texto) => crear("p", { clase: "juego__nota", texto });
  const vacio = (texto) => crear("li", { clase: "juego__vacio", texto });

  return {
    // La pantalla Juego: también vuelve a preguntar si participa (pudo cambiar en otra pestaña).
    async mostrar() {
      pintarPantalla();
      pintarRelojEnJuego($("juego-reloj"));
      try {
        await cargarParticipacion();
      } catch (fallo) {
        error = fallo;
        pintarPantalla();
      }
      refrescar();
    },
    // Al ingresar, o al abrir la página con una sesión guardada: consulta y, si la persona todavía no
    // decidió si participa, le pregunta.
    async iniciar() {
      refrescar();
      if (contexto.sinApi?.()) return;
      let actual;
      try {
        actual = await cargarParticipacion();
      } catch {
        return; // sin conexión: se pregunta la próxima vez que entre
      }
      if (actual?.estado === "SIN_DECIDIR" && sesion.activa()) dialogo.preguntar(sesion.usuario()?.id);
    },
    // Al cerrar la sesión: nada del juego de esta cuenta queda para la que entre después.
    reiniciar() {
      generacion += 1;
      materas = new Map();
      puntaje = null;
      participacion = null;
      tabla = null;
      error = null;
      consultado = null;
      otraVez = false;
      todosLosMovimientos = false;
      avisos.reiniciar();
      dialogo.reiniciar();
      pintarCabecera();
      pintarPantalla();
    },
    refrescar,
    mascotaDe: (plantaId) => materas.get(plantaId),
    // oyente(ids): las plantas cuya matera Tamagotchi cambió.
    alCambiar: (oyente) => oyentes.add(oyente),
    cargarParticipacion,
    elegir,
  };
}
