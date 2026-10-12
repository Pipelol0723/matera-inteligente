// Simular sensor: manda una medición como lo haría el ESP32, con el código y la clave del sensor
// y sin sesión. Sirve para probar el recorrido completo sin el dispositivo.
import { enviarComoSensor } from "./api.js";
import { nombreDeEstado } from "./formato.js";
import { botonDe, mostrarError, mostrarExito, ocupado } from "./formularios.js";
import { crearCamposMedicion } from "./lecturas.js";

export function crearSimulador(contexto) {
  const $ = (id) => document.getElementById(id);
  let campos = null;

  $("form-simulador").addEventListener("submit", async (evento) => {
    evento.preventDefault();
    mostrarExito($("resultado-simulador"), null);
    let respuesta;
    try {
      respuesta = await ocupado(botonDe(evento), () =>
        enviarComoSensor($("sim-codigo").value, $("sim-clave").value, campos.leer()));
    } catch (error) {
      mostrarError($("error-simulador"), error);
      return;
    }
    mostrarError($("error-simulador"), null);
    const { planta, diagnostico } = respuesta;
    mostrarExito($("resultado-simulador"),
      `Guardada en «${planta.apodo}»: ${nombreDeEstado(diagnostico.estado)}. Ya aparece en Mis materas y en el Historial.`);
  });

  function alCargarCatalogos() {
    campos = crearCamposMedicion(contexto.parametros, "simular");
    $("sim-campos").replaceChildren(campos.nodo);
  }

  // Justo después de vincular, el simulador queda listo con el código y la clave.
  function prellenar(codigo, clave, especie) {
    $("sim-codigo").value = codigo;
    $("sim-clave").value = clave;
    campos?.proponer(especie);
    mostrarError($("error-simulador"), null);
    mostrarExito($("resultado-simulador"), null);
  }

  return { alCargarCatalogos, prellenar };
}
