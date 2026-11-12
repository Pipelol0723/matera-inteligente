// Historial de una planta: la lista y la gráfica con los registros de GET /plantas/{id}/historial.
// Cada registro trae el estado que la API calculó en ese momento; aquí no se recalcula nada.
// Se vuelve a pedir cada 10 s (consulta-periodica.js), y una medición que llega en vivo (tiempo-real.js)
// se agrega arriba al instante, sin esperar la próxima consulta.
import { obtenerHistorial, obtenerPlantas } from "./api.js";
import { consultarCadaRato, textoConsulta } from "./consulta-periodica.js";
import { dominioVisual, fraccion } from "./escala.js";
import {
  capitalizar, colorDeEstado, crear, crearSvg, etiqueta, nombreDeEstado, pastillaEstado, tono,
} from "./formato.js";
import { fechaCorta, mostrarError } from "./formularios.js";
import { especieDe, textoLecturas, textoOrigen } from "./lecturas.js";

const LIMITE = 30;
const ANCHO = 640;
const BASE = 190;
const ALTO_UTIL = 170;
const ESTADOS = ["SALUDABLE", "EN_RIESGO", "CRITICO"];

export function crearPantallaHistorial(contexto) {
  const $ = (id) => document.getElementById(id);
  const selector = $("historial-planta");
  let plantas = [];
  let actual = null; // { planta, registros } de la planta elegida

  selector.addEventListener("change", () => {
    contexto.plantaElegida = Number(selector.value);
    actual = null; // hasta que llegue el historial de la nueva, no se agrega nada en vivo
    cargarHistorial();
  });

  consultarCadaRato(() => !$("pantalla-historial").hidden && plantas.length > 0, cargarHistorial);

  contexto.tiempoReal.alRecibir((mensaje) => {
    if ($("pantalla-historial").hidden) return;
    if (mensaje.tipo === "reconectado") {
      if (plantas.length) cargarHistorial();
    } else if (mensaje.tipo === "medicion" && actual && mensaje.planta.id === actual.planta.id) {
      actual.registros = unir([mensaje.medicion], actual.registros);
      pintar(actual.planta, actual.registros);
    }
  });

  // Los registros de la consulta y los que llegaron en vivo, sin repetir, del más reciente al más antiguo.
  // Así una respuesta que salió antes de la última medición no la borra, y una que ya la trae no la duplica.
  function unir(unos, otros) {
    const porClave = new Map([...otros, ...unos].map((r) => [`${r.momento}|${r.origen}`, r]));
    return [...porClave.values()].sort((a, b) => Date.parse(b.momento) - Date.parse(a.momento)).slice(0, LIMITE);
  }

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
    $("pantalla-historial").classList.toggle("historial--sin-materas", plantas.length === 0);
    if (plantas.length) {
      cargarHistorial();
    } else {
      actual = null;
      pintar(null, []);
      $("historial-bajada").textContent = "Todavía no tiene materas. Agréguelas en Mis materas.";
    }
  }

  async function cargarHistorial() {
    const pedida = Number(selector.value);
    let historial;
    try {
      historial = await obtenerHistorial(pedida, LIMITE);
    } catch (error) {
      if (pedida === Number(selector.value)) mostrarError($("error-historial"), error);
      return;
    }
    // Si mientras tanto se eligió otra planta, esta respuesta ya no sirve.
    if (pedida !== Number(selector.value)) return;
    mostrarError($("error-historial"), null);
    $("historial-consulta").textContent = textoConsulta();
    const enVivo = actual?.planta.id === historial.planta.id ? actual.registros : [];
    actual = { planta: historial.planta, registros: unir(historial.registros, enVivo) };
    pintar(actual.planta, actual.registros);
  }

  function pintar(planta, registros) {
    // La API los entrega del más reciente al más antiguo; la gráfica va de izquierda (antes) a derecha.
    const cronologicos = [...registros].reverse();
    $("historial-bajada").textContent = registros.length
      ? `Últimas ${registros.length} mediciones de ${planta.apodo}, la más reciente arriba.`
      : planta ? `${planta.apodo} todavía no tiene mediciones: aparecen aquí apenas el sensor envía una.` : "";
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
      crearSvg("rect", { x: 0, y: 0, width: ANCHO, height: 200, fill: "var(--grafica-fondo)" }),
      ...[50, 100, 150].map((y) => crearSvg("line", {
        x1: 0, y1: y, x2: ANCHO, y2: y, stroke: "var(--grafica-linea)", "stroke-width": 1,
      })),
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
    // Debajo, la fecha de la primera y de la última medición de la gráfica.
    const primera = cronologicos[0];
    const ultima = cronologicos.at(-1);
    $("grafica-desde").textContent = primera ? fechaCorta(primera.momento) : "";
    $("grafica-hasta").textContent = ultima && ultima !== primera ? fechaCorta(ultima.momento) : "";
    $("grafica-vacia").hidden = cronologicos.length > 0;
  }

  // Cada medición en una fila: la fecha, una ficha por lectura (con el color de su línea en la gráfica),
  // el origen y el estado que calculó la API.
  function pintarRegistros(registros) {
    $("registros").replaceChildren(...registros.map((registro) =>
      crear("li", { clase: "registro" },
        crear("span", { clase: "registro__fecha", texto: fechaCorta(registro.momento) }),
        crear("span", { clase: "registro__lecturas" }, ...fichasDeLecturas(registro.lecturas)),
        crear("span", { clase: "registro__origen", texto: textoOrigen(registro.origen) }),
        crear("span", { clase: "registro__estado" }, pastillaEstado(registro.estado)))));
    $("registros").hidden = registros.length === 0;
    document.querySelector("#pantalla-historial .registros__titulos").hidden = registros.length === 0;
  }

  // En el orden de GET /parametros. El nombre del parámetro queda para los lectores de pantalla.
  function fichasDeLecturas(lecturas) {
    return contexto.parametros.flatMap((parametro, indice) => {
      const lectura = lecturas.find((l) => l.nombre === parametro.nombre);
      if (!lectura) return [];
      return [crear("span", { clase: "registro__dato" },
        crear("span", { clase: "registro__punto", estilo: { background: tono(indice).linea } }),
        crear("span", { clase: "solo-lectores", texto: `${etiqueta(parametro.nombre)}: ` }),
        textoLecturas([lectura], contexto.parametros))];
    });
  }

  // Las cifras de arriba: cuántas mediciones, cuántas en cada estado (con una barra que las reparte) y la última.
  function pintarResumen(registros) {
    const cuantos = (estado) => registros.filter((r) => r.estado === estado).length;
    const total = registros.length;
    const reparto = crear("span", { clase: "cifra__reparto" }, ...ESTADOS.filter((e) => cuantos(e) > 0).map((estado) =>
      crear("span", { estilo: { flexGrow: String(cuantos(estado)), background: colorDeEstado(estado).texto } })));
    reparto.setAttribute("aria-hidden", "true");
    const cifras = [
      cifra("Mediciones", String(total), { clase: "cifra--total", extra: total ? reparto : null }),
      ...ESTADOS.map((estado) => cifra(nombreDeEstado(estado), String(cuantos(estado)), { color: colorDeEstado(estado).texto })),
      cifra("Última", total ? fechaCorta(registros[0].momento) : "—", { clase: "cifra--fecha" }),
    ];
    $("resumen-filas").replaceChildren(...cifras);
  }

  function cifra(nombre, valor, { clase = "", color = null, extra = null } = {}) {
    const rotulo = crear("span", { clase: "cifra__nombre" });
    if (color) rotulo.append(crear("span", { clase: "cifra__punto", estilo: { background: color } }));
    rotulo.append(nombre);
    const nodo = crear("div", { clase: `cifra ${clase}`.trim() }, rotulo, crear("span", { clase: "cifra__valor", texto: valor }));
    if (extra) nodo.append(extra);
    return nodo;
  }

  // Al cerrar la sesión: nada de esta cuenta queda para la que entre después en la misma pestaña.
  function reiniciar() {
    plantas = [];
    actual = null;
    selector.replaceChildren();
    $("pantalla-historial").classList.remove("historial--sin-materas");
    $("historial-consulta").textContent = "";
    mostrarError($("error-historial"), null);
    pintar(null, []);
  }

  return { mostrar, reiniciar };
}
