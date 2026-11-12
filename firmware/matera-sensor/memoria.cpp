#include "memoria.h"

#include <Preferences.h>

#include "ajustes.h"
#include "identidad.h"

namespace {

Preferences preferencias;
bool abierta = false;

// Los nombres de las claves en NVS (15 caracteres como maximo). Llevan NVS_ para no chocar con los
// #define de un config.h viejo, que tenia CLAVE_SENSOR.
const char *const NVS_RED = "red";
const char *const NVS_CLAVE_RED = "claveRed";
const char *const NVS_SERVIDORES = "servidores";  // separados por saltos de linea
const char *const NVS_ELEGIDO = "servidor";
const char *const NVS_CLAVE_SENSOR = "claveSensor";

const size_t LARGO_CLAVE = 43;

String leer(const char *nombre) {
  if (!abierta || !preferencias.isKey(nombre)) return String();
  return preferencias.getString(nombre, "");
}

void escribir(const char *nombre, const String &valor) {
  if (!abierta) return;
  if (preferencias.putString(nombre, valor) != valor.length()) {
    Serial.printf("Memoria: no se pudo guardar «%s».\n", nombre);
  }
}

String crearClave() {
  String clave = claveAlAzar();
  escribir(NVS_CLAVE_SENSOR, clave);
  if (leer(NVS_CLAVE_SENSOR) != clave) {
    Serial.println("Memoria: la clave del sensor no quedó guardada. Al reiniciar, la placa tendrá otra.");
  }
  return clave;
}

}  // namespace

void memoriaIniciar() {
  abierta = preferencias.begin("matera", false);
  if (!abierta) Serial.println("Memoria: no se pudo abrir la NVS. La placa no recordará nada al reiniciar.");
}

Conexion memoriaConexion() {
  Conexion conexion;
  conexion.red = leer(NVS_RED);
  conexion.claveRed = leer(NVS_CLAVE_RED);
  const String lista = leer(NVS_SERVIDORES);
  int desde = 0;
  while (desde < (int)lista.length() && conexion.cuantos < MAX_SERVIDORES) {
    int fin = lista.indexOf('\n', desde);
    if (fin < 0) fin = lista.length();
    String base = lista.substring(desde, fin);
    base.trim();
    if (base.length() > 0) conexion.servidores[conexion.cuantos++] = base;
    desde = fin + 1;
  }
  conexion.elegido = leer(NVS_ELEGIDO);
  if (conexion.hayRed()) return conexion;

#if defined(WIFI_SSID) && defined(WIFI_CLAVE) && defined(API_BASE)
  Conexion respaldo;
  respaldo.red = WIFI_SSID;
  respaldo.claveRed = WIFI_CLAVE;
  respaldo.servidores[0] = API_BASE;
  respaldo.cuantos = 1;
  respaldo.deConfigH = true;
  return respaldo;
#else
  return conexion;
#endif
}

void memoriaGuardarConexion(const Conexion &conexion) {
  String lista;
  for (int i = 0; i < conexion.cuantos; i++) {
    if (i > 0) lista += '\n';
    lista += conexion.servidores[i];
  }
  escribir(NVS_RED, conexion.red);
  escribir(NVS_CLAVE_RED, conexion.claveRed);
  escribir(NVS_SERVIDORES, lista);
  if (abierta) preferencias.remove(NVS_ELEGIDO);
}

void memoriaGuardarElegido(const String &base) {
  if (leer(NVS_ELEGIDO) != base) escribir(NVS_ELEGIDO, base);
}

void memoriaOlvidarConexion() {
  if (!abierta) return;
  preferencias.remove(NVS_RED);
  preferencias.remove(NVS_CLAVE_RED);
  preferencias.remove(NVS_SERVIDORES);
  preferencias.remove(NVS_ELEGIDO);
}

String memoriaClaveSensor() {
  String clave = leer(NVS_CLAVE_SENSOR);
  if (clave.length() == LARGO_CLAVE) return clave;
  Serial.println("Memoria: primera vez de esta placa. Se crea la clave del sensor.");
  return crearClave();
}

String memoriaNuevaClaveSensor() {
  return crearClave();
}
