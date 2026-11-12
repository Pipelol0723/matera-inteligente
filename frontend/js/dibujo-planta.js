// La matera Tamagotchi en SVG. Cada capa llega tal cual de GET /juego/materas, que la calcula el dominio:
// la etapa da el tamaño, la condición el color y la postura de las hojas, la última lectura la cara (o la
// cara dormida) y la necesidad el globo. Aquí solo se hace corresponder cada valor con su dibujo y su texto.
// Los colores salen de variables CSS (estilos.css). El SVG se arma con piezas fijas y números: ningún texto
// que mande la API entra al marcado sin pasar por las tablas de abajo.

const ETAPAS = {
  SEMILLA: { clave: "semilla", tamano: [9, 7], nombre: "Semilla", genero: "f" },
  BROTE: { clave: "brote", tamano: [13, 12], nombre: "Brote", genero: "m" },
  PLANTA: { clave: "planta", tamano: [18, 17], nombre: "Planta joven", genero: "f" },
  FLORECIDA: { clave: "florecida", tamano: [21, 20], nombre: "Planta florecida", genero: "f" },
};

const CONDICIONES = {
  SANA: { clave: "sana", color: "var(--hoja-sana)", f: "sana", m: "sano" },
  DECAIDA: { clave: "decaida", color: "var(--hoja-riesgo)", f: "decaída", m: "decaído" },
  MARCHITA: { clave: "marchita", color: "var(--hoja-mal)", f: "marchita", m: "marchito" },
};

// La cara sale del estado de la última lectura; si la API dice que duerme, la cara es la dormida.
const CARAS = {
  SALUDABLE: { clave: "feliz", f: "feliz", m: "feliz" },
  EN_RIESGO: { clave: "preocupada", f: "preocupada", m: "preocupado" },
  CRITICO: { clave: "triste", f: "triste", m: "triste" },
};
const DORMIDA = { clave: "dormida", f: "dormida", m: "dormido" };
// Solo para un valor que este front todavía no conozca: no inventa un ánimo.
const SIN_CARA = { clave: "neutra", f: "sin ánimo", m: "sin ánimo" };

const NECESIDADES = {
  SED: { globo: "¡tengo sed!", texto: "tiene sed" },
  EXCESO_AGUA: { globo: "¡me ahogo!", texto: "tiene demasiada agua" },
  FRIO: { globo: "¡tengo frío!", texto: "tiene frío" },
  CALOR: { globo: "¡tengo calor!", texto: "tiene calor" },
  POCA_LUZ: { globo: "¡poca luz!", texto: "le falta luz" },
  MUCHA_LUZ: { globo: "¡mucha luz!", texto: "le sobra luz" },
};

// Trazos de cada cara, centrados en 0,0 para una planta de tamaño completo; se escalan con la planta.
const TRAZOS = {
  feliz: '<path d="M-10 -1 q3.5 -4.5 7 0 M3 -1 q3.5 -4.5 7 0"/><path d="M-8 6 q8 8 16 0"/>' +
    '<circle cx="-13" cy="6" r="3" fill="var(--mejilla)" stroke="none"/><circle cx="13" cy="6" r="3" fill="var(--mejilla)" stroke="none"/>',
  preocupada: '<circle cx="-6.5" cy="-1" r="2" fill="var(--cara)" stroke="none"/><circle cx="6.5" cy="-1" r="2" fill="var(--cara)" stroke="none"/>' +
    '<path d="M-8 8 q4 -3 8 0 q4 3 8 0"/><path d="M15 -9 q2.5 4 0 6 q-2.5 -2 0 -6 z" fill="var(--gota)" stroke="none"/>',
  triste: '<path d="M-10 -3 l6 -2.5 M4 -5.5 l6 2.5"/><circle cx="-6.5" cy="1" r="1.8" fill="var(--cara)" stroke="none"/>' +
    '<circle cx="6.5" cy="1" r="1.8" fill="var(--cara)" stroke="none"/><path d="M-7 10 q7 -6 14 0"/>',
  dormida: '<path d="M-10 0 q3.5 3 7 0 M3 0 q3.5 3 7 0"/><circle cx="0" cy="8" r="2"/>',
  neutra: '<circle cx="-6.5" cy="-1" r="2" fill="var(--cara)" stroke="none"/><circle cx="6.5" cy="-1" r="2" fill="var(--cara)" stroke="none"/>' +
    '<path d="M-6 7 h12"/>',
};

// Lo que dice cada capa, ya en palabras. Un valor desconocido no rompe el dibujo: cae en uno neutro.
function partes(matera) {
  const etapa = ETAPAS[matera.etapa] ?? ETAPAS.PLANTA;
  const condicion = CONDICIONES[matera.condicion] ?? CONDICIONES.SANA;
  const cara = matera.dormida ? DORMIDA : CARAS[matera.cara] ?? SIN_CARA;
  const necesidad = NECESIDADES[matera.necesidad] ?? null;
  return { etapa, condicion, cara, necesidad };
}

// Los rótulos para mostrar junto al dibujo: «Planta joven», «decaída», «preocupada», «tiene sed».
export function rotulosDeMatera(matera) {
  const { etapa, condicion, cara, necesidad } = partes(matera);
  return {
    etapa: etapa.nombre,
    condicion: condicion[etapa.genero],
    cara: cara[etapa.genero],
    necesidad: necesidad?.texto ?? null,
    globo: necesidad?.globo ?? null,
  };
}

// «Planta joven, decaída, preocupada: tiene sed».
export function descripcionDeMatera(matera) {
  const r = rotulosDeMatera(matera);
  const base = `${r.etapa}, ${r.condicion}, ${r.cara}`;
  return r.necesidad ? `${base}: ${r.necesidad}` : base;
}

// El globo de una necesidad («¡tengo sed!»), o null.
export const globoDe = (necesidad) => NECESIDADES[necesidad]?.globo ?? null;

// El lienzo: la planta va centrada en x = 50, sobre la maceta. Los dibujos grandes dejan arriba lugar para el
// globo, haya o no globo, así todas las materas quedan a la misma altura.
const LIENZO = "-10 0 120 112";
const LIENZO_CON_GLOBO = "-10 -24 120 136";

// La matera dibujada, dentro de un <div class="planta">. Con sinGlobo (los dibujos pequeños), la necesidad
// solo queda en la descripción accesible.
export function dibujoDeMatera(matera, { sinGlobo = false, clase = "" } = {}) {
  const { etapa, condicion, cara, necesidad } = partes(matera);
  const globo = sinGlobo ? null : necesidad?.globo ?? null;
  const caja = document.createElement("div");
  caja.className = `planta planta--${condicion.clave} planta--${cara.clave}${clase ? ` ${clase}` : ""}`;
  caja.innerHTML = svgPlanta(etapa, condicion, cara.clave, globo, descripcionDeMatera(matera), sinGlobo ? LIENZO : LIENZO_CON_GLOBO);
  return caja;
}

// Una maceta sin planta, mientras llega la respuesta del juego.
export function macetaVacia({ sinGlobo = false, clase = "" } = {}) {
  const caja = document.createElement("div");
  caja.className = `planta planta--vacia${clase ? ` ${clase}` : ""}`;
  caja.innerHTML = `<svg viewBox="${sinGlobo ? LIENZO : LIENZO_CON_GLOBO}" aria-hidden="true">${MACETA}</svg>`;
  return caja;
}

const MACETA =
  '<rect x="25" y="70" width="50" height="9" rx="2" fill="var(--maceta)" stroke="var(--maceta-borde)" stroke-width="1.2"/>' +
  '<path d="M29 79 L71 79 L66 106 L34 106 Z" fill="var(--maceta)" stroke="var(--maceta-borde)" stroke-width="1.2"/>';

const fijo = (n) => n.toFixed(1);

// Escapa el texto de la descripción para un atributo (sale de las tablas de arriba, pero por si acaso).
const atributo = (texto) => texto.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

function hoja(x, y, rx, ry, angulo, color) {
  return `<ellipse cx="${fijo(x)}" cy="${fijo(y)}" rx="${fijo(rx)}" ry="${fijo(ry)}" ` +
    `transform="rotate(${angulo} ${fijo(x)} ${fijo(y)})" fill="${color}" stroke="var(--cara)" stroke-width="1.1"/>`;
}

// El dibujo paramétrico del plan del corte 3, con el globo encima de la planta para que se lea también en
// una tarjeta angosta.
function svgPlanta(etapa, condicion, cara, globo, descripcion, lienzo) {
  const [rx, alto] = etapa.tamano;
  const color = condicion.color;
  const ry = condicion.clave === "marchita" ? alto * 0.84 : alto;
  const cx = 50;
  const cy = 72 - ry;
  const s = rx / 21;
  const arriba = cy - ry;
  const lrx = 6.5 * s;
  const lry = 13 * s;

  let hojas;
  if (etapa.clave === "semilla") {
    hojas = hoja(cx + 2, arriba - 3.5, 2.6, 5, 25, color);
  } else if (condicion.clave === "sana") {
    hojas = hoja(cx - 10 * s, arriba - 6 * s, lrx, lry, -28, color) + hoja(cx + 10 * s, arriba - 6 * s, lrx, lry, 28, color);
  } else if (condicion.clave === "decaida") {
    hojas = hoja(cx - rx - 2 * s, cy - ry * 0.55, lrx, lry, -72, color) + hoja(cx + rx + 2 * s, cy - ry * 0.55, lrx, lry, 72, color);
  } else {
    hojas = hoja(cx - rx - 1 * s, cy + 1 * s, lrx, lry, -155, color) + hoja(cx + rx + 1 * s, cy + 1 * s, lrx, lry, 155, color);
  }

  let flor = "";
  if (etapa.clave === "florecida" && condicion.clave !== "marchita") {
    const fy = arriba - 13 * s;
    const pr = 3.4 * s;
    const pd = 4 * s;
    flor = `<path d="M${cx} ${fijo(arriba + 1)} L${cx} ${fijo(fy)}" stroke="var(--cara)" stroke-width="1.1"/>`;
    for (let i = 0; i < 5; i += 1) {
      const angulo = ((i * 72 - 90) * Math.PI) / 180;
      flor += `<circle cx="${fijo(cx + pd * Math.cos(angulo))}" cy="${fijo(fy + pd * Math.sin(angulo))}" r="${fijo(pr)}" ` +
        'fill="var(--petalo)" stroke="var(--cara)" stroke-width="0.8"/>';
    }
    flor += `<circle cx="${cx}" cy="${fijo(fy)}" r="${fijo(2.4 * s)}" fill="var(--centro-flor)" stroke="var(--cara)" stroke-width="0.8"/>`;
  }

  let extra = "";
  if (cara === "dormida") {
    extra += `<text class="planta__z" x="${fijo(cx + rx + 3)}" y="${fijo(arriba + 4)}" font-size="9">z</text>` +
      `<text class="planta__z planta__z--segunda" x="${fijo(cx + rx + 9)}" y="${fijo(arriba - 3)}" font-size="7">z</text>`;
  }
  if (globo) {
    // El ancho del globo sigue al texto; textLength lo ajusta para que nunca se salga del borde.
    const ancho = Math.round(globo.length * 5.3 + 14);
    const x = 109 - ancho;
    extra += '<g class="planta__globo">' +
      `<rect x="${x}" y="-23" width="${ancho}" height="19" rx="5" fill="var(--superficie)" stroke="var(--borde-acento)" stroke-width="1.1"/>` +
      `<path d="M${x + 9} -4 L${x + 3} 4 L${x + 17} -4 Z" fill="var(--superficie)" stroke="var(--borde-acento)" stroke-width="1.1" stroke-linejoin="round"/>` +
      `<path d="M${x + 8.4} -4.6 L${x + 17.6} -4.6" stroke="var(--superficie)" stroke-width="1.8"/>` +
      `<text x="${fijo(x + ancho / 2)}" y="-10" text-anchor="middle" font-size="10.5" font-weight="700" fill="var(--tinta)" ` +
      `textLength="${ancho - 12}" lengthAdjust="spacingAndGlyphs">${globo}</text></g>`;
  }

  return `<svg viewBox="${lienzo}" role="img" aria-label="${atributo(descripcion)}">` +
    `<g class="planta__cuerpo">${flor}${hojas}` +
    `<ellipse cx="${cx}" cy="${fijo(cy)}" rx="${rx}" ry="${fijo(ry)}" fill="${color}" stroke="var(--cara)" stroke-width="1.3"/>` +
    `<g transform="translate(${cx} ${fijo(cy + s)}) scale(${s.toFixed(3)})" fill="none" stroke="var(--cara)" stroke-width="1.8" stroke-linecap="round">${TRAZOS[cara]}</g>` +
    `</g>${MACETA}${extra}</svg>`;
}
