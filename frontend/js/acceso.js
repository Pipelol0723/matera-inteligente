// Pantalla Ingresar / Crear cuenta. El correo, la contraseña y el nombre los valida la API.
// Los dos formularios comparten una tarjeta: dos pestañas (role="tab") eligen cuál se ve.
import { iniciarSesion, registrarse } from "./api.js";
import { botonDe, datosDe, mostrarError, ocupado } from "./formularios.js";
import { sesion } from "./sesion.js";

export function crearPantallaAcceso(contexto) {
  const $ = (id) => document.getElementById(id);
  const ingresar = $("form-ingresar");
  const registrar = $("form-registrar");
  const pestanas = { ingresar: $("pestana-ingresar"), registrar: $("pestana-registrar") };
  const formularios = { ingresar, registrar };
  const primerCampo = { ingresar: "ingresar-correo", registrar: "registrar-nombre" };
  let visible = "ingresar";

  ingresar.addEventListener("submit", (evento) => {
    evento.preventDefault();
    const { correo, contrasena } = datosDe(ingresar);
    entrar(correo, contrasena, $("error-ingresar"), botonDe(evento));
  });

  registrar.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const datos = datosDe(registrar);
    try {
      await ocupado(botonDe(evento), () => registrarse(datos));
    } catch (error) {
      mostrarError($("error-registrar"), error);
      return;
    }
    // Recién creada la cuenta, se entra con los mismos datos.
    entrar(datos.correo, datos.contrasena, $("error-registrar"), botonDe(evento));
  });

  // ---- las dos pestañas ----

  function elegir(cual, { enfocar = "campo" } = {}) {
    visible = cual;
    for (const [nombre, pestana] of Object.entries(pestanas)) {
      const activa = nombre === cual;
      pestana.setAttribute("aria-selected", String(activa));
      pestana.tabIndex = activa ? 0 : -1;
      formularios[nombre].hidden = !activa;
    }
    if (enfocar === "pestana") pestanas[cual].focus();
    else if (enfocar === "campo") $(primerCampo[cual]).focus();
  }

  for (const [nombre, pestana] of Object.entries(pestanas)) {
    pestana.addEventListener("click", () => elegir(nombre));
    // Con las flechas se pasa de una pestaña a la otra, como en cualquier lista de pestañas.
    pestana.addEventListener("keydown", (evento) => {
      if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(evento.key)) return;
      evento.preventDefault();
      elegir(nombre === "ingresar" ? "registrar" : "ingresar", { enfocar: "pestana" });
    });
  }

  // «¿Todavía no tiene cuenta? Créela aquí» y «¿Ya tiene cuenta? Ingrese».
  for (const enlace of document.querySelectorAll("[data-acceso-ir]")) {
    enlace.addEventListener("click", () => elegir(enlace.dataset.accesoIr));
  }

  // Mostrar u ocultar lo escrito en la contraseña.
  for (const boton of document.querySelectorAll("[data-mostrar-clave]")) {
    boton.addEventListener("click", () => {
      const campo = $(boton.dataset.mostrarClave);
      const mostrar = campo.type === "password";
      campo.type = mostrar ? "text" : "password";
      boton.textContent = mostrar ? "Ocultar" : "Mostrar";
      boton.setAttribute("aria-pressed", String(mostrar));
    });
  }

  function ocultarClaves() {
    for (const boton of document.querySelectorAll("[data-mostrar-clave]")) {
      $(boton.dataset.mostrarClave).type = "password";
      boton.textContent = "Mostrar";
      boton.setAttribute("aria-pressed", "false");
    }
  }

  async function entrar(correo, contrasena, cajaError, boton) {
    try {
      const respuesta = await ocupado(boton, () => iniciarSesion({ correo, contrasena }));
      sesion.abrir(respuesta.token, respuesta.usuario);
    } catch (error) {
      mostrarError(cajaError, error);
      return;
    }
    for (const formulario of [ingresar, registrar]) formulario.reset();
    ocultarClaves();
    mostrarError($("error-ingresar"), null);
    mostrarError($("error-registrar"), null);
    elegir("ingresar", { enfocar: "nada" });
    contexto.alIniciarSesion();
  }

  return {
    mostrar() {
      $(primerCampo[visible]).focus();
    },
  };
}
