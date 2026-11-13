// La dirección de la API en la app Android. En la web, config.js la deduce del equipo que abrió el front; en
// la app la página vive en el celular (https://localhost), así que la persona la elige la primera vez y queda
// guardada en este celular (localStorage). Aquí solo se lee, se guarda y se escribe en una forma única; si de
// verdad es la API, lo prueba servidor-app.js preguntándole a ella.
//
// También arma y lee el enlace que abre la app con un servidor propuesto, el del QR de Mi cuenta:
// co.edu.usergioarboleda.matera://servidor?api=<dirección de la API>.
import { ESQUEMA_APP } from "./plataforma.js";

const GUARDADA = "matera.app.api";
const PUERTO_DEL_BACKEND = "5000"; // el de siempre (MATERA_PUERTO), si se escribe solo la IP
const PREFIJO = "/api/v1";
const HOST_DEL_ENLACE = "servidor";

// Empieza con un esquema («http://», «https://», «co.edu...://»).
const CON_ESQUEMA = /^[a-z][a-z0-9+.-]*:\/\//i;

export function leerDireccionGuardada() {
  try {
    return normalizarDireccion(localStorage.getItem(GUARDADA) ?? "");
  } catch {
    return null;
  }
}

// Falla si el celular no deja guardar (sin almacenamiento): quien la llama lo muestra.
export function guardarDireccion(direccion) {
  localStorage.setItem(GUARDADA, direccion);
}

// Lo que la persona escribió (o pegó: también un enlace de la app) en la forma http(s)://equipo:puerto/api/v1,
// o null si no es una dirección http(s). Acepta «10.34.101.124», «10.34.101.124:5000»,
// «http://10.34.101.124:5000» y «http://10.34.101.124:5000/api/v1/». Sin esquema ni puerto se usa el 5000
// del backend; con el esquema escrito, el puerto es el que se escribió (https://equipo.ts.net va al 443).
export function normalizarDireccion(texto) {
  const limpio = String(texto ?? "").trim();
  if (esEnlaceDeLaApp(limpio)) return direccionDelEnlace(limpio);
  return normalizarHttp(limpio);
}

function normalizarHttp(limpio) {
  if (!limpio) return null;
  const conEsquema = CON_ESQUEMA.test(limpio);
  let url;
  try {
    url = new URL(conEsquema ? limpio : `http://${limpio}`);
  } catch {
    return null;
  }
  if ((url.protocol !== "http:" && url.protocol !== "https:") || !url.hostname || url.username || url.password) return null;
  if (!conEsquema && !url.port) url.port = PUERTO_DEL_BACKEND;
  const ruta = url.pathname.replace(/\/+$/, "");
  return `${url.protocol}//${url.host}${ruta || PREFIJO}`;
}

// El enlace que abre la app proponiendo ese servidor (el QR de Mi cuenta).
export function enlaceDeServidor(api) {
  return `${ESQUEMA_APP}://${HOST_DEL_ENLACE}?${new URLSearchParams({ api })}`;
}

function esEnlaceDeLaApp(texto) {
  return texto.toLowerCase().startsWith(`${ESQUEMA_APP}:`);
}

// La dirección que propone un enlace de la app, ya normalizada; null si el texto no es un enlace de la app o
// si lo que trae no es una dirección http(s). Un enlace o un QR lo puede fabricar cualquiera: sin cifrar
// (http://) solo se acepta un equipo de la red local; para un servidor de afuera, el enlace debe traer https://.
// Escrita a mano, la persona puede poner la que quiera.
export function direccionDelEnlace(texto) {
  let url;
  try {
    url = new URL(String(texto ?? "").trim());
  } catch {
    return null;
  }
  if (url.protocol !== `${ESQUEMA_APP}:` || url.hostname !== HOST_DEL_ENLACE) return null;
  const direccion = normalizarHttp(url.searchParams.get("api")?.trim() ?? "");
  if (!direccion) return null;
  const propuesta = new URL(direccion);
  return propuesta.protocol === "https:" || esDeLaRedLocal(propuesta.hostname) ? direccion : null;
}

// El equipo es este mismo o una IP de una red local: 10/8, 172.16/12, 192.168/16, 169.254/16 o 100.64/10
// (la de los celulares que comparten datos y la de Tailscale).
export function esDeLaRedLocal(nombre) {
  if (nombre === "localhost") return true;
  const partes = nombre.split(".");
  if (partes.length !== 4 || !partes.every((parte) => /^\d{1,3}$/.test(parte) && Number(parte) <= 255)) return false;
  const [a, b] = partes.map(Number);
  return a === 10 || a === 127 || (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168)
    || (a === 169 && b === 254) || (a === 100 && b >= 64 && b <= 127);
}
