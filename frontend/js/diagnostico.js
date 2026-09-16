// Pantalla de diagnóstico. Muestra lo que responde la API: el estado global, el estado de
// cada parámetro y las recomendaciones llegan decididos desde el backend.
import { pedirDiagnostico, pedirDiagnosticoSinConexion } from "./api.js";
import { angulo, arco, dominioVisual, fraccion, limitar, porcentaje, punto } from "./escala.js";
import {
  capitalizar, colorDeEstado, crear, crearSvg, etiqueta, nombreDeEstado,
  numero, redondear, textoDetalle, tono, unidad,
} from "./formato.js";

// Se espera a que la persona deje de escribir antes de consultar la API.
const ESPERA_MS = 400;
const GROSOR_ANILLO = 14;
const RADIO_EXTERIOR = 148;
const SEPARACION_ANILLOS = 28;
const ESPECIE_INICIAL = "sansevieria";
const VALORES_INICIALES = { humedad: "18", luz: "800", temperatura: "22" };
const ESCENARIOS = ["SALUDABLE", "EN_RIESGO", "CRITICO"];

// Peticiones inválidas a propósito, para ver el manejo de errores de RF6.
const PRUEBAS = {
  "especie-inexistente": (base) => ({ ...base, especie: "planta-que-no-existe" }),
  "humedad-vacia": (base) => ({ ...base, humedad: null }),
  "luz-no-numerica": (base) => ({ ...base, luz: "mucha" }),
  "humedad-imposible": (base) => ({ ...base, humedad: 150 }),
};

const medio = (rango) => (rango.min + rango.max) / 2;

export function crearPantallaDiagnostico(contexto) {
  const $ = (id) => document.getElementById(id);
  const selector = $("especie");
  const campos = new Map();

  let especie = null;
  let diagnostico = null;
  let error = null;
  let temporizador = null;
  let peticion = null;

  selector.addEventListener("change", () => usarEspecie(selector.value));
  $("pruebas").addEventListener("click", (evento) => {
    const boton = evento.target.closest("[data-prueba]");
    if (boton) probarError(boton.dataset.prueba);
  });

  function alCargarCatalogos() {
    selector.replaceChildren(...contexto.especies.map((e) => new Option(capitalizar(e.nombre), e.nombre)));
    selector.disabled = false;
    construirCampos();
    construirEscenarios();
    const inicial = contexto.especies.find((e) => e.nombre === ESPECIE_INICIAL) ?? contexto.especies[0];
    usarEspecie(inicial.nombre, VALORES_INICIALES);
  }

  // Desde el catálogo: la especie elegida con valores en la mitad de sus rangos.
  function seleccionarEspecie(nombre) {
    const elegida = contexto.especies.find((e) => e.nombre === nombre);
    if (!elegida) return;
    const valores = Object.fromEntries(
      contexto.parametros.map((p) => [p.nombre, String(Math.round(medio(elegida.rangos[p.nombre])))]),
    );
    usarEspecie(nombre, valores);
  }

  function usarEspecie(nombre, valores = {}) {
    especie = contexto.especies.find((e) => e.nombre === nombre);
    selector.value = especie.nombre;
    for (const { parametro, entrada } of campos.values()) {
      if (parametro.nombre in valores) entrada.value = valores[parametro.nombre];
      else if (entrada.value === "") entrada.value = String(redondear(medio(especie.rangos[parametro.nombre])));
    }
    pintarEspecie();
    diagnosticarAhora();
  }

  function mostrarErrorDeCarga(errorDeCarga) {
    selector.replaceChildren(new Option("No se pudieron cargar las especies"));
    selector.disabled = true;
    error = errorDeCarga;
    pintarResultado();
  }

  // ---- consultas a la API ----

  function leerDatos() {
    const datos = { especie: selector.value };
    for (const [nombre, { entrada }] of campos) {
      // Se envía lo que la persona escribió: el backend es el único que valida.
      const texto = entrada.value.trim();
      datos[nombre] = texto === "" ? null : texto;
    }
    return datos;
  }

  function programarDiagnostico() {
    clearTimeout(temporizador);
    temporizador = setTimeout(() => consultar(leerDatos()), ESPERA_MS);
  }

  function diagnosticarAhora() {
    clearTimeout(temporizador);
    consultar(leerDatos());
  }

  async function consultar(datos, enviar = pedirDiagnostico) {
    peticion?.abort();
    const propia = new AbortController();
    peticion = propia;
    try {
      diagnostico = await enviar(datos, { signal: propia.signal });
      error = null;
      contexto.marcarConexion(true);
    } catch (errorDeApi) {
      if (errorDeApi.name === "AbortError") return;
      error = errorDeApi;
      if (errorDeApi.codigo === "SIN_CONEXION" && enviar === pedirDiagnostico) contexto.marcarConexion(false);
    }
    pintarResultado();
  }

  function probarError(prueba) {
    clearTimeout(temporizador);
    const base = { especie: especie?.nombre ?? ESPECIE_INICIAL };
    if (especie) {
      for (const parametro of contexto.parametros) {
        base[parametro.nombre] = redondear(medio(especie.rangos[parametro.nombre]));
      }
    }
    if (prueba === "sin-conexion") consultar(base, pedirDiagnosticoSinConexion);
    else consultar(PRUEBAS[prueba](base));
  }

  // ---- mediciones ----

  function construirCampos() {
    const filas = contexto.parametros.map((parametro, indice) => {
      const color = tono(indice);
      const entrada = crear("input", { clase: "campo__entrada" });
      Object.assign(entrada, {
        id: `valor-${parametro.nombre}`, name: parametro.nombre, inputMode: "decimal", autocomplete: "off",
      });
      entrada.addEventListener("input", () => {
        pintarMarca(parametro.nombre);
        programarDiagnostico();
      });

      const rotulo = crear("label", { clase: "campo__etiqueta", texto: etiqueta(parametro.nombre) });
      rotulo.htmlFor = entrada.id;
      const banda = crear("div", { clase: "escala-mini__banda", estilo: { background: color.banda } });
      const marca = crear("div", { clase: "escala-mini__marca", estilo: { background: color.linea } });
      const minimo = crear("span");
      const maximo = crear("span");
      campos.set(parametro.nombre, { parametro, entrada, banda, marca, minimo, maximo });

      return crear("div", { clase: "campo" },
        crear("div", { clase: "campo__cabecera" },
          crear("span", { clase: "campo__muestra", estilo: { background: color.linea } }),
          rotulo,
          crear("span", { clase: "campo__unidad", texto: unidad(parametro.unidad) })),
        crear("div", { clase: "campo__fila" },
          entrada,
          crear("div", { clase: "campo__escala" },
            crear("div", { clase: "escala-mini" }, banda, marca),
            crear("div", { clase: "campo__limites" }, minimo, maximo))));
    });
    $("campos").replaceChildren(...filas);
  }

  function pintarEspecie() {
    $("cientifico").textContent = especie.nombreCientifico;
    for (const { parametro, banda, minimo, maximo } of campos.values()) {
      const rango = especie.rangos[parametro.nombre];
      const dominio = dominioVisual(rango, parametro);
      const desde = fraccion(rango.min, dominio);
      banda.style.left = porcentaje(desde);
      banda.style.width = porcentaje(fraccion(rango.max, dominio) - desde);
      minimo.textContent = numero.format(rango.min);
      maximo.textContent = numero.format(rango.max);
      pintarMarca(parametro.nombre);
    }
  }

  // La marca solo ubica el número escrito sobre la escala; no clasifica nada.
  function pintarMarca(nombre) {
    const { parametro, entrada, marca } = campos.get(nombre);
    const valor = Number(entrada.value.trim().replace(",", "."));
    marca.hidden = entrada.value.trim() === "" || !Number.isFinite(valor);
    if (!marca.hidden) {
      marca.style.left = porcentaje(fraccion(valor, dominioVisual(especie.rangos[nombre], parametro)));
    }
  }

  function construirEscenarios() {
    const botones = ESCENARIOS.map((tipo) => {
      const boton = crear("button", { clase: "escenario", texto: nombreDeEstado(tipo) });
      boton.type = "button";
      boton.dataset.escenario = tipo;
      boton.addEventListener("click", () => aplicarEscenario(tipo));
      return boton;
    });
    $("escenarios").replaceChildren(...botones);
  }

  // Valores de ejemplo calculados desde los rangos de GET /especies. El estado lo decide la API.
  function aplicarEscenario(tipo) {
    contexto.parametros.forEach((parametro, indice) => {
      const rango = especie.rangos[parametro.nombre];
      const ancho = rango.max - rango.min;
      let valor = medio(rango);
      if (tipo === "EN_RIESGO" && indice === 0) valor = rango.min - ancho * 0.15;
      if (tipo === "CRITICO" && indice === 0) valor = rango.min - ancho * 0.8;
      if (tipo === "CRITICO" && indice === 1) valor = rango.max * 1.4;
      valor = limitar(valor, parametro.minimoFisico, parametro.maximoFisico);
      campos.get(parametro.nombre).entrada.value = String(redondear(valor));
      pintarMarca(parametro.nombre);
    });
    diagnosticarAhora();
  }

  // ---- resultado ----

  function pintarResultado() {
    pintarError();
    pintarEntradas();
    pintarAnillos();
    pintarLecturas();
    pintarRecomendaciones();
    pintarEscenarios();
  }

  function pintarError() {
    $("error").hidden = !error;
    if (!error) return;
    $("error-codigo").textContent = error.status ? `${error.status} · ${error.codigo}` : error.codigo;
    $("error-mensaje").textContent = error.message;
    $("error-detalle").textContent = `detalle: ${textoDetalle(error.detalle)}`;
  }

  const resultadoDe = (nombre) => diagnostico?.parametros.find((p) => p.nombre === nombre);

  function pintarEntradas() {
    const campoConError = error?.detalle?.campo;
    for (const [nombre, { entrada }] of campos) {
      const resultado = resultadoDe(nombre);
      let colores = null;
      if (nombre === campoConError) colores = colorDeEstado("CRITICO");
      else if (resultado && resultado.estado !== "OPTIMO") colores = colorDeEstado(resultado.estado);
      entrada.style.borderColor = colores ? colores.texto : "";
      entrada.style.background = colores ? colores.fondo : "";
      entrada.setAttribute("aria-invalid", String(nombre === campoConError));
    }
  }

  function pintarAnillos() {
    const anillos = contexto.parametros.map((parametro, indice) => {
      const radio = RADIO_EXTERIOR - indice * SEPARACION_ANILLOS;
      const color = tono(indice);
      const resultado = resultadoDe(parametro.nombre);
      const rango = resultado
        ? { min: resultado.rangoOptimo[0], max: resultado.rangoOptimo[1] }
        : especie?.rangos[parametro.nombre];
      const grupo = crearSvg("g");
      grupo.append(crearSvg("path", {
        d: arco(radio, -135, 135), fill: "none", stroke: "#e6ece4",
        "stroke-width": GROSOR_ANILLO, "stroke-linecap": "round",
      }));
      if (!rango) return grupo;

      const dominio = dominioVisual(rango, parametro);
      grupo.append(crearSvg("path", {
        d: arco(radio, angulo(fraccion(rango.min, dominio)), angulo(fraccion(rango.max, dominio))),
        fill: "none", stroke: color.banda, "stroke-width": GROSOR_ANILLO, "stroke-linecap": "butt",
      }));
      if (resultado) {
        const final = angulo(fraccion(resultado.valor, dominio));
        const [x, y] = punto(radio, final);
        grupo.append(
          crearSvg("path", {
            d: arco(radio, -135, final), fill: "none", stroke: color.linea,
            "stroke-width": 3, "stroke-linecap": "round", opacity: 0.5,
          }),
          crearSvg("circle", {
            cx: x.toFixed(1), cy: y.toFixed(1), r: 9, fill: color.linea, stroke: "#fff", "stroke-width": 3,
          }),
        );
      }
      return grupo;
    });
    $("anillos").replaceChildren(...anillos);

    const colores = colorDeEstado(diagnostico?.estado);
    const estadoGlobal = $("estado-global");
    estadoGlobal.textContent = diagnostico ? nombreDeEstado(diagnostico.estado) : "Sin datos";
    estadoGlobal.style.color = colores.texto;
    $("pulso").style.background = colores.fondo;
    $("estado-especie").textContent = capitalizar(diagnostico?.especie ?? especie?.nombre ?? "");
  }

  function pintarLecturas() {
    const contenedor = $("lecturas");
    contenedor.style.setProperty("--columnas", String(Math.max(1, contexto.parametros.length)));
    const tarjetas = contexto.parametros.map((parametro, indice) => {
      const resultado = resultadoDe(parametro.nombre);
      return crear("div", { clase: "lectura" },
        crear("div", { clase: "lectura__cabecera" },
          crear("span", { clase: "lectura__punto", estilo: { background: tono(indice).linea } }),
          crear("span", { clase: "lectura__etiqueta", texto: etiqueta(parametro.nombre) })),
        crear("p", {
          clase: "lectura__valor",
          texto: resultado ? `${numero.format(resultado.valor)} ${unidad(resultado.unidad)}` : "—",
        }),
        crear("p", {
          clase: "lectura__rango",
          texto: resultado
            ? `óptimo ${numero.format(resultado.rangoOptimo[0])}–${numero.format(resultado.rangoOptimo[1])}`
            : "óptimo —",
        }),
        crear("p", {
          clase: "lectura__estado",
          texto: resultado?.estado ?? "—",
          estilo: { color: colorDeEstado(resultado?.estado).texto },
        }));
    });
    contenedor.replaceChildren(...tarjetas);
  }

  function pintarRecomendaciones() {
    const contenedor = $("recomendaciones");
    if (!diagnostico) {
      contenedor.replaceChildren(crear("p", { clase: "recomendaciones__vacio", texto: "Todavía no hay un diagnóstico." }));
      return;
    }
    const hayAcciones = diagnostico.recomendaciones.length > 0;
    // Cada recomendación corresponde a un parámetro fuera de rango (BAJO o ALTO comparten color).
    const colores = colorDeEstado(hayAcciones ? "BAJO" : "OPTIMO");
    const textos = hayAcciones
      ? diagnostico.recomendaciones
      : ["Todos los parámetros están en su rango óptimo. No hay nada que corregir hoy."];
    contenedor.replaceChildren(...textos.map((texto, indice) =>
      crear("div", { clase: "recomendacion", estilo: { background: colores.fondo } },
        crear("span", { clase: "recomendacion__indice", texto: String(indice + 1), estilo: { color: colores.texto } }),
        crear("p", { clase: "recomendacion__texto", texto }))));
  }

  function pintarEscenarios() {
    for (const boton of $("escenarios").children) {
      const tipo = boton.dataset.escenario;
      const colores = colorDeEstado(tipo);
      const activo = diagnostico?.estado === tipo;
      Object.assign(boton.style, {
        color: activo ? "#fff" : colores.texto,
        background: activo ? colores.texto : colores.fondo,
        borderColor: activo ? colores.texto : "transparent",
      });
      boton.setAttribute("aria-pressed", String(activo));
    }
  }

  pintarResultado();
  return { alCargarCatalogos, seleccionarEspecie, mostrarErrorDeCarga };
}
