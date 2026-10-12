// Historial de una planta: la lista y la gráfica con los registros de GET /plantas/{id}/historial.
// Cada registro trae el estado que la API calculó en ese momento; aquí no se recalcula nada.
import { obtenerHistorial, obtenerPlantas } from "./api.js";
import { dominioVisual, fraccion } from "./escala.js";
import { capitalizar, crear, crearSvg, etiqueta, nombreDeEstado, pastillaEstado, tono } from "./formato.js";
import { fechaCorta, mostrarError } from "./formularios.js";
import { especieDe, textoLecturas } from "./lecturas.js";

const LIMITE = 30;
const ANCHO = 640;
const BASE = 190;
const ALTO_UTIL = 170;
const ESTADOS = ["SALUDABLE", "EN_RIESGO", "CRITICO"];

export function crearPantallaHistorial(contexto) {
  const $ = (id) => document.getElementById(id);
  const selector = $("historial-planta");
  let plantas = [];

  selector.addEventListener("change", () => {
    contexto.plantaElegida = Number(selector.value);
    cargarHistorial();
  });

  async function mostrar() {
    mostrarError($("error-historial"), null);
    try {
      plantas = await obtenerPlantas();
    } catch (error) {
      mostrarError($("error-historial"), error);
      return;
    }
    selector.replaceChildren(...plantas.map((p) => new Option(`${p.apodo} · ${capitalizar(p.especie)}`, p.id)));
    if (plantas.some((p) => p.id === contexto.plantaElegida)) selector.value = String(contexto.plantaElegida);
    if (plantas.length) {
      cargarHistorial();
    } else {
      pintar(null, []);
      $("historial-bajada").textContent = "Todavía no tiene plantas. Agréguelas en Mis materas.";
    }
  }

  async function cargarHistorial() {
    let historial;
    try {
      historial = await obtenerHistorial(Number(selector.value), LIMITE);
    } catch (error) {
      mostrarError($("error-historial"), error);
      return;
    }
    mostrarError($("error-historial"), null);
    pintar(historial.planta, historial.registros);
  }

  function pintar(planta, registros) {
    // La API los entrega del más reciente al más antiguo; la gráfica va de izquierda (antes) a derecha.
    const cronologicos = [...registros].reverse();
    $("historial-bajada").textContent = registros.length
      ? `Últimas ${registros.length} mediciones de ${planta.apodo}, la más reciente arriba.`
      : planta ? `${planta.apodo} todavía no tiene mediciones: registre una en Mis materas o con el sensor.` : "";
    pintarGrafica(planta, cronologicos);
    pintarRegistros(registros);
    pintarResumen(registros);
  }

  function pintarGrafica(planta, cronologicos) {
    const especie = planta && especieDe(contexto, planta.especie);
    $("leyenda").replaceChildren(...contexto.parametros.map((parametro, indice) =>
      crear("div", { clase: "leyenda__item" },
        crear("span", { clase: "leyenda__linea", estilo: { background: tono(indice).linea } }),
        etiqueta(parametro.nombre))));

    const fondo = [
      crearSvg("rect", { x: 0, y: 0, width: ANCHO, height: 200, fill: "#fbfdfa" }),
      ...[50, 100, 150].map((y) => crearSvg("line", { x1: 0, y1: y, x2: ANCHO, y2: y, stroke: "#eaf0e8", "stroke-width": 1 })),
    ];
    const trazos = contexto.parametros.flatMap((parametro, indice) => {
      // Cada serie con su propia escala: el rango óptimo de la especie con margen, o los límites físicos.
      const rango = especie?.rangos[parametro.nombre];
      const escala = rango ? dominioVisual(rango, parametro) : [parametro.minimoFisico, parametro.maximoFisico];
      const puntos = cronologicos.flatMap((registro, i) => {
        const lectura = registro.lecturas.find((l) => l.nombre === parametro.nombre);
        if (!lectura) return [];
        const x = cronologicos.length === 1 ? ANCHO / 2 : (i / (cronologicos.length - 1)) * ANCHO;
        return [[x, BASE - fraccion(lectura.valor, escala) * ALTO_UTIL]];
      });
      if (puntos.length === 0) return [];
      const color = tono(indice).linea;
      if (puntos.length === 1) {
        const [[x, y]] = puntos;
        return [crearSvg("circle", { cx: x, cy: y, r: 5, fill: color })];
      }
      const texto = puntos.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ");
      return [
        crearSvg("polygon", { points: `0,${BASE} ${texto} ${ANCHO},${BASE}`, fill: color, "fill-opacity": 0.07 }),
        crearSvg("polyline", {
          points: texto, fill: "none", stroke: color,
          "stroke-width": 2.5, "stroke-linejoin": "round", "stroke-linecap": "round",
        }),
      ];
    });
    $("grafica").replaceChildren(...fondo, ...trazos);
  }

  function pintarRegistros(registros) {
    $("registros").replaceChildren(...registros.map((registro) =>
      crear("div", { clase: "registro registro--origen" },
        crear("span", { clase: "registro__fecha", texto: fechaCorta(registro.momento) }),
        crear("span", { clase: "registro__lectura", texto: textoLecturas(registro.lecturas, contexto.parametros) }),
        crear("span", { clase: "registro__origen", texto: registro.origen === "MANUAL" ? "a mano" : registro.origen }),
        pastillaEstado(registro.estado))));
    $("registros").hidden = registros.length === 0;
  }

  function pintarResumen(registros) {
    const cuantos = (estado) => registros.filter((r) => r.estado === estado).length;
    const filas = [
      ["Mediciones", String(registros.length)],
      ...ESTADOS.map((estado) => [nombreDeEstado(estado), String(cuantos(estado))]),
      ["Última", registros.length ? fechaCorta(registros[0].momento) : "—"],
    ];
    $("resumen-filas").replaceChildren(...filas.map(([nombre, valor]) =>
      crear("div", { clase: "resumen__fila" },
        crear("span", { clase: "resumen__nombre", texto: nombre }),
        crear("span", { clase: "resumen__valor", texto: valor }))));
  }

  return { mostrar };
}
