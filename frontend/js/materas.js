// Mis materas: cada matera nace con su sensor y muestra su última medición, que viene de GET /plantas.
// Se actualiza sola de dos maneras: vuelve a pedir GET /plantas cada 10 s (consulta-periodica.js) y,
// mientras la conexión en vivo funciona, recibe cada medición al instante (tiempo-real.js). El estado
// de cada tarjeta lo calculó la API; aquí solo se ubica en pantalla. Desde el front no se escriben mediciones.
// «Agregar matera» y «Cambiar sensor» abren el asistente que conecta la placa (conectar-sensor.js). El flujo
// de antes (escribir el código y copiar la clave en config.h) queda en «Conectar a mano».
// Cada tarjeta muestra además la matera Tamagotchi y sus puntos, tal como los manda GET /juego/materas
// (juego.js): cuando el juego cambia, solo se vuelve a dibujar esa parte de las tarjetas que cambiaron.
import { cambiarSensor, eliminarPlanta, obtenerPlantas, registrarPlanta } from "./api.js";
import { crearAsistente } from "./conectar-sensor.js";
import { consultarCadaRato, textoConsulta } from "./consulta-periodica.js";
import { dibujoDeMatera, macetaVacia, rotulosDeMatera } from "./dibujo-planta.js";
import { dominioVisual, fraccion, porcentaje } from "./escala.js";
import {
  capitalizar, colorDeEstado, crear, etiqueta, numero, pastillaEstado, puntosConSigno, signoDe, tono, unidad,
} from "./formato.js";
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
  let aMano = false; // «Conectar a mano»: el formulario pide también el código, y la API da la clave

  const asistente = crearAsistente(contexto, {
    raiz: $("asistente"),
    // Mientras el asistente está abierto, no se empieza otra matera desde el formulario.
    alAbrirOCerrar: (abierto) => {
      formulario.hidden = abierto;
    },
    alCambiarLasMateras: () => cargar(),
    alConectarAMano: conectarAMano,
  });

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    if (!aMano) {
      // El apodo y la especie los revisa la API al final, cuando se crea la matera con el código de la placa.
      const { apodo, especie } = datosDe(formulario);
      mostrarError($("error-planta"), null);
      ocultarClave();
      formulario.reset();
      asistente.abrir({ modo: "nueva", apodo, especie });
      return;
    }
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
  $("conectar-a-mano").addEventListener("click", () => ponerAMano(!aMano));

  // El flujo de antes, para placas con config.h: el código se escribe y la clave se muestra una vez.
  function ponerAMano(activo) {
    aMano = activo;
    $("planta-grupo-codigo").hidden = !activo;
    $("planta-ayuda-asistente").hidden = activo;
    $("planta-ayuda-a-mano").hidden = !activo;
    $("planta-enviar").textContent = activo ? "Agregar con el código" : "Agregar matera";
    $("conectar-a-mano").textContent = activo ? "Volver al asistente" : "Conectar a mano (placas con config.h)";
    mostrarError($("error-planta"), null);
  }

  // Desde el asistente: «Conectar a mano» sigue con lo que ya se había escrito.
  function conectarAMano({ modo, apodo, especie, plantaId }) {
    if (modo === "nueva") {
      ponerAMano(true);
      $("planta-apodo").value = apodo ?? "";
      if (especie) $("planta-especie").value = especie;
      $("planta-codigo").focus();
      return;
    }
    abierta = plantaId;
    borrador = plantas.find((p) => p.id === plantaId)?.sensor?.codigo ?? "";
    pintar();
    $(`sensor-${plantaId}`)?.focus();
  }

  consultarCadaRato(() => !$("pantalla-materas").hidden, actualizar);

  // El juego se consulta aparte (juego.js); aquí solo se vuelve a dibujar la matera de las que cambiaron.
  contexto.juego.alCambiar((ids) => {
    for (const id of ids) {
      const actual = $("materas").querySelector(`[data-planta="${id}"] .matera__mascota`);
      const planta = plantas.find((p) => p.id === id);
      if (!actual || !planta) continue;
      const nueva = mascota(planta);
      // Se marca un momento solo si cambió el dibujo (no basta con que cambien los puntos).
      const descripcion = (nodo) => nodo.querySelector("svg")?.getAttribute("aria-label");
      if (descripcion(actual) !== descripcion(nueva)) nueva.classList.add("matera__mascota--nueva");
      actual.replaceWith(nueva);
    }
  });

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
    contexto.juego.refrescar(); // una matera nueva tiene su dibujo apenas responda el juego
  }

  // La consulta periódica: solo se vuelven a pintar las tarjetas que cambiaron, así no se pierde lo que
  // el usuario está escribiendo. Si cambió la lista (una matera nueva o borrada en otra pestaña), se pinta todo.
  async function actualizar() {
    if (asistente.sinApi()) return; // el equipo puede estar en la red de la placa, donde no hay API
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
      contexto.juego.refrescar();
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
      : "Todavía no tiene materas. Agregue la primera: el asistente conecta su placa.";
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
      mascota(planta),
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

  // La matera Tamagotchi: el dibujo y lo que dice, con los puntos de esta matera. Todo viene de la API;
  // mientras no responde, se ve la maceta vacía.
  function mascota(planta) {
    const matera = contexto.juego.mascotaDe(planta.id);
    if (!matera) {
      return crear("div", { clase: "matera__mascota" },
        macetaVacia({ clase: "matera__planta" }),
        crear("div", { clase: "matera__juego" }, crear("p", { clase: "matera__cuidado", texto: "Consultando el juego…" })));
    }
    const rotulos = rotulosDeMatera(matera);
    const horas = matera.horasCuidada;
    const sueno = !matera.dormida ? null : matera.ultimaLectura
      ? `${capitalizar(rotulos.cara)}: hace rato no le llegan lecturas.`
      : `${capitalizar(rotulos.cara)}: espera su primera lectura.`;
    const lineas = [
      crear("p", { clase: `matera__puntos juego__valor--${signoDe(matera.puntos)}` },
        crear("span", { clase: "matera__puntos-valor", texto: puntosConSigno(matera.puntos) }),
        crear("span", { clase: "matera__puntos-unidad", texto: " puntos" })),
      crear("p", { clase: "matera__etapa", texto: `${rotulos.etapa} · ${rotulos.condicion}` }),
      crear("p", {
        clase: "matera__cuidado",
        texto: `${numero.format(horas)} ${horas === 1 ? "hora" : "horas"} de juego bien cuidada`,
      }),
    ];
    if (sueno) lineas.push(crear("p", { clase: "matera__cuidado", texto: sueno }));
    return crear("div", { clase: "matera__mascota" },
      dibujoDeMatera(matera, { clase: "matera__planta" }),
      crear("div", { clase: "matera__juego" }, ...lineas));
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

  // Conectar a mano (placas con config.h): cambiar el sensor escribiendo el código, o pedir otra clave con
  // el mismo código. Conserva la planta y su historial.
  function formularioSensor(planta) {
    const id = `sensor-${planta.id}`;
    const entrada = crear("input", { clase: "formulario__campo formulario__campo--codigo" });
    Object.assign(entrada, { id, name: "codigo", autocomplete: "off", placeholder: "MT-0000-XX", value: borrador });
    entrada.addEventListener("input", () => {
      borrador = entrada.value;
    });
    const rotulo = crear("label", { clase: "formulario__etiqueta", texto: "Conectar a mano: código del sensor nuevo" });
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
        if (abierta === planta.id) { // cierra el formulario de «Conectar a mano»
          abierta = null;
          borrador = "";
          pintar();
          return;
        }
        abierta = null;
        borrador = "";
        pintar();
        asistente.abrir({ modo: "cambio", planta });
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
      asistente.ponerVista(true);
      ocultarClave();
      cargar();
      asistente.reanudar(); // si había una placa a medio conectar (también después de recargar la página)
    },
    // Al salir de Mis materas: el asistente deja de consultar hasta que vuelva.
    ocultar() {
      asistente.ponerVista(false);
    },
    alCargarCatalogos,
    // Mientras el equipo está en la red de la placa no hay API: el juego tampoco consulta.
    sinApi: () => asistente.sinApi(),
    // Al cerrar la sesión: nada de esta cuenta queda para la que entre después en la misma pestaña.
    reiniciar() {
      plantas = [];
      $("materas-consulta").textContent = "";
      abierta = null;
      borrador = "";
      diagnosticos.clear();
      ocultarClave();
      asistente.reiniciar();
      ponerAMano(false);
      formulario.reset();
      pintar();
    },
  };
}
