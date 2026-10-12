// Administración: cuentas y especies. La pestaña solo aparece para un ADMIN, pero eso es comodidad:
// los permisos los revisa la API en cada caso de uso, y a cualquier otro le responde 403.
import { agregarEspecie, cambiarUsuario, eliminarUsuario, obtenerUsuarios } from "./api.js";
import { crear, etiqueta, unidad } from "./formato.js";
import { botonDe, mostrarError, mostrarExito, ocupado } from "./formularios.js";
import { sesion } from "./sesion.js";

const ROLES = { USUARIO: "Usuario", ADMIN: "Administrador" };

export function crearPantallaAdmin(contexto) {
  const $ = (id) => document.getElementById(id);
  const formulario = $("form-especie");

  formulario.addEventListener("submit", async (evento) => {
    evento.preventDefault();
    mostrarExito($("exito-especie"), null);
    let especie;
    try {
      especie = await ocupado(botonDe(evento), () => agregarEspecie(leerEspecie()));
    } catch (error) {
      mostrarError($("error-especie"), error);
      return;
    }
    mostrarError($("error-especie"), null);
    formulario.reset();
    mostrarExito($("exito-especie"),
      `Especie «${especie.nombre}» agregada. Ya aparece en Especies y se puede usar en Mis materas.`);
    contexto.recargarCatalogos();
  });

  // Un mínimo y un máximo por cada parámetro de GET /parametros: si se agrega el pH, aparece solo.
  function alCargarCatalogos() {
    $("rangos-especie").replaceChildren(...contexto.parametros.map((parametro) => {
      const limite = (cual) => {
        const entrada = crear("input", { clase: "formulario__campo admin__limite" });
        Object.assign(entrada, { name: `${parametro.nombre}-${cual}`, inputMode: "decimal", autocomplete: "off", placeholder: cual });
        entrada.setAttribute("aria-label", `${etiqueta(parametro.nombre)}, ${cual === "min" ? "mínimo" : "máximo"}`);
        return entrada;
      };
      return crear("div", { clase: "admin__rango" },
        crear("span", { clase: "formulario__etiqueta", texto: `${etiqueta(parametro.nombre)} (${unidad(parametro.unidad)})` }),
        limite("min"),
        limite("max"));
    }));
  }

  // Se envía lo escrito: un número si se puede leer como número, y si no, el texto, para que la API lo rechace.
  function leerEspecie() {
    const valor = (nombre) => {
      const texto = (formulario.elements[nombre]?.value ?? "").trim();
      const numero = Number(texto.replace(",", "."));
      return texto === "" ? null : Number.isFinite(numero) ? numero : texto;
    };
    return {
      nombre: formulario.elements.nombre.value,
      nombreCientifico: formulario.elements.nombreCientifico.value,
      rangos: Object.fromEntries(contexto.parametros.map((p) => [
        p.nombre, { min: valor(`${p.nombre}-min`), max: valor(`${p.nombre}-max`) },
      ])),
    };
  }

  async function mostrar() {
    mostrarError($("error-admin"), null);
    let usuarios;
    try {
      usuarios = await obtenerUsuarios();
    } catch (error) {
      mostrarError($("error-admin"), error);
      return;
    }
    $("filas-usuarios").replaceChildren(...usuarios.map(fila));
  }

  function fila(usuario) {
    const propia = usuario.id === sesion.usuario()?.id;
    const boton = (texto, accion, peligro = false) => {
      const nodo = crear("button", { clase: `boton-contorno${peligro ? " boton-contorno--peligro" : ""}`, texto });
      nodo.type = "button";
      nodo.addEventListener("click", () => accion(nodo));
      return nodo;
    };
    const estado = crear("span", {
      clase: `pastilla ${usuario.activo ? "pastilla--activa" : "pastilla--inactiva"}`,
      texto: usuario.activo ? "ACTIVA" : "DESACTIVADA",
    });
    return crear("tr", {},
      crear("td", { clase: "tabla__fuerte", texto: propia ? `${usuario.nombre} (usted)` : usuario.nombre }),
      crear("td", { texto: usuario.correo }),
      crear("td", { texto: ROLES[usuario.rol] ?? usuario.rol }),
      crear("td", {}, estado),
      crear("td", { clase: "tabla__numero", texto: String(usuario.cantidadPlantas) }),
      crear("td", {},
        crear("div", { clase: "tabla__acciones" },
          boton(usuario.activo ? "Desactivar" : "Reactivar", (nodo) => cambiar(nodo, usuario, { activo: !usuario.activo })),
          boton(usuario.rol === "ADMIN" ? "Quitar admin" : "Dar admin",
            (nodo) => cambiar(nodo, usuario, { rol: usuario.rol === "ADMIN" ? "USUARIO" : "ADMIN" })),
          boton("Eliminar", (nodo) => eliminar(nodo, usuario), true))));
  }

  async function cambiar(nodo, usuario, cambio) {
    try {
      await ocupado(nodo, () => cambiarUsuario(usuario.id, cambio));
    } catch (error) {
      mostrarError($("error-admin"), error);
      return;
    }
    mostrar();
  }

  async function eliminar(nodo, usuario) {
    // Eliminar no tiene vuelta atrás: se pide escribir el correo de la cuenta.
    const escrito = window.prompt(
      `Se eliminará la cuenta de ${usuario.nombre} con sus plantas, sensores e historial. Escriba su correo para confirmar:`);
    if (escrito === null) return;
    if (escrito.trim().toLowerCase() !== usuario.correo) {
      mostrarError($("error-admin"), { codigo: "CONFIRMACION", message: "El correo no coincide. No se eliminó nada.", detalle: {} });
      return;
    }
    try {
      await ocupado(nodo, () => eliminarUsuario(usuario.id));
    } catch (error) {
      mostrarError($("error-admin"), error);
      return;
    }
    mostrar();
  }

  return { mostrar, alCargarCatalogos };
}
