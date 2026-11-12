// Diagnóstico (corte 3): las materas del usuario en vivo. El corte 3 pide reducir lo manual, así que aquí ya
// no se escriben valores: se elige una matera y se ve su matera Tamagotchi, su última lectura real y lo que la
// API decide de ella.
//
// De dónde sale cada cosa (este módulo no decide ningún estado):
// - GET /plantas: las materas del usuario, cada una con su última medición (la que mandó su sensor).
// - GET /juego/materas, que consulta juego.js: el tamaño, la condición, la cara, el globo y si duerme.
// - POST /diagnosticos: la última lectura real se manda a la validación del corte 1 (R1, el puerto de entrada
//   DiagnosticarPlanta), y la API responde el estado global, el estado y el rango óptimo de cada parámetro
//   y las recomendaciones. Aquí no se compara ningún valor contra un rango ni se escribe ninguna recomendación.
//
// Se actualiza sola, como Mis materas: cada 10 s vuelve a pedir GET /plantas (consulta-periodica.js) y,
// mientras la conexión en vivo funciona, recibe cada medición al instante (tiempo-real.js). Cada lectura
// nueva se diagnostica una sola vez.
import { obtenerPlantas, pedirDiagnostico } from "./api.js";
import { consultarCadaRato, textoConsulta } from "./consulta-periodica.js";
import { dibujoDeMatera, macetaVacia, rotulosDeMatera } from "./dibujo-planta.js";
import { dominioVisual, fraccion, porcentaje } from "./escala.js";
import {
  capitalizar, colorDeEstado, crear, etiqueta, nombreDeEstado, numero, puntosConSigno, signoDe, tono, unidad,
} from "./formato.js";
import { fechaCorta, mostrarError } from "./formularios.js";
import { esMasNueva, especieDe, textoOrigen } from "./lecturas.js";
import { sesion } from "./sesion.js";

// La última matera elegida, por usuario: así, al volver a la app, se abre la misma.
const CLAVE_ELEGIDA = "matera.diagnostico.elegida";

// Solo los rótulos del estado de cada parámetro que manda la API; un valor nuevo se muestra tal cual.
const ROTULOS_PARAMETRO = Object.assign(Object.create(null), { OPTIMO: "ÓPTIMO", BAJO: "BAJO", ALTO: "ALTO" });
const rotuloParametro = (estado) => ROTULOS_PARAMETRO[estado] ?? String(estado);

export function crearPantallaDiagnostico(contexto) {
  const $ = (id) => document.getElementById(id);
  const pantalla = $("pantalla-diagnostico");
  const menu = $("diagnostico-menu");
  const aLaVista = () => !pantalla.hidden;

  let plantas = []; // GET /plantas
  let cargadas = false; // ya respondió GET /plantas al menos una vez con esta sesión
  let elegidaId = null;
  let especiePedida = null; // «Diagnosticar» desde Especies: la primera matera de esa especie
  // plantaId -> { momento, diagnostico }: lo que respondió POST /diagnosticos para la lectura de ese momento.
  const diagnosticos = new Map();
  let fallo = null; // { clave, error }: el último POST /diagnosticos que falló
  let enCurso = null; // { clave, control }
  let errorPlantas = null;
  let errorCatalogos = null;
  let generacion = 0; // cambia al cerrar la sesión: una respuesta de la sesión anterior se descarta

  menu.addEventListener("click", (evento) => {
    const ficha = evento.target.closest("[data-planta]");
    if (ficha) elegir(Number(ficha.dataset.planta));
  });
  menu.addEventListener("keydown", moverConTeclado);
  $("diagnostico-historial").addEventListener("click", () => {
    if (elegidaId !== null) contexto.verPlanta("historial", elegidaId);
  });
  $("diagnostico-vacio-dibujo").replaceChildren(macetaVacia({ sinGlobo: true, clase: "diagnostico__vacio-planta" }));

  consultarCadaRato(aLaVista, actualizar);

  contexto.tiempoReal.alRecibir((mensaje) => {
    if (!aLaVista() || !cargadas) return; // al volver a la pantalla se recarga todo
    if (mensaje.tipo === "reconectado") {
      actualizar();
      return;
    }
    if (mensaje.tipo !== "medicion") return;
    const planta = plantas.find((p) => p.id === mensaje.planta.id);
    if (!planta) {
      actualizar(); // una matera creada en otra pestaña
      return;
    }
    if (esMasNueva(planta.ultimaMedicion, mensaje.medicion)) return; // la consulta ya trajo una posterior
    planta.ultimaMedicion = mensaje.medicion;
    pintarMenu();
    if (planta.id === elegidaId) {
      pintarMatera();
      diagnosticar();
    }
  });

  // El juego se consulta aparte (juego.js); aquí solo se vuelve a dibujar lo de las materas que cambiaron.
  contexto.juego.alCambiar((ids) => {
    if (!aLaVista() || !cargadas) return;
    if (ids.some((id) => plantas.some((p) => p.id === id))) pintarMenu();
    if (ids.includes(elegidaId)) pintarMatera();
  });

  // ---- las materas ----

  async function actualizar() {
    // Mientras el asistente «Conectar sensor» tiene al equipo en la red de la placa no hay API que consultar.
    if (!sesion.activa() || contexto.sinApi?.()) return;
    const mia = generacion;
    let nuevas;
    try {
      nuevas = await obtenerPlantas();
    } catch (error) {
      if (mia !== generacion) return;
      errorPlantas = error;
      pintarErrores();
      if (!cargadas) $("diagnostico-bajada").textContent = "No se pudieron cargar sus materas.";
      return;
    }
    if (mia !== generacion) return;
    errorPlantas = null;
    // Si mientras se esperaba la respuesta llegó una medición en vivo, esa es más reciente: no se retrocede.
    const antes = new Map(plantas.map((p) => [p.id, p]));
    for (const nueva of nuevas) {
      const vieja = antes.get(nueva.id)?.ultimaMedicion;
      if (esMasNueva(vieja, nueva.ultimaMedicion)) nueva.ultimaMedicion = vieja;
    }
    plantas = nuevas;
    cargadas = true;
    for (const id of diagnosticos.keys()) if (!plantas.some((p) => p.id === id)) diagnosticos.delete(id);
    $("diagnostico-consulta").textContent = textoConsulta();
    ponerElegida(idInicial(), { guardar: false });
    pintar();
    diagnosticar();
  }

  // Desde Especies («Diagnosticar»), la de la especie pedida; si no, la que se eligió en otra pantalla, la de
  // esta pantalla, la que quedó guardada o la primera.
  function idInicial() {
    const existe = (id) => id !== null && plantas.some((p) => p.id === id);
    if (especiePedida) {
      const pedida = especiePedida;
      especiePedida = null;
      const deEsa = plantas.find((p) => p.especie === pedida);
      avisar(deEsa || !plantas.length ? "" : `No tiene materas de ${pedida}: agregue una en Mis materas para ver su diagnóstico.`);
      if (deEsa) return deEsa.id;
    }
    if (existe(contexto.plantaElegida)) return contexto.plantaElegida;
    if (existe(elegidaId)) return elegidaId;
    const guardada = leerGuardada();
    if (existe(guardada)) return guardada;
    return plantas[0]?.id ?? null;
  }

  const elegida = () => plantas.find((p) => p.id === elegidaId) ?? null;

  function elegir(id) {
    if (id === elegidaId) return;
    avisar("");
    ponerElegida(id, { guardar: true });
    pintar();
    const nueva = menu.querySelector('[aria-selected="true"]');
    nueva?.focus({ preventScroll: true });
    nueva?.scrollIntoView({ block: "nearest", inline: "nearest" });
    diagnosticar();
  }

  function ponerElegida(id, { guardar }) {
    elegidaId = id;
    // Historial abre la misma matera, y la próxima vez que entre a la app se abre esta.
    if (id !== null) contexto.plantaElegida = id;
    if (guardar && id !== null) guardarElegida(id);
  }

  function claveGuardada() {
    const usuario = sesion.usuario();
    return usuario ? `${CLAVE_ELEGIDA}.${usuario.id}` : null;
  }

  function leerGuardada() {
    try {
      const clave = claveGuardada();
      const valor = clave ? Number(localStorage.getItem(clave)) : NaN;
      return Number.isInteger(valor) && valor > 0 ? valor : null;
    } catch {
      return null; // sin almacenamiento (modo privado estricto): se abre la primera
    }
  }

  function guardarElegida(id) {
    try {
      const clave = claveGuardada();
      if (clave) localStorage.setItem(clave, String(id));
    } catch {
      // Sin almacenamiento: solo se recuerda mientras la página esté abierta.
    }
  }

  // ---- el diagnóstico de la última lectura ----

  const claveDe = (planta, medicion) => `${planta.id}|${medicion.momento}`;

  // Sin conexión o con un error del servidor se vuelve a intentar en la consulta siguiente; un 4xx no cambia
  // con reintentar la misma lectura, así que se muestra hasta que llegue otra.
  const reintentable = (error) => !error.status || error.status >= 500;

  async function diagnosticar() {
    const planta = elegida();
    const medicion = planta?.ultimaMedicion;
    if (!medicion || contexto.sinApi?.()) return;
    const clave = claveDe(planta, medicion);
    if (diagnosticos.get(planta.id)?.momento === medicion.momento || enCurso?.clave === clave) return;
    if (fallo?.clave === clave && !reintentable(fallo.error)) return;
    enCurso?.control.abort(); // la de otra matera u otra lectura: ya no sirve
    const control = new AbortController();
    enCurso = { clave, control };
    const mia = generacion;
    let respuesta;
    try {
      // R1: la lectura real del sensor pasa por la misma validación del corte 1, POST /diagnosticos. Se manda
      // tal como la guardó la API, con la especie de la matera; la respuesta trae todo lo que se muestra.
      respuesta = await pedirDiagnostico(solicitudDe(planta, medicion), { signal: control.signal });
    } catch (error) {
      if (error.name === "AbortError" || mia !== generacion) return;
      fallo = { clave, error };
      if (error.codigo === "SIN_CONEXION") contexto.marcarConexion(false);
      if (planta.id === elegidaId) pintarResultado();
      return;
    } finally {
      if (enCurso?.control === control) enCurso = null;
    }
    if (mia !== generacion) return;
    // Se marca un momento solo si reemplaza el diagnóstico de una lectura anterior de la misma matera.
    const nuevo = diagnosticos.has(planta.id);
    diagnosticos.set(planta.id, { momento: medicion.momento, diagnostico: respuesta });
    if (fallo?.clave === clave) fallo = null;
    contexto.marcarConexion(true);
    if (planta.id === elegidaId) pintarResultado({ nuevo });
  }

  // { especie, humedad, luz, temperatura }: el cuerpo de POST /diagnosticos con los valores de la lectura.
  function solicitudDe(planta, medicion) {
    const solicitud = { especie: planta.especie };
    for (const lectura of medicion.lecturas) solicitud[lectura.nombre] = lectura.valor;
    return solicitud;
  }

  // ---- pintar ----

  function pintar() {
    pintarErrores();
    const hay = plantas.length > 0;
    $("diagnostico-bajada").textContent = !cargadas
      ? "Cargando sus materas…"
      : hay
        ? "La última lectura de cada matera, revisada por la API. Se actualiza sola cuando llega otra."
        : "Aquí verá la última lectura de cada matera y lo que la API dice de ella.";
    menu.hidden = !hay;
    $("diagnostico-panel").hidden = !hay;
    $("diagnostico-vacio").hidden = !cargadas || hay;
    pintarMenu();
    if (!hay) return;
    $("diagnostico-panel").setAttribute("aria-labelledby", idFicha(elegidaId));
    pintarMatera();
    pintarResultado();
  }

  function pintarErrores() {
    mostrarError($("error-diagnostico"), errorPlantas ?? errorCatalogos);
  }

  function avisar(texto) {
    $("diagnostico-aviso").textContent = texto;
    $("diagnostico-aviso").hidden = !texto;
  }

  // ---- el menú: una ficha por matera, con su dibujo pequeño y el color de su última medición ----

  const idFicha = (id) => `diagnostico-ficha-${id}`;

  // Lo que se ve en una ficha. Solo se vuelve a crear la ficha que cambió: así no se pierde un clic a medias
  // ni el foco cuando llega una lectura o cambian los puntos.
  function firmaDe(planta) {
    const matera = contexto.juego.mascotaDe(planta.id);
    return JSON.stringify([
      planta.apodo, planta.especie, planta.ultimaMedicion?.estado ?? null, planta.id === elegidaId,
      matera ? [matera.etapa, matera.condicion, matera.cara, matera.dormida] : null,
    ]);
  }

  function pintarMenu() {
    const conFoco = menu.contains(document.activeElement);
    const viejas = [...menu.children];
    const mismasMaterasEnOrden = viejas.length === plantas.length
      && viejas.every((nodo, i) => nodo.dataset.planta === String(plantas[i].id));
    if (mismasMaterasEnOrden) {
      plantas.forEach((planta, i) => {
        if (viejas[i].dataset.firma !== firmaDe(planta)) viejas[i].replaceWith(ficha(planta));
      });
    } else {
      const desplazado = menu.scrollLeft;
      menu.replaceChildren(...plantas.map(ficha));
      menu.scrollLeft = desplazado;
    }
    if (conFoco && !menu.contains(document.activeElement)) {
      menu.querySelector('[aria-selected="true"]')?.focus({ preventScroll: true });
    }
  }

  function ficha(planta) {
    const elegidaAhora = planta.id === elegidaId;
    const matera = contexto.juego.mascotaDe(planta.id);
    const estado = planta.ultimaMedicion?.estado;
    const dibujo = matera
      ? dibujoDeMatera(matera, { sinGlobo: true, clase: "diagnostico__ficha-dibujo" })
      : macetaVacia({ sinGlobo: true, clase: "diagnostico__ficha-dibujo" });
    dibujo.setAttribute("aria-hidden", "true");
    const nodo = crear("button", { clase: "diagnostico__ficha" },
      dibujo,
      crear("span", { clase: "diagnostico__ficha-nombres" },
        crear("span", { clase: "diagnostico__ficha-apodo", texto: planta.apodo }),
        crear("span", { clase: "diagnostico__ficha-especie", texto: capitalizar(planta.especie) })),
      crear("span", {
        clase: "diagnostico__ficha-punto",
        estilo: { color: colorDeEstado(estado).texto },
      }),
      crear("span", { clase: "solo-lectores", texto: estado ? `, ${nombreDeEstado(estado)}` : ", sin lecturas" }));
    nodo.querySelector(".diagnostico__ficha-punto").setAttribute("aria-hidden", "true");
    Object.assign(nodo, { type: "button", id: idFicha(planta.id), tabIndex: elegidaAhora ? 0 : -1 });
    nodo.dataset.planta = planta.id;
    nodo.dataset.firma = firmaDe(planta);
    nodo.setAttribute("role", "tab");
    nodo.setAttribute("aria-selected", String(elegidaAhora));
    nodo.setAttribute("aria-controls", "diagnostico-panel");
    return nodo;
  }

  // Las flechas, Inicio y Fin mueven entre las fichas y eligen esa matera (como unas pestañas).
  function moverConTeclado(evento) {
    const fichas = [...menu.querySelectorAll("[role=tab]")];
    const actual = fichas.indexOf(document.activeElement);
    if (actual < 0) return;
    const destino = {
      ArrowRight: actual + 1, ArrowDown: actual + 1, ArrowLeft: actual - 1, ArrowUp: actual - 1,
      Home: 0, End: fichas.length - 1,
    }[evento.key];
    if (destino === undefined) return;
    evento.preventDefault();
    elegir(Number(fichas[(destino + fichas.length) % fichas.length].dataset.planta));
  }

  // ---- la matera elegida: su Tamagotchi y sus datos ----

  function pintarMatera() {
    const planta = elegida();
    if (!planta) return;
    const especie = especieDe(contexto, planta.especie);
    $("diagnostico-apodo").textContent = planta.apodo;
    $("diagnostico-especie").replaceChildren(
      capitalizar(planta.especie),
      ...(especie?.nombreCientifico
        ? [" · ", crear("span", { clase: "diagnostico__cientifico", texto: especie.nombreCientifico })]
        : []));
    pintarMascota(planta);
    $("diagnostico-nota").textContent = nota(planta);
  }

  function pintarMascota(planta) {
    const caja = $("diagnostico-mascota");
    const matera = contexto.juego.mascotaDe(planta.id);
    if (!matera) {
      caja.replaceChildren(macetaVacia({ clase: "diagnostico__planta" }));
      caja.dataset.planta = "";
      $("diagnostico-juego").replaceChildren(crear("p", { clase: "diagnostico__cuidado", texto: "Consultando el juego…" }));
      return;
    }
    const dibujo = dibujoDeMatera(matera, { clase: "diagnostico__planta" });
    // Se marca un momento solo si cambió el dibujo de la misma matera (no al cambiar de matera).
    const descripcion = (nodo) => nodo?.querySelector("svg")?.getAttribute("aria-label");
    const cambio = caja.dataset.planta === String(planta.id) && descripcion(caja) !== descripcion(dibujo);
    caja.replaceChildren(dibujo);
    caja.dataset.planta = String(planta.id);
    caja.classList.remove("diagnostico__mascota--nueva");
    if (cambio) {
      void caja.offsetWidth; // vuelve a empezar la animación
      caja.classList.add("diagnostico__mascota--nueva");
    }

    const rotulos = rotulosDeMatera(matera);
    const horas = matera.horasCuidada;
    const lineas = [
      crear("p", { clase: `diagnostico__puntos juego__valor--${signoDe(matera.puntos)}` },
        crear("span", { clase: "diagnostico__puntos-valor", texto: puntosConSigno(matera.puntos) }),
        crear("span", { clase: "diagnostico__puntos-unidad", texto: " puntos" })),
      crear("p", { clase: "diagnostico__etapa", texto: `${rotulos.etapa} · ${rotulos.condicion}` }),
      crear("p", {
        clase: "diagnostico__cuidado",
        texto: `${numero.format(horas)} ${horas === 1 ? "hora" : "horas"} de juego bien cuidada`,
      }),
    ];
    if (matera.dormida) {
      lineas.push(crear("p", {
        clase: "diagnostico__cuidado",
        texto: matera.ultimaLectura
          ? `${capitalizar(rotulos.cara)}: hace rato no le llegan lecturas.`
          : `${capitalizar(rotulos.cara)}: espera su primera lectura.`,
      }));
    }
    $("diagnostico-juego").replaceChildren(...lineas);
  }

  function nota(planta) {
    const sensor = planta.sensor ? `Sensor ${planta.sensor.codigo}` : "Sin sensor";
    const medicion = planta.ultimaMedicion;
    if (!medicion) return `${sensor} · todavía no llega ninguna lectura`;
    // El origen solo se dice si no es el sensor actual: una medición vieja a mano o de un sensor anterior.
    const origen = medicion.origen === planta.sensor?.codigo
      ? ""
      : medicion.origen === "MANUAL" ? `, ${textoOrigen(medicion.origen)}` : `, del sensor anterior ${medicion.origen}`;
    return `${sensor} · última lectura ${fechaCorta(medicion.momento)}${origen}`;
  }

  // ---- el resultado de POST /diagnosticos ----

  function pintarResultado({ nuevo = false } = {}) {
    const planta = elegida();
    if (!planta) return;
    const medicion = planta.ultimaMedicion;
    const tarjeta = $("diagnostico-estado");
    if (!medicion) {
      pintarSinLecturas(planta);
      return;
    }
    const guardado = diagnosticos.get(planta.id);
    const error = fallo?.clave === claveDe(planta, medicion) ? fallo.error : null;
    // Mientras se diagnostica una lectura nueva, sigue a la vista el diagnóstico de la anterior (con su
    // fecha), así la pantalla no parpadea cada vez que llega una.
    if (guardado && !error) {
      pintarDiagnostico(planta, guardado);
      if (nuevo) {
        tarjeta.classList.remove("diagnostico__estado--nuevo");
        void tarjeta.offsetWidth;
        tarjeta.classList.add("diagnostico__estado--nuevo");
      }
      return;
    }
    // Todavía sin respuesta, o con un error: los valores de la lectura, sin ningún estado.
    ponerVeredicto(null, error ? "Sin diagnóstico" : "Consultando a la API…");
    // Sin punto después de la hora: ya termina en «p. m.».
    $("diagnostico-detalle").textContent = `Lectura del ${fechaCorta(medicion.momento)}: ` +
      (error ? "la API no pudo revisarla. Se vuelve a intentar con la próxima consulta." : "la API la está revisando.");
    mostrarError($("error-diagnostico-api"), error);
    $("diagnostico-lecturas").hidden = false;
    $("diagnostico-lecturas").replaceChildren(...ordenar(medicion.lecturas).map((lectura) => tarjetaLectura(lectura, null)));
    $("diagnostico-consejos").hidden = true;
  }

  function pintarSinLecturas(planta) {
    ponerVeredicto(null, "Sin lecturas todavía");
    $("diagnostico-detalle").textContent =
      `«${planta.apodo}» todavía no recibe lecturas de su sensor. Apenas llegue la primera, la API la revisa con ` +
      `los rangos de ${planta.especie} y aquí verá el estado de cada parámetro y qué hacer.`;
    mostrarError($("error-diagnostico-api"), null);
    $("diagnostico-lecturas").hidden = true;
    $("diagnostico-lecturas").replaceChildren();
    $("diagnostico-consejos").hidden = true;
  }

  function pintarDiagnostico(planta, { momento, diagnostico }) {
    ponerVeredicto(diagnostico.estado, nombreDeEstado(diagnostico.estado));
    $("diagnostico-detalle").textContent =
      `Lectura del ${fechaCorta(momento)}, revisada con los rangos de ${diagnostico.especie}.`;
    mostrarError($("error-diagnostico-api"), null);
    $("diagnostico-lecturas").hidden = false;
    $("diagnostico-lecturas").replaceChildren(...ordenar(diagnostico.parametros).map((resultado) =>
      tarjetaLectura(resultado, resultado)));
    pintarRecomendaciones(diagnostico);
  }

  // El estado global, con su color; sin estado, el color neutro.
  function ponerVeredicto(estado, texto) {
    const colores = colorDeEstado(estado);
    const tarjeta = $("diagnostico-estado");
    tarjeta.style.setProperty("--estado", colores.texto);
    tarjeta.style.setProperty("--estado-fondo", colores.fondo);
    tarjeta.dataset.estado = estado ?? "";
    // Solo si cambia: así el lector de pantalla lo anuncia una vez y no con cada lectura igual.
    if ($("diagnostico-veredicto").textContent !== texto) $("diagnostico-veredicto").textContent = texto;
  }

  // En el orden de GET /parametros; si los catálogos todavía no llegan, en el que vino.
  function ordenar(lista) {
    const orden = contexto.parametros.map((p) => p.nombre);
    const posicion = (nombre) => (orden.includes(nombre) ? orden.indexOf(nombre) : orden.length);
    return [...lista].sort((a, b) => posicion(a.nombre) - posicion(b.nombre));
  }

  // Un parámetro: el valor leído y, con el diagnóstico, su estado y su rango óptimo según la API. La banda y la
  // marca solo ubican esos números en la escala.
  function tarjetaLectura(lectura, resultado) {
    const indice = contexto.parametros.findIndex((p) => p.nombre === lectura.nombre);
    const parametro = contexto.parametros[indice];
    const color = tono(Math.max(indice, 0));
    const nodo = crear("div", { clase: "diagnostico__lectura" },
      crear("div", { clase: "diagnostico__lectura-nombre" },
        crear("span", { clase: "diagnostico__lectura-muestra", estilo: { background: color.linea } }),
        etiqueta(lectura.nombre)),
      crear("p", { clase: "diagnostico__lectura-valor", texto: `${numero.format(lectura.valor)} ${unidad(lectura.unidad)}` }));
    if (!resultado) return nodo;
    const [minimo, maximo] = resultado.rangoOptimo;
    const colores = colorDeEstado(resultado.estado);
    nodo.dataset.estado = resultado.estado;
    nodo.append(crear("span", {
      clase: "pastilla diagnostico__lectura-estado",
      texto: rotuloParametro(resultado.estado),
      estilo: { color: colores.texto, background: colores.fondo },
    }));
    if (parametro) nodo.append(escalaDe(resultado.valor, { min: minimo, max: maximo }, parametro, color));
    nodo.append(crear("p", {
      clase: "diagnostico__lectura-rango",
      texto: `Rango óptimo: ${numero.format(minimo)}–${numero.format(maximo)} ${unidad(resultado.unidad)}`,
    }));
    return nodo;
  }

  function escalaDe(valor, rango, parametro, color) {
    const dominio = dominioVisual(rango, parametro);
    const desde = fraccion(rango.min, dominio);
    const pista = crear("div", { clase: "diagnostico__pista" },
      crear("div", {
        clase: "diagnostico__banda",
        estilo: { left: porcentaje(desde), width: porcentaje(fraccion(rango.max, dominio) - desde) },
      }),
      crear("div", {
        clase: "diagnostico__marca",
        estilo: { left: porcentaje(fraccion(valor, dominio)), background: color.linea },
      }));
    pista.setAttribute("aria-hidden", "true");
    return pista;
  }

  function pintarRecomendaciones(diagnostico) {
    $("diagnostico-consejos").hidden = false;
    const lista = $("diagnostico-recomendaciones");
    const hay = diagnostico.recomendaciones.length > 0;
    // El color sigue al estado global que mandó la API; sin recomendaciones, el de una planta bien.
    const colores = colorDeEstado(hay ? diagnostico.estado : "SALUDABLE");
    lista.classList.toggle("diagnostico__recomendaciones--vacia", !hay);
    lista.style.setProperty("--consejo", colores.texto);
    lista.style.setProperty("--consejo-fondo", colores.fondo);
    if (!hay) {
      lista.replaceChildren(crear("li", {
        clase: "diagnostico__consejo",
        texto: "La API no recomienda nada para esta lectura: no hay nada que corregir.",
      }));
      return;
    }
    lista.replaceChildren(...diagnostico.recomendaciones.map((texto) =>
      crear("li", { clase: "diagnostico__consejo", texto })));
  }

  // ---- lo que usa app.js ----

  return {
    mostrar() {
      avisar("");
      pintar();
      actualizar();
      contexto.juego.refrescar(); // el Tamagotchi de cada matera, al día
    },
    ocultar() {
      enCurso?.control.abort();
      enCurso = null;
    },
    // Con los catálogos llegan el nombre científico y el orden de los parámetros.
    alCargarCatalogos() {
      errorCatalogos = null;
      if (cargadas) pintar();
      else pintarErrores();
    },
    mostrarErrorDeCarga(error) {
      errorCatalogos = error;
      pintarErrores();
    },
    // «Diagnosticar» en Especies: la primera matera de esa especie (app.js navega a esta pantalla después).
    seleccionarEspecie(nombre) {
      especiePedida = nombre;
    },
    // Al cerrar la sesión: nada de esta cuenta queda para la que entre después en la misma pestaña.
    reiniciar() {
      generacion += 1;
      enCurso?.control.abort();
      enCurso = null;
      plantas = [];
      cargadas = false;
      elegidaId = null;
      especiePedida = null;
      diagnosticos.clear();
      fallo = null;
      errorPlantas = null;
      errorCatalogos = null;
      avisar("");
      for (const id of ["diagnostico-consulta", "diagnostico-veredicto", "diagnostico-detalle", "diagnostico-apodo",
        "diagnostico-especie", "diagnostico-nota"]) $(id).textContent = "";
      for (const id of ["diagnostico-mascota", "diagnostico-juego", "diagnostico-lecturas", "diagnostico-recomendaciones"]) {
        $(id).replaceChildren();
      }
      $("diagnostico-mascota").dataset.planta = "";
      mostrarError($("error-diagnostico-api"), null);
      pintar();
    },
  };
}
