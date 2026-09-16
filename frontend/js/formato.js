// Formato, paleta y ayudas para crear nodos. Solo presentación: aquí no se decide ningún estado.

export const numero = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });

export const capitalizar = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1);

const ETIQUETAS = { humedad: "Humedad", luz: "Luz", temperatura: "Temperatura" };
export const etiqueta = (nombre) => ETIQUETAS[nombre] ?? capitalizar(nombre);

export const unidad = (simbolo) => (simbolo === "C" ? "°C" : simbolo);

// Color de línea y de banda según la posición del parámetro; uno nuevo toma el siguiente.
const TONOS = [
  { linea: "#2f6f8f", banda: "#dce9f0" },
  { linea: "#b58a1b", banda: "#f3e8cb" },
  { linea: "#b4543f", banda: "#f2ddd7" },
  { linea: "#6a5a8c", banda: "#e5e0ee" },
];
export const tono = (indice) => TONOS[indice % TONOS.length];

// Colores para los estados que devuelve la API.
const VERDE = { texto: "#2b7a4b", fondo: "#e1f0e6" };
const AMBAR = { texto: "#87570a", fondo: "#f6ead1" };
const ROJO = { texto: "#ae3636", fondo: "#f6e0de" };
const SIN_ESTADO = { texto: "#5a6a5f", fondo: "#eef2ec" };
const COLORES = { SALUDABLE: VERDE, OPTIMO: VERDE, EN_RIESGO: AMBAR, BAJO: AMBAR, ALTO: AMBAR, CRITICO: ROJO };
export const colorDeEstado = (estado) => COLORES[estado] ?? SIN_ESTADO;

const NOMBRES_DE_ESTADO = { SALUDABLE: "Saludable", EN_RIESGO: "En riesgo", CRITICO: "Crítico" };
export const nombreDeEstado = (estado) => NOMBRES_DE_ESTADO[estado] ?? capitalizar(estado.toLowerCase());
export const rotuloDeEstado = (estado) => estado.replace("_", " ");

export function textoDetalle(detalle) {
  const pares = Object.entries(detalle ?? {}).map(([clave, valor]) => `"${clave}": ${JSON.stringify(valor)}`);
  return pares.length ? `{ ${pares.join(", ")} }` : "{}";
}

// Valores de ejemplo legibles: enteros para cifras grandes, un decimal para el resto.
export const redondear = (valor) => (Math.abs(valor) >= 1000 ? Math.round(valor) : Math.round(valor * 10) / 10);

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
