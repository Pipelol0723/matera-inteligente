// Formato, paleta y ayudas para crear nodos. Solo presentación: aquí no se decide ningún estado.

export const numero = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });

export const capitalizar = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1);

// La inicial de un nombre, para los avatares redondos de Mi cuenta y Administración.
export const inicialDe = (nombre) => (Array.from((nombre ?? "").trim())[0] ?? "?").toUpperCase();

// Puntos del juego, como los manda la API: «1.250», «−40» (con el signo menos tipográfico).
const ENTERO = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 0 });
export const puntos = (valor) => (valor < 0 ? `−${ENTERO.format(-valor)}` : ENTERO.format(valor));
// Con signo también los positivos: «+10», «−5», «0».
export const puntosConSigno = (valor) => (valor > 0 ? `+${ENTERO.format(valor)}` : puntos(valor));
// Para colorear: «mas», «menos» o «cero».
export const signoDe = (valor) => (valor > 0 ? "mas" : valor < 0 ? "menos" : "cero");

const ETIQUETAS = { humedad: "Humedad", luz: "Luz", temperatura: "Temperatura" };
export const etiqueta = (nombre) => ETIQUETAS[nombre] ?? capitalizar(nombre);

export const unidad = (simbolo) => (simbolo === "C" ? "°C" : simbolo);

// Color de línea y de banda según la posición del parámetro; uno nuevo toma el siguiente. Son variables CSS
// (css/variables.css): cada tema tiene los suyos.
const TONOS = [1, 2, 3, 4].map((n) => ({ linea: `var(--serie-${n})`, banda: `var(--serie-${n}-banda)` }));
export const tono = (indice) => TONOS[indice % TONOS.length];

// Colores para los estados que devuelve la API, también variables CSS del tema.
const VERDE = { texto: "var(--saludable)", fondo: "var(--saludable-fondo)" };
const AMBAR = { texto: "var(--riesgo)", fondo: "var(--riesgo-fondo)" };
const ROJO = { texto: "var(--critico)", fondo: "var(--critico-fondo)" };
const SIN_ESTADO = { texto: "var(--sin-estado)", fondo: "var(--sin-estado-fondo)" };
const COLORES = Object.assign(Object.create(null), { SALUDABLE: VERDE, OPTIMO: VERDE, EN_RIESGO: AMBAR, BAJO: AMBAR, ALTO: AMBAR, CRITICO: ROJO });
export const colorDeEstado = (estado) => COLORES[estado] ?? SIN_ESTADO;

const NOMBRES_DE_ESTADO = Object.assign(Object.create(null), { SALUDABLE: "Saludable", EN_RIESGO: "En riesgo", CRITICO: "Crítico" });
export const nombreDeEstado = (estado) => NOMBRES_DE_ESTADO[estado] ?? capitalizar(estado.toLowerCase());
// Una sola tabla de rótulos para pastillas, juego y avisos.
const ROTULOS_DE_ESTADO = Object.assign(Object.create(null), { SALUDABLE: "SALUDABLE", EN_RIESGO: "EN RIESGO", CRITICO: "CRÍTICO" });
export const rotuloDeEstado = (estado) => ROTULOS_DE_ESTADO[estado] ?? String(estado).replace("_", " ");

export function textoDetalle(detalle) {
  const pares = Object.entries(detalle ?? {}).map(([clave, valor]) => `"${clave}": ${JSON.stringify(valor)}`);
  return pares.length ? `{ ${pares.join(", ")} }` : "{}";
}

export function crear(tipo, { clase, texto, estilo } = {}, ...hijos) {
  const nodo = document.createElement(tipo);
  if (clase) nodo.className = clase;
  if (texto !== undefined) nodo.textContent = texto;
  if (estilo) Object.assign(nodo.style, estilo);
  nodo.append(...hijos);
  return nodo;
}

export function crearSvg(tipo, atributos = {}) {
  const nodo = document.createElementNS("http://www.w3.org/2000/svg", tipo);
  for (const [nombre, valor] of Object.entries(atributos)) nodo.setAttribute(nombre, valor);
  return nodo;
}

export function pastillaEstado(estado) {
  const colores = colorDeEstado(estado);
  return crear("span", {
    clase: "pastilla",
    texto: estado ? rotuloDeEstado(estado) : "SIN DATOS",
    estilo: { color: colores.texto, background: colores.fondo },
  });
}
