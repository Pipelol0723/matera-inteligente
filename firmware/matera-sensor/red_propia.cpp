#include "red_propia.h"

#include <DNSServer.h>
#include <WebServer.h>
#include <WiFi.h>
#include <esp_task_wdt.h>

#include "identidad.h"
#include "lector_json.h"

namespace {

const IPAddress IP_PROPIA(192, 168, 4, 1);  // la de siempre de la ESP32 en modo punto de acceso
const char ALFABETO_CLAVE[] = "abcdefghjkmnpqrstuvwxyz23456789";  // sin 0/o, 1/l/i: se copia a mano
const int LARGO_CLAVE = 8;
// Una sola persona a la vez: nadie mas en el salon puede leer /info (el codigo y la huella) y registrar
// la placa primero en su cuenta.
const int MAX_CLIENTES = 1;
const int MAX_REDES = 15;
const unsigned long VIGENCIA_REDES_MS = 30000;  // GET /info pide otra busqueda si la lista es mas vieja
const unsigned long DEMORA_MS = 400;            // entre responder y cambiar de red o cerrar
const size_t MAX_CUERPO = 1024;
const size_t MAX_DIRECCION = 120;

WebServer web(80);
DNSServer dns;
bool abierta = false;
String nombre;
String clave;
String codigoPlaca;
String huellaPlaca;
String etapaActual = "sin-red";
String detalleActual;

struct Red {
  String nombre;
  int senal;
  bool segura;
};
Red redes[MAX_REDES];
int cuantasRedes = 0;
unsigned long redesDesde = 0;
bool escaneando = false;

bool hayConfiguracion = false;
unsigned long configuracionDesde = 0;
Conexion configuracion;
bool cierrePedido = false;
unsigned long cierreDesde = 0;

// ---- redes que ve la placa ----

void guardarRedes(int encontradas) {
  cuantasRedes = 0;
  for (int i = 0; i < encontradas; i++) {
    const String ssid = WiFi.SSID(i);
    if (ssid.length() == 0) continue;  // red oculta
    const int senal = WiFi.RSSI(i);
    const bool segura = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    // La misma red con varios puntos de acceso aparece una vez, con la mejor senal.
    int j = 0;
    while (j < cuantasRedes && redes[j].nombre != ssid) j++;
    if (j < cuantasRedes) {
      if (senal > redes[j].senal) redes[j] = {ssid, senal, segura};
      continue;
    }
    if (cuantasRedes < MAX_REDES) {
      redes[cuantasRedes++] = {ssid, senal, segura};
      continue;
    }
    int peor = 0;
    for (int k = 1; k < cuantasRedes; k++) {
      if (redes[k].senal < redes[peor].senal) peor = k;
    }
    if (senal > redes[peor].senal) redes[peor] = {ssid, senal, segura};
  }
  // De la mejor senal a la peor.
  for (int i = 1; i < cuantasRedes; i++) {
    Red actual = redes[i];
    int j = i - 1;
    while (j >= 0 && redes[j].senal < actual.senal) {
      redes[j + 1] = redes[j];
      j--;
    }
    redes[j + 1] = actual;
  }
  WiFi.scanDelete();
  redesDesde = millis();
}

void escanearAhora() {
  esp_task_wdt_reset();
  const int encontradas = WiFi.scanNetworks(false, false);
  if (encontradas >= 0) guardarRedes(encontradas);
  esp_task_wdt_reset();
  // Sirve para saber si la red de la casa esta al alcance y es de 2,4 GHz.
  Serial.printf("La placa ve %d redes:\n", cuantasRedes);
  for (int i = 0; i < cuantasRedes && i < 10; i++) {
    Serial.printf("  «%s», señal %d dBm%s\n", redes[i].nombre.c_str(), redes[i].senal, redes[i].segura ? "" : ", abierta");
  }
}

// Pide otra busqueda en segundo plano. Mientras la placa intenta entrar a una red, buscar corta el intento:
// solo se busca sin red o ya conectada.
void pedirBusqueda() {
  if (escaneando || millis() - redesDesde < VIGENCIA_REDES_MS) return;
  if (etapaActual != "sin-red" && WiFi.status() != WL_CONNECTED) return;
  if (WiFi.scanNetworks(true, false) == WIFI_SCAN_RUNNING) escaneando = true;
}

void revisarBusqueda() {
  if (!escaneando) return;
  const int resultado = WiFi.scanComplete();
  if (resultado == WIFI_SCAN_RUNNING) return;
  escaneando = false;
  if (resultado >= 0) guardarRedes(resultado);
}

// ---- respuestas ----

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

void responderJson(int codigoHttp, const String &cuerpo) {
  cabecerasCors();
  web.send(codigoHttp, "application/json; charset=utf-8", cuerpo);
}

void responderVacio(int codigoHttp) {
  cabecerasCors();
  web.send(codigoHttp);
}

// {"error": "CODIGO", "mensaje": "texto para la persona"}, y el campo que hay que corregir en un 400.
void responderError(int codigoHttp, const char *error, const String &mensaje, const char *campo) {
  String cuerpo = String("{\"error\":") + jsonComillas(error) + ",\"mensaje\":" + jsonComillas(mensaje);
  if (campo != nullptr) cuerpo += String(",\"detalle\":{\"campo\":") + jsonComillas(campo) + "}";
  cuerpo += "}";
  responderJson(codigoHttp, cuerpo);
}

bool rechazarAjeno() {
  if (desdeRedPropia()) return false;
  responderError(403, "SOLO_RED_PROPIA", "La placa solo atiende a quien está unido a su red.", nullptr);
  return true;
}

String estadoJson(const String &etapa, const String &detalle) {
  return String("{\"etapa\":") + jsonComillas(etapa) + ",\"detalle\":" + jsonComillas(detalle) + "}";
}

// ---- validaciones de POST /configurar ----

// Vacia (red abierta), de 8 a 63 caracteres, o 64 hexadecimales: lo que acepta WPA2.
bool claveRedValida(const String &texto) {
  const size_t largo = texto.length();
  if (largo == 0 || (largo >= 8 && largo <= 63)) return true;
  if (largo != 64) return false;
  for (size_t i = 0; i < largo; i++) {
    if (!isxdigit((uint8_t)texto[i])) return false;
  }
  return true;
}

// http://<host>[:puerto]/<ruta>, sin espacios ni comillas.
bool direccionValida(const String &base) {
  if (!base.startsWith("http://") || base.length() <= 7 || base.length() > MAX_DIRECCION) return false;
  for (size_t i = 0; i < base.length(); i++) {
    const uint8_t c = base[i];
    if (c <= ' ' || c >= 0x7F || c == '"' || c == '\\') return false;
  }
  return base[7] != '/' && base[7] != ':';
}

// ---- rutas ----

void info() {
  if (rechazarAjeno()) return;
  String cuerpo = String("{\"codigo\":") + jsonComillas(codigoPlaca) + ",\"huella\":" + jsonComillas(huellaPlaca) +
                  ",\"redes\":[";
  for (int i = 0; i < cuantasRedes; i++) {
    if (i > 0) cuerpo += ',';
    cuerpo += String("{\"nombre\":") + jsonComillas(redes[i].nombre) + ",\"senal\":" + String(redes[i].senal) +
              ",\"segura\":" + (redes[i].segura ? "true" : "false") + "}";
  }
  cuerpo += "]}";
  responderJson(200, cuerpo);
  pedirBusqueda();  // la proxima vez, la lista estara al dia
}

// El cuerpo llega en JSON aunque la app lo mande como text/plain (asi no hay consulta previa de CORS): se
// lee igual con cualquier Content-Type.
void configurar() {
  if (rechazarAjeno()) return;
  const String cuerpo = web.arg("plain");
  if (cuerpo.length() > MAX_CUERPO || !jsonEsObjeto(cuerpo)) {
    responderError(400, "SOLICITUD_INVALIDA", "La placa no entendió el pedido: el cuerpo debe ser un objeto JSON.",
                   nullptr);
    return;
  }
  Conexion nueva;
  if (!jsonTexto(cuerpo, "red", nueva.red) || nueva.red.length() == 0) {
    responderError(400, "PARAMETRO_INVALIDO", "Falta el nombre del WiFi.", "red");
    return;
  }
  if (nueva.red.length() > 32) {
    responderError(400, "PARAMETRO_INVALIDO", "El nombre del WiFi tiene 32 caracteres como máximo.", "red");
    return;
  }
  if (!jsonTexto(cuerpo, "claveRed", nueva.claveRed) || !claveRedValida(nueva.claveRed)) {
    responderError(400, "PARAMETRO_INVALIDO",
                   "La clave del WiFi tiene de 8 a 63 caracteres, o va vacía si la red es abierta.", "claveRed");
    return;
  }
  String lista[MAX_SERVIDORES];
  const int cuantos = jsonTextos(cuerpo, "servidores", lista, MAX_SERVIDORES);
  if (cuantos < 1 || cuantos > MAX_SERVIDORES) {
    responderError(400, "PARAMETRO_INVALIDO",
                   "Faltan las direcciones del servidor: de 1 a 4, como http://10.34.101.124:5000/api/v1.", "servidores");
    return;
  }
  for (int i = 0; i < cuantos; i++) {
    String base = lista[i];
    base.trim();
    while (base.endsWith("/")) base.remove(base.length() - 1);
    if (!direccionValida(base)) {
      responderError(400, "PARAMETRO_INVALIDO", "«" + lista[i] + "» no es una dirección http:// del servidor.",
                     "servidores");
      return;
    }
    nueva.servidores[nueva.cuantos++] = base;
  }
  configuracion = nueva;
  hayConfiguracion = true;
  configuracionDesde = millis();
  responderJson(202, estadoJson("conectando", "Conectando a «" + nueva.red + "»"));
}

void estado() {
  if (rechazarAjeno()) return;
  // Entre el 202 y el momento en que la placa empieza a conectarse ya se dice «conectando».
  if (hayConfiguracion) {
    responderJson(200, estadoJson("conectando", "Conectando a «" + configuracion.red + "»"));
  } else {
    responderJson(200, estadoJson(etapaActual, detalleActual));
  }
}

void cerrar() {
  if (rechazarAjeno()) return;
  if (etapaActual == "sin-red" && !hayConfiguracion) {
    responderError(409, "SIN_RED", "La placa todavía no tiene red: su red propia sigue abierta.", nullptr);
    return;
  }
  cierrePedido = true;
  cierreDesde = millis();
  responderVacio(204);
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
    responderVacio(204);
    return;
  }
  const String ruta = web.uri();
  if (ruta == "/info" || ruta == "/estado" || ruta == "/configurar" || ruta == "/cerrar") {
    responderError(405, "METODO_NO_PERMITIDO", "La ruta " + ruta + " no acepta ese método.", nullptr);
    return;
  }
  responderError(404, "RUTA_NO_ENCONTRADA", "La placa no tiene la ruta " + ruta + ".", nullptr);
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
  huellaPlaca = huella;
  nombre = "Matera-" + codigo.substring(3, 7) + codigo.substring(8);
  WiFi.mode(WIFI_AP_STA);
  clave = textoAlAzar(ALFABETO_CLAVE, LARGO_CLAVE);  // con la radio encendida: esp_random es aleatorio
  escanearAhora();
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
  hayConfiguracion = false;
  cierrePedido = false;
  Serial.printf("Red propia abierta: «%s», clave %s, API en http://%s (ve %d redes).\n", nombre.c_str(), clave.c_str(),
                WiFi.softAPIP().toString().c_str(), cuantasRedes);
}

void redPropiaCerrar() {
  if (!abierta) return;
  web.stop();
  dns.stop();
  if (escaneando) {
    WiFi.scanDelete();
    escaneando = false;
  }
  WiFi.softAPdisconnect(true);  // la radio queda solo en modo estacion
  abierta = false;
  hayConfiguracion = false;
  cierrePedido = false;
  Serial.println("Red propia cerrada.");
}

bool redPropiaAbierta() {
  return abierta;
}

void redPropiaAtender() {
  if (!abierta) return;
  dns.processNextRequest();
  web.handleClient();
  revisarBusqueda();
  if (cierrePedido && millis() - cierreDesde >= DEMORA_MS) redPropiaCerrar();
}

const String &redPropiaNombre() {
  return nombre;
}

const String &redPropiaClave() {
  return clave;
}

int redPropiaClientes() {
  return abierta ? WiFi.softAPgetStationNum() : 0;
}

void redPropiaEstado(const char *etapa, const String &detalle) {
  if (etapaActual != etapa) etapaActual = etapa;
  if (detalleActual != detalle) detalleActual = detalle;
}

bool redPropiaConfiguracion(Conexion &conexion) {
  if (!hayConfiguracion || millis() - configuracionDesde < DEMORA_MS) return false;
  conexion = configuracion;
  hayConfiguracion = false;
  return true;
}
