// Catálogo de especies: todo sale de GET /especies y GET /parametros.
import { porcentaje } from "./escala.js";
import { capitalizar, crear, etiqueta, numero, tono, unidad } from "./formato.js";

// Ancho mínimo de la banda, para que un rango angosto siga siendo visible.
const ANCHO_MINIMO = 0.03;

export function crearPantallaEspecies(contexto) {
  const $ = (id) => document.getElementById(id);

  function pintar() {
    const cantidad = contexto.especies.length;
    $("especies-bajada").textContent =
      `${cantidad} ${cantidad === 1 ? "especie soportada" : "especies soportadas"} por la tabla de referencia. ` +
      "Las bandas muestran el rango óptimo de cada parámetro.";
    $("catalogo").replaceChildren(...contexto.especies.map(tarjeta));
  }

  function tarjeta(especie) {
    const boton = crear("button", { clase: "boton-contorno", texto: "Diagnosticar" });
    boton.type = "button";
    boton.addEventListener("click", () => contexto.diagnosticarEspecie(especie.nombre));

    const barras = contexto.parametros.map((parametro, indice) => {
      const rango = especie.rangos[parametro.nombre];
      // Escala completa: de un límite físico al otro.
      const total = parametro.maximoFisico - parametro.minimoFisico;
      const izquierda = (rango.min - parametro.minimoFisico) / total;
      const ancho = Math.max(ANCHO_MINIMO, (rango.max - rango.min) / total);
      return crear("div", {},
        crear("div", { clase: "barra__cabecera" },
          crear("span", { clase: "barra__etiqueta", texto: etiqueta(parametro.nombre) }),
          crear("span", {
            clase: "barra__texto",
            texto: `${numero.format(rango.min)}–${numero.format(rango.max)} ${unidad(rango.unidad)}`,
          })),
        crear("div", { clase: "barra__pista" },
          crear("div", {
            clase: "barra__banda",
            estilo: { left: porcentaje(izquierda), width: porcentaje(ancho), background: tono(indice).linea },
          })));
    });

    return crear("article", { clase: "tarjeta" },
      crear("div", { clase: "especie__cabecera" },
        crear("h2", { clase: "especie__nombre", texto: capitalizar(especie.nombre) }),
        boton),
      crear("p", { clase: "especie__cientifico", texto: especie.nombreCientifico }),
      crear("div", { clase: "barras" }, ...barras));
  }

  return { pintar };
}
