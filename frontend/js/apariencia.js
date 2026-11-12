// Apariencia: el estilo (Profesional o Juego) y el tema (claro, oscuro, AMOLED o el del sistema).
//
// Es el único script clásico del front: va en <head>, sin defer ni módulo, para poner data-estilo y
// data-tema en <html> antes de que se pinte la página (así no se ve un momento con otro tema). Los colores y
// las formas están en css/variables.css; aquí solo se elige cuál juego de variables vale.
//
// - Sin elección guardada, el estilo depende del ancho: Juego con menos de 900 px (el celular) y Profesional
//   en pantallas anchas. El tema por defecto es «sistema»: sigue a prefers-color-scheme.
// - Lo que se elige se recuerda en este equipo (localStorage), no en la cuenta: cada equipo puede tener el
//   suyo. Si el navegador no deja guardar, la elección dura mientras la página esté abierta.
// - El selector está dos veces (el menú de la cabecera y la tarjeta de Mi cuenta): las dos copias salen de
//   la plantilla #plantilla-apariencia y se mantienen iguales.
// No habla con la API ni decide nada del negocio.
(function () {
  "use strict";

  var raiz = document.documentElement;
  var CLAVES = { estilo: "matera.apariencia.estilo", tema: "matera.apariencia.tema" };
  // La primera opción de cada lista es la de por defecto, que no se guarda.
  var OPCIONES = { estilo: ["auto", "profesional", "juego"], tema: ["sistema", "claro", "oscuro", "amoled"] };
  var NOMBRES = {
    profesional: "Profesional", juego: "Juego", claro: "claro", oscuro: "oscuro", amoled: "AMOLED",
  };
  var angosta = window.matchMedia("(max-width: 899.98px)");
  var oscura = window.matchMedia("(prefers-color-scheme: dark)");
  // Si no hay almacenamiento, lo elegido se guarda aquí mientras la página esté abierta.
  var enMemoria = {};

  function leer(tipo) {
    var valor = null;
    if (tipo in enMemoria) {
      valor = enMemoria[tipo];
    } else {
      try {
        valor = window.localStorage.getItem(CLAVES[tipo]);
      } catch (error) {
        // Sin almacenamiento (modo privado, datos bloqueados): vale el de por defecto.
      }
    }
    return OPCIONES[tipo].indexOf(valor) > 0 ? valor : OPCIONES[tipo][0];
  }

  function guardar(tipo, valor) {
    try {
      if (valor === OPCIONES[tipo][0]) window.localStorage.removeItem(CLAVES[tipo]);
      else window.localStorage.setItem(CLAVES[tipo], valor);
      delete enMemoria[tipo];
    } catch (error) {
      enMemoria[tipo] = valor; // sin almacenamiento: queda en la memoria de esta página
    }
  }

  function aplicar() {
    var estilo = leer("estilo");
    var tema = leer("tema");
    raiz.setAttribute("data-estilo", estilo === "auto" ? (angosta.matches ? "juego" : "profesional") : estilo);
    raiz.setAttribute("data-tema", tema === "sistema" ? (oscura.matches ? "oscuro" : "claro") : tema);
    pintarBarraDelNavegador();
    marcar();
  }

  // En el celular, la barra del navegador toma el color del fondo.
  function pintarBarraDelNavegador() {
    var meta = document.querySelector('meta[name="theme-color"]');
    var fondo = window.getComputedStyle(raiz).getPropertyValue("--fondo").trim();
    if (meta && fondo) meta.setAttribute("content", fondo);
  }

  // Marca en los dos selectores lo elegido y dice qué vale ahora.
  function marcar() {
    var entradas = document.querySelectorAll("input[data-apariencia]");
    for (var i = 0; i < entradas.length; i += 1) {
      entradas[i].checked = entradas[i].value === leer(entradas[i].getAttribute("data-apariencia"));
    }
    var texto = "Ahora: " + NOMBRES[raiz.getAttribute("data-estilo")] + ", tema " +
      NOMBRES[raiz.getAttribute("data-tema")] + ". Se recuerda en este equipo.";
    var notas = document.querySelectorAll("[data-apariencia-nota]");
    for (var j = 0; j < notas.length; j += 1) notas[j].textContent = texto;
  }

  // Copia la plantilla en cada lugar (la cabecera y Mi cuenta), con nombres de grupo propios.
  function armarSelectores() {
    var plantilla = document.getElementById("plantilla-apariencia");
    var lugares = document.querySelectorAll("[data-apariencia-lugar]");
    if (!plantilla) return;
    for (var i = 0; i < lugares.length; i += 1) {
      var lugar = lugares[i].getAttribute("data-apariencia-lugar");
      var copia = plantilla.content.cloneNode(true);
      var entradas = copia.querySelectorAll("input[data-apariencia]");
      for (var j = 0; j < entradas.length; j += 1) {
        entradas[j].name = entradas[j].getAttribute("data-apariencia") + "-" + lugar;
      }
      lugares[i].replaceChildren(copia);
    }
    document.addEventListener("change", function (evento) {
      var entrada = evento.target;
      if (!entrada.matches || !entrada.matches("input[data-apariencia]")) return;
      guardar(entrada.getAttribute("data-apariencia"), entrada.value);
      aplicar();
    });
    marcar();
  }

  function escuchar(consulta) {
    if (consulta.addEventListener) consulta.addEventListener("change", aplicar);
    else if (consulta.addListener) consulta.addListener(aplicar); // navegadores viejos
  }

  escuchar(angosta);
  escuchar(oscura);
  // Si se cambia en otra pestaña de este equipo, esta también cambia.
  window.addEventListener("storage", function (evento) {
    if (evento.key === null || evento.key === CLAVES.estilo || evento.key === CLAVES.tema) aplicar();
  });

  aplicar();
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () {
      armarSelectores();
      pintarBarraDelNavegador();
    });
  } else {
    armarSelectores();
  }
})();
