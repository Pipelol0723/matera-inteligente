// Mi cuenta: los datos de GET /usuarios/yo y el botón para cerrar sesión.
import { cerrarSesion, obtenerMiCuenta } from "./api.js";
import { crear } from "./formato.js";
import { mostrarError } from "./formularios.js";
import { sesion } from "./sesion.js";

const ROLES = { USUARIO: "Usuario", ADMIN: "Administrador" };

export function crearPantallaCuenta(contexto) {
  const $ = (id) => document.getElementById(id);

  $("cerrar-sesion").addEventListener("click", async () => {
    try {
      await cerrarSesion();
    } catch {
      // Si la API no responde, la sesión igual se cierra en este navegador.
    }
    sesion.cerrar();
    contexto.alCerrarSesion();
  });

  async function mostrar() {
    mostrarError($("error-cuenta"), null);
    let cuenta;
    try {
      cuenta = await obtenerMiCuenta();
    } catch (error) {
      mostrarError($("error-cuenta"), error);
      return;
    }
    const { plantas, ...usuario } = cuenta;
    sesion.actualizarUsuario(usuario);
    contexto.alCambiarUsuario();
    const filas = [
      ["Nombre", usuario.nombre],
      ["Correo", usuario.correo],
      ["Rol", ROLES[usuario.rol] ?? usuario.rol],
      ["Plantas", String(plantas)],
    ];
    $("datos-cuenta").replaceChildren(...filas.map(([nombre, valor]) =>
      crear("div", { clase: "resumen__fila" },
        crear("span", { clase: "resumen__nombre", texto: nombre }),
        crear("span", { clase: "cuenta__valor", texto: valor }))));
  }

  return { mostrar };
}
