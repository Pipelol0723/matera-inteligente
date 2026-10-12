// Mis materas: las plantas del usuario con su última medición, que viene de GET /plantas.
// El estado de cada tarjeta lo calculó la API; aquí solo se ubica en pantalla.
import { eliminarPlanta, obtenerPlantas, registrarMedicion, registrarPlanta } from "./api.js";
import { dominioVisual, fraccion, porcentaje } from "./escala.js";
import { capitalizar, colorDeEstado, crear, etiqueta, numero, pastillaEstado, tono, unidad } from "./formato.js";
import { botonDe, datosDe, fechaCorta, mostrarError, ocupado } from "./formularios.js";
import { crearCamposMedicion, especieDe } from "./lecturas.js";

const ORIGENES = { MANUAL: "a mano" };

export function crearPantallaMateras(contexto) {
  const $ = (id) => document.getElementById(id);
  const formulario = $("form-planta");
  let plantas = [];
  let abierta = null; // la tarjeta con el formulario de medición abierto
  let respuesta = null; // la última medición manual: { plantaId, diagnostico }

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    try {
      await ocupado(botonDe(evento), () => registrarPlanta(datosDe(formulario)));
    } catch (error) {
      mostrarError($("error-planta"), error);
      return;
    }
    mostrarError($("error-planta"), null);
    formulario.reset();
    cargar();
  });

  function alCargarCatalogos() {
    const elegida = $("planta-especie").value;
    $("planta-especie").replaceChildren(...contexto.especies.map((e) => new Option(capitalizar(e.nombre), e.nombre)));
    if (elegida) $("planta-especie").value = elegida;
    pintar();
  }

  async function cargar() {
    try {
      plantas = await obtenerPlantas();
      mostrarError($("error-materas"), null);
    } catch (error) {
      mostrarError($("error-materas"), error);
      return;
    }
    pintar();
  }

  function pintar() {
    const conAtencion = plantas.filter((p) => p.ultimaMedicion && p.ultimaMedicion.estado !== "SALUDABLE").length;
    $("materas-bajada").textContent = plantas.length
      ? `${plantas.length} ${plantas.length === 1 ? "planta" : "plantas"} · ` +
        `${conAtencion} ${conAtencion === 1 ? "necesita" : "necesitan"} atención según su última medición`
      : "Todavía no tiene plantas. Agregue la primera con el formulario.";
    $("materas").replaceChildren(...plantas.map(tarjeta));
  }

  function tarjeta(planta) {
    const medicion = planta.ultimaMedicion;
    const especie = especieDe(contexto, planta.especie);
    const colores = colorDeEstado(medicion?.estado);

    const nodo = crear("article", { clase: "tarjeta matera" },
      crear("div", { clase: "matera__cabecera" },
        crear("div", { clase: "matera__icono", estilo: { background: colores.fondo } },
          crear("div", { clase: "matera__punto", estilo: { background: colores.texto } })),
        crear("div", { clase: "matera__nombres" },
          crear("p", { clase: "matera__lugar", texto: planta.apodo }),
          crear("p", { clase: "matera__especie", texto: capitalizar(planta.especie) }))),
      pastillaEstado(medicion?.estado),
      crear("div", { clase: "matera__barras" }, ...barras(medicion, especie)),
      crear("p", { clase: "matera__nota", texto: nota(planta) }));
    if (medicion?.estado === "CRITICO") nodo.classList.add("matera--critica");

    if (respuesta?.plantaId === planta.id) nodo.append(recomendaciones(respuesta.diagnostico));
    if (abierta === planta.id) nodo.append(formularioMedicion(planta, especie));
    nodo.append(acciones(planta));
    return nodo;
  }

  function barras(medicion, especie) {
    return contexto.parametros.map((parametro, indice) => {
      const lectura = medicion?.lecturas.find((l) => l.nombre === parametro.nombre);
      const rango = especie?.rangos[parametro.nombre];
      const pista = crear("div", { clase: "matera__pista" });
      if (rango) {
        const dominio = dominioVisual(rango, parametro);
        const desde = fraccion(rango.min, dominio);
        pista.append(crear("div", {
          clase: "matera__banda",
          estilo: { left: porcentaje(desde), width: porcentaje(fraccion(rango.max, dominio) - desde) },
        }));
        if (lectura) {
          pista.append(crear("div", {
            clase: "matera__marca",
            estilo: { left: porcentaje(fraccion(lectura.valor, dominio)), background: tono(indice).linea },
          }));
        }
      }
      return crear("div", { clase: "matera__barra" },
        crear("span", { clase: "matera__etiqueta", texto: etiqueta(parametro.nombre) }),
        pista,
        crear("span", {
          clase: "matera__valor",
          texto: lectura ? `${numero.format(lectura.valor)} ${unidad(parametro.unidad)}` : "—",
        }));
    });
  }

  function nota(planta) {
    const sensor = planta.sensor ? `Sensor ${planta.sensor.codigo}` : "Sin sensor";
    const medicion = planta.ultimaMedicion;
    if (!medicion) return `${sensor} · todavía no tiene mediciones.`;
    const origen = ORIGENES[medicion.origen] ?? `por el sensor ${medicion.origen}`;
    return `${sensor} · última medición ${fechaCorta(medicion.momento)}, ${origen}.`;
  }

  function recomendaciones(diagnostico) {
    const textos = diagnostico.recomendaciones.length
      ? diagnostico.recomendaciones
      : ["Todos los parámetros están en su rango óptimo."];
    return crear("div", { clase: "matera__respuesta" },
      crear("p", { clase: "rotulo", texto: "Respuesta de la API a la medición" }),
      ...textos.map((texto) => crear("p", { clase: "matera__recomendacion", texto })));
  }

  function formularioMedicion(planta, especie) {
    const campos = crearCamposMedicion(contexto.parametros, `medir-${planta.id}`);
    campos.proponer(especie);
    const error = crear("div", { clase: "tarjeta-error" });
    error.hidden = true;
    const enviar = crear("button", { clase: "boton-primario", texto: "Guardar medición" });
    const forma = crear("form", { clase: "matera__medicion" },
      crear("p", { clase: "rotulo", texto: "Medición a mano" }), campos.nodo, error, enviar);
    forma.noValidate = true;
    forma.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      try {
        const resultado = await ocupado(enviar, () => registrarMedicion(planta.id, campos.leer()));
        respuesta = { plantaId: planta.id, diagnostico: resultado.diagnostico };
      } catch (fallo) {
        mostrarError(error, fallo);
        return;
      }
      abierta = null;
      cargar();
    });
    return forma;
  }

  function acciones(planta) {
    const boton = (texto, clase, accion) => {
      const nodo = crear("button", { clase, texto });
      nodo.type = "button";
      nodo.addEventListener("click", accion);
      return nodo;
    };
    return crear("div", { clase: "matera__acciones" },
      boton(abierta === planta.id ? "Cancelar" : "Registrar medición", "boton-contorno", () => {
        abierta = abierta === planta.id ? null : planta.id;
        pintar();
      }),
      boton("Historial", "boton-contorno", () => contexto.verPlanta("historial", planta.id)),
      boton(planta.sensor ? "Sensor" : "Vincular sensor", "boton-contorno", () => contexto.verPlanta("vincular", planta.id)),
      boton("Eliminar", "boton-contorno boton-contorno--peligro", () => eliminar(planta)));
  }

  async function eliminar(planta) {
    const confirmado = window.confirm(`¿Eliminar «${planta.apodo}»? También se borran su sensor y su historial.`);
    if (!confirmado) return;
    try {
      await eliminarPlanta(planta.id);
    } catch (error) {
      mostrarError($("error-materas"), error);
      return;
    }
    if (respuesta?.plantaId === planta.id) respuesta = null;
    cargar();
  }

  return { mostrar: cargar, alCargarCatalogos };
}
