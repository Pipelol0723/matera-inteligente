// Piezas que comparten Mis materas, el simulador y el historial: los campos de una medición
// y el texto de unas lecturas. Los parámetros salen de GET /parametros; ninguno se escribe aquí.
import { crear, etiqueta, numero, unidad } from "./formato.js";

const medio = (rango) => Math.round((rango.min + rango.max) / 2);

// Un campo por parámetro. leer() devuelve lo escrito tal cual: la API es la que valida.
export function crearCamposMedicion(parametros, prefijo) {
  const entradas = new Map();
  const filas = parametros.map((parametro) => {
    const entrada = crear("input", { clase: "campo__entrada" });
    Object.assign(entrada, { id: `${prefijo}-${parametro.nombre}`, inputMode: "decimal", autocomplete: "off" });
    entradas.set(parametro.nombre, entrada);
    const rotulo = crear("label", { clase: "medicion__etiqueta", texto: `${etiqueta(parametro.nombre)} (${unidad(parametro.unidad)})` });
    rotulo.htmlFor = entrada.id;
    return crear("div", { clase: "medicion__campo" }, rotulo, entrada);
  });

  return {
    nodo: crear("div", { clase: "medicion" }, ...filas),
    leer() {
      return Object.fromEntries([...entradas].map(([nombre, entrada]) => {
        const texto = entrada.value.trim();
        return [nombre, texto === "" ? null : texto];
      }));
    },
    // Valores de partida: la mitad del rango óptimo de la especie, como en Diagnóstico.
    proponer(especie) {
      for (const [nombre, entrada] of entradas) {
        const rango = especie?.rangos[nombre];
        if (rango && entrada.value.trim() === "") entrada.value = String(medio(rango));
      }
    },
  };
}

// "18 % · 800 lux · 22 °C", en el orden de GET /parametros.
export function textoLecturas(lecturas, parametros) {
  const orden = parametros.map((p) => p.nombre);
  return [...lecturas]
    .sort((a, b) => orden.indexOf(a.nombre) - orden.indexOf(b.nombre))
    .map((lectura) => `${numero.format(lectura.valor)} ${unidad(lectura.unidad)}`)
    .join(" · ");
}

export const especieDe = (contexto, nombre) => contexto.especies.find((especie) => especie.nombre === nombre);
