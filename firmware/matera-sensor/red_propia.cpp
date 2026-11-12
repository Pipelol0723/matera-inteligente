#include "red_propia.h"

#include <DNSServer.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_ota_ops.h>

#include "api_local.h"
#include "bluetooth.h"
#include "identidad.h"

namespace {

const IPAddress IP_PROPIA(192, 168, 4, 1);  // la de siempre de la ESP32 en modo punto de acceso
const char ALFABETO_CLAVE[] = "abcdefghjkmnpqrstuvwxyz23456789";  // sin 0/o, 1/l/i: se copia a mano
const int LARGO_CLAVE = 8;
// Una sola persona a la vez: nadie mas en el salon puede leer /info (el codigo y la huella) y registrar
// la placa primero en su cuenta.
const int MAX_CLIENTES = 1;

WebServer web(80);
DNSServer dns;
bool abierta = false;
String nombre;
String clave;
String codigoPlaca;

// ---- adaptador HTTP de la API local (las reglas estan en api_local) ----

// El servidor web escucha en todas las interfaces: lo que llegue por el WiFi de la casa no se atiende.
bool desdeRedPropia() {
  return web.client().localIP() == IP_PROPIA;
}

void cabecerasCors() {
  web.sendHeader("Access-Control-Allow-Origin", "*");
  web.sendHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  web.sendHeader("Access-Control-Allow-Headers", "Content-Type");
  // Chrome pide este permiso cuando una pagina le habla a una IP privada.
  web.sendHeader("Access-Control-Allow-Private-Network", "true");
  web.sendHeader("Cache-Control", "no-store");
}

void responder(const RespuestaLocal &respuesta) {
  cabecerasCors();
  if (respuesta.cuerpo.length() == 0) {
    web.send(respuesta.http);
  } else {
    web.send(respuesta.http, "application/json; charset=utf-8", respuesta.cuerpo);
  }
}

bool rechazarAjeno() {
  if (desdeRedPropia()) return false;
  responder(apiLocalError(403, "SOLO_RED_PROPIA", "La placa solo atiende a quien está unido a su red."));
  return true;
}

// ---- rutas ----

void info() {
  if (rechazarAjeno()) return;
  responder(apiLocalInfo());
}

// El cuerpo llega en JSON aunque la app lo mande como text/plain (asi no hay consulta previa de CORS): se
// lee igual con cualquier Content-Type.
void configurar() {
  if (rechazarAjeno()) return;
  responder(apiLocalConfigurar(web.arg("plain")));
}

void estado() {
  if (rechazarAjeno()) return;
  responder(apiLocalEstado());
}

void cerrar() {
  if (rechazarAjeno()) return;
  responder(apiLocalCerrar());
}

void inicio() {
  const String titulo = "Matera " + codigoPlaca;
  web.send(200, "text/html; charset=utf-8",
           "<!doctype html><html lang=\"es\"><head><meta charset=\"utf-8\">"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1\"><title>" + titulo +
           "</title></head><body style=\"font-family:sans-serif;margin:2em\"><h1>" + titulo +
           "</h1><p>Esta es la red de la placa. Vuelve a la app de la matera para terminar de conectarla.</p>"
           "</body></html>");
}

// Las pruebas de conexion de los sistemas: con estas respuestas creen que la red tiene internet y no la dejan.
void sinContenido() {
  web.send(204);
}

void exitoApple() {
  web.send(200, "text/html", "<HTML><HEAD><TITLE>Success</TITLE></HEAD><BODY>Success</BODY></HTML>");
}

void pruebaWindows() {
  web.send(200, "text/plain", "Microsoft Connect Test");
}

void ncsiWindows() {
  web.send(200, "text/plain", "Microsoft NCSI");
}

void otraRuta() {
  if (web.method() == HTTP_OPTIONS) {
    cabecerasCors();
    web.send(204);
    return;
  }
  const String ruta = web.uri();
  if (ruta == "/info" || ruta == "/estado" || ruta == "/configurar" || ruta == "/cerrar") {
    responder(apiLocalError(405, "METODO_NO_PERMITIDO", "La ruta " + ruta + " no acepta ese método."));
    return;
  }
  responder(apiLocalError(404, "RUTA_NO_ENCONTRADA", "La placa no tiene la ruta " + ruta + "."));
}

void registrarRutas() {
  static bool registradas = false;
  if (registradas) return;
  registradas = true;
  web.on("/info", HTTP_GET, info);
  web.on("/configurar", HTTP_POST, configurar);
  web.on("/estado", HTTP_GET, estado);
  web.on("/cerrar", HTTP_POST, cerrar);
  web.on("/", HTTP_GET, inicio);
  web.on("/generate_204", HTTP_GET, sinContenido);  // Android
  web.on("/gen_204", HTTP_GET, sinContenido);
  web.on("/hotspot-detect.html", HTTP_GET, exitoApple);  // iPhone y Mac
  web.on("/library/test/success.html", HTTP_GET, exitoApple);
  web.on("/connecttest.txt", HTTP_GET, pruebaWindows);  // Windows
  web.on("/ncsi.txt", HTTP_GET, ncsiWindows);
  web.onNotFound(otraRuta);
}

}  // namespace

void redPropiaAbrir(const String &codigo, const String &huella) {
  if (abierta) redPropiaCerrar();
  codigoPlaca = codigo;
  nombre = "Matera-" + codigo.substring(3, 7) + codigo.substring(8);
  apiLocalIniciar(codigo, huella);
  WiFi.mode(WIFI_AP_STA);
  clave = textoAlAzar(ALFABETO_CLAVE, LARGO_CLAVE);  // con la radio encendida: esp_random es aleatorio
  apiLocalBuscarRedes();
  // Si la placa ya esta en un WiFi, su red propia tiene que ir en el mismo canal.
  const int canal = WiFi.status() == WL_CONNECTED ? WiFi.channel() : 1;
  if (!WiFi.softAP(nombre.c_str(), clave.c_str(), canal, 0, MAX_CLIENTES)) {
    Serial.println("No se pudo abrir la red propia.");
  }
  dns.setErrorReplyCode(DNSReplyCode::NoError);
  dns.start(53, "*", IP_PROPIA);
  registrarRutas();
  web.begin();
  abierta = true;
  Serial.printf("Red propia abierta: «%s», clave %s, API en http://%s (ve %d redes).\n", nombre.c_str(), clave.c_str(),
                WiFi.softAPIP().toString().c_str(), apiLocalCuantasRedes());
  bluetoothEncender(nombre, clave);
  redPropiaImprimirRecursos("modo de conexión abierto (WiFi, red propia, servidor web y Bluetooth)");
}

void redPropiaCerrar() {
  if (!abierta) return;
  bluetoothApagar();
  web.stop();
  dns.stop();
  apiLocalTerminar();
  WiFi.softAPdisconnect(true);  // la radio queda solo en modo estacion
  abierta = false;
  Serial.println("Red propia cerrada.");
  redPropiaImprimirRecursos("modo de conexión cerrado");
}

bool redPropiaAbierta() {
  return abierta;
}

void redPropiaAtender() {
  if (!abierta) return;
  dns.processNextRequest();
  web.handleClient();
  bluetoothAtender();
  apiLocalRevisarBusqueda();
  if (apiLocalCierreVencido()) redPropiaCerrar();
}

const String &redPropiaNombre() {
  return nombre;
}

const String &redPropiaClave() {
  return clave;
}

int redPropiaClientes() {
  return abierta ? WiFi.softAPgetStationNum() + bluetoothConectados() : 0;
}

void redPropiaEstado(const char *etapa, const String &detalle) {
  apiLocalEstadoPlaca(etapa, detalle);
}

bool redPropiaConfiguracion(Conexion &conexion) {
  return apiLocalConfiguracion(conexion);
}

void redPropiaCortarBusqueda() {
  apiLocalCortarBusqueda();
}

void redPropiaImprimirRecursos(const char *momento) {
  const esp_partition_t *particion = esp_ota_get_running_partition();
  static const uint32_t programa = ESP.getSketchSize();  // lee el programa entero: se mide una vez
  const uint32_t espacio = particion != nullptr ? particion->size : 0;
  Serial.printf("Memoria, %s: programa %u de %u bytes (%u %%); RAM libre %u bytes (mínima %u, bloque mayor %u).\n",
                momento, programa, espacio, espacio > 0 ? (unsigned)(100ULL * programa / espacio) : 0u,
                ESP.getFreeHeap(), ESP.getMinFreeHeap(), ESP.getMaxAllocHeap());
}
