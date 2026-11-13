// Administración de cuentas. La pestaña solo aparece para un ADMIN, pero eso es comodidad: los permisos los
// revisa la API en cada caso de uso, y a cualquier otro le responde 403. Las especies se agregan en la
// pantalla Especies (especies.js).
import { cambiarUsuario, eliminarUsuario, obtenerUsuarios } from "./api.js";
import { crear, inicialDe } from "./formato.js";
import { mostrarError, ocupado } from "./formularios.js";
import { sesion } from "./sesion.js";

// En una pastilla, en mayúsculas como los estados.
const ROLES = { USUARIO: "USUARIO", ADMIN: "ADMINISTRADOR" };

export function crearPantallaAdmin() {
  const $ = (id) => document.getElementById(id);
  const dialogo = $("dialogo-eliminar");
  const formularioEliminar = $("form-eliminar");
  let aEliminar = null; // la cuenta del diálogo «¿Eliminar la cuenta?»
  // Cambia al cerrar la sesión: una respuesta que llega después ya no se pinta.
  let generacion = 0;

  async function mostrar() {
    const mia = generacion;
    mostrarError($("error-admin"), null);
    let usuarios;
    try {
      usuarios = await obtenerUsuarios();
    } catch (error) {
      if (mia === generacion) mostrarError($("error-admin"), error);
      return;
    }
    if (mia !== generacion) return;
    pintarCifras(usuarios);
    $("filas-usuarios").replaceChildren(...usuarios.map(fila));
  }

  // Solo cuenta lo que trajo GET /admin/usuarios.
  function pintarCifras(usuarios) {
    const cuantas = (condicion) => usuarios.filter(condicion).length;
    const plantas = usuarios.reduce((suma, usuario) => suma + usuario.cantidadPlantas, 0);
    const cifras = [
      ["Cuentas", usuarios.length],
      ["Activas", cuantas((u) => u.activo)],
      ["Administradores", cuantas((u) => u.rol === "ADMIN")],
      ["Plantas", plantas],
    ];
    $("admin-cifras").replaceChildren(...cifras.map(([nombre, valor]) =>
      crear("div", { clase: "cifra" },
        crear("span", { clase: "cifra__nombre", texto: nombre }),
        crear("span", { clase: "cifra__valor", texto: String(valor) }))));
  }

  // Cada celda lleva su rótulo en data-etiqueta: en el celular la tabla se ve como una tarjeta por cuenta.
  function fila(usuario) {
    const propia = usuario.id === sesion.usuario()?.id;
    const boton = (texto, accion, peligro = false) => {
      const nodo = crear("button", { clase: `boton-contorno${peligro ? " boton-contorno--peligro" : ""}`, texto });
      nodo.type = "button";
      nodo.addEventListener("click", () => accion(nodo));
      return nodo;
    };
    const celda = (etiqueta, clase, ...hijos) => {
      const nodo = crear("td", { clase }, ...hijos);
      if (etiqueta) nodo.dataset.etiqueta = etiqueta;
      return nodo;
    };
    const avatar = crear("span", { clase: "cuenta-fila__avatar", texto: inicialDe(usuario.nombre) });
    avatar.setAttribute("aria-hidden", "true");
    const nombre = crear("span", { clase: "cuenta-fila__nombre", texto: usuario.nombre });
    if (propia) nombre.append(crear("span", { clase: "cuenta-fila__usted", texto: " (usted)" }));
    const esAdmin = usuario.rol === "ADMIN";
    const nodo = crear("tr", { clase: usuario.activo ? "" : "cuenta-fila--inactiva" },
      celda(null, "",
        crear("div", { clase: "cuenta-fila" },
          avatar,
          crear("span", { clase: "cuenta-fila__textos" }, nombre, crear("span", { clase: "cuenta-fila__correo", texto: usuario.correo })))),
      celda("Rol", "", crear("span", {
        clase: `pastilla ${esAdmin ? "pastilla--admin" : "pastilla--inactiva"}`, texto: ROLES[usuario.rol] ?? usuario.rol,
      })),
      celda("Estado", "", crear("span", {
        clase: `pastilla ${usuario.activo ? "pastilla--activa" : "pastilla--inactiva"}`,
        texto: usuario.activo ? "ACTIVA" : "DESACTIVADA",
      })),
      celda("Plantas", "tabla__numero", String(usuario.cantidadPlantas)),
      celda(null, "tabla__acciones-celda",
        crear("div", { clase: "tabla__acciones" },
          boton(usuario.activo ? "Desactivar" : "Reactivar", (b) => cambiar(b, usuario, { activo: !usuario.activo })),
          boton(esAdmin ? "Quitar admin" : "Dar admin", (b) => cambiar(b, usuario, { rol: esAdmin ? "USUARIO" : "ADMIN" })),
          boton("Eliminar", () => pedirConfirmacion(usuario), true))));
    if (propia) nodo.classList.add("cuenta-fila--propia");
    return nodo;
  }

  async function cambiar(nodo, usuario, cambio) {
    try {
      await ocupado(nodo, () => cambiarUsuario(usuario.id, cambio));
    } catch (error) {
      mostrarError($("error-admin"), error);
      $("error-admin").scrollIntoView({ block: "nearest" });
      return;
    }
    mostrar();
  }

  // ---- eliminar: no tiene vuelta atrás, así que se pide escribir el correo de la cuenta ----

  function pedirConfirmacion(usuario) {
    aEliminar = usuario;
    formularioEliminar.reset();
    mostrarError($("error-eliminar"), null);
    $("eliminar-texto").textContent =
      `Se eliminará la cuenta de ${usuario.nombre} (${usuario.correo}) con sus plantas, sensores e historial. No se puede deshacer.`;
    dialogo.showModal();
    $("eliminar-correo").focus();
  }

  $("eliminar-cancelar").addEventListener("click", () => dialogo.close());
  // El evento close llega después: si el diálogo ya se abrió para otra cuenta, esa se conserva.
  dialogo.addEventListener("close", () => {
    if (!dialogo.open) aEliminar = null;
  });

  formularioEliminar.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    const usuario = aEliminar;
    if (!usuario) return;
    if ($("eliminar-correo").value.trim().toLowerCase() !== usuario.correo) {
      mostrarError($("error-eliminar"), { codigo: "CONFIRMACION", message: "El correo no coincide. No se eliminó nada.", detalle: {} });
      $("eliminar-correo").focus();
      return;
    }
    try {
      await ocupado($("eliminar-confirmar"), () => eliminarUsuario(usuario.id));
    } catch (error) {
      mostrarError($("error-eliminar"), error);
      return;
    }
    dialogo.close();
    mostrar();
  });

  return {
    mostrar,
    // Al salir de Administración (también al cerrar la sesión), el diálogo no queda abierto encima de otra pantalla.
    ocultar() {
      if (dialogo.open) dialogo.close();
    },
    // Al cerrar la sesión no quedan en la página los nombres ni los correos de las cuentas.
    reiniciar() {
      generacion += 1;
      if (dialogo.open) dialogo.close();
      aEliminar = null;
      $("filas-usuarios").replaceChildren();
      $("admin-cifras").replaceChildren();
      mostrarError($("error-admin"), null);
    },
  };
}
