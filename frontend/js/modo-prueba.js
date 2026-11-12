// Modo prueba (solo admins): ponerle a una matera propia un estado de mentira para ver cómo se dibuja, en la
// app y en la pantalla de la placa (en su próxima lectura), y volverla a lo normal. Solo cambia el dibujo:
// los puntos y el diagnóstico siguen siendo los reales. Quién puede usarlo lo decide la API
// (PUT y DELETE /juego/materas/{id}/prueba responden 403 a quien no es ADMIN); que el panel solo se vea si
// la cuenta es ADMIN es comodidad. Aquí no se calcula nada: solo se elige qué valor mandar.
import { ponerEstadoDePrueba, quitarEstadoDePrueba } from "./api.js";
import { crear } from "./formato.js";
import { mostrarError, ocupado } from "./formularios.js";

const OPCIONES = {
  etapa: [
    ["SEMILLA", "Semilla"],
    ["BROTE", "Brote"],
    ["PLANTA", "Planta joven"],
    ["FLORECIDA", "Planta florecida"],
  ],
  condicion: [
    ["SANA", "Sana"],
    ["DECAIDA", "Decaída"],
    ["MARCHITA", "Marchita"],
  ],
  cara: [
    ["SALUDABLE", "Feliz (SALUDABLE)"],
    ["EN_RIESGO", "Preocupada (EN RIESGO)"],
    ["CRITICO", "Triste (CRÍTICO)"],
  ],
  necesidad: [
    ["", "Sin globo"],
    ["SED", "¡Tengo sed!"],
    ["EXCESO_AGUA", "¡Me ahogo!"],
    ["FRIO", "¡Tengo frío!"],
    ["CALOR", "¡Tengo calor!"],
    ["POCA_LUZ", "¡Poca luz!"],
    ["MUCHA_LUZ", "¡Mucha luz!"],
  ],
};

const ROTULOS = { etapa: "Tamaño", condicion: "Condición", cara: "Cara", necesidad: "Globo" };

let contador = 0;

// El panel plegable de una matera. mascotaActual() da lo que la API dice ahora de esa matera, para llenar
// el formulario al abrirlo; alCambiar() pide a la app volver a consultar el juego.
export function panelDePrueba(planta, { mascotaActual, alCambiar }) {
  const id = `prueba-${planta.id}-${++contador}`;
  const selectores = {};
  const campos = Object.keys(OPCIONES).map((campo) => {
    const selector = crear("select", { clase: "selector" },
      ...OPCIONES[campo].map(([valor, texto]) => {
        const opcion = crear("option", { texto });
        opcion.value = valor;
        return opcion;
      }));
    selector.id = `${id}-${campo}`;
    selectores[campo] = selector;
    const etiqueta = crear("label", { clase: "formulario__etiqueta", texto: ROTULOS[campo] });
    etiqueta.htmlFor = selector.id;
    return crear("div", { clase: "prueba__campo" }, etiqueta, selector);
  });

  const dormida = crear("input");
  dormida.type = "checkbox";
  dormida.id = `${id}-dormida`;
  const etiquetaDormida = crear("label", { clase: "prueba__dormida" }, dormida, " Dormida (sin globo)");
  etiquetaDormida.htmlFor = dormida.id;
  dormida.addEventListener("change", () => {
    selectores.necesidad.disabled = dormida.checked;
  });

  const estado = crear("p", { clase: "prueba__estado" });
  estado.setAttribute("role", "status");
  const error = crear("div", { clase: "tarjeta-error" });
  error.setAttribute("role", "alert");
  error.hidden = true;

  const aplicar = crear("button", { clase: "boton-primario", texto: "Ver este estado" });
  aplicar.type = "submit";
  const normal = crear("button", { clase: "boton-contorno", texto: "Volver a lo normal" });
  normal.type = "button";

  const formulario = crear("form", { clase: "prueba__formulario" },
    crear("div", { clase: "prueba__campos" }, ...campos),
    etiquetaDormida,
    crear("p", {
      clase: "prueba__ayuda",
      texto: "Solo cambia el dibujo, en la app y en la pantalla de la placa (en su próxima lectura). " +
        "Los puntos y el diagnóstico siguen siendo los reales.",
    }),
    crear("div", { clase: "prueba__acciones" }, aplicar, normal),
    estado,
    error);

  const panel = crear("details", { clase: "matera__prueba" },
    crear("summary", { clase: "prueba__titulo", texto: "Modo prueba · solo administradores" }),
    formulario);

  // Al abrir, el formulario muestra lo que se ve ahora: la prueba puesta, o el estado real.
  panel.addEventListener("toggle", () => {
    if (!panel.open) return;
    const matera = mascotaActual();
    const actual = matera?.prueba ?? matera;
    if (actual) {
      for (const campo of Object.keys(OPCIONES)) {
        const valor = actual[campo] ?? "";
        if (OPCIONES[campo].some(([opcion]) => opcion === valor)) selectores[campo].value = valor;
      }
      dormida.checked = Boolean(actual.dormida);
      selectores.necesidad.disabled = dormida.checked;
    }
    estado.textContent = matera?.prueba ? "Esta matera está en modo prueba." : "";
  });

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const datos = {
      etapa: selectores.etapa.value,
      condicion: selectores.condicion.value,
      cara: selectores.cara.value,
      dormida: dormida.checked,
      necesidad: dormida.checked || !selectores.necesidad.value ? null : selectores.necesidad.value,
    };
    await enviar(aplicar, () => ponerEstadoDePrueba(planta.id, datos), "Listo: la matera se ve con el estado de prueba.");
  });

  normal.addEventListener("click", () =>
    enviar(normal, () => quitarEstadoDePrueba(planta.id), "Listo: la matera volvió a su estado real."));

  async function enviar(boton, pedido, mensaje) {
    estado.textContent = "";
    try {
      await ocupado(boton, pedido);
    } catch (problema) {
      mostrarError(error, problema);
      return;
    }
    mostrarError(error, null);
    estado.textContent = mensaje;
    alCambiar();
  }

  return panel;
}
