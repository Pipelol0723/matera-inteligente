// Interfaz: muestra lo que responde la API. No conoce rangos, umbrales ni reglas:
// los estados y las recomendaciones llegan ya decididos desde el backend.
import { obtenerEspecies, pedirDiagnostico } from "./api.js";

const $ = (id) => document.getElementById(id);
const formulario = $("formulario");
const selector = $("especie");
const boton = $("diagnosticar");

const ETIQUETAS = { humedad: "Humedad", luz: "Luz", temperatura: "Temperatura" };
const UNIDADES = { C: "°C" };
const numero = new Intl.NumberFormat("es-CO", { maximumFractionDigits: 2 });

let especies = [];

const capitalizar = (texto) => texto.charAt(0).toUpperCase() + texto.slice(1);
const etiqueta = (nombre) => ETIQUETAS[nombre] ?? capitalizar(nombre);
const unidad = (simbolo) => UNIDADES[simbolo] ?? simbolo;

function elemento(tipo, texto, clase) {
  const nodo = document.createElement(tipo);
  if (texto !== undefined) nodo.textContent = texto;
  if (clase) nodo.className = clase;
  return nodo;
}

function chipEstado(estado) {
  return elemento("span", estado.replace("_", " "), `estado estado--${estado.toLowerCase()}`);
}

async function cargarEspecies() {
  try {
    especies = await obtenerEspecies();
    selector.replaceChildren(...especies.map((e) => new Option(capitalizar(e.nombre), e.nombre)));
    selector.disabled = false;
    boton.disabled = false;
    mostrarRangos();
  } catch (error) {
    selector.replaceChildren(new Option("No se pudieron cargar las especies"));
    mostrarError(error);
  }
}

function mostrarRangos() {
  const especie = especies.find((e) => e.nombre === selector.value);
  const filas = Object.entries(especie?.rangos ?? {}).flatMap(([nombre, rango]) => [
    elemento("dt", etiqueta(nombre)),
    elemento("dd", `${numero.format(rango.min)} – ${numero.format(rango.max)} ${unidad(rango.unidad)}`),
  ]);
  $("rangos").replaceChildren(...filas);
}

function leerFormulario() {
  const datos = { especie: selector.value };
  for (const campo of formulario.querySelectorAll("[data-parametro]")) {
    // Se envía lo que la persona escribió: el backend es el único que valida.
    const texto = campo.value.trim();
    datos[campo.name] = texto === "" ? null : texto;
  }
  return datos;
}

async function enviar(datos) {
  limpiar();
  boton.disabled = true;
  boton.textContent = "Consultando…";
  try {
    mostrarDiagnostico(await pedirDiagnostico(datos));
  } catch (error) {
    mostrarError(error);
  } finally {
    boton.disabled = false;
    boton.textContent = "Diagnosticar";
  }
}

function mostrarDiagnostico(diagnostico) {
  $("resultado-especie").textContent = capitalizar(diagnostico.especie);
  const estadoGlobal = $("resultado-estado");
  estadoGlobal.textContent = diagnostico.estado.replace("_", " ");
  estadoGlobal.className = `estado estado--${diagnostico.estado.toLowerCase()}`;

  const filas = diagnostico.parametros.map((p) => {
    const fila = document.createElement("tr");
    const celdaEstado = elemento("td");
    celdaEstado.append(chipEstado(p.estado));
    fila.append(
      elemento("td", etiqueta(p.nombre)),
      elemento("td", `${numero.format(p.valor)} ${unidad(p.unidad)}`, "numero"),
      elemento("td", `${numero.format(p.rangoOptimo[0])} – ${numero.format(p.rangoOptimo[1])}`, "numero"),
      celdaEstado,
    );
    return fila;
  });
  $("resultado-parametros").replaceChildren(...filas);

  const recomendaciones = diagnostico.recomendaciones.length
    ? diagnostico.recomendaciones.map((texto) => elemento("li", texto))
    : [elemento("li", "Sin recomendaciones: todos los parámetros están en su rango óptimo.", "recomendaciones__vacio")];
  $("resultado-recomendaciones").replaceChildren(...recomendaciones);

  $("resultado").hidden = false;
}

function mostrarError(error) {
  $("error-codigo").textContent = error.status ? `${error.status} · ${error.codigo}` : error.codigo;
  $("error-mensaje").textContent = error.message;
  $("error").hidden = false;

  const nombreCampo = error.detalle?.campo;
  const campo = nombreCampo ? formulario.elements.namedItem(nombreCampo) : null;
  if (campo) {
    campo.setAttribute("aria-invalid", "true");
    campo.focus();
  }
}

function limpiar() {
  $("resultado").hidden = true;
  $("error").hidden = true;
  for (const campo of formulario.querySelectorAll("[aria-invalid]")) {
    campo.removeAttribute("aria-invalid");
  }
}

// Peticiones inválidas de ejemplo para mostrar el manejo de errores de RF6.
const PRUEBAS_DE_ERROR = {
  "especie-inexistente": (base) => ({ ...base, especie: "planta-que-no-existe" }),
  "parametro-ausente": (base) => ({ ...base, humedad: null }),
  "no-numerico": (base) => ({ ...base, luz: "mucha" }),
  "fisicamente-imposible": (base) => ({ ...base, humedad: 150 }),
};

function probarError(evento) {
  const prueba = PRUEBAS_DE_ERROR[evento.target.closest("[data-prueba]")?.dataset.prueba];
  if (!prueba) return;
  const base = { especie: selector.value || "sansevieria", humedad: 30, luz: 800, temperatura: 22 };
  enviar(prueba(base));
}

selector.addEventListener("change", mostrarRangos);
formulario.addEventListener("submit", (evento) => {
  evento.preventDefault();
  enviar(leerFormulario());
});
document.querySelector(".pruebas__botones").addEventListener("click", probarError);

cargarEspecies();
