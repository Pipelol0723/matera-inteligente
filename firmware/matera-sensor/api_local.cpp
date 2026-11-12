#include "api_local.h"

#include <WiFi.h>
#include <esp_task_wdt.h>
#include <esp_wifi.h>

#include "lector_json.h"

namespace {

const unsigned long VIGENCIA_REDES_MS = 30000;  // la lista se renueva si es mas vieja que esto
const unsigned long REINTENTO_BUSQUEDA_MS = 5000;  // despues de una busqueda que fallo
const unsigned long DEMORA_MS = 400;            // entre responder y cambiar de red o cerrar
const size_t MAX_DIRECCION = 120;

String codigoPlaca;
String huellaPlaca;
String etapaActual = "sin-red";
String detalleActual;

struct Red {
  String nombre;
  int senal;
  bool segura;
  int canal;  // solo para el monitor serie
};
Red redes[MAX_REDES];
int cuantasRedes = 0;
int puntosVistos = 0;  // lo que encontro la ultima busqueda, con repetidas y ocultas
unsigned long redesDesde = 0;    // la ultima busqueda que termino bien
unsigned long busquedaDesde = 0;  // el ultimo intento, haya salido o no
bool hayRedes = false;
bool escaneando = false;

bool hayConfiguracion = false;
unsigned long configuracionDesde = 0;
Conexion configuracion;
bool cierrePedido = false;
unsigned long cierreDesde = 0;

// ---- redes que ve la placa ----

void guardarRedes(int encontradas) {
  cuantasRedes = 0;
  puntosVistos = encontradas;
  for (int i = 0; i < encontradas; i++) {
    const String ssid = WiFi.SSID(i);
    if (ssid.length() == 0) continue;  // red oculta
    const int senal = WiFi.RSSI(i);
    const bool segura = WiFi.encryptionType(i) != WIFI_AUTH_OPEN;
    const int canal = WiFi.channel(i);
    // La misma red con varios puntos de acceso aparece una vez, con la mejor senal.
    int j = 0;
    while (j < cuantasRedes && redes[j].nombre != ssid) j++;
    if (j < cuantasRedes) {
      if (senal > redes[j].senal) redes[j] = {ssid, senal, segura, canal};
      continue;
    }
    if (cuantasRedes < MAX_REDES) {
      redes[cuantasRedes++] = {ssid, senal, segura, canal};
      continue;
    }
    int peor = 0;
    for (int k = 1; k < cuantasRedes; k++) {
      if (redes[k].senal < redes[peor].senal) peor = k;
    }
    if (senal > redes[peor].senal) redes[peor] = {ssid, senal, segura, canal};
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
  hayRedes = true;
}

// Los nombres de la lista, cada uno entre saltos de linea: "\nred1\nred2\n". Sirve para saber si cambio.
String nombresDeRedes() {
  String nombres = "\n";
  for (int i = 0; i < cuantasRedes; i++) nombres += redes[i].nombre + "\n";
  return nombres;
}

// true si la lista tiene las mismas redes que `antes` (de nombresDeRedes), en cualquier orden: la senal
// cambia el orden a cada rato.
bool mismasRedes(const String &antes) {
  int cuantasAntes = 0;
  for (size_t i = 1; i < antes.length(); i++) {
    if (antes[i] == '\n') cuantasAntes++;
  }
  if (cuantasAntes != cuantasRedes) return false;
  for (int i = 0; i < cuantasRedes; i++) {
    if (antes.indexOf("\n" + redes[i].nombre + "\n") < 0) return false;
  }
  return true;
}

// Al monitor serie, todas las redes que entrega info, con su canal: sirve para saber si la red de la casa
// esta al alcance y es de 2,4 GHz.
void imprimirRedes() {
  Serial.printf("La búsqueda encontró %d puntos de acceso; info entrega estas %d redes:\n", puntosVistos,
                cuantasRedes);
  for (int i = 0; i < cuantasRedes; i++) {
    Serial.printf("  «%s», señal %d dBm, canal %d%s\n", redes[i].nombre.c_str(), redes[i].senal, redes[i].canal,
                  redes[i].segura ? "" : ", abierta");
  }
}

// Pide otra busqueda en segundo plano si la lista tiene mas de 30 s. Mientras la placa intenta entrar a una
// red, buscar corta el intento: solo se busca sin red o ya conectada.
void pedirBusqueda() {
  if (escaneando || (hayRedes && millis() - redesDesde < VIGENCIA_REDES_MS)) return;
  if (busquedaDesde != 0 && millis() - busquedaDesde < REINTENTO_BUSQUEDA_MS) return;
  if (etapaActual != "sin-red" && WiFi.status() != WL_CONNECTED) return;
  busquedaDesde = millis();
  if (WiFi.scanNetworks(true, false) == WIFI_SCAN_RUNNING) escaneando = true;
}

String estadoJson(const String &etapa, const String &detalle) {
  return String("{\"etapa\":") + jsonComillas(etapa) + ",\"detalle\":" + jsonComillas(detalle) + "}";
}

// ---- validaciones de configurar ----

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

}  // namespace

RespuestaLocal apiLocalError(int http, const char *error, const String &mensaje, const char *campo) {
  String cuerpo = String("{\"error\":") + jsonComillas(error) + ",\"mensaje\":" + jsonComillas(mensaje);
  if (campo != nullptr) cuerpo += String(",\"detalle\":{\"campo\":") + jsonComillas(campo) + "}";
  cuerpo += "}";
  return {http, cuerpo};
}

void apiLocalIniciar(const String &codigo, const String &huella) {
  codigoPlaca = codigo;
  huellaPlaca = huella;
  hayConfiguracion = false;
  cierrePedido = false;
}

void apiLocalTerminar() {
  apiLocalCortarBusqueda();
  hayConfiguracion = false;
  cierrePedido = false;
}

RespuestaLocal apiLocalInfo() {
  String cuerpo = String("{\"codigo\":") + jsonComillas(codigoPlaca) + ",\"huella\":" + jsonComillas(huellaPlaca) +
                  ",\"redes\":[";
  for (int i = 0; i < cuantasRedes; i++) {
    if (i > 0) cuerpo += ',';
    cuerpo += String("{\"nombre\":") + jsonComillas(redes[i].nombre) + ",\"senal\":" + String(redes[i].senal) +
              ",\"segura\":" + (redes[i].segura ? "true" : "false") + "}";
  }
  cuerpo += "]}";
  pedirBusqueda();  // la proxima vez, la lista estara al dia
  return {200, cuerpo};
}

RespuestaLocal apiLocalConfigurar(const String &cuerpo) {
  if (cuerpo.length() > MAX_PEDIDO_LOCAL || !jsonEsObjeto(cuerpo)) {
    return apiLocalError(400, "SOLICITUD_INVALIDA", "La placa no entendió el pedido: el cuerpo debe ser un objeto JSON.");
  }
  Conexion nueva;
  if (!jsonTexto(cuerpo, "red", nueva.red) || nueva.red.length() == 0) {
    return apiLocalError(400, "PARAMETRO_INVALIDO", "Falta el nombre del WiFi.", "red");
  }
  if (nueva.red.length() > 32) {
    return apiLocalError(400, "PARAMETRO_INVALIDO", "El nombre del WiFi tiene 32 caracteres como máximo.", "red");
  }
  if (!jsonTexto(cuerpo, "claveRed", nueva.claveRed) || !claveRedValida(nueva.claveRed)) {
    return apiLocalError(400, "PARAMETRO_INVALIDO",
                         "La clave del WiFi tiene de 8 a 63 caracteres, o va vacía si la red es abierta.", "claveRed");
  }
  String lista[MAX_SERVIDORES];
  const int cuantos = jsonTextos(cuerpo, "servidores", lista, MAX_SERVIDORES);
  if (cuantos < 1 || cuantos > MAX_SERVIDORES) {
    return apiLocalError(400, "PARAMETRO_INVALIDO",
                         "Faltan las direcciones del servidor: de 1 a 4, como http://10.34.101.124:5000/api/v1.",
                         "servidores");
  }
  for (int i = 0; i < cuantos; i++) {
    String base = lista[i];
    base.trim();
    while (base.endsWith("/")) base.remove(base.length() - 1);
    if (!direccionValida(base)) {
      return apiLocalError(400, "PARAMETRO_INVALIDO", "«" + lista[i] + "» no es una dirección http:// del servidor.",
                           "servidores");
    }
    nueva.servidores[nueva.cuantos++] = base;
  }
  configuracion = nueva;
  hayConfiguracion = true;
  configuracionDesde = millis();
  return {202, estadoJson("conectando", "Conectando a «" + nueva.red + "»")};
}

RespuestaLocal apiLocalEstado() {
  // Entre el 202 y el momento en que la placa empieza a conectarse ya se dice «conectando».
  if (hayConfiguracion) return {200, estadoJson("conectando", "Conectando a «" + configuracion.red + "»")};
  return {200, estadoJson(etapaActual, detalleActual)};
}

RespuestaLocal apiLocalCerrar() {
  if (etapaActual == "sin-red" && !hayConfiguracion) {
    return apiLocalError(409, "SIN_RED", "La placa todavía no tiene red: su red propia sigue abierta.");
  }
  cierrePedido = true;
  cierreDesde = millis();
  return {204, String()};
}

void apiLocalBuscarRedes() {
  apiLocalCortarBusqueda();
  esp_task_wdt_reset();
  busquedaDesde = millis();
  const int encontradas = WiFi.scanNetworks(false, false);
  esp_task_wdt_reset();
  if (encontradas < 0) {
    Serial.printf("La búsqueda de redes falló (%d): la placa vuelve a buscar en unos segundos.\n", encontradas);
    return;
  }
  guardarRedes(encontradas);
  imprimirRedes();
}

void apiLocalRevisarBusqueda() {
  if (escaneando) {
    const int resultado = WiFi.scanComplete();
    if (resultado == WIFI_SCAN_RUNNING) return;
    escaneando = false;
    if (resultado < 0) return;
    const String antes = nombresDeRedes();
    guardarRedes(resultado);
    if (!mismasRedes(antes)) {
      Serial.print("Cambió la lista de redes. ");
      imprimirRedes();
    }
    return;
  }
  // Mientras nadie este unido a la red propia, la lista se renueva sola cada 30 s: asi la primera info ya
  // trae una red que se encendio despues de abrir el modo de conexion (el hotspot del celular, por
  // ejemplo). Con alguien unido solo se busca despues de una info, porque buscar saca a la red propia de
  // su canal unos segundos.
  if (WiFi.softAPgetStationNum() == 0) pedirBusqueda();
}

void apiLocalCortarBusqueda() {
  if (!escaneando) return;
  esp_wifi_scan_stop();
  WiFi.scanDelete();
  escaneando = false;
}

int apiLocalCuantasRedes() {
  return cuantasRedes;
}

void apiLocalEstadoPlaca(const char *etapa, const String &detalle) {
  if (etapaActual != etapa) etapaActual = etapa;
  if (detalleActual != detalle) detalleActual = detalle;
}

bool apiLocalConfiguracion(Conexion &conexion) {
  if (!hayConfiguracion || millis() - configuracionDesde < DEMORA_MS) return false;
  conexion = configuracion;
  hayConfiguracion = false;
  return true;
}

bool apiLocalCierreVencido() {
  return cierrePedido && millis() - cierreDesde >= DEMORA_MS;
}
