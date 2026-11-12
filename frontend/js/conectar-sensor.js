// Asistente «Conectar sensor»: conecta una placa nueva a su WiFi y a una matera, sin tocar código.
//
// La placa, en su modo de conexión, abre su propia red (Matera-…), muestra en su pantalla un QR con esa red y
// su clave, y se anuncia por Bluetooth. La app le habla por un canal (CanalPlaca, en canal-placa.js): le
// pide su código y la huella de su clave (info), le pasa el WiFi de la casa y las direcciones del servidor
// (configurar), espera a que entre a ese WiFi (estado) y le pide que apague su red (cerrar). Después crea la
// matera con ese código y esa huella (o le cambia el sensor) y espera la primera lectura.
//
// El asistente no sabe cuál canal usa: le pide la lista a canales-placa.js (el punto de composición) y solo
// mira lo que cada canal declara. Si deja la red (la red de la placa), el equipo se une a ella con el QR y
// mientras tanto no alcanza la API. Si pide la clave (Bluetooth), la persona escribe la clave de la pantalla
// y el equipo no deja su WiFi. Si un canal falla, se ofrece el otro sin perder lo ya escrito.
//
// Aquí no vive ninguna regla de negocio: la placa dice en qué etapa va, la API valida el código y la huella
// y calcula el estado de la lectura. La clave del WiFi y la de la pantalla solo viajan a la placa y nunca se
// guardan. Al cambiar de red la página puede recargarse: por eso el avance se guarda en sessionStorage
// (paso, canal, matera, código, huella y servidores).
import { cambiarSensor, obtenerPlantas, obtenerRed, registrarPlanta } from "./api.js";
import { CONEXION_CANCELADA, esFallaDelCanal } from "./canal-placa.js";
import { crearCanales } from "./canales-placa.js";
import { API_BASE, API_EN_ESTE_EQUIPO } from "./config.js";
import { capitalizar, crear, crearSvg, pastillaEstado } from "./formato.js";
import { mostrarError, ocupado } from "./formularios.js";
import { textoLecturas } from "./lecturas.js";
import { sesion } from "./sesion.js";

const GUARDADO = "matera.conectar-sensor";
// Lo único que se guarda del avance. Nunca la clave del WiFi ni la de la pantalla.
const CAMPOS_GUARDADOS = [
  "usuario", "modo", "paso", "canal", "apodo", "especie", "plantaId", "plantaApodo",
  "codigo", "huella", "servidores", "enviado", "momentoAntes", "yaVinculada", "ajena", "nota",
];

const BUSCAR_PLACA_MS = 2000; // cada cuánto se pregunta por la placa
const ESTADO_MS = 1500; // cada cuánto se pregunta en qué etapa va la placa
const CORTE_BREVE_MS = 6000; // al entrar al WiFi, la placa cambia de canal y su red se cae un momento
const CORTE_LARGO_MS = 45000;
const API_MS = 2000; // cada cuánto se pregunta si la API ya responde
const API_MAXIMO_MS = 4000;
const LECTURA_MS = 3000;
const PISTAS_MS = 120000; // a los 2 minutos sin novedad, la app da pistas
const UNIRSE_MAXIMO_MS = 600000; // buscar la placa: a los 10 minutos activos la app para y lo dice
const REVISAR_ENVIO_MS = 3000; // antes de reenviar una petición sin respuesta, se vuelve a mirar
const VISTA_MS = 400; // cada cuánto se mira si Mis materas volvió a la vista

// Los seis pasos. El segundo y el cuarto se llaman distinto según el canal: con la red de la placa el
// equipo se une a ella y después vuelve a su WiFi; por Bluetooth nunca deja su WiFi.
const PASOS = [
  { id: "preparar", texto: () => "Preparar" },
  { id: "unirse", texto: (canal) => (canal?.dejaLaRed ? "Unirse a la placa" : "Encontrar la placa") },
  { id: "wifi", texto: () => "Elegir el WiFi" },
  { id: "volver", texto: (canal) => (canal?.dejaLaRed ? "Volver a su red" : "Cerrar la conexión") },
  { id: "crear", texto: (canal, nueva) => (nueva ? "Crear la matera" : "Cambiar el sensor") },
  { id: "lectura", texto: () => "Primera lectura" },
];
// «conectando» es la segunda mitad de «Elegir el WiFi»; «listo» es el final.
const PASO_VISIBLE = { conectando: "wifi" };
const PASOS_VALIDOS = new Set([...PASOS.map((p) => p.id), "conectando", "listo"]);
// Mientras tanto, la app le habla a la placa (y, con la red de la placa, el equipo puede estar sin la API).
const PASOS_EN_LA_PLACA = new Set(["unirse", "wifi", "conectando", "volver"]);

// Cómo se cuenta cada etapa que dice la placa (estado). Las etapas las decide la placa.
const ETAPAS = Object.assign(Object.create(null), {
  conectando: "La placa se está uniendo a su WiFi…",
  "buscando-servidor": "La placa ya entró a su WiFi y está buscando el servidor…",
  "esperando-matera": "La placa encontró el servidor.",
  conectada: "La placa ya tiene su matera y quedó conectada.",
  "sin-red": "La placa no pudo unirse a esa red.",
});

const RED_DE_LA_PLACA = "Matera-…";

const esperar = (ms) => new Promise((listo) => setTimeout(listo, ms));

// Un AbortSignal que se dispara a los ms milisegundos (AbortSignal.timeout no está en todos los navegadores).
function senalCon(ms) {
  const control = new AbortController();
  setTimeout(() => control.abort(), ms);
  return control.signal;
}

function leerGuardado() {
  try {
    return JSON.parse(sessionStorage.getItem(GUARDADO)) ?? null;
  } catch {
    return null;
  }
}

function escribirGuardado(valor) {
  try {
    if (valor) sessionStorage.setItem(GUARDADO, JSON.stringify(valor));
    else sessionStorage.removeItem(GUARDADO);
  } catch {
    // Sin almacenamiento: el avance dura lo que dure la página.
  }
}

// ---- piezas de la vista ----

// Los íconos, dibujados con el color del texto (currentColor): siguen al tema.
const TRAZOS = {
  bluetooth: [["path", { d: "M7 7.5l10 9-5 4.5V3l5 4.5-10 9" }]],
  wifi: [
    ["path", { d: "M2.6 9.2a13.6 13.6 0 0 1 18.8 0" }],
    ["path", { d: "M5.7 12.6a9.2 9.2 0 0 1 12.6 0" }],
    ["path", { d: "M8.8 16a4.6 4.6 0 0 1 6.4 0" }],
    ["circle", { cx: "12", cy: "19.4", r: "1.3", fill: "currentColor", stroke: "none" }],
  ],
  sensor: [
    ["rect", { x: "6", y: "8", width: "12", height: "10", rx: "2.5" }],
    ["path", { d: "M9.5 8V4.5M14.5 8V4.5M12 18v3" }],
    ["path", { d: "M12 15.4v-3.2" }],
    ["path", { d: "M12 12.4c0-1.6-1.2-2.6-2.8-2.6 0 1.6 1.2 2.6 2.8 2.6zM12 12.2c0-1.4 1.1-2.4 2.6-2.4 0 1.4-1.1 2.4-2.6 2.4z" }],
  ],
};

function icono(nombre) {
  const svg = crearSvg("svg", {
    viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", "stroke-width": "1.9",
    "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true",
  });
  for (const [tipo, atributos] of TRAZOS[nombre] ?? []) svg.append(crearSvg(tipo, atributos));
  return svg;
}

function encabezado(texto) {
  const nodo = crear("h3", { clase: "asistente__subtitulo", texto });
  nodo.tabIndex = -1;
  return nodo;
}

const parrafo = (texto, clase = "asistente__texto") => crear("p", { clase, texto });

// Una línea de estado con el indicador de espera.
function linea(texto) {
  const nodo = crear("p", { clase: "asistente__estado" },
    crear("span", { clase: "asistente__girando" }),
    crear("span", { texto }));
  nodo.setAttribute("role", "status");
  return nodo;
}

function cambiarLinea(nodo, texto, { esperando = true } = {}) {
  nodo.lastChild.textContent = texto;
  nodo.firstChild.hidden = !esperando;
  nodo.hidden = false;
}

function pistas(titulo, textos, ...extra) {
  const nodo = crear("div", { clase: "asistente__pistas" },
    crear("p", { clase: "asistente__pistas-titulo", texto: titulo }),
    crear("ul", {}, ...textos.map((texto) => crear("li", { texto }))),
    ...extra);
  nodo.hidden = true;
  return nodo;
}

function aviso(texto) {
  const nodo = crear("div", { clase: "tarjeta-error asistente__aviso" },
    crear("p", { clase: "tarjeta-error__mensaje", texto }));
  nodo.setAttribute("role", "alert");
  return nodo;
}

function cajaError() {
  const nodo = crear("div", { clase: "tarjeta-error" });
  nodo.hidden = true;
  nodo.setAttribute("role", "alert");
  return nodo;
}

function boton(texto, clase, accion) {
  const nodo = crear("button", { clase, texto });
  nodo.type = "button";
  nodo.addEventListener("click", accion);
  return nodo;
}

function rotuloPara(texto, campo) {
  const nodo = crear("label", { clase: "formulario__etiqueta", texto });
  nodo.htmlFor = campo.id;
  return nodo;
}

// Las barras de la señal que dice la placa (en dBm). Solo es dibujo.
function senal(dbm) {
  if (typeof dbm !== "number") return crear("span");
  const llenas = dbm >= -55 ? 4 : dbm >= -67 ? 3 : dbm >= -78 ? 2 : 1;
  const nodo = crear("span", { clase: "senal" },
    ...[1, 2, 3, 4].map((n) => crear("span", {
      clase: `senal__barra${n <= llenas ? " senal__barra--llena" : ""}`,
      estilo: { height: `${n * 25}%` },
    })));
  nodo.title = `${dbm} dBm`;
  nodo.setAttribute("aria-label", `Señal de ${dbm} dBm`);
  nodo.setAttribute("role", "img");
  return nodo;
}

// La misma red puede aparecer varias veces (varios puntos de acceso): se muestra una vez.
function sinRepetir(redes) {
  const vistas = new Set();
  return redes.filter((red) => {
    if (typeof red?.nombre !== "string" || !red.nombre || vistas.has(red.nombre)) return false;
    vistas.add(red.nombre);
    return true;
  });
}

// Cuántas direcciones del servidor acepta la API local de la placa (configurar).
const SERVIDORES_POR_PLACA = 4;

// La dirección por la que este front llegó a la API va primero: desde ese WiFi ya se sabe que responde.
function ordenar(servidores) {
  const lista = servidores.filter((s) => typeof s === "string" && s);
  return [...lista.filter((s) => s === API_BASE), ...lista.filter((s) => s !== API_BASE)];
}

// ---- el asistente ----

// opciones.raiz: el contenedor en Mis materas. alAbrirOCerrar(abierto), alCambiarLasMateras() (volver a
// pedir la lista) y alConectarAMano(datos) (el flujo viejo con config.h) los pone Mis materas.
export function crearAsistente(contexto, { raiz, alAbrirOCerrar, alCambiarLasMateras, alConectarAMano }) {
  const canales = crearCanales(); // los adaptadores de CanalPlaca, en orden de preferencia
  let estado = null; // el avance, el mismo que se guarda
  let canal = null; // el canal elegido: solo en memoria (en el avance va su id)
  let vuelta = 0; // cada paso nuevo (o cancelar) deja sin efecto las esperas del paso anterior
  let redes = []; // las redes que ve la placa: solo en memoria
  let redesEnMemoria = false;
  let redElegida = ""; // solo para mostrarla mientras la placa se conecta
  let ultimaLectura = null; // la primera lectura, para mostrarla en «Listo»
  let alLlegarMedicion = null;
  let vista = false; // Mis materas está a la vista: solo entonces el asistente consulta
  // Lo ya escrito, para no perderlo si se cambia de canal. Solo en memoria, nunca se guarda.
  let clavePlaca = ""; // la clave de la pantalla
  let borradorWifi = null; // { red, otra, clave }: el formulario del WiFi
  let leerFormularioWifi = null; // mientras se ve «Elegir el WiFi», guarda lo escrito en borradorWifi
  let nombrePlaca = ""; // el nombre con que se anuncia (por ejemplo, Matera-7518JP), si un canal lo supo
  let despuesDeEncontrarla = null; // a qué paso ir al encontrar la placa (si no, a «Elegir el WiFi»)

  // Si la conexión en vivo trae la lectura, no hay que esperar la próxima consulta.
  contexto.tiempoReal.alRecibir((mensaje) => alLlegarMedicion?.(mensaje));

  const nueva = () => estado.modo === "nueva";
  const disponibles = () => canales.filter((c) => c.disponible());
  const otrosCanales = () => disponibles().filter((c) => c !== canal);

  // Mis materas a la vista y la pestaña visible. Fuera de ahí, el asistente no consulta ni crea nada.
  const visible = () => vista && !document.hidden;

  // Espera a que el asistente vuelva a estar a la vista. Devuelve false si el paso ya no está vigente.
  async function alVer(mia) {
    while (!visible() && vigente(mia)) await esperar(VISTA_MS);
    return vigente(mia);
  }

  // La lista de materas solo se vuelve a pedir con la sesión abierta.
  function cambiaronLasMateras() {
    if (sesion.activa()) alCambiarLasMateras();
  }

  function guardar() {
    escribirGuardado(Object.fromEntries(CAMPOS_GUARDADOS.map((campo) => [campo, estado[campo]])));
  }

  // Suelta el canal y borra lo escrito (las claves solo estaban en memoria).
  function soltarCanal() {
    canal?.desconectar();
    canal = null;
    clavePlaca = "";
    borradorWifi = null;
    leerFormularioWifi = null;
    nombrePlaca = "";
    despuesDeEncontrarla = null;
  }

  function abrir({ modo, apodo = "", especie = "", planta = null }) {
    if (estado && !["lectura", "listo"].includes(estado.paso)
      && !window.confirm("Hay una placa a medio conectar. ¿Dejarla y empezar otra vez?")) {
      return;
    }
    soltarCanal();
    estado = {
      usuario: sesion.usuario()?.id ?? null,
      modo,
      paso: "preparar",
      canal: null,
      apodo,
      especie,
      plantaId: planta?.id ?? null,
      plantaApodo: planta?.apodo ?? "",
      codigo: null,
      huella: null,
      servidores: [],
      enviado: false,
      momentoAntes: null,
      yaVinculada: false,
      ajena: false,
      nota: "",
    };
    redes = [];
    redesEnMemoria = false;
    ultimaLectura = null;
    irA("preparar");
  }

  // Al volver a Mis materas (también después de recargar la página): sigue donde iba.
  function reanudar() {
    if (estado) {
      mostrarse();
      return;
    }
    const guardado = leerGuardado();
    if (!guardado || !PASOS_VALIDOS.has(guardado.paso)) return;
    if (guardado.usuario !== (sesion.usuario()?.id ?? null)) {
      escribirGuardado(null); // el avance era de otra cuenta
      return;
    }
    estado = { ...guardado };
    // Un avance de antes de los canales era por la red de la placa.
    const id = estado.canal ?? canales.find((c) => c.dejaLaRed)?.id ?? null;
    canal = canales.find((c) => c.id === id && c.disponible()) ?? null;
    estado.canal = canal?.id ?? null;
    if (PASOS_EN_LA_PLACA.has(estado.paso)) {
      if (!canal) {
        irA("preparar"); // ese canal ya no se puede usar aquí: se elige otro
        return;
      }
      if (canal.pideClave && estado.paso !== "volver") {
        // La conexión (y la clave de la pantalla) no sobreviven a la recarga: hay que volver a encontrar la
        // placa. Si ya tenía el WiFi, se sigue esperando sus etapas.
        despuesDeEncontrarla = estado.paso === "conectando" ? "conectando" : null;
        irA("unirse");
        return;
      }
    }
    // Las redes que ve la placa no se guardan: hay que volver a pedírselas.
    irA(estado.paso === "wifi" ? "unirse" : estado.paso);
  }

  function cerrar() {
    vuelta += 1;
    alLlegarMedicion = null;
    estado = null;
    soltarCanal();
    escribirGuardado(null);
    raiz.hidden = true;
    raiz.replaceChildren();
    alAbrirOCerrar(false);
  }

  function cancelar() {
    if (PASOS_EN_LA_PLACA.has(estado.paso) || estado.paso === "crear") {
      if (!window.confirm("¿Cancelar la conexión de la placa? Podrá empezar otra vez desde «Agregar matera».")) return;
    }
    cerrar();
  }

  // Al cerrar la sesión: deja de esperar y se oculta. El avance queda guardado por si la misma cuenta
  // vuelve a entrar (por ejemplo, si la sesión venció a mitad de camino); a otra cuenta no se le muestra.
  function reiniciar() {
    vuelta += 1;
    alLlegarMedicion = null;
    estado = null;
    soltarCanal();
    raiz.hidden = true;
    raiz.replaceChildren();
    alAbrirOCerrar(false);
  }

  function mostrarse() {
    raiz.hidden = false;
    alAbrirOCerrar(true);
  }

  function irA(paso) {
    vuelta += 1;
    alLlegarMedicion = null;
    leerFormularioWifi = null;
    estado.paso = paso;
    guardar();
    const mia = vuelta;
    PASOS_DEL_ASISTENTE[paso](mia);
  }

  const vigente = (mia) => mia === vuelta;

  // Usa otro canal desde «Encontrar la placa», sin perder lo ya escrito (el apodo, la clave de la pantalla
  // y lo del WiFi). despues: a qué paso ir al encontrar la placa.
  function usarCanal(otro, { despues = null } = {}) {
    leerFormularioWifi?.();
    if (canal && canal !== otro) {
      nombrePlaca = canal.placa || nombrePlaca;
      canal.desconectar();
    }
    canal = otro;
    estado.canal = otro.id;
    despuesDeEncontrarla = despues;
    irA("unirse");
  }

  // Si un canal falla: «Seguir por …» con cada uno de los otros. null si no hay otro.
  function cambioDeCanal(texto) {
    const otros = otrosCanales();
    if (!otros.length) return null;
    // Si ya tenía el WiFi (esperando sus etapas), con el otro canal se sigue esperando.
    const despues = estado.paso === "conectando" ? "conectando" : null;
    const botones = otros.map((otro) => boton(`Seguir por ${otro.nombre}`, "boton-contorno", () => usarCanal(otro, { despues })));
    const nodo = crear("div", { clase: "asistente__otro-canal" },
      crear("p", { clase: "asistente__otro-canal-texto", texto }),
      crear("div", { clase: "asistente__fila" }, ...botones));
    nodo.hidden = true;
    return nodo;
  }

  // El marco de cada paso: título, matera, los seis pasos, el contenido y el pie.
  function pintar(paso, ...cuerpo) {
    const visiblePaso = PASO_VISIBLE[paso] ?? paso;
    const actual = paso === "listo" ? PASOS.length : PASOS.findIndex((p) => p.id === visiblePaso);
    const titulo = crear("h2", { clase: "asistente__titulo", texto: "Conectar sensor" });
    titulo.id = "asistente-titulo";
    const lista = crear("ol", { clase: "asistente__pasos" }, ...PASOS.map((p, indice) => {
      const hecho = indice < actual;
      const clase = hecho ? " asistente__paso--hecho" : indice === actual ? " asistente__paso--actual" : "";
      const nodo = crear("li", { clase: `asistente__paso${clase}` },
        crear("span", { clase: "asistente__paso-numero", texto: hecho ? "✓" : String(indice + 1) }),
        crear("span", { clase: "asistente__paso-texto", texto: p.texto(canal, nueva()) }),
        ...(hecho ? [crear("span", { clase: "solo-lectores", texto: " (hecho)" })] : []));
      if (indice === actual) nodo.setAttribute("aria-current", "step");
      return nodo;
    }));
    lista.setAttribute("aria-label", "Pasos");
    const [subtitulo, ...resto] = cuerpo;
    const contador = actual < PASOS.length ? [crear("p", { clase: "asistente__contador", texto: `Paso ${actual + 1} de ${PASOS.length}` })] : [];
    const avisoDelCanal = canal?.aviso && PASOS_EN_LA_PLACA.has(paso) ? [aviso(canal.aviso)] : [];
    raiz.replaceChildren(
      crear("div", { clase: "asistente__cabecera" },
        crear("span", { clase: "asistente__icono" }, icono("sensor")),
        crear("div", { clase: "asistente__titulos" }, titulo, crear("p", { clase: "asistente__matera", texto: descripcion() })),
        ...(canal ? [crear("span", { clase: "asistente__canal" }, icono(canal.icono), crear("span", { texto: `Por ${canal.nombre}` }))] : [])),
      lista,
      crear("div", { clase: "asistente__cuerpo" }, ...contador, subtitulo, ...avisoDelCanal, ...resto),
      pie(paso));
    mostrarse();
    subtitulo?.focus?.();
  }

  function descripcion() {
    const placa = estado.codigo ? ` · placa ${estado.codigo}` : "";
    if (nueva()) {
      const apodo = estado.apodo ? `«${estado.apodo}»` : "sin apodo";
      const especie = estado.especie ? ` · ${capitalizar(estado.especie)}` : "";
      return `Matera nueva ${apodo}${especie}${placa}`;
    }
    return `Sensor nuevo para «${estado.plantaApodo}»${placa}`;
  }

  function pie(paso) {
    const nodos = [];
    if (paso !== "listo") {
      const enLaMatera = paso === "lectura" || (paso === "crear" && estado.enviado);
      nodos.push(boton(enLaMatera ? "Cerrar" : "Cancelar", "boton-secundario", cancelar));
    }
    if (["preparar", "unirse", "wifi"].includes(paso)) {
      nodos.push(boton("Conectar a mano (placas con config.h)", "enlace", () => {
        const { modo, apodo, especie, plantaId } = estado;
        cerrar();
        alConectarAMano({ modo, apodo, especie, plantaId });
      }));
    }
    return crear("div", { clase: "asistente__pie" }, ...nodos);
  }

  // ---- 1. Preparar: mientras todavía hay API, se anotan las direcciones del servidor y se elige el canal ----

  async function preparar(mia) {
    const estadoNodo = linea("Consultando la API…");
    const resultado = crear("div", { clase: "asistente__resultado" });
    const error = cajaError();
    const principal = boton("Volver a intentar", "boton-primario", () => irA("preparar"));
    principal.hidden = true;
    pintar("preparar",
      encabezado("Preparar"),
      parrafo("Mientras este equipo sigue en su WiFi, la app le pregunta a la API a qué dirección tendrá que mandar la placa sus lecturas. Tenga a mano el nombre y la clave de su WiFi."),
      estadoNodo, resultado, error, principal);

    if (!await alVer(mia)) return;
    let red;
    try {
      red = await obtenerRed();
    } catch (fallo) {
      if (!vigente(mia)) return;
      estadoNodo.hidden = true;
      mostrarError(error, fallo);
      principal.hidden = false;
      principal.focus();
      return;
    }
    if (!vigente(mia)) return;
    estadoNodo.hidden = true;
    const servidores = ordenar(Array.isArray(red?.servidores) ? red.servidores : []);
    if (!servidores.length) {
      resultado.append(aviso(red?.aviso ?? "La API no dio ninguna dirección para la placa."));
      principal.hidden = false;
      principal.focus();
      return;
    }
    // La API local de la placa recibe de 1 a 4 direcciones: van las primeras, que la API ya ordenó.
    estado.servidores = servidores.slice(0, SERVIDORES_POR_PLACA);
    guardar();
    const canalesAqui = opcionesDeCanal();
    resultado.append(
      parrafo("La placa mandará sus lecturas a:"),
      crear("ul", { clase: "asistente__servidores" }, ...estado.servidores.map((s) => crear("li", {}, crear("code", { texto: s })))),
      canalesAqui);
    canalesAqui.querySelector("button")?.focus();
  }

  // Los canales que se pueden usar aquí, como tarjetas para elegir. El primero es el recomendado.
  function opcionesDeCanal() {
    const lista = disponibles();
    const opciones = lista.map((c, indice) => {
      const recomendado = indice === 0 && lista.length > 1;
      const nodo = crear("button", { clase: `canal-opcion${recomendado ? " canal-opcion--recomendada" : ""}` },
        crear("span", { clase: "canal-opcion__icono" }, icono(c.icono)),
        crear("span", { clase: "canal-opcion__textos" },
          crear("span", { clase: "canal-opcion__nombre", texto: `Por ${c.nombre}` }),
          crear("span", { clase: "canal-opcion__descripcion", texto: c.descripcion })),
        ...(recomendado ? [crear("span", { clase: "canal-opcion__marca", texto: "Recomendado" })] : []));
      nodo.type = "button";
      nodo.addEventListener("click", () => usarCanal(c));
      return nodo;
    });
    const noDisponibles = canales.filter((c) => !c.disponible() && c.motivoNoDisponible);
    return crear("div", { clase: "asistente__canales" },
      crear("p", { clase: "asistente__canales-titulo", texto: "¿Cómo le habla este equipo a la placa?" }),
      crear("div", { clase: "asistente__canales-lista" }, ...opciones),
      ...noDisponibles.map((c) => parrafo(c.motivoNoDisponible, "asistente__texto asistente__texto--tenue")));
  }

  // ---- 2. Encontrar la placa: por el canal elegido, se le pide su código, su huella y las redes que ve ----

  function unirse(mia) {
    if (!canal) {
      irA("preparar");
      return;
    }
    if (canal.pideClave) encontrarConClave(mia);
    else unirseASuRed(mia);
  }

  // Lo que dijo la placa en info. Devuelve false si le faltan el código o la huella.
  function anotarInfo(info) {
    if (typeof info?.codigo !== "string" || !info.codigo || typeof info?.huella !== "string" || !info.huella) return false;
    estado.codigo = info.codigo;
    estado.huella = info.huella;
    redes = sinRepetir(Array.isArray(info.redes) ? info.redes : []);
    redesEnMemoria = true;
    nombrePlaca = canal.placa || nombrePlaca;
    const siguiente = despuesDeEncontrarla ?? "wifi";
    despuesDeEncontrarla = null;
    irA(siguiente);
    return true;
  }

  // 2a. Con la clave de la pantalla (los canales Bluetooth, web o nativo): el equipo no deja su WiFi.
  function encontrarConClave(mia) {
    const campo = crear("input", { clase: "formulario__campo asistente__clave" });
    Object.assign(campo, { id: `asistente-clave-placa-${mia}`, autocomplete: "off", spellcheck: false, value: clavePlaca });
    campo.setAttribute("autocapitalize", "none");
    campo.setAttribute("autocorrect", "off");
    campo.setAttribute("enterkeyhint", "go");
    campo.addEventListener("input", () => {
      clavePlaca = campo.value;
    });
    const estadoNodo = linea("");
    estadoNodo.hidden = true;
    const error = cajaError();
    const enviar = crear("button", { clase: "boton-primario", texto: canal.placa ? "Volver a intentar" : "Buscar la placa" });
    enviar.type = "submit";
    const forma = crear("form", { clase: "asistente__formulario" },
      rotuloPara("Clave de la pantalla", campo),
      campo,
      parrafo("Son 8 letras y números, junto al QR. Cambian cada vez que la placa abre su modo de conexión.", "formulario__ayuda"),
      error,
      enviar);
    forma.noValidate = true;
    const otraPlaca = boton("Elegir otra placa", "enlace", () => {
      canal.desconectar(); // la próxima búsqueda vuelve a abrir la lista
      irA("unirse");
    });
    otraPlaca.hidden = !canal.placa;
    const otroCanal = cambioDeCanal(`¿No funciona por ${canal.nombre}? Siga por otro camino: lo que ya escribió se conserva.`);
    const ayuda = pistas("¿No aparece la placa en la lista?", [
      "Acérquese a la matera: el Bluetooth alcanza unos pocos metros.",
      "Revise que el Bluetooth de este equipo esté encendido.",
      "La placa atiende una conexión a la vez: si otro celular o PC está conectado a ella, desconéctelo.",
      "Si la pantalla no muestra el QR, desenchufe la matera y vuelva a enchufarla. Si ya tenía un WiFi guardado, mantenga el botón BOOT 5 segundos.",
    ]);
    pintar("unirse",
      encabezado("Encontrar la placa"),
      parrafo("Enchufe la matera. Su pantalla muestra un QR y, al lado, el nombre de su red y una clave. Escriba esa clave aquí: con ella, la placa sabe que usted la tiene enfrente."),
      parrafo("Al buscarla, el navegador abre una lista con las placas cercanas: elija la que se llama como la red de la pantalla (Matera-…) y confirme.", "asistente__texto asistente__texto--tenue"),
      forma, estadoNodo, otraPlaca, ...(otroCanal ? [otroCanal] : []), ayuda);

    let reloj = null; // la cuenta atrás de un 429
    forma.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      if (enviar.disabled) return;
      clavePlaca = campo.value;
      mostrarError(error, null);
      cambiarLinea(estadoNodo, canal.placa ? `Conectando con «${canal.placa}»…` : "Buscando la placa…");
      let info;
      try {
        info = await ocupado(enviar, async () => {
          await canal.conectar({ clave: clavePlaca }); // la primera vez abre la lista de placas
          if (!vigente(mia)) return null;
          cambiarLinea(estadoNodo, `Conectado con «${canal.placa || "la placa"}». Pidiéndole sus datos…`);
          return canal.info();
        });
      } catch (fallo) {
        if (!vigente(mia)) return;
        otraPlaca.hidden = !canal.placa;
        enviar.textContent = canal.placa ? "Volver a intentar" : "Buscar la placa";
        if (fallo?.codigo === CONEXION_CANCELADA) {
          // Puede que la placa no apareciera en la lista: se dan las pistas y el otro camino.
          cambiarLinea(estadoNodo, "No eligió ninguna placa. Búsquela otra vez cuando aparezca en la lista.", { esperando: false });
          ayuda.hidden = false;
          if (otroCanal) otroCanal.hidden = false;
          return;
        }
        estadoNodo.hidden = true;
        mostrarError(error, fallo);
        if (fallo?.status === 401) {
          enviar.textContent = "Probar con esta clave";
          campo.focus();
          campo.select();
          return;
        }
        if (fallo?.status === 429) {
          esperarBloqueo(fallo.detalle?.segundos);
          return;
        }
        if (esFallaDelCanal(fallo)) {
          ayuda.hidden = false;
          if (otroCanal) otroCanal.hidden = false;
        }
        return;
      }
      if (!vigente(mia) || !info) return;
      if (!anotarInfo(info)) {
        cambiarLinea(estadoNodo, "La placa respondió, pero sin su código o sin la huella de su clave. Vuelva a intentarlo.", { esperando: false });
      }
    });

    // Con 429 la placa no atiende pedidos por un rato: el botón espera con la cuenta atrás.
    function esperarBloqueo(segundos) {
      if (!(segundos > 0)) return;
      const hasta = Date.now() + segundos * 1000;
      enviar.disabled = true;
      const contar = () => {
        if (!vigente(mia)) return;
        const faltan = Math.ceil((hasta - Date.now()) / 1000);
        if (faltan <= 0) {
          enviar.disabled = false;
          enviar.textContent = "Volver a intentar";
          return;
        }
        enviar.textContent = `Espere ${faltan} s`;
        clearTimeout(reloj);
        reloj = setTimeout(contar, 1000);
      };
      contar();
    }
  }

  // 2b. Uniéndose a la red de la placa: el equipo entra a su red y la app la encuentra sola.
  async function unirseASuRed(mia) {
    const estadoNodo = linea("Buscando la placa…");
    const ayuda = pistas("¿No aparece?", [
      "Apague los datos móviles del celular mientras tanto: con ellos encendidos, el celular puede mandar las peticiones por los datos y no llegar a la placa.",
      "El celular que comparte su internet (hotspot) no puede unirse a otra red: use el PC o el celular de otra persona.",
      "Si Chrome pregunta si esta página puede buscar dispositivos de la red local, elija Permitir.",
      "Si la pantalla no muestra el QR, desenchufe la matera y vuelva a enchufarla. Si ya tenía un WiFi guardado, mantenga el botón BOOT 5 segundos.",
    ]);
    const red = nombrePlaca ? `«${nombrePlaca}»` : RED_DE_LA_PLACA;
    const clave = clavePlaca.trim() ? ` La clave de esa red es la misma que ya escribió: «${clavePlaca.trim()}».` : "";
    const otroCanal = cambioDeCanal("¿Prefiere que este equipo no deje su WiFi?");
    if (otroCanal) otroCanal.hidden = false;
    pintar("unirse",
      encabezado("Unirse a la placa"),
      parrafo(`Enchufe la matera. En su pantalla aparece un QR: escanéelo con la cámara del celular, o en el PC conéctese a la red ${red} con la clave que muestra.${clave}`),
      parrafo("Cuando este equipo entre a esa red, la app encuentra la placa sola. Esa red no tiene internet: es normal.", "asistente__texto asistente__texto--tenue"),
      estadoNodo, ayuda, ...(otroCanal ? [otroCanal] : []));

    let activo = 0; // tiempo buscando con el asistente a la vista
    while (vigente(mia)) {
      if (!await alVer(mia)) return;
      if (activo >= UNIRSE_MAXIMO_MS) {
        cambiarLinea(estadoNodo, "No se encontró la placa. Revise que este equipo siga unido a su red y vuelva a buscarla.", { esperando: false });
        ayuda.hidden = false;
        estadoNodo.after(boton("Buscar la placa otra vez", "boton-primario", () => irA("unirse")));
        return;
      }
      const intento = Date.now();
      let info = null;
      try {
        info = await canal.info();
      } catch {
        // Todavía no está en la red de la placa.
      }
      if (!vigente(mia)) return;
      if (info) {
        if (anotarInfo(info)) return;
        cambiarLinea(estadoNodo, "La placa respondió, pero sin su código o sin la huella de su clave. Volviendo a preguntar…");
      }
      await esperar(Math.max(0, BUSCAR_PLACA_MS - (Date.now() - intento)));
      activo += Date.now() - intento;
      if (activo >= PISTAS_MS) ayuda.hidden = false;
    }
  }

  // ---- 3. Elegir el WiFi: la placa dice qué redes ve; la clave va directo a ella ----

  // previo: lo que la persona ya había escrito (al actualizar la lista de redes o al cambiar de canal).
  function elegirWifi(mia, previo = borradorWifi) {
    if (!redesEnMemoria) {
      unirse(mia);
      return;
    }
    const grupo = `asistente-red-${mia}`;
    const opcion = (valor, marcada, ...contenido) => {
      const radio = crear("input");
      Object.assign(radio, { type: "radio", name: grupo, value: valor, checked: marcada });
      return crear("label", { clase: "asistente__red" }, radio, ...contenido);
    };
    const otraNombre = crear("input", { clase: "formulario__campo" });
    Object.assign(otraNombre, { id: `asistente-otra-${mia}`, autocomplete: "off", placeholder: "Nombre de la red" });
    otraNombre.setAttribute("aria-label", "Nombre de la otra red");
    otraNombre.hidden = redes.length > 0;
    const lista = crear("fieldset", { clase: "asistente__redes" },
      crear("legend", { clase: "formulario__etiqueta", texto: "Redes que ve la placa" }),
      ...redes.map((red, indice) => opcion(red.nombre, indice === 0,
        crear("span", { clase: "asistente__red-nombre", texto: red.nombre }),
        crear("span", { clase: "asistente__red-nota", texto: red.segura === false ? "abierta" : "con clave" }),
        senal(red.senal))),
      opcion("", redes.length === 0,
        crear("span", { clase: "asistente__red-nombre", texto: "Otra red" }),
        crear("span", { clase: "asistente__red-nota", texto: "escriba su nombre" })),
      otraNombre);
    lista.addEventListener("change", (evento) => {
      if (evento.target.type !== "radio") return;
      otraNombre.hidden = lista.querySelector("input[type=radio]:checked")?.value !== "";
      if (!otraNombre.hidden) otraNombre.focus();
    });

    const clave = crear("input", { clase: "formulario__campo" });
    Object.assign(clave, { id: `asistente-clave-${mia}`, type: "password", autocomplete: "new-password", spellcheck: false });
    const ver = crear("input");
    ver.type = "checkbox";
    ver.addEventListener("change", () => {
      clave.type = ver.checked ? "text" : "password";
    });
    if (previo) {
      const radios = [...lista.querySelectorAll("input[type=radio]")];
      const igual = radios.find((r) => r.value === previo.red && r.value !== "");
      const elegir = igual ?? radios.find((r) => r.value === "");
      for (const r of radios) r.checked = r === elegir;
      otraNombre.value = igual ? previo.otra : previo.red || previo.otra;
      otraNombre.hidden = elegir.value !== "";
      clave.value = previo.clave;
    }
    const leer = () => ({
      red: lista.querySelector("input[type=radio]:checked")?.value ?? "",
      otra: otraNombre.value,
      clave: clave.value,
    });
    // Si se cambia de canal desde aquí, lo escrito se conserva (solo en memoria).
    leerFormularioWifi = () => {
      borradorWifi = leer();
    };
    const error = cajaError();
    const otroCanal = cambioDeCanal("¿Se cortó la conexión con la placa? Siga por otro camino: la red y la clave que escribió se conservan.");
    const enviar = crear("button", { clase: "boton-primario", texto: "Conectar la matera a este WiFi" });
    enviar.type = "submit";
    const forma = crear("form", { clase: "asistente__formulario" },
      lista,
      rotuloPara("Clave del WiFi", clave),
      clave,
      crear("label", { clase: "asistente__ver" }, ver, crear("span", { texto: "Mostrar la clave" })),
      parrafo(`La clave va directo a la placa, por ${canal.nombre}. La app no la guarda. Si la red es abierta, déjela vacía.`, "formulario__ayuda"),
      error,
      enviar);
    forma.noValidate = true;
    forma.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const { red: elegida, otra } = leer();
      const red = elegida || otra;
      try {
        await ocupado(enviar, () => canal.configurar({
          red, claveRed: clave.value, servidores: estado.servidores.slice(0, SERVIDORES_POR_PLACA),
        }));
      } catch (fallo) {
        if (!vigente(mia)) return;
        mostrarError(error, fallo);
        if (otroCanal) otroCanal.hidden = !esFallaDelCanal(fallo);
        return;
      }
      if (!vigente(mia)) return;
      clave.value = "";
      borradorWifi = null;
      redElegida = red;
      irA("conectando");
    });

    const actualizar = boton("Actualizar la lista", "boton-contorno", async () => {
      try {
        const info = await ocupado(actualizar, () => canal.info());
        if (!vigente(mia)) return;
        redes = sinRepetir(Array.isArray(info?.redes) ? info.redes : []);
        elegirWifi(++vuelta, leer());
      } catch (fallo) {
        if (!vigente(mia)) return;
        mostrarError(error, fallo);
        if (otroCanal) otroCanal.hidden = !esFallaDelCanal(fallo);
      }
    });

    pintar("wifi",
      encabezado("Elegir el WiFi"),
      parrafo(redes.length
        ? `La placa ${estado.codigo} está lista. Elija el WiFi de la casa al que se va a conectar la matera.`
        : `La placa ${estado.codigo} está lista, pero no ve ninguna red. Escriba el nombre de la suya o actualice la lista.`),
      forma,
      crear("div", { clase: "asistente__fila" }, actualizar),
      ...(otroCanal ? [otroCanal] : []));
  }

  // ---- 3b. La placa entra al WiFi y busca el servidor ----

  async function conectando(mia) {
    const estadoNodo = linea(redElegida ? `Conectando la matera a «${redElegida}»…` : "Conectando la matera a su WiFi…");
    const detalle = parrafo("", "asistente__texto asistente__texto--tenue");
    detalle.hidden = true;
    const resultado = crear("div");
    const error = cajaError();
    const servidores = estado.servidores.join(" o ");
    const sinServidor = pistas("La placa no encuentra el servidor", [
      `Lo busca en ${servidores}.`,
      "Revise que el backend esté corriendo con MATERA_HOST=0.0.0.0 y que el firewall del PC deje pasar el puerto 5000.",
      "Revise que el PC esté en el mismo WiFi que eligió para la matera.",
    ]);
    const sinPlaca = pistas("La placa no responde", canal.dejaLaRed
      ? [
        `Si este equipo se salió de la red ${RED_DE_LA_PLACA}, vuelva a unirse: la pantalla de la matera muestra la red y su clave.`,
        "Si la pantalla volvió a mostrar un QR, la placa no pudo entrar al WiFi: escanéelo otra vez y revise el nombre y la clave.",
      ]
      : [
        "Acérquese a la matera: el Bluetooth alcanza unos pocos metros.",
        "Si la pantalla volvió a mostrar un QR, la placa no pudo entrar al WiFi: búsquela otra vez y revise el nombre y la clave.",
      ]);
    const otroCanal = cambioDeCanal("¿No hay caso con este camino? Siga por otro: la placa sigue en la misma etapa.");
    const principal = boton("Elegir el WiFi otra vez", "boton-primario", () => irA("unirse"));
    principal.hidden = true;
    pintar("conectando",
      encabezado("Elegir el WiFi"),
      parrafo("La placa entra a su WiFi y busca el servidor. Puede tardar hasta un minuto, y mientras tanto su red puede desaparecer un momento: la app vuelve a preguntar sola."),
      estadoNodo, detalle, resultado, error, sinServidor, sinPlaca, principal, ...(otroCanal ? [otroCanal] : []));

    let ultimaRespuesta = Date.now();
    let buscandoDesde = null;
    while (vigente(mia)) {
      if (!await alVer(mia)) return;
      const intento = Date.now();
      let respuesta = null;
      try {
        respuesta = await canal.estado();
      } catch (fallo) {
        if (!vigente(mia)) return;
        // La placa respondió con un error (por ejemplo, una clave de la pantalla que ya no sirve porque la
        // placa volvió a abrir su modo de conexión): seguir preguntando no lo arregla.
        if (fallo?.status >= 400) {
          cambiarLinea(estadoNodo, "La placa no aceptó el pedido.", { esperando: false });
          mostrarError(error, fallo);
          principal.textContent = "Encontrar la placa otra vez";
          principal.hidden = false;
          principal.focus();
          despuesDeEncontrarla = "conectando";
          return;
        }
        // Si no respondió: al cambiar de canal, la red de la placa se cae un momento.
      }
      if (!vigente(mia)) return;
      if (respuesta) {
        ultimaRespuesta = Date.now();
        sinPlaca.hidden = true;
        principal.hidden = true;
        if (otroCanal) otroCanal.hidden = true;
        const etapa = respuesta.etapa;
        cambiarLinea(estadoNodo, ETAPAS[etapa] ?? `La placa dice: ${etapa}`);
        detalle.textContent = typeof respuesta.detalle === "string" ? respuesta.detalle : "";
        detalle.hidden = !detalle.textContent;
        // Con el front en este mismo PC y la red de la placa, el PC está en la red de la placa y no en el
        // WiFi: la placa no lo encuentra hasta que el PC vuelva. Por eso basta con que ya haya entrado al WiFi.
        const listaParaCerrar = etapa === "esperando-matera" || etapa === "conectada"
          || (etapa === "buscando-servidor" && canal.dejaLaRed && API_EN_ESTE_EQUIPO);
        if (listaParaCerrar) {
          estado.yaVinculada = etapa === "conectada";
          irA("volver");
          return;
        }
        if (etapa === "sin-red") {
          cambiarLinea(estadoNodo, ETAPAS["sin-red"], { esperando: false });
          detalle.hidden = true;
          resultado.replaceChildren(aviso(detalle.textContent || "Revise el nombre de la red y su clave."));
          principal.hidden = false;
          principal.focus();
          return;
        }
        buscandoDesde = etapa === "buscando-servidor" ? buscandoDesde ?? Date.now() : null;
        sinServidor.hidden = buscandoDesde === null || Date.now() - buscandoDesde < PISTAS_MS / 2;
      } else {
        const callada = Date.now() - ultimaRespuesta;
        if (callada >= CORTE_BREVE_MS) {
          cambiarLinea(estadoNodo, canal.dejaLaRed
            ? "La placa no responde: puede ser el cambio de canal de su red. Volviendo a preguntar…"
            : `La placa no responde por ${canal.nombre}. Volviendo a preguntar…`);
        }
        if (callada >= CORTE_LARGO_MS) {
          sinPlaca.hidden = false;
          principal.hidden = false;
          if (otroCanal) otroCanal.hidden = false;
        }
      }
      await esperar(Math.max(0, ESTADO_MS - (Date.now() - intento)));
    }
  }

  // ---- 4. Volver a su red (o cerrar la conexión): la placa apaga su red y su Bluetooth ----

  async function volver(mia) {
    const estadoNodo = linea("Pidiéndole a la placa que cierre su modo de conexión…");
    const ayuda = pistas("¿No vuelve?", [
      "Si este equipo no vuelve solo a su WiFi, únase a él a mano desde la configuración de WiFi.",
      `Revise que el backend siga corriendo: la app lo busca en ${API_BASE}.`,
    ]);
    let introduccion = "La placa ya está en su WiFi y encontró el servidor.";
    if (estado.yaVinculada) introduccion = "La placa ya tiene su matera y quedó conectada a su WiFi.";
    else if (canal?.dejaLaRed && API_EN_ESTE_EQUIPO) {
      introduccion = "La placa ya entró a su WiFi. Para que encuentre el servidor, este PC tiene que volver a esa misma red.";
    }
    pintar("volver",
      encabezado(canal?.dejaLaRed === false ? "Cerrar la conexión" : "Volver a su red"),
      parrafo(introduccion),
      parrafo(canal?.dejaLaRed === false
        ? "Ahora la placa apaga su red y su Bluetooth. Este equipo nunca dejó su WiFi."
        : "Ahora la placa apaga su red y este equipo vuelve solo a su WiFi de siempre."),
      estadoNodo, ayuda);

    // Si la placa no contesta, puede que ya la haya apagado: se sigue igual.
    for (let intento = 0; intento < 3 && vigente(mia) && canal; intento += 1) {
      if (!await alVer(mia)) return;
      try {
        await canal.cerrar();
        break;
      } catch (fallo) {
        if (fallo.status) break; // respondió: no tiene sentido insistir
        await esperar(1000);
      }
    }
    if (!vigente(mia)) return;
    canal?.desconectar(); // ya no hace falta: lo que sigue es con la API
    cambiarLinea(estadoNodo, `Esperando a que la API responda en ${API_BASE}…`);

    const inicio = Date.now();
    while (vigente(mia)) {
      if (!await alVer(mia)) return;
      const intento = Date.now();
      try {
        await obtenerRed({ signal: senalCon(API_MAXIMO_MS) });
        if (!vigente(mia)) return;
        irA("crear");
        return;
      } catch (fallo) {
        if (fallo?.codigo === "SESION_INVALIDA") return; // la app ya lleva a Ingresar; el avance queda guardado
      }
      if (!vigente(mia)) return;
      if (Date.now() - inicio >= PISTAS_MS / 2) ayuda.hidden = false;
      await esperar(Math.max(0, API_MS - (Date.now() - intento)));
    }
  }

  // ---- 5. Crear la matera (o cambiarle el sensor) con el código y la huella de la placa ----

  async function crearOCambiar(mia) {
    const titulo = nueva() ? "Crear la matera" : "Cambiar el sensor";
    let enCurso = nueva()
      ? `Creando «${estado.apodo}» con la placa ${estado.codigo}…`
      : `Poniéndole la placa ${estado.codigo} a «${estado.plantaApodo}»…`;
    if (estado.yaVinculada) enCurso = `Buscando la matera de la placa ${estado.codigo}…`;
    const estadoNodo = linea(enCurso);
    const error = cajaError();
    const pista = parrafo("", "asistente__texto asistente__texto--tenue");
    pista.hidden = true;
    const campos = camposDeLaMatera();
    campos.nodo.hidden = true;
    const principal = boton("Volver a intentar", "boton-primario", () => {
      if (nueva()) {
        estado.apodo = campos.apodo.value;
        estado.especie = campos.especie.value;
      }
      irA("crear");
    });
    principal.hidden = true;
    pintar("crear",
      encabezado(titulo),
      parrafo(nueva()
        ? "La app crea la matera con el código de la placa y la huella de su clave. La clave nunca sale de la placa."
        : "La app le pone a la matera el código de la placa y la huella de su clave. Su historial se conserva."),
      estadoNodo, error, pista, campos.nodo, principal);

    if (!await alVer(mia)) return;
    try {
      if (estado.yaVinculada) await buscarSuMatera(mia);
      else if (nueva()) await crearMatera(mia);
      else await cambiarElSensor(mia);
    } catch (fallo) {
      if (!vigente(mia) || fallo?.codigo === "SESION_INVALIDA") return;
      // Si la API la rechazó, no se creó nada. Sin respuesta no se sabe: al reintentar se revisa primero.
      if (fallo?.status >= 400) estado.enviado = false;
      guardar();
      cambiarLinea(estadoNodo, nueva() ? "No se pudo crear la matera." : "No se pudo cambiar el sensor.", { esperando: false });
      mostrarError(error, fallo);
      if (fallo?.codigo === "SENSOR_YA_VINCULADO") {
        pista.textContent = "Si esa matera es suya, elimínela o cámbiele el sensor en Mis materas, y vuelva a intentar.";
        pista.hidden = false;
      }
      campos.nodo.hidden = !nueva();
      principal.hidden = false;
    }
  }

  // El apodo y la especie, por si la API los rechaza al final: se corrigen aquí y se vuelve a intentar.
  function camposDeLaMatera() {
    const apodo = crear("input", { clase: "formulario__campo" });
    Object.assign(apodo, { id: "asistente-apodo", autocomplete: "off", value: estado.apodo ?? "" });
    const especie = crear("select", { clase: "selector" });
    especie.id = "asistente-especie";
    especie.append(...contexto.especies.map((e) => new Option(capitalizar(e.nombre), e.nombre)));
    if (estado.especie) especie.value = estado.especie;
    const nodo = crear("div", { clase: "formulario__fila" },
      crear("div", { clase: "formulario__grupo" }, rotuloPara("Apodo de la planta", apodo), apodo),
      crear("div", { clase: "formulario__grupo" }, rotuloPara("Especie", especie), especie));
    return { nodo, apodo, especie };
  }

  async function crearMatera(mia) {
    // Si la página se recargó (o se cortó la red) justo después de enviarla, la matera ya puede existir:
    // no se crea dos veces.
    if (estado.enviado) {
      const buscar = async () => (await obtenerPlantas()).find((p) => p.sensor?.codigo === estado.codigo);
      let creada = await buscar();
      if (!creada) {
        // Sin respuesta no se sabe si la API terminó de crearla: se espera un momento y se vuelve a mirar.
        await esperar(REVISAR_ENVIO_MS);
        if (!await alVer(mia)) return;
        creada = await buscar();
      }
      if (!vigente(mia)) return;
      if (creada) {
        estado.plantaId = creada.id;
        estado.plantaApodo = creada.apodo;
        cambiaronLasMateras();
        irA("lectura");
        return;
      }
    }
    estado.enviado = true;
    guardar();
    const { planta } = await registrarPlanta({
      apodo: estado.apodo,
      especie: estado.especie,
      codigo: estado.codigo,
      huella: estado.huella,
    });
    cambiaronLasMateras(); // aunque se haya cancelado mientras tanto, la matera ya existe
    if (!vigente(mia)) return;
    estado.plantaId = planta.id;
    estado.plantaApodo = planta.apodo;
    irA("lectura");
  }

  async function cambiarElSensor(mia) {
    // La primera lectura es la primera de esta placa que llegue después de la última que había.
    const antes = (await obtenerPlantas()).find((p) => p.id === estado.plantaId);
    if (!vigente(mia)) return;
    if (estado.enviado && antes?.sensor?.codigo === estado.codigo) {
      // Ya se había enviado y la API lo aplicó: no se reenvía, y momentoAntes sigue siendo el de entonces.
      cambiaronLasMateras();
      estado.plantaApodo = antes.apodo;
      irA("lectura");
      return;
    }
    estado.momentoAntes = antes?.ultimaMedicion?.momento ?? null;
    estado.enviado = true;
    guardar();
    const { planta } = await cambiarSensor(estado.plantaId, estado.codigo, estado.huella);
    cambiaronLasMateras();
    if (!vigente(mia)) return;
    estado.plantaApodo = planta.apodo;
    irA("lectura");
  }

  // La placa dijo «conectada»: su clave ya sirve en una matera. Solo cambió de WiFi.
  async function buscarSuMatera(mia) {
    const suya = (await obtenerPlantas()).find((p) => p.sensor?.codigo === estado.codigo);
    if (!vigente(mia)) return;
    if (!suya) {
      estado.ajena = true;
      irA("listo");
      return;
    }
    const pedida = nueva() ? `No se creó «${estado.apodo}».` : suya.id === estado.plantaId ? "" : `El sensor de «${estado.plantaApodo}» no cambió.`;
    estado.nota = `La placa ya era el sensor de «${suya.apodo}»: solo cambió de WiFi. ${pedida}`.trim();
    estado.plantaId = suya.id;
    estado.plantaApodo = suya.apodo;
    estado.momentoAntes = suya.ultimaMedicion?.momento ?? null;
    irA("lectura");
  }

  // ---- 6. Esperar la primera lectura ----

  async function lectura(mia) {
    const estadoNodo = linea("Esperando la primera lectura…");
    const otraVez = boton("Conectar la placa otra vez", "boton-contorno", () => {
      const planta = { id: estado.plantaId, apodo: estado.plantaApodo };
      cerrar();
      abrir({ modo: "cambio", planta });
    });
    const ayuda = pistas("¿No llega?", [
      `Si la pantalla de la matera sigue en «Agrégame en la app», revise que muestre el código ${estado.codigo}.`,
      "Si volvió a mostrar el QR, la placa no encontró el servidor: revise que el PC esté en el mismo WiFi, que el backend corra con MATERA_HOST=0.0.0.0 y que el firewall deje pasar el puerto 5000. Después, conéctela otra vez.",
    ], crear("div", { clase: "asistente__fila" }, otraVez));
    const error = cajaError();
    pintar("lectura",
      encabezado("Primera lectura"),
      ...(estado.nota ? [parrafo(estado.nota)] : []),
      parrafo("La placa cambia su clave por su token y manda su primera lectura. Su pantalla pasa de «Agrégame en la app» a la carita de la matera. Puede tardar hasta un minuto."),
      estadoNodo, error, ayuda);

    // La primera lectura de esta placa que llegue después de la última que había.
    const esLaPrimera = (medicion) => Boolean(medicion)
      && medicion.origen === estado.codigo && medicion.momento !== estado.momentoAntes;
    const terminar = (medicion) => {
      if (!vigente(mia)) return;
      ultimaLectura = medicion;
      cambiaronLasMateras();
      irA("listo");
    };
    alLlegarMedicion = (mensaje) => {
      if (mensaje.tipo === "medicion" && mensaje.planta?.id === estado.plantaId && esLaPrimera(mensaje.medicion)) {
        terminar(mensaje.medicion);
      }
    };

    const inicio = Date.now();
    while (vigente(mia)) {
      if (!await alVer(mia)) return;
      const intento = Date.now();
      try {
        const planta = (await obtenerPlantas({ signal: senalCon(API_MAXIMO_MS) })).find((p) => p.id === estado.plantaId);
        if (!vigente(mia)) return;
        mostrarError(error, null);
        if (!planta) {
          cambiarLinea(estadoNodo, "La matera ya no está en su cuenta.", { esperando: false });
          return;
        }
        if (esLaPrimera(planta.ultimaMedicion)) {
          terminar(planta.ultimaMedicion);
          return;
        }
      } catch (fallo) {
        if (!vigente(mia) || fallo?.codigo === "SESION_INVALIDA") return;
        if (fallo?.name !== "AbortError") mostrarError(error, fallo);
      }
      if (Date.now() - inicio >= PISTAS_MS) ayuda.hidden = false;
      await esperar(Math.max(0, LECTURA_MS - (Date.now() - intento)));
    }
  }

  // ---- Listo ----

  async function listo(mia) {
    const principal = boton("Ver mis materas", "boton-primario", cerrar);
    if (estado.ajena) {
      pintar("listo",
        encabezado("La placa ya tiene dueño"),
        aviso("La placa quedó conectada a su WiFi, pero ya es el sensor de una matera de otra cuenta: sus lecturas van a esa matera."),
        parrafo("Para usarla en una matera suya, mantenga el botón BOOT 15 segundos: la placa crea una clave nueva y vuelve a pedir que la agreguen."),
        principal);
      return;
    }
    const resumen = crear("div", { clase: "asistente__lectura" });
    pintar("listo",
      encabezado("Listo"),
      crear("p", { clase: "mensaje-exito", texto: `«${estado.plantaApodo}» ya recibe las lecturas de la placa ${estado.codigo}.` }),
      ...(estado.nota ? [parrafo(estado.nota)] : []),
      resumen,
      principal);
    // Si la página se recargó en este paso, la lectura se vuelve a pedir.
    let medicion = ultimaLectura;
    if (!medicion) {
      if (!await alVer(mia)) return;
      try {
        medicion = (await obtenerPlantas()).find((p) => p.id === estado.plantaId)?.ultimaMedicion ?? null;
      } catch {
        medicion = null;
      }
    }
    if (!vigente(mia) || !medicion) return;
    resumen.append(
      parrafo("La lectura que acaba de llegar, con el estado que calculó la API:", "asistente__texto asistente__texto--tenue"),
      crear("div", { clase: "asistente__fila" },
        pastillaEstado(medicion.estado),
        crear("span", { texto: textoLecturas(medicion.lecturas, contexto.parametros) })));
  }

  const PASOS_DEL_ASISTENTE = {
    preparar,
    unirse,
    wifi: elegirWifi,
    conectando,
    volver,
    crear: crearOCambiar,
    lectura,
    listo,
  };

  return {
    abrir,
    reanudar,
    reiniciar,
    activo: () => Boolean(estado),
    // Mis materas entra o sale de la vista: fuera de ella, el asistente se pausa.
    ponerVista(valor) {
      vista = valor;
    },
    // Mientras el equipo puede estar en la red de la placa, Mis materas no consulta la API (no la alcanza).
    // Por Bluetooth el equipo no deja su WiFi: la API sigue respondiendo. Solo vale mientras Mis materas está
    // a la vista: en las otras pantallas no hay nada que la pause.
    sinApi: () => vista && Boolean(estado) && Boolean(canal?.dejaLaRed) && !API_EN_ESTE_EQUIPO
      && PASOS_EN_LA_PLACA.has(estado.paso),
  };
}
