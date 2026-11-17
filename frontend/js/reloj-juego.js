// El reloj del juego: cuánto dura en tiempo real una hora de juego. Lo ve cualquiera con sesión (una línea en
// Juego) y lo cambia un admin (la tarjeta «Reloj del juego» en Administración), sin reiniciar el backend.
// Quién puede cambiarlo y si la duración sirve lo decide la API (403 y 400 RELOJ_INVALIDO); aquí solo se
// convierte lo que la persona elige a minutos reales por día de juego, que es lo que la API recibe.
import { cambiarRelojDeJuego, obtenerRelojDeJuego } from "./api.js";
import { crear } from "./formato.js";
import { mostrarError, ocupado } from "./formularios.js";

const HORAS_POR_DIA = 24;
// La placa manda una lectura cada 15 s: con horas de juego más cortas, algunas quedan sin lecturas.
const SEGUNDOS_ENTRE_LECTURAS = 15;

// Atajos: segundos reales que dura una hora de juego.
const ATAJOS = [
  { segundos: 3600, texto: "Tiempo real", detalle: "1 hora = 1 hora" },
  { segundos: 60, texto: "1 hora = 1 minuto", detalle: "un día dura 24 minutos" },
  { segundos: 15, texto: "1 hora = 15 segundos", detalle: "un día dura 6 minutos" },
];

const UNIDADES = { segundos: 1, minutos: 60, horas: 3600 };

const numero = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });

// «15 segundos», «1 minuto», «2,5 horas».
export function duracion(segundos) {
  const [valor, singular, plural] = segundos >= 3600 && segundos % 360 === 0
    ? [segundos / 3600, "hora", "horas"]
    : segundos >= 60 && segundos % 6 === 0
      ? [segundos / 60, "minuto", "minutos"]
      : [segundos, "segundo", "segundos"];
  return `${numero.format(valor)} ${valor === 1 ? singular : plural}`;
}

// «1 hora de juego = 1 minuto en tiempo real · un día de juego dura 24 minutos».
export function textoDelReloj(reloj) {
  if (!reloj) return "";
  const real = reloj.segundosPorHora === 3600 ? "el reloj del juego va en tiempo real" : null;
  return real ?? `1 hora de juego = ${duracion(reloj.segundosPorHora)} en tiempo real · un día de juego dura ${duracion(reloj.minutosPorDia * 60)}`;
}

// La línea de la pantalla Juego. Si no responde, simplemente no se muestra.
export async function pintarRelojEnJuego(nodo) {
  try {
    nodo.textContent = `Reloj del juego: ${textoDelReloj(await obtenerRelojDeJuego())}.`;
  } catch {
    nodo.textContent = "";
  }
}

// La tarjeta de Administración. Devuelve { mostrar, reiniciar }.
export function crearTarjetaReloj({ raiz }) {
  const actual = crear("p", { clase: "reloj__actual" });
  actual.setAttribute("role", "status");
  const error = crear("div", { clase: "tarjeta-error" });
  error.setAttribute("role", "alert");
  error.hidden = true;
  const aviso = crear("p", { clase: "reloj__aviso" });
  aviso.hidden = true;

  const atajos = ATAJOS.map(({ segundos, texto, detalle }) => {
    const boton = crear("button", { clase: "boton-contorno reloj__atajo" },
      crear("span", { clase: "reloj__atajo-texto", texto }),
      crear("span", { clase: "reloj__atajo-detalle", texto: detalle }));
    boton.type = "button";
    boton.dataset.segundos = String(segundos);
    boton.addEventListener("click", () => cambiar(boton, segundos));
    return boton;
  });

  const valor = crear("input", { clase: "formulario__campo reloj__valor" });
  Object.assign(valor, { type: "number", min: "0.1", step: "any", inputMode: "decimal", id: "reloj-valor", required: true });
  const unidad = crear("select", { clase: "selector reloj__unidad" },
    ...Object.keys(UNIDADES).map((nombre) => {
      const opcion = crear("option", { texto: nombre });
      opcion.value = nombre;
      return opcion;
    }));
  unidad.id = "reloj-unidad";
  unidad.value = "minutos";
  const etiqueta = crear("label", { clase: "formulario__etiqueta", texto: "1 hora de juego dura (en tiempo real)" });
  etiqueta.htmlFor = valor.id;
  const aplicar = crear("button", { clase: "boton-primario", texto: "Aplicar" });
  aplicar.type = "submit";
  const formulario = crear("form", { clase: "reloj__formulario" },
    etiqueta,
    crear("div", { clase: "reloj__fila" }, valor, unidad, aplicar));
  formulario.noValidate = true;
  formulario.addEventListener("submit", (evento) => {
    evento.preventDefault();
    cambiar(aplicar, Number(valor.value) * UNIDADES[unidad.value]);
  });

  raiz.replaceChildren(
    crear("h2", { id: "admin-reloj-titulo", clase: "rotulo", texto: "Reloj del juego" }),
    crear("p", {
      clase: "formulario__ayuda",
      texto: "Cuánto dura en tiempo real una hora de juego, para todas las materas. Vale desde ya: las lecturas " +
        "que ya llegaron no se reagrupan, y los 30 minutos para dormirse siguen siendo reales.",
    }),
    actual,
    crear("div", { clase: "reloj__atajos" }, ...atajos),
    formulario,
    aviso,
    error);

  let generacion = 0;

  function pintar(reloj) {
    actual.textContent = `Ahora: ${textoDelReloj(reloj)}.`;
    for (const boton of atajos) {
      boton.setAttribute("aria-pressed", String(Number(boton.dataset.segundos) === reloj.segundosPorHora));
    }
    aviso.hidden = reloj.segundosPorHora >= SEGUNDOS_ENTRE_LECTURAS;
    aviso.textContent = `La placa manda una lectura cada ${SEGUNDOS_ENTRE_LECTURAS} s: con horas de juego más cortas, ` +
      "algunas horas quedan sin lecturas y la matera crece más despacio.";
  }

  async function cambiar(boton, segundosPorHora) {
    mostrarError(error, null);
    let reloj;
    try {
      // La API recibe minutos reales por día de juego: 24 horas de juego.
      reloj = await ocupado(boton, () => cambiarRelojDeJuego((segundosPorHora * HORAS_POR_DIA) / 60));
    } catch (fallo) {
      mostrarError(error, fallo);
      return;
    }
    pintar(reloj);
  }

  return {
    async mostrar() {
      const mia = generacion;
      mostrarError(error, null);
      let reloj;
      try {
        reloj = await obtenerRelojDeJuego();
      } catch (fallo) {
        if (mia === generacion) mostrarError(error, fallo);
        return;
      }
      if (mia === generacion) pintar(reloj);
    },
    reiniciar() {
      generacion += 1;
      actual.textContent = "";
      aviso.hidden = true;
      mostrarError(error, null);
    },
  };
}
