// Web: en Mi cuenta, el QR para apuntar la app Android a este servidor. Lleva el enlace de la app
// (co.edu.usergioarboleda.matera://servidor?api=<dirección>): con la cámara del celular, la app se abre y
// propone esa dirección (servidor-app.js). Al lado va la dirección en texto, por si la cámara no ofrece abrir
// la app, y en un celular, un enlace que abre la app directamente.
// La dirección sale de GET /red (las del PC que alcanza la red local, la de la ruta por defecto primero), o de
// la que ya usa este front si se abrió desde la red. En la app no se muestra: ahí está la tarjeta «Servidor».
import { obtenerRed } from "./api.js";
import { API_BASE, API_EN_ESTE_EQUIPO } from "./config.js";
import { enlaceDeServidor } from "./direccion-api.js";
import { crear } from "./formato.js";
import { mostrarError } from "./formularios.js";
import { EN_APP } from "./plataforma.js";
import { qrComoSvg } from "./qr.js";

const MAXIMO_DE_DIRECCIONES = 4; // como el asistente: las demás suelen ser adaptadores virtuales
const SIN_RED = "Este backend solo responde en este PC, así que el celular no lo alcanza. Arránquelo con " +
  "MATERA_HOST=0.0.0.0 (y permita el puerto en el firewall) y vuelva a abrir Mi cuenta.";

const $ = (id) => document.getElementById(id);
let vuelta = 0; // una respuesta de una visita anterior a Mi cuenta se descarta

export async function pintarQrDelServidor() {
  const tarjeta = $("cuenta-app");
  if (EN_APP || !tarjeta) return;
  const mia = ++vuelta;
  tarjeta.hidden = false;
  mostrarError($("error-cuenta-app"), null);
  $("cuenta-app-aviso").hidden = true;
  let direcciones = API_EN_ESTE_EQUIPO ? [] : [API_BASE];
  try {
    const { servidores = [] } = await obtenerRed();
    direcciones = [...new Set([...direcciones, ...servidores])].slice(0, MAXIMO_DE_DIRECCIONES);
  } catch (error) {
    if (mia !== vuelta) return;
    if (!direcciones.length) {
      vaciar();
      mostrarError($("error-cuenta-app"), error);
      return;
    }
  }
  if (mia !== vuelta) return;
  if (!direcciones.length) {
    vaciar();
    $("cuenta-app-aviso").textContent = SIN_RED;
    $("cuenta-app-aviso").hidden = false;
    return;
  }
  mostrar(direcciones, direcciones[0]);
}

export function quitarQrDelServidor() {
  vuelta += 1;
  const tarjeta = $("cuenta-app");
  if (!tarjeta) return;
  vaciar();
  mostrarError($("error-cuenta-app"), null);
  $("cuenta-app-aviso").hidden = true;
  tarjeta.hidden = true;
}

function mostrar(direcciones, elegida) {
  const enlace = enlaceDeServidor(elegida);
  $("cuenta-app-qr").replaceChildren(qrComoSvg(enlace, { titulo: `QR para abrir la app Matera con el servidor ${elegida}` }));
  $("cuenta-app-qr").hidden = false;
  $("cuenta-app-direccion").textContent = elegida;
  $("cuenta-app-abrir").href = enlace;
  $("cuenta-app-abrir").hidden = false;
  const otras = direcciones.filter((d) => d !== elegida);
  $("cuenta-app-otras").replaceChildren(...(otras.length
    ? [crear("p", { clase: "formulario__ayuda", texto: "¿El celular está en otra red? Otras direcciones de este PC:" }),
      ...otras.map((direccion) => {
        const boton = crear("button", { clase: "boton-contorno", texto: new URL(direccion).host });
        boton.type = "button";
        boton.title = direccion;
        boton.addEventListener("click", () => mostrar(direcciones, direccion));
        return boton;
      })]
    : []));
  $("cuenta-app-otras").hidden = !otras.length;
}

function vaciar() {
  $("cuenta-app-qr").replaceChildren();
  $("cuenta-app-qr").hidden = true;
  $("cuenta-app-direccion").textContent = "";
  $("cuenta-app-abrir").removeAttribute("href");
  $("cuenta-app-abrir").hidden = true;
  $("cuenta-app-otras").replaceChildren();
  $("cuenta-app-otras").hidden = true;
}
