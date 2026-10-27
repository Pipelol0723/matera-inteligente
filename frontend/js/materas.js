// Mis materas: cada matera nace con su sensor y muestra su última medición, que viene de GET /plantas.
// Se actualiza sola de dos maneras: vuelve a pedir GET /plantas cada 10 s (consulta-periodica.js) y,
// mientras la conexión en vivo funciona, recibe cada medición al instante (tiempo-real.js). El estado
// de cada tarjeta lo calculó la API; aquí solo se ubica en pantalla. Desde el front no se escriben mediciones.
import { cambiarSensor, eliminarPlanta, obtenerPlantas, registrarPlanta } from "./api.js";
import { consultarCadaRato, textoConsulta } from "./consulta-periodica.js";
import { dominioVisual, fraccion, porcentaje } from "./escala.js";
import { capitalizar, colorDeEstado, crear, etiqueta, numero, pastillaEstado, tono, unidad } from "./formato.js";
import { botonDe, datosDe, fechaCorta, mostrarError, ocupado } from "./formularios.js";
import { esMasNueva, especieDe, textoOrigen } from "./lecturas.js";

export function crearPantallaMateras(contexto) {
  const $ = (id) => document.getElementById(id);
  const formulario = $("form-planta");
  let plantas = [];
  let abierta = null; // la tarjeta con el formulario para cambiar el sensor
  let borrador = ""; // lo escrito en ese formulario, para no perderlo si la tarjeta se vuelve a pintar
  // Lo que GET /plantas no trae: las recomendaciones de la medición que llegó en vivo, con su momento.
  // Solo se muestran mientras esa siga siendo la última medición de la tarjeta.
  const diagnosticos = new Map();

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    let nueva;
    try {
      nueva = await ocupado(botonDe(evento), () => registrarPlanta(datosDe(formulario)));
    } catch (error) {
      mostrarError($("error-planta"), error);
      return;
    }
    mostrarError($("error-planta"), null);
    formulario.reset();
    mostrarClave(nueva, "Matera creada");
    cargar();
  });

  $("copiar-clave").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("clave-texto").textContent);
      $("copiar-clave").textContent = "Copiada";
    } catch {
      $("copiar-clave").textContent = "Selecciónela y cópiela a mano";
    }
  });
  $("cerrar-clave").addEventListener("click", ocultarClave);

  consultarCadaRato(() => !$("pantalla-materas").hidden, actualizar);

  contexto.tiempoReal.alRecibir((mensaje) => {
    if ($("pantalla-materas").hidden) return; // al volver a la pantalla se recarga todo
    if (mensaje.tipo === "reconectado") {
      cargar();
      return;
    }
    if (mensaje.tipo !== "medicion") return;
    const planta = plantas.find((p) => p.id === mensaje.planta.id);
    if (!planta) {
      cargar(); // una matera creada en otra pestaña
      return;
    }
    if (esMasNueva(planta.ultimaMedicion, mensaje.medicion)) return; // la consulta ya trajo una posterior
    planta.ultimaMedicion = mensaje.medicion;
    diagnosticos.set(planta.id, { momento: mensaje.medicion.momento, diagnostico: mensaje.diagnostico });
    repintarTarjeta(planta);
    pintarBajada();
  });

  // La clave sale una sola vez: al crear la matera o al cambiarle el sensor. El panel está arriba de
  // la lista, así que se lleva la vista hasta él: si no se ve, la clave se pierde al cambiar de pantalla.
  function mostrarClave({ planta, codigo, clave }, accion) {
    $("clave-rotulo").textContent = `${accion}: «${planta.apodo}» con el sensor ${codigo} · la clave se muestra una sola vez`;
    $("clave-texto").textContent = clave;
    $("copiar-clave").textContent = "Copiar";
    $("clave-nueva").hidden = false;
    $("clave-nueva").scrollIntoView({ block: "center" });
    $("copiar-clave").focus({ preventScroll: true });
  }

  function ocultarClave() {
    $("clave-nueva").hidden = true;
    $("clave-texto").textContent = "";
  }

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
    $("materas-consulta").textContent = textoConsulta();
    pintar();
  }

  // La consulta periódica: solo se vuelven a pintar las tarjetas que cambiaron, así no se pierde lo que
  // el usuario está escribiendo. Si cambió la lista (una matera nueva o borrada en otra pestaña), se pinta todo.
  async function actualizar() {
    let nuevas;
    try {
      nuevas = await obtenerPlantas();
    } catch (error) {
      mostrarError($("error-materas"), error);
      return;
    }
    mostrarError($("error-materas"), null);
    $("materas-consulta").textContent = textoConsulta();
    const ids = (lista) => lista.map((p) => p.id).join(",");
    if (ids(nuevas) !== ids(plantas)) {
      plantas = nuevas;
      pintar();
      return;
    }
    nuevas.forEach((nueva, indice) => {
      const vieja = plantas[indice];
      // Si mientras se esperaba la respuesta llegó una medición en vivo, esa es más reciente: no se retrocede.
      if (esMasNueva(vieja.ultimaMedicion, nueva.ultimaMedicion)) nueva.ultimaMedicion = vieja.ultimaMedicion;
      const cambio = nueva.ultimaMedicion?.momento !== vieja.ultimaMedicion?.momento
        || nueva.sensor?.codigo !== vieja.sensor?.codigo;
      plantas[indice] = nueva;
      if (cambio) repintarTarjeta(nueva);
    });
    pintarBajada();
  }

  function pintarBajada() {
    const conAtencion = plantas.filter((p) => p.ultimaMedicion && p.ultimaMedicion.estado !== "SALUDABLE").length;
    $("materas-bajada").textContent = plantas.length
      ? `${plantas.length} ${plantas.length === 1 ? "matera" : "materas"} · ` +
        `${conAtencion} ${conAtencion === 1 ? "necesita" : "necesitan"} atención según su última medición`
      : "Todavía no tiene materas. Agregue la primera con el código de su sensor.";
  }

  function pintar() {
    pintarBajada();
    $("materas").replaceChildren(...plantas.map((planta) => tarjeta(planta)));
  }

  // Solo la tarjeta que cambió, marcada un momento para que se note la medición nueva. Si tenía abierto
  // el formulario del sensor, se conserva el mismo: con lo escrito, su error y su botón ocupado.
  function repintarTarjeta(planta) {
    const vieja = $("materas").querySelector(`[data-planta="${planta.id}"]`);
    if (!vieja) return;
    const escribiendo = vieja.contains(document.activeElement) && document.activeElement.tagName === "INPUT";
    const nueva = tarjeta(planta);
    const formularioAbierto = vieja.querySelector(".matera__sensor");
    if (formularioAbierto) nueva.querySelector(".matera__sensor")?.replaceWith(formularioAbierto);
    nueva.classList.add("matera--nueva");
    vieja.replaceWith(nueva);
    if (escribiendo) nueva.querySelector("input")?.focus();
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
    nodo.dataset.planta = planta.id;
    if (medicion?.estado === "CRITICO") nodo.classList.add("matera--critica");

    const enVivo = diagnosticos.get(planta.id);
    if (enVivo && enVivo.momento === medicion?.momento) nodo.append(recomendaciones(enVivo.diagnostico));
    if (abierta === planta.id) nodo.append(formularioSensor(planta));
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
    // Solo una matera creada antes de que el sensor fuera obligatorio puede no tenerlo.
    const sensor = planta.sensor ? `Sensor ${planta.sensor.codigo}` : "Sin sensor: agréguele uno";
    const medicion = planta.ultimaMedicion;
    if (!medicion) return `${sensor} · todavía no llega ninguna medición`;
    // El origen solo se dice si no es el sensor actual: una medición vieja a mano o de un sensor anterior.
    // Sin punto final: la hora ya termina en «p. m.».
    const origen = medicion.origen === planta.sensor?.codigo
      ? ""
      : medicion.origen === "MANUAL" ? `, ${textoOrigen(medicion.origen)}` : `, del sensor anterior ${medicion.origen}`;
    return `${sensor} · última medición ${fechaCorta(medicion.momento)}${origen}`;
  }

  function recomendaciones(diagnostico) {
    const textos = diagnostico.recomendaciones.length
      ? diagnostico.recomendaciones
      : ["Todos los parámetros están en su rango óptimo."];
    return crear("div", { clase: "matera__respuesta" },
      crear("p", { clase: "rotulo", texto: "Recomendaciones de la medición que llegó en vivo" }),
      ...textos.map((texto) => crear("p", { clase: "matera__recomendacion", texto })));
  }

  // Cambiar el sensor (o pedir otra clave con el mismo código) conserva la planta y su historial.
  function formularioSensor(planta) {
    const id = `sensor-${planta.id}`;
    const entrada = crear("input", { clase: "formulario__campo formulario__campo--codigo" });
    Object.assign(entrada, { id, name: "codigo", autocomplete: "off", placeholder: "MT-0000-XX", value: borrador });
    entrada.addEventListener("input", () => {
      borrador = entrada.value;
    });
    const rotulo = crear("label", { clase: "formulario__etiqueta", texto: "Código del sensor nuevo" });
    rotulo.htmlFor = id;
    const error = crear("div", { clase: "tarjeta-error" });
    error.hidden = true;
    const enviar = crear("button", { clase: "boton-primario", texto: planta.sensor ? "Cambiar sensor" : "Agregar sensor" });
    const forma = crear("form", { clase: "matera__sensor" },
      rotulo,
      crear("p", {
        clase: "formulario__ayuda",
        texto: "El historial se conserva. Con el mismo código, la API da una clave nueva y la anterior deja de servir.",
      }),
      crear("div", { clase: "matera__sensor-fila" }, entrada, enviar),
      error);
    forma.noValidate = true;
    forma.addEventListener("submit", async (evento) => {
      evento.preventDefault();
      let cambio;
      try {
        cambio = await ocupado(enviar, () => cambiarSensor(planta.id, entrada.value));
      } catch (fallo) {
        mostrarError(error, fallo);
        return;
      }
      abierta = null;
      borrador = "";
      mostrarClave(cambio, planta.sensor ? "Sensor cambiado" : "Sensor agregado");
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
    const textoSensor = abierta === planta.id ? "Cancelar" : planta.sensor ? "Cambiar sensor" : "Agregar sensor";
    return crear("div", { clase: "matera__acciones" },
      boton(textoSensor, "boton-contorno", () => {
        abierta = abierta === planta.id ? null : planta.id;
        borrador = abierta === null ? "" : planta.sensor?.codigo ?? "";
        pintar();
        if (abierta !== null) $(`sensor-${planta.id}`)?.focus();
      }),
      boton("Historial", "boton-contorno", () => contexto.verPlanta("historial", planta.id)),
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
    diagnosticos.delete(planta.id);
    if (abierta === planta.id) abierta = null;
    cargar();
  }

  return {
    mostrar() {
      ocultarClave();
      cargar();
    },
    alCargarCatalogos,
    // Al cerrar la sesión: nada de esta cuenta queda para la que entre después en la misma pestaña.
    reiniciar() {
      plantas = [];
      $("materas-consulta").textContent = "";
      abierta = null;
      borrador = "";
      diagnosticos.clear();
      ocultarClave();
      pintar();
    },
  };
}
