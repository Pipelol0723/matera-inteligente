#include "api_local.h"

#include <WiFi.h>
#include <esp_task_wdt.h>

#include "lector_json.h"

namespace {

const unsigned long VIGENCIA_REDES_MS = 30000;  // info pide otra busqueda si la lista es mas vieja
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

// Pide otra busqueda en segundo plano. Mientras la placa intenta entrar a una red, buscar corta el intento:
// solo se busca sin red o ya conectada.
void pedirBusqueda() {
  if (escaneando || millis() - redesDesde < VIGENCIA_REDES_MS) return;
  if (etapaActual != "sin-red" && WiFi.status() != WL_CONNECTED) return;
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
  if (escaneando) {
    WiFi.scanDelete();
    escaneando = false;
  }
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

void apiLocalRevisarBusqueda() {
  if (!escaneando) return;
  const int resultado = WiFi.scanComplete();
  if (resultado == WIFI_SCAN_RUNNING) return;
  escaneando = false;
  if (resultado >= 0) guardarRedes(resultado);
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
