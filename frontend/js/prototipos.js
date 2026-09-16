// Maquetas de pantallas que NO entran en este corte: histórico de mediciones, varias materas
// por usuario y vinculación del sensor. Las lecturas son datos de ejemplo, pero los estados
// no se inventan: se le piden a la API real con esas lecturas.
import { pedirDiagnostico } from "./api.js";
import { dominioVisual, fraccion, porcentaje } from "./escala.js";
import { capitalizar, colorDeEstado, crear, crearSvg, etiqueta, numero, pastillaEstado, tono, unidad } from "./formato.js";

const HISTORIAL = {
  especie: "sansevieria",
  lecturas: [
    { fecha: "16 sep", valores: { humedad: 18, luz: 800, temperatura: 22 } },
    { fecha: "15 sep", valores: { humedad: 24, luz: 910, temperatura: 23 } },
    { fecha: "14 sep", valores: { humedad: 31, luz: 870, temperatura: 24 } },
    { fecha: "13 sep", valores: { humedad: 38, luz: 640, temperatura: 22 } },
    { fecha: "12 sep", valores: { humedad: 17, luz: 520, temperatura: 19 } },
    { fecha: "11 sep", valores: { humedad: 22, luz: 780, temperatura: 21 } },
  ],
};

// Catorce días de ejemplo para la gráfica, cada serie con su propia escala.
const SERIES = [
  { nombre: "humedad", escala: [0, 60], relleno: "rgba(47, 111, 143, 0.10)",
    valores: [30, 27, 22, 19, 34, 31, 28, 24, 18, 22, 31, 38, 24, 18] },
  { nombre: "luz", escala: [0, 1600], relleno: "rgba(181, 138, 27, 0.08)",
    valores: [980, 860, 1120, 640, 520, 900, 1010, 870, 800, 780, 640, 870, 910, 800] },
  { nombre: "temperatura", escala: [10, 35], relleno: "rgba(180, 84, 63, 0.08)",
    valores: [23, 22, 24, 21, 19, 21, 23, 24, 22, 21, 22, 24, 23, 22] },
];

const MATERAS = [
  { lugar: "Estudio", especie: "sansevieria", valores: { humedad: 18, luz: 800, temperatura: 22 },
    nota: "Sustrato seco desde ayer; riegue poco." },
  { lugar: "Sala", especie: "potos", valores: { humedad: 55, luz: 900, temperatura: 22 },
    nota: "Todo en rango. Próxima revisión en 3 días." },
  { lugar: "Balcón", especie: "lavanda", valores: { humedad: 12, luz: 128000, temperatura: 31 },
    nota: "Sol directo y sustrato seco: mueva a media sombra." },
  { lugar: "Cocina", especie: "helecho", valores: { humedad: 72, luz: 2400, temperatura: 20 },
    nota: "Húmedo y templado, como le gusta." },
];

const ANCHO_GRAFICA = 640;
const BASE_GRAFICA = 190;
const ALTO_UTIL = 170;

async function diagnosticarEjemplo(especie, valores) {
  try {
    return await pedirDiagnostico({ especie, ...valores });
  } catch {
    return null;
  }
}

export function crearPrototipos(contexto) {
  const $ = (id) => document.getElementById(id);
  let seleccion = null;

  $("vincular-matera").addEventListener("click", () => contexto.navegar("vincular"));
  $("vincular-buscar").addEventListener("click", () => contexto.navegar("materas"));
  $("vincular-despues").addEventListener("click", () => contexto.navegar("diagnostico"));
  pintarGrafica();

  function alCargarCatalogos() {
    pintarHistorial();
    pintarMateras();
    pintarChips();
  }

  // ---- historial ----

  function pintarGrafica() {
    $("leyenda").replaceChildren(...SERIES.map((serie, indice) =>
      crear("div", { clase: "leyenda__item" },
        crear("span", { clase: "leyenda__linea", estilo: { background: tono(indice).linea } }),
        etiqueta(serie.nombre))));

    const fondo = [
      crearSvg("rect", { x: 0, y: 0, width: ANCHO_GRAFICA, height: 200, fill: "#fbfdfa" }),
      ...[50, 100, 150].map((y) =>
        crearSvg("line", { x1: 0, y1: y, x2: ANCHO_GRAFICA, y2: y, stroke: "#eaf0e8", "stroke-width": 1 })),
    ];
    const trazos = SERIES.flatMap((serie, indice) => {
      const puntos = serie.valores.map((valor, i) => {
        const x = (i / (serie.valores.length - 1)) * ANCHO_GRAFICA;
        const y = BASE_GRAFICA - fraccion(valor, serie.escala) * ALTO_UTIL;
        return `${x.toFixed(1)},${y.toFixed(1)}`;
      }).join(" ");
      return [
        crearSvg("polygon", { points: `0,${BASE_GRAFICA} ${puntos} ${ANCHO_GRAFICA},${BASE_GRAFICA}`, fill: serie.relleno }),
        crearSvg("polyline", {
          points: puntos, fill: "none", stroke: tono(indice).linea,
          "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-linecap": "round",
        }),
      ];
    });
    $("grafica").replaceChildren(...fondo, ...trazos);
  }

  function textoLectura(valores) {
    return contexto.parametros
      .filter((p) => p.nombre in valores)
      .map((p) => `${numero.format(valores[p.nombre])} ${unidad(p.unidad)}`)
      .join(" · ");
  }

  function pintarHistorial() {
    const filas = HISTORIAL.lecturas.map(({ fecha, valores }) => {
      const pastilla = crear("span", { clase: "pastilla", texto: "…" });
      diagnosticarEjemplo(HISTORIAL.especie, valores)
        .then((resultado) => pastilla.replaceWith(pastillaEstado(resultado?.estado)));
      return crear("div", { clase: "registro" },
        crear("span", { clase: "registro__fecha", texto: fecha }),
        crear("span", { clase: "registro__lectura", texto: textoLectura(valores) }),
        pastilla);
    });
    $("registros").replaceChildren(...filas);
  }

  // ---- materas ----

  async function pintarMateras() {
    const resultados = await Promise.all(MATERAS.map((m) => diagnosticarEjemplo(m.especie, m.valores)));
    $("materas").replaceChildren(...MATERAS.map((matera, i) => tarjetaMatera(matera, resultados[i])));

    const cantidad = `${MATERAS.length} materas de ejemplo`;
    if (resultados.includes(null)) {
      $("materas-bajada").textContent = `${cantidad} · sin respuesta de la API`;
      return;
    }
    const conAtencion = resultados.filter((r) => r.estado !== "SALUDABLE").length;
    $("materas-bajada").textContent =
      `${cantidad} · ${conAtencion} ${conAtencion === 1 ? "necesita" : "necesitan"} atención hoy`;
  }

  function tarjetaMatera(matera, resultado) {
    const colores = colorDeEstado(resultado?.estado);
    const especie = contexto.especies.find((e) => e.nombre === matera.especie);

    const barras = contexto.parametros
      .filter((parametro) => parametro.nombre in matera.valores)
      .map((parametro) => {
        const indice = contexto.parametros.indexOf(parametro);
        const valor = matera.valores[parametro.nombre];
        const rango = especie?.rangos[parametro.nombre];
        const pista = crear("div", { clase: "matera__pista" });
        if (rango) {
          const dominio = dominioVisual(rango, parametro);
          const desde = fraccion(rango.min, dominio);
          pista.append(
            crear("div", {
              clase: "matera__banda",
              estilo: { left: porcentaje(desde), width: porcentaje(fraccion(rango.max, dominio) - desde) },
            }),
            crear("div", {
              clase: "matera__marca",
              estilo: { left: porcentaje(fraccion(valor, dominio)), background: tono(indice).linea },
            }));
        }
        return crear("div", { clase: "matera__barra" },
          crear("span", { clase: "matera__etiqueta", texto: etiqueta(parametro.nombre) }),
          pista,
          crear("span", { clase: "matera__valor", texto: `${numero.format(valor)} ${unidad(parametro.unidad)}` }));
      });

    const tarjeta = crear("article", { clase: "tarjeta matera" },
      crear("div", { clase: "matera__cabecera" },
        crear("div", { clase: "matera__icono", estilo: { background: colores.fondo } },
          crear("div", { clase: "matera__punto", estilo: { background: colores.texto } })),
        crear("div", { clase: "matera__nombres" },
          crear("p", { clase: "matera__lugar", texto: matera.lugar }),
          crear("p", { clase: "matera__especie", texto: capitalizar(matera.especie) }))),
      pastillaEstado(resultado?.estado),
      crear("div", { clase: "matera__barras" }, ...barras),
      crear("p", { clase: "matera__nota", texto: matera.nota }));
    if (resultado?.estado === "CRITICO") tarjeta.classList.add("matera--critica");
    return tarjeta;
  }

  // ---- vincular sensor ----

  function pintarChips() {
    seleccion ??= (contexto.especies.find((e) => e.nombre === "sansevieria") ?? contexto.especies[0])?.nombre;
    $("chips").replaceChildren(...contexto.especies.map((especie) => {
      const activa = especie.nombre === seleccion;
      const chip = crear("button", { clase: `chip${activa ? " chip--activo" : ""}`, texto: capitalizar(especie.nombre) });
      chip.type = "button";
      chip.setAttribute("aria-pressed", String(activa));
      chip.addEventListener("click", () => {
        seleccion = especie.nombre;
        pintarChips();
      });
      return chip;
    }));
  }

  return { alCargarCatalogos };
}
