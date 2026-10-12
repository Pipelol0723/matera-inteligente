// Pantalla Ingresar / Crear cuenta. El correo, la contraseña y el nombre los valida la API.
import { iniciarSesion, registrarse } from "./api.js";
import { botonDe, datosDe, mostrarError, ocupado } from "./formularios.js";
import { sesion } from "./sesion.js";

export function crearPantallaAcceso(contexto) {
  const $ = (id) => document.getElementById(id);
  const ingresar = $("form-ingresar");
  const registrar = $("form-registrar");

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

  async function entrar(correo, contrasena, cajaError, boton) {
    try {
      const respuesta = await ocupado(boton, () => iniciarSesion({ correo, contrasena }));
      sesion.abrir(respuesta.token, respuesta.usuario);
    } catch (error) {
      mostrarError(cajaError, error);
      return;
    }
    for (const formulario of [ingresar, registrar]) formulario.reset();
    mostrarError($("error-ingresar"), null);
    mostrarError($("error-registrar"), null);
    contexto.alIniciarSesion();
  }

  return {
    mostrar() {
      $("ingresar-correo").focus();
    },
  };
}
