// Vincular sensor: se elige una planta propia y se escribe el código del dispositivo.
// La API entrega la clave una sola vez; después solo guarda su huella.
import { desvincularSensor, obtenerPlantas, vincularSensor } from "./api.js";
import { capitalizar } from "./formato.js";
import { mostrarError, ocupado } from "./formularios.js";
import { especieDe } from "./lecturas.js";

export function crearPantallaVincular(contexto, simulador) {
  const $ = (id) => document.getElementById(id);
  const selector = $("vincular-planta");
  let plantas = [];

  selector.addEventListener("change", () => {
    contexto.plantaElegida = Number(selector.value);
    ocultarClave();
    pintarEstado();
  });

  $("form-vincular").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const planta = elegida();
    if (!planta) return;
    let vinculado;
    try {
      vinculado = await ocupado($("boton-vincular"), () => vincularSensor(planta.id, $("codigo-sensor").value));
    } catch (error) {
      mostrarError($("error-vincular"), error);
      return;
    }
    mostrarError($("error-vincular"), null);
    $("codigo-sensor").value = "";
    $("clave-texto").textContent = vinculado.clave;
    $("clave-sensor").hidden = false;
    simulador.prellenar(vinculado.codigo, vinculado.clave, especieDe(contexto, planta.especie));
    await cargar();
  });

  $("boton-desvincular").addEventListener("click", async () => {
    const planta = elegida();
    if (!planta?.sensor) return;
    if (!window.confirm(`¿Desvincular el sensor ${planta.sensor.codigo} de «${planta.apodo}»? Su clave dejará de servir.`)) return;
    try {
      await desvincularSensor(planta.id);
    } catch (error) {
      mostrarError($("error-vincular"), error);
      return;
    }
    mostrarError($("error-vincular"), null);
    ocultarClave();
    await cargar();
  });

  $("copiar-clave").addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText($("clave-texto").textContent);
      $("copiar-clave").textContent = "Copiada";
    } catch {
      $("copiar-clave").textContent = "Selecciónela y cópiela a mano";
    }
  });

  function elegida() {
    return plantas.find((planta) => planta.id === Number(selector.value));
  }

  function ocultarClave() {
    $("clave-sensor").hidden = true;
    $("clave-texto").textContent = "";
    $("copiar-clave").textContent = "Copiar";
  }

  async function cargar() {
    try {
      plantas = await obtenerPlantas();
    } catch (error) {
      mostrarError($("error-vincular"), error);
      return;
    }
    selector.replaceChildren(...plantas.map((p) => new Option(`${p.apodo} · ${capitalizar(p.especie)}`, p.id)));
    const sigue = plantas.some((p) => p.id === contexto.plantaElegida);
    if (sigue) selector.value = String(contexto.plantaElegida);
    pintarEstado();
  }

  function pintarEstado() {
    const planta = elegida();
    const sinPlantas = plantas.length === 0;
    $("form-vincular").classList.toggle("vincular__formulario--vacio", sinPlantas);
    $("boton-vincular").disabled = sinPlantas;
    $("vincular-estado").textContent = sinPlantas
      ? "Primero agregue una planta en Mis materas."
      : planta.sensor
        ? `Esta planta tiene el sensor ${planta.sensor.codigo}. Para cambiarlo, desvincúlelo primero.`
        : "Esta planta todavía no tiene sensor.";
    $("boton-desvincular").hidden = !planta?.sensor;
  }

  return {
    mostrar() {
      ocultarClave();
      mostrarError($("error-vincular"), null);
      cargar();
    },
  };
}
