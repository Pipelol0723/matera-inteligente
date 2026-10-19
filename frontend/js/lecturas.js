// Piezas que comparten Mis materas y el historial: el texto de unas lecturas y la especie de una planta.
// Los parámetros salen de GET /parametros; ninguno se escribe aquí.
import { numero, unidad } from "./formato.js";

// "18 % · 800 lux · 22 °C", en el orden de GET /parametros.
export function textoLecturas(lecturas, parametros) {
  const orden = parametros.map((p) => p.nombre);
  return [...lecturas]
    .sort((a, b) => orden.indexOf(a.nombre) - orden.indexOf(b.nombre))
    .map((lectura) => `${numero.format(lectura.valor)} ${unidad(lectura.unidad)}`)
    .join(" · ");
}

export const especieDe = (contexto, nombre) => contexto.especies.find((especie) => especie.nombre === nombre);

// Las mediciones escritas a mano antes de que solo midiera el sensor conservan el origen MANUAL.
export const textoOrigen = (origen) => (origen === "MANUAL" ? "a mano" : origen);
