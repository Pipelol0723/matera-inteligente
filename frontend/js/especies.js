// Catálogo de especies: todo sale de GET /especies y GET /parametros. Para el admin, además, el formulario
// para agregar una especie (POST /admin/especies). Los rangos se escriben a mano y los revisa la API: aquí no
// se valida nada. El botón solo aparece para un ADMIN, pero eso es comodidad: a cualquier otro la API le
// responde 403.
import { agregarEspecie } from "./api.js";
import { fraccion, porcentaje } from "./escala.js";
import { capitalizar, crear, etiqueta, numero, tono, unidad } from "./formato.js";
import { botonDe, mostrarError, mostrarExito, ocupado } from "./formularios.js";
import { sesion } from "./sesion.js";

// Ancho mínimo de la banda, para que un rango angosto siga siendo visible.
const ANCHO_MINIMO = 0.03;

// Una hoja, el ícono de cada tarjeta (marcado fijo, sin datos de la API).
const HOJA = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" '
  + 'stroke-linejoin="round"><path d="M5 19c0-8.2 5.2-14 14-14 0 8.8-5.8 14-14 14z"/><path d="M5 19l8.5-8.5"/></svg>';

// Lo escrito en un límite: un número si se puede leer como número («12,5» también), y si no, el texto tal cual,
// para que la API lo rechace con su error.
function leerLimite(entrada) {
  const texto = (entrada?.value ?? "").trim();
  const valor = Number(texto.replace(",", "."));
  return texto === "" ? null : Number.isFinite(valor) ? valor : texto;
}

export function crearPantallaEspecies(contexto) {
  const $ = (id) => document.getElementById(id);
  const formulario = $("form-especie");
  const abrir = $("abrir-especie");
  let recienAgregada = null; // para marcar un momento la tarjeta de la especie nueva
  let abrirAlMostrar = false; // «Agregar especie» desde Administración
  let parametrosDelFormulario = "";

  abrir.addEventListener("click", () => ponerFormulario(formulario.hidden));
  $("cancelar-especie").addEventListener("click", () => {
    ponerFormulario(false);
    abrir.focus();
  });
  document.addEventListener("click", (evento) => {
    if (evento.target.closest?.("[data-abrir-especie]")) abrirAlMostrar = true;
  });

  formulario.addEventListener("input", (evento) => {
    const fila = evento.target.closest(".nueva-especie__rango");
    if (fila) dibujarVista(fila);
  });

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    mostrarExito($("exito-especie"), null);
    let especie;
    try {
      especie = await ocupado(botonDe(evento), () => agregarEspecie(leerEspecie()));
    } catch (error) {
      mostrarError($("error-especie"), error);
      return;
    }
    recienAgregada = especie.nombre;
    ponerFormulario(false);
    mostrarExito($("exito-especie"),
      `Especie «${capitalizar(especie.nombre)}» agregada. Ya aparece en el catálogo y se puede usar en Mis materas.`);
    contexto.recargarCatalogos();
  });

  function ponerFormulario(abierto) {
    formulario.hidden = !abierto;
    abrir.setAttribute("aria-expanded", String(abierto));
    if (abierto) {
      mostrarExito($("exito-especie"), null);
      $("especie-nombre").focus();
      return;
    }
    formulario.reset();
    mostrarError($("error-especie"), null);
    for (const fila of formulario.querySelectorAll(".nueva-especie__rango")) dibujarVista(fila);
  }

  // ---- el catálogo ----

  function pintar() {
    const cantidad = contexto.especies.length;
    $("especies-bajada").textContent =
      `${cantidad} ${cantidad === 1 ? "especie soportada" : "especies soportadas"} por la tabla de referencia. ` +
      "Cada banda es el rango óptimo de un parámetro, entre los límites físicos del sensor.";
    $("catalogo").replaceChildren(...contexto.especies.map(tarjeta));
    recienAgregada = null;
    pintarRangos();
    ponerRol();
  }

  function tarjeta(especie) {
    const icono = crear("span", { clase: "especie__icono" });
    icono.innerHTML = HOJA;
    icono.setAttribute("aria-hidden", "true");
    const nombres = crear("div", { clase: "especie__nombres" },
      crear("h2", { clase: "especie__nombre", texto: capitalizar(especie.nombre) }));
    if (especie.nombreCientifico) {
      nombres.append(crear("p", { clase: "especie__cientifico", texto: especie.nombreCientifico }));
    }
    const nodo = crear("article", { clase: "tarjeta especie" },
      crear("div", { clase: "especie__cabecera" }, icono, nombres),
      crear("div", { clase: "barras" }, ...contexto.parametros.map((parametro, indice) => barra(especie, parametro, indice))));
    if (especie.nombre === recienAgregada) nodo.classList.add("especie--nueva");
    return nodo;
  }

  function barra(especie, parametro, indice) {
    const rango = especie.rangos[parametro.nombre];
    const escala = [parametro.minimoFisico, parametro.maximoFisico];
    const izquierda = fraccion(rango.min, escala);
    const ancho = Math.max(ANCHO_MINIMO, fraccion(rango.max, escala) - izquierda);
    return crear("div", { clase: "barra" },
      crear("div", { clase: "barra__cabecera" },
        crear("span", { clase: "barra__etiqueta" },
          crear("span", { clase: "barra__punto", estilo: { background: tono(indice).linea } }),
          etiqueta(parametro.nombre)),
        crear("span", {
          clase: "barra__texto",
          texto: `${numero.format(rango.min)}–${numero.format(rango.max)} ${unidad(rango.unidad)}`,
        })),
      crear("div", { clase: "barra__pista" },
        crear("div", {
          clase: "barra__banda",
          estilo: { left: porcentaje(izquierda), width: porcentaje(ancho), background: tono(indice).linea },
        })));
  }

  // ---- el formulario del admin ----

  // Un mínimo y un máximo por cada parámetro de GET /parametros: si se agrega el pH, aparece solo. Solo se
  // vuelve a armar si cambian los parámetros, así no se pierde lo escrito.
  function pintarRangos() {
    const clave = contexto.parametros.map((p) => `${p.nombre}:${p.minimoFisico}:${p.maximoFisico}`).join("|");
    if (clave === parametrosDelFormulario) return;
    parametrosDelFormulario = clave;
    $("rangos-especie").replaceChildren(...contexto.parametros.map(filaDeRango));
  }

  function filaDeRango(parametro, indice) {
    const campo = (cual) => {
      const id = `rango-${parametro.nombre}-${cual}`;
      const entrada = crear("input", { clase: "formulario__campo nueva-especie__limite" });
      Object.assign(entrada, { id, name: `${parametro.nombre}-${cual}`, inputMode: "decimal", autocomplete: "off" });
      const rotulo = crear("label", { clase: "nueva-especie__rotulo", texto: cual === "min" ? "Mínimo" : "Máximo" });
      rotulo.htmlFor = id;
      entrada.setAttribute("aria-describedby", `rango-${parametro.nombre}-limites`);
      return crear("div", { clase: "nueva-especie__campo" }, rotulo, entrada);
    };
    const simbolo = unidad(parametro.unidad);
    const limites = crear("span", {
      clase: "nueva-especie__limites",
      texto: `entre ${numero.format(parametro.minimoFisico)} y ${numero.format(parametro.maximoFisico)} ${simbolo}`,
    });
    limites.id = `rango-${parametro.nombre}-limites`;
    const fila = crear("div", { clase: "nueva-especie__rango" },
      crear("div", { clase: "nueva-especie__parametro" },
        crear("span", { clase: "barra__etiqueta" },
          crear("span", { clase: "barra__punto", estilo: { background: tono(indice).linea } }),
          `${etiqueta(parametro.nombre)} (${simbolo})`),
        limites),
      crear("div", { clase: "nueva-especie__campos" }, campo("min"), campo("max")),
      crear("div", { clase: "barra__pista nueva-especie__vista" },
        crear("div", { clase: "barra__banda", estilo: { background: tono(indice).linea } })));
    fila.dataset.parametro = parametro.nombre;
    dibujarVista(fila);
    return fila;
  }

  // La vista previa de la banda: solo se dibuja si los dos límites son números y el mínimo va antes que el
  // máximo. Es un dibujo: lo que valga o no lo dice la API al enviar.
  function dibujarVista(fila) {
    const parametro = contexto.parametros.find((p) => p.nombre === fila.dataset.parametro);
    const banda = fila.querySelector(".nueva-especie__vista .barra__banda");
    const minimo = leerLimite(fila.querySelector('[name$="-min"]'));
    const maximo = leerLimite(fila.querySelector('[name$="-max"]'));
    const dibujable = parametro && typeof minimo === "number" && typeof maximo === "number" && minimo < maximo;
    banda.hidden = !dibujable;
    if (!dibujable) return;
    const escala = [parametro.minimoFisico, parametro.maximoFisico];
    const izquierda = fraccion(minimo, escala);
    Object.assign(banda.style, {
      left: porcentaje(izquierda),
      width: porcentaje(Math.max(ANCHO_MINIMO, fraccion(maximo, escala) - izquierda)),
    });
  }

  function leerEspecie() {
    return {
      nombre: formulario.elements.nombre.value,
      nombreCientifico: formulario.elements.nombreCientifico.value,
      rangos: Object.fromEntries(contexto.parametros.map((p) => [
        p.nombre, {
          min: leerLimite(formulario.elements[`${p.nombre}-min`]),
          max: leerLimite(formulario.elements[`${p.nombre}-max`]),
        },
      ])),
    };
  }

  // El botón «Agregar especie» solo para el admin. Si deja de serlo, el formulario se cierra.
  function ponerRol() {
    const esAdmin = sesion.esAdmin();
    abrir.hidden = !esAdmin;
    if (!esAdmin && !formulario.hidden) ponerFormulario(false);
  }

  return {
    pintar,
    mostrar() {
      ponerRol();
      if (abrirAlMostrar && sesion.esAdmin()) ponerFormulario(true);
      abrirAlMostrar = false;
    },
    ocultar() {
      mostrarExito($("exito-especie"), null);
    },
  };
}
