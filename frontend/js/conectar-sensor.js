// Asistente «Conectar sensor»: conecta una placa nueva a su WiFi y a una matera, sin tocar código.
//
// La placa abre su propia red (Matera-…) y muestra en su pantalla un QR con esa red y su clave. El equipo
// se une a esa red; la app le pide a la placa su código y la huella de su clave (GET /info), le pasa el
// WiFi de la casa y las direcciones del servidor (POST /configurar), espera a que entre a ese WiFi
// (GET /estado) y le pide que apague su red (POST /cerrar). Ya de vuelta en su WiFi, la app crea la matera
// con ese código y esa huella (o le cambia el sensor) y espera la primera lectura.
//
// Aquí no vive ninguna regla de negocio: la placa dice en qué etapa va, la API valida el código y la huella
// y calcula el estado de la lectura. La clave del WiFi solo viaja a la placa y nunca se guarda.
// Mientras el equipo está en la red de la placa no alcanza la API, y al cambiar de red la página puede
// recargarse: por eso el avance se guarda en sessionStorage (paso, matera, código, huella y servidores).
import { cambiarSensor, ErrorApi, obtenerPlantas, obtenerRed, registrarPlanta } from "./api.js";
import { API_BASE, API_EN_ESTE_EQUIPO, PLACA_BASE } from "./config.js";
import { capitalizar, crear, pastillaEstado } from "./formato.js";
import { mostrarError, ocupado } from "./formularios.js";
import { textoLecturas } from "./lecturas.js";
import { sesion } from "./sesion.js";

const GUARDADO = "matera.conectar-sensor";
// Lo único que se guarda del avance. Nunca la clave del WiFi.
const CAMPOS_GUARDADOS = [
  "usuario", "modo", "paso", "apodo", "especie", "plantaId", "plantaApodo",
  "codigo", "huella", "servidores", "enviado", "momentoAntes", "yaVinculada", "ajena", "nota",
];

const BUSCAR_PLACA_MS = 2000; // cada cuánto se pregunta por la placa
const PLACA_MAXIMO_MS = 3000; // una petición a la placa que no termina en este tiempo se corta
const CONFIGURAR_MAXIMO_MS = 6000;
const ESTADO_MS = 1500; // cada cuánto se pregunta en qué etapa va la placa
const CORTE_BREVE_MS = 6000; // al entrar al WiFi, la placa cambia de canal y su red se cae un momento
const CORTE_LARGO_MS = 45000;
const API_MS = 2000; // cada cuánto se pregunta si la API ya responde
const API_MAXIMO_MS = 4000;
const LECTURA_MS = 3000;
const PISTAS_MS = 120000; // a los 2 minutos sin novedad, la app da pistas

const PASOS = [
  { id: "preparar", texto: "Preparar" },
  { id: "unirse", texto: "Unirse a la placa" },
  { id: "wifi", texto: "Elegir el WiFi" },
  { id: "volver", texto: "Volver a su red" },
  { id: "crear", texto: "Crear la matera", textoCambio: "Cambiar el sensor" },
  { id: "lectura", texto: "Primera lectura" },
];
// «conectando» es la segunda mitad de «Elegir el WiFi»; «listo» es el final.
const PASO_VISIBLE = { conectando: "wifi" };
const PASOS_VALIDOS = new Set([...PASOS.map((p) => p.id), "conectando", "listo"]);
// Mientras tanto, el equipo puede estar en la red de la placa, sin la API.
const PASOS_EN_LA_PLACA = new Set(["unirse", "wifi", "conectando", "volver"]);

// Cómo se cuenta cada etapa que dice la placa (GET /estado). Las etapas las decide la placa.
const ETAPAS = {
  conectando: "La placa se está uniendo a su WiFi…",
  "buscando-servidor": "La placa ya entró a su WiFi y está buscando el servidor…",
  "esperando-matera": "La placa encontró el servidor.",
  conectada: "La placa ya tiene su matera y quedó conectada.",
  "sin-red": "La placa no pudo unirse a esa red.",
};

const RED_DE_LA_PLACA = "Matera-…";

const esperar = (ms) => new Promise((listo) => setTimeout(listo, ms));

// Un AbortSignal que se dispara a los ms milisegundos (AbortSignal.timeout no está en todos los navegadores).
function senalCon(ms) {
  const control = new AbortController();
  setTimeout(() => control.abort(), ms);
  return control.signal;
}

// La API local de la placa. Responde JSON con CORS abierto, y solo la alcanza quien está en su red.
async function pedirPlaca(ruta, { metodo = "GET", datos, ms = PLACA_MAXIMO_MS } = {}) {
  const opciones = { method: metodo, cache: "no-store", signal: senalCon(ms) };
  if (datos !== undefined) {
    // Petición simple (text/plain, con el cuerpo en JSON): así el navegador no necesita la consulta
    // previa de CORS (OPTIONS) y basta con que la placa responda Access-Control-Allow-Origin.
    opciones.headers = { "Content-Type": "text/plain;charset=UTF-8" };
    opciones.body = JSON.stringify(datos);
  }
  const inalcanzable = () => new ErrorApi(0, {
    error: "PLACA_INALCANZABLE",
    mensaje: `No se pudo contactar la placa en ${PLACA_BASE}. Revise que este equipo siga unido a la red ${RED_DE_LA_PLACA} de la matera.`,
  });
  let respuesta;
  let cuerpo = null;
  try {
    respuesta = await fetch(`${PLACA_BASE}${ruta}`, opciones);
    const texto = await respuesta.text();
    if (texto) cuerpo = JSON.parse(texto);
  } catch (error) {
    if (!respuesta || error.name === "AbortError") throw inalcanzable();
    if (respuesta.ok) {
      throw new ErrorApi(respuesta.status, { error: "RESPUESTA_INVALIDA", mensaje: "La placa respondió algo que no es JSON." });
    }
  }
  if (!respuesta.ok) {
    throw new ErrorApi(respuesta.status, {
      error: cuerpo?.error ?? "ERROR_DE_LA_PLACA",
      mensaje: cuerpo?.mensaje ?? (typeof cuerpo?.detalle === "string" ? cuerpo.detalle : `La placa respondió ${respuesta.status}.`),
      detalle: cuerpo?.detalle && typeof cuerpo.detalle === "object" ? cuerpo.detalle : {},
    });
  }
  return cuerpo;
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

// La dirección por la que este front llegó a la API va primero: desde ese WiFi ya se sabe que responde.
function ordenar(servidores) {
  const lista = servidores.filter((s) => typeof s === "string" && s);
  return [...lista.filter((s) => s === API_BASE), ...lista.filter((s) => s !== API_BASE)];
}

// ---- el asistente ----

// opciones.raiz: el contenedor en Mis materas. alAbrirOCerrar(abierto), alCambiarLasMateras() (volver a
// pedir la lista) y alConectarAMano(datos) (el flujo viejo con config.h) los pone Mis materas.
export function crearAsistente(contexto, { raiz, alAbrirOCerrar, alCambiarLasMateras, alConectarAMano }) {
  let estado = null; // el avance, el mismo que se guarda
  let vuelta = 0; // cada paso nuevo (o cancelar) deja sin efecto las esperas del paso anterior
  let redes = []; // las redes que ve la placa: solo en memoria
  let redesEnMemoria = false;
  let redElegida = ""; // solo para mostrarla mientras la placa se conecta
  let ultimaLectura = null; // la primera lectura, para mostrarla en «Listo»
  let alLlegarMedicion = null;

  // Si la conexión en vivo trae la lectura, no hay que esperar la próxima consulta.
  contexto.tiempoReal.alRecibir((mensaje) => alLlegarMedicion?.(mensaje));

  const nueva = () => estado.modo === "nueva";

  function guardar() {
    escribirGuardado(Object.fromEntries(CAMPOS_GUARDADOS.map((campo) => [campo, estado[campo]])));
  }

  function abrir({ modo, apodo = "", especie = "", planta = null }) {
    if (estado && !["lectura", "listo"].includes(estado.paso)
      && !window.confirm("Hay una placa a medio conectar. ¿Dejarla y empezar otra vez?")) {
      return;
    }
    estado = {
      usuario: sesion.usuario()?.id ?? null,
      modo,
      paso: "preparar",
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
    // Las redes que ve la placa no se guardan: hay que volver a pedírselas.
    irA(estado.paso === "wifi" ? "unirse" : estado.paso);
  }

  function cerrar() {
    vuelta += 1;
    alLlegarMedicion = null;
    estado = null;
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
    estado.paso = paso;
    guardar();
    const mia = vuelta;
    PASOS_DEL_ASISTENTE[paso](mia);
  }

  const vigente = (mia) => mia === vuelta;

  // El marco de cada paso: título, matera, los seis pasos, el contenido y el pie.
  function pintar(paso, ...cuerpo) {
    const visible = PASO_VISIBLE[paso] ?? paso;
    const actual = paso === "listo" ? PASOS.length : PASOS.findIndex((p) => p.id === visible);
    const titulo = crear("h2", { clase: "asistente__titulo", texto: "Conectar sensor" });
    titulo.id = "asistente-titulo";
    const lista = crear("ol", { clase: "asistente__pasos" }, ...PASOS.map((p, indice) => {
      const clase = indice < actual ? " asistente__paso--hecho" : indice === actual ? " asistente__paso--actual" : "";
      const nodo = crear("li", { clase: `asistente__paso${clase}` },
        crear("span", { clase: "asistente__paso-numero", texto: String(indice + 1) }),
        crear("span", { clase: "asistente__paso-texto", texto: !nueva() && p.textoCambio ? p.textoCambio : p.texto }));
      if (indice === actual) nodo.setAttribute("aria-current", "step");
      return nodo;
    }));
    const subtitulo = cuerpo[0];
    raiz.replaceChildren(
      crear("div", { clase: "asistente__cabecera" }, titulo, crear("p", { clase: "asistente__matera", texto: descripcion() })),
      lista,
      crear("div", { clase: "asistente__cuerpo" }, ...cuerpo),
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

  // ---- 1. Preparar: mientras todavía hay API, se anotan las direcciones del servidor ----

  async function preparar(mia) {
    const estadoNodo = linea("Consultando la API…");
    const resultado = crear("div", { clase: "asistente__resultado" });
    const error = cajaError();
    const principal = boton("Buscar la placa", "boton-primario", () => irA("unirse"));
    principal.hidden = true;
    pintar("preparar",
      encabezado("Preparar"),
      parrafo("Mientras este equipo sigue en su WiFi, la app le pregunta a la API a qué dirección tendrá que mandar la placa sus lecturas. Tenga a mano el nombre y la clave de su WiFi."),
      estadoNodo, resultado, error, principal);

    let red;
    try {
      red = await obtenerRed();
    } catch (fallo) {
      if (!vigente(mia)) return;
      estadoNodo.hidden = true;
      mostrarError(error, fallo);
      reintentar(principal, () => irA("preparar"));
      return;
    }
    if (!vigente(mia)) return;
    estadoNodo.hidden = true;
    const servidores = ordenar(Array.isArray(red?.servidores) ? red.servidores : []);
    if (!servidores.length) {
      resultado.append(aviso(red?.aviso ?? "La API no dio ninguna dirección para la placa."));
      reintentar(principal, () => irA("preparar"));
      return;
    }
    estado.servidores = servidores;
    guardar();
    resultado.append(
      parrafo("La placa mandará sus lecturas a:"),
      crear("ul", { clase: "asistente__servidores" }, ...servidores.map((s) => crear("li", {}, crear("code", { texto: s })))));
    principal.hidden = false;
    principal.focus();
  }

  function reintentar(principal, accion) {
    const nuevo = boton("Volver a intentar", "boton-primario", accion);
    principal.replaceWith(nuevo);
    nuevo.focus();
  }

  // ---- 2. Unirse a la placa: el equipo entra a su red y la app la encuentra sola ----

  async function unirse(mia) {
    const estadoNodo = linea(`Buscando la placa en ${PLACA_BASE}…`);
    const ayuda = pistas("¿No aparece?", [
      "Apague los datos móviles del celular mientras tanto: con ellos encendidos, el celular puede mandar las peticiones por los datos y no llegar a la placa.",
      "El celular que comparte su internet (hotspot) no puede unirse a otra red: use el PC o el celular de otra persona.",
      "Si Chrome pregunta si esta página puede buscar dispositivos de la red local, elija Permitir.",
      "Si la pantalla no muestra el QR, desenchufe la matera y vuelva a enchufarla. Si ya tenía un WiFi guardado, mantenga el botón BOOT 5 segundos.",
    ]);
    pintar("unirse",
      encabezado("Unirse a la placa"),
      parrafo(`Enchufe la matera. En su pantalla aparece un QR: escanéelo con la cámara del celular, o en el PC conéctese a la red ${RED_DE_LA_PLACA} con la clave que muestra.`),
      parrafo("Cuando este equipo entre a esa red, la app encuentra la placa sola. Esa red no tiene internet: es normal.", "asistente__texto asistente__texto--tenue"),
      estadoNodo, ayuda);

    const inicio = Date.now();
    while (vigente(mia)) {
      const intento = Date.now();
      let info = null;
      try {
        info = await pedirPlaca("/info");
      } catch {
        // Todavía no está en la red de la placa.
      }
      if (!vigente(mia)) return;
      if (info) {
        if (typeof info.codigo === "string" && info.codigo && typeof info.huella === "string" && info.huella) {
          estado.codigo = info.codigo;
          estado.huella = info.huella;
          redes = sinRepetir(Array.isArray(info.redes) ? info.redes : []);
          redesEnMemoria = true;
          irA("wifi");
          return;
        }
        cambiarLinea(estadoNodo, "La placa respondió, pero sin su código o sin la huella de su clave. Volviendo a preguntar…");
      }
      if (Date.now() - inicio >= PISTAS_MS) ayuda.hidden = false;
      await esperar(Math.max(0, BUSCAR_PLACA_MS - (Date.now() - intento)));
    }
  }

  // ---- 3. Elegir el WiFi: la placa dice qué redes ve; la clave va directo a ella ----

  function elegirWifi(mia) {
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

    const claveId = `asistente-clave-${mia}`;
    const clave = crear("input", { clase: "formulario__campo" });
    Object.assign(clave, { id: claveId, type: "password", autocomplete: "off", spellcheck: false });
    const rotuloClave = crear("label", { clase: "formulario__etiqueta", texto: "Clave del WiFi" });
    rotuloClave.htmlFor = claveId;
    const ver = crear("input");
    ver.type = "checkbox";
    ver.addEventListener("change", () => {
      clave.type = ver.checked ? "text" : "password";
    });
    const error = cajaError();
    const enviar = crear("button", { clase: "boton-primario", texto: "Conectar la matera a este WiFi" });
    enviar.type = "submit";
    const forma = crear("form", { clase: "asistente__formulario" },
      lista,
      rotuloClave,
      clave,
      crear("label", { clase: "asistente__ver" }, ver, crear("span", { texto: "Mostrar la clave" })),
      parrafo("La clave va directo a la placa, por su red. La app no la guarda. Si la red es abierta, déjela vacía.", "formulario__ayuda"),
      error,
      enviar);
    forma.noValidate = true;
    forma.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      const elegida = lista.querySelector("input[type=radio]:checked")?.value ?? "";
      const red = elegida || otraNombre.value;
      try {
        await ocupado(enviar, () => pedirPlaca("/configurar", {
          metodo: "POST",
          datos: { red, claveRed: clave.value, servidores: estado.servidores },
          ms: CONFIGURAR_MAXIMO_MS,
        }));
      } catch (fallo) {
        if (vigente(mia)) mostrarError(error, fallo);
        return;
      }
      if (!vigente(mia)) return;
      clave.value = "";
      redElegida = red;
      irA("conectando");
    });

    const actualizar = boton("Actualizar la lista", "boton-contorno", async () => {
      try {
        const info = await ocupado(actualizar, () => pedirPlaca("/info"));
        if (!vigente(mia)) return;
        redes = sinRepetir(Array.isArray(info?.redes) ? info.redes : []);
        elegirWifi(++vuelta);
      } catch (fallo) {
        if (vigente(mia)) mostrarError(error, fallo);
      }
    });

    pintar("wifi",
      encabezado("Elegir el WiFi"),
      parrafo(redes.length
        ? `La placa ${estado.codigo} está lista. Elija el WiFi de la casa al que se va a conectar la matera.`
        : `La placa ${estado.codigo} está lista, pero no ve ninguna red. Escriba el nombre de la suya o actualice la lista.`),
      forma,
      crear("div", { clase: "asistente__fila" }, actualizar));
  }

  // ---- 3b. La placa entra al WiFi y busca el servidor ----

  async function conectando(mia) {
    const estadoNodo = linea(redElegida ? `Conectando la matera a «${redElegida}»…` : "Conectando la matera a su WiFi…");
    const detalle = parrafo("", "asistente__texto asistente__texto--tenue");
    detalle.hidden = true;
    const resultado = crear("div");
    const servidores = estado.servidores.join(" o ");
    const sinServidor = pistas("La placa no encuentra el servidor", [
      `Lo busca en ${servidores}.`,
      "Revise que el backend esté corriendo con MATERA_HOST=0.0.0.0 y que el firewall del PC deje pasar el puerto 5000.",
      "Revise que el PC esté en el mismo WiFi que eligió para la matera.",
    ]);
    const sinPlaca = pistas("La placa no responde", [
      `Si este equipo se salió de la red ${RED_DE_LA_PLACA}, vuelva a unirse: la pantalla de la matera muestra la red y su clave.`,
      "Si la pantalla volvió a mostrar un QR, la placa no pudo entrar al WiFi: escanéelo otra vez y revise el nombre y la clave.",
    ]);
    const principal = boton("Elegir el WiFi otra vez", "boton-primario", () => irA("unirse"));
    principal.hidden = true;
    pintar("conectando",
      encabezado("Elegir el WiFi"),
      parrafo("La placa entra a su WiFi y busca el servidor. Puede tardar hasta un minuto, y mientras tanto su red puede desaparecer un momento: la app vuelve a preguntar sola."),
      estadoNodo, detalle, resultado, sinServidor, sinPlaca, principal);

    let ultimaRespuesta = Date.now();
    let buscandoDesde = null;
    while (vigente(mia)) {
      const intento = Date.now();
      let respuesta = null;
      try {
        respuesta = await pedirPlaca("/estado");
      } catch {
        // Al cambiar de canal, la red de la placa se cae un momento.
      }
      if (!vigente(mia)) return;
      if (respuesta) {
        ultimaRespuesta = Date.now();
        sinPlaca.hidden = true;
        principal.hidden = true;
        const etapa = respuesta.etapa;
        cambiarLinea(estadoNodo, ETAPAS[etapa] ?? `La placa dice: ${etapa}`);
        detalle.textContent = typeof respuesta.detalle === "string" ? respuesta.detalle : "";
        detalle.hidden = !detalle.textContent;
        // Con el front en este mismo PC, el PC está en la red de la placa y no en el WiFi: la placa no lo
        // encuentra hasta que el PC vuelva. Por eso basta con que ya haya entrado al WiFi.
        const listaParaCerrar = etapa === "esperando-matera" || etapa === "conectada"
          || (etapa === "buscando-servidor" && API_EN_ESTE_EQUIPO);
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
          cambiarLinea(estadoNodo, "La placa no responde: puede ser el cambio de canal de su red. Volviendo a preguntar…");
        }
        if (callada >= CORTE_LARGO_MS) {
          sinPlaca.hidden = false;
          principal.hidden = false;
        }
      }
      await esperar(Math.max(0, ESTADO_MS - (Date.now() - intento)));
    }
  }

  // ---- 4. Volver a su red: la placa apaga la suya y el equipo vuelve solo a su WiFi ----

  async function volver(mia) {
    const estadoNodo = linea("Pidiéndole a la placa que apague su red…");
    const ayuda = pistas("¿No vuelve?", [
      "Si este equipo no vuelve solo a su WiFi, únase a él a mano desde la configuración de WiFi.",
      `Revise que el backend siga corriendo: la app lo busca en ${API_BASE}.`,
    ]);
    let introduccion = "La placa ya está en su WiFi y encontró el servidor.";
    if (estado.yaVinculada) introduccion = "La placa ya tiene su matera y quedó conectada a su WiFi.";
    else if (API_EN_ESTE_EQUIPO) {
      introduccion = "La placa ya entró a su WiFi. Para que encuentre el servidor, este PC tiene que volver a esa misma red.";
    }
    pintar("volver",
      encabezado("Volver a su red"),
      parrafo(introduccion),
      parrafo("Ahora la placa apaga su red y este equipo vuelve solo a su WiFi de siempre."),
      estadoNodo, ayuda);

    // Si la placa no contesta, puede que ya la haya apagado: se sigue igual.
    for (let intento = 0; intento < 3 && vigente(mia); intento += 1) {
      try {
        await pedirPlaca("/cerrar", { metodo: "POST" });
        break;
      } catch (fallo) {
        if (fallo.status) break; // respondió: no tiene sentido insistir
        await esperar(1000);
      }
    }
    if (!vigente(mia)) return;
    cambiarLinea(estadoNodo, `Esperando a que la API responda en ${API_BASE}…`);

    const inicio = Date.now();
    while (vigente(mia)) {
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
    const rotulo = (texto, para) => {
      const nodo = crear("label", { clase: "formulario__etiqueta", texto });
      nodo.htmlFor = para;
      return nodo;
    };
    const nodo = crear("div", { clase: "formulario__fila" },
      crear("div", { clase: "formulario__grupo" }, rotulo("Apodo de la planta", apodo.id), apodo),
      crear("div", { clase: "formulario__grupo" }, rotulo("Especie", especie.id), especie));
    return { nodo, apodo, especie };
  }

  async function crearMatera(mia) {
    // Si la página se recargó (o se cortó la red) justo después de enviarla, la matera ya puede existir:
    // no se crea dos veces.
    if (estado.enviado) {
      const creada = (await obtenerPlantas()).find((p) => p.sensor?.codigo === estado.codigo);
      if (!vigente(mia)) return;
      if (creada) {
        estado.plantaId = creada.id;
        estado.plantaApodo = creada.apodo;
        alCambiarLasMateras();
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
    alCambiarLasMateras(); // aunque se haya cancelado mientras tanto, la matera ya existe
    if (!vigente(mia)) return;
    estado.plantaId = planta.id;
    estado.plantaApodo = planta.apodo;
    irA("lectura");
  }

  async function cambiarElSensor(mia) {
    // La primera lectura es la primera de esta placa que llegue después de la última que había.
    const antes = (await obtenerPlantas()).find((p) => p.id === estado.plantaId);
    if (!vigente(mia)) return;
    estado.momentoAntes = antes?.ultimaMedicion?.momento ?? null;
    estado.enviado = true;
    guardar();
    const { planta } = await cambiarSensor(estado.plantaId, estado.codigo, estado.huella);
    alCambiarLasMateras();
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
      alCambiarLasMateras();
      irA("listo");
    };
    alLlegarMedicion = (mensaje) => {
      if (mensaje.tipo === "medicion" && mensaje.planta?.id === estado.plantaId && esLaPrimera(mensaje.medicion)) {
        terminar(mensaje.medicion);
      }
    };

    const inicio = Date.now();
    while (vigente(mia)) {
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
    // Mientras el equipo puede estar en la red de la placa, Mis materas no consulta la API (no la alcanza).
    sinApi: () => Boolean(estado) && !API_EN_ESTE_EQUIPO && PASOS_EN_LA_PLACA.has(estado.paso),
  };
}
