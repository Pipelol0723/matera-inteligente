// Sesión en este navegador. El token vive en sessionStorage: se borra al cerrar la pestaña.
// Tensión reconocida: un script inyectado podría leerlo. Una cookie HttpOnly exigiría HTTPS y
// SameSite=None, porque el front se sirve desde otro origen que la API (RA2).
const CLAVE = "matera.sesion";

function leer() {
  try {
    return JSON.parse(sessionStorage.getItem(CLAVE)) ?? null;
  } catch {
    return null;
  }
}

function guardar(valor) {
  try {
    if (valor) sessionStorage.setItem(CLAVE, JSON.stringify(valor));
    else sessionStorage.removeItem(CLAVE);
  } catch {
    // Sin almacenamiento (modo privado estricto): la sesión dura lo que dure la página.
  }
}

let actual = leer();

export const sesion = {
  token: () => actual?.token ?? null,
  usuario: () => actual?.usuario ?? null,
  activa: () => Boolean(actual?.token),
  // El rol lo dice la API; mostrar u ocultar la pestaña de administración es solo comodidad.
  esAdmin: () => actual?.usuario?.rol === "ADMIN",

  abrir(token, usuario) {
    actual = { token, usuario };
    guardar(actual);
  },

  actualizarUsuario(usuario) {
    if (!actual) return;
    actual = { ...actual, usuario };
    guardar(actual);
  },

  cerrar() {
    actual = null;
    guardar(null);
  },
};
