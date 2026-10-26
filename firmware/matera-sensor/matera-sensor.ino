// Matera inteligente: firmware del sensor, para la ESP32 con DHT11 y modulo LDR (DevKit con CH340) en el Arduino IDE 2.
//
// Habla con la API igual que el simulador (simulador/simulador_esp32.py), en dos pasos:
//   1. Canje: cambia la clave del sensor por un token de alcance «lecturas», que vence a las 24 horas.
//        POST {API_BASE}/dispositivos/{CODIGO_SENSOR}/token     {"clave":"..."}
//        -> {"token":"<JWT>","venceEn":"..."}
//   2. Cada INTERVALO_MS, una lectura con ese token y la hora en que se tomo:
//        POST {API_BASE}/dispositivos/{CODIGO_SENSOR}/lecturas
//        Authorization: Bearer <JWT>
//        {"dispositivo":"MT-0001-AA","momento":"2026-10-22T15:04:05Z","lecturas":{"humedad":53.0,"luz":1500,"temperatura":25.5}}
// Si la API responde que el token ya no sirve (vencio, o lo reemplazo otro canje), vuelve a canjear la clave.
// La API diagnostica, guarda la lectura y la muestra en Mis materas. Aqui no hay reglas: el estado y las
// recomendaciones los calcula el backend.
//
// Sensores de esta placa:
//   DHT11 en GPIO26: temperatura y humedad DEL AIRE. La API espera la humedad del sustrato; para la demo se
//     manda la del aire, y se avisa en la presentacion.
//   Modulo LDR (LM393) en GPIO18: solo dice si hay luz o no. Se manda en lux, con LUX_CON_LUZ o LUX_SIN_LUZ.
// La hora sale de NTP: sin hora no se envia nada. La red, la API, el codigo y la clave van en config.h
// (copia de config.example.h).

#include <HTTPClient.h>
#include <WiFi.h>
#include <esp_task_wdt.h>
#include <time.h>

#include <DHT.h>  // DHT sensor library, de Adafruit

#if __has_include("config.h")
#include "config.h"
#else
#error "Falta config.h: copie config.example.h como config.h, en esta misma carpeta, y complete sus datos."
#endif

// Lo que config.h puede omitir: los valores de la demo.
#ifndef INTERVALO_MS
#define INTERVALO_MS 15000
#endif
#ifndef LDR_CON_LUZ
#define LDR_CON_LUZ LOW  // el LM393 baja su salida cuando hay mas luz que la que marca su perilla
#endif
#ifndef LUX_CON_LUZ
#define LUX_CON_LUZ 1500
#endif
#ifndef LUX_SIN_LUZ
#define LUX_SIN_LUZ 50
#endif

// ---- pines de esta placa ----
const int PIN_DHT = 26;
const int PIN_LUZ = 18;  // la salida digital (DO) del modulo LDR
const int PIN_LED = 2;   // el LED azul de la placa

// ---- tiempos ----
const unsigned long ESPERA_WIFI_MS = 20000;  // cuanto se intenta conectar antes de rendirse un rato
const unsigned long ESPERA_HORA_MS = 15000;  // cuanto se espera la hora de NTP
const unsigned long REINTENTO_MS = 30000;    // si falla el WiFi, la hora, el sensor o el envio
// Si algo traba el programa mas de este tiempo, la placa se reinicia sola. Tiene margen sobre las
// esperas normales: el WiFi (20 s), la hora (15 s) y una peticion HTTP (15 s).
const int SEGUNDOS_VIGILANCIA = 60;
// Cualquier hora anterior a esta (2024-01-01) es la de una placa que todavia no sincronizo con NTP.
const time_t HORA_MINIMA = 1704067200;

// Lo que paso con una lectura. Va aqui arriba: el IDE pone los prototipos de las funciones antes que el resto.
enum Resultado { ENVIADA, TOKEN_VENCIDO, FALLO };

DHT dht(PIN_DHT, DHT11);
String token;  // el JWT del ultimo canje; vacio hasta canjear
unsigned long proximoEnvio = 0;

// ---- LED: parpadeo lento = conectando, fijo = conectado, 5 parpadeos rapidos = algo fallo ----

void led(bool encendido) {
  digitalWrite(PIN_LED, encendido ? HIGH : LOW);
}

void avisarFallo() {
  for (int i = 0; i < 5; i++) {
    led(true);
    delay(100);
    led(false);
    delay(100);
  }
  led(WiFi.status() == WL_CONNECTED);
}

// ---- red ----

const char *motivoWifi(wl_status_t estado) {
  switch (estado) {
    case WL_NO_SSID_AVAIL:
      return "no ve la red: revise WIFI_SSID y que sea de 2,4 GHz";
    case WL_CONNECT_FAILED:
      return "la red rechazó la conexión: revise WIFI_CLAVE";
    case WL_CONNECTION_LOST:
      return "se perdió la conexión";
    case WL_DISCONNECTED:
      return "la red no la dejó entrar: suele ser WIFI_CLAVE o el límite de dispositivos del hotspot";
    default:
      return "estado desconocido";
  }
}

// Las redes que ve la placa: sirve para saber si el hotspot esta al alcance y en 2,4 GHz.
void mostrarRedes() {
  esp_task_wdt_reset();
  int cuantas = WiFi.scanNetworks();
  Serial.printf("La placa ve %d redes:\n", cuantas);
  for (int i = 0; i < cuantas && i < 10; i++) {
    Serial.printf("  «%s», canal %d, señal %d dBm\n", WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i));
  }
  WiFi.scanDelete();
}

bool conectarWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.printf("Conectando al WiFi «%s»", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_CLAVE);
  bool encendido = false;
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < ESPERA_WIFI_MS) {
    esp_task_wdt_reset();
    encendido = !encendido;
    led(encendido);
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.printf("No se pudo conectar: %s.\n", motivoWifi(WiFi.status()));
    WiFi.disconnect();
    mostrarRedes();
    led(false);
    return false;
  }
  Serial.printf("Conectado. IP de la placa: %s\n", WiFi.localIP().toString().c_str());
  led(true);
  return true;
}

// La hora en UTC por NTP. La API rechaza una lectura sin zona horaria o del futuro, asi que sin hora no se envia.
bool sincronizarHora() {
  if (time(nullptr) >= HORA_MINIMA) return true;
  Serial.print("Pidiendo la hora por NTP");
  configTime(0, 0, "pool.ntp.org", "time.google.com");
  unsigned long inicio = millis();
  while (time(nullptr) < HORA_MINIMA && millis() - inicio < ESPERA_HORA_MS) {
    esp_task_wdt_reset();
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (time(nullptr) < HORA_MINIMA) {
    Serial.println("No llegó la hora: la red tiene que dar salida a internet (puerto 123 de NTP).");
    return false;
  }
  Serial.printf("Hora sincronizada: %s\n", momentoAhora().c_str());
  return true;
}

// Por ejemplo 2026-10-22T15:04:05Z, como lo pide la API.
String momentoAhora() {
  time_t ahora = time(nullptr);
  struct tm utc;
  gmtime_r(&ahora, &utc);
  char texto[25];
  strftime(texto, sizeof texto, "%Y-%m-%dT%H:%M:%SZ", &utc);
  return String(texto);
}

void prepararPeticion(HTTPClient &http, const String &url) {
  http.setConnectTimeout(5000);
  http.setTimeout(10000);
  http.begin(url);
  http.addHeader("Content-Type", "application/json");  // sin ella, la API responde 400
}

// El texto de un campo de la respuesta, buscado despues de `desde`. Sin libreria de JSON: el token
// es un JWT, que no lleva comillas, y lo demas solo se usa para mostrarlo en el monitor serie.
String campoDespues(const String &json, const char *desde, const char *campo) {
  int pos = json.indexOf(desde);
  if (pos >= 0) pos = json.indexOf(String("\"") + campo + "\"", pos);
  if (pos >= 0) pos = json.indexOf(':', pos);
  if (pos >= 0) pos = json.indexOf('"', pos);
  int fin = pos >= 0 ? json.indexOf('"', pos + 1) : -1;
  return fin > pos ? json.substring(pos + 1, fin) : String("?");
}

// Sin sensores ya se puede probar esto: el WiFi, la IP del PC, el firewall y que el backend responda.
bool comprobarApi() {
  HTTPClient http;
  http.setConnectTimeout(5000);
  http.setTimeout(10000);
  http.begin(String(API_BASE) + "/parametros");
  int estado = http.GET();
  http.end();
  if (estado == 200) {
    Serial.println("La API responde (GET /parametros 200).");
    return true;
  }
  if (estado < 0) {
    Serial.printf("No se pudo contactar la API en %s (%s).\n", API_BASE, HTTPClient::errorToString(estado).c_str());
  } else {
    Serial.printf("GET /parametros respondió %d.\n", estado);
  }
  Serial.println("Revise API_BASE, que el backend corra con MATERA_HOST=0.0.0.0 y que el firewall deje pasar el puerto.");
  return false;
}

// ---- canje de la clave por el token ----

bool canjearClave() {
  HTTPClient http;
  prepararPeticion(http, String(API_BASE) + "/dispositivos/" + CODIGO_SENSOR + "/token");
  int estado = http.POST(String("{\"clave\":\"") + CLAVE_SENSOR + "\"}");
  String respuesta = estado > 0 ? http.getString() : String();
  http.end();
  if (estado == 200) {
    token = campoDespues(respuesta, "{", "token");
    Serial.printf("Canje listo: token del sensor hasta %s.\n", campoDespues(respuesta, "{", "venceEn").c_str());
    return true;
  }
  token = "";
  if (estado < 0) {
    Serial.printf("Canje sin respuesta (%s). Revise la red y API_BASE.\n", HTTPClient::errorToString(estado).c_str());
  } else if (estado == 401) {
    Serial.println("401: la API no reconoce el código o la clave. Revise CODIGO_SENSOR y CLAVE_SENSOR en config.h;");
    Serial.println("si la clave se perdió, «Cambiar sensor» con el mismo código da otra.");
  } else {
    Serial.printf("Canje: %d %s\n", estado, respuesta.c_str());
  }
  return false;
}

// ---- sensores ----

// El DHT11 da temperatura y humedad del aire. La libreria no lo deja leer mas de una vez cada 2 s.
bool leerAire(float &humedad, float &temperatura) {
  humedad = dht.readHumidity();
  temperatura = dht.readTemperature();
  if (isnan(humedad) || isnan(temperatura)) {
    Serial.printf("El DHT11 no respondió: revise que esté en GPIO%d y alimentado con 3V3.\n", PIN_DHT);
    return false;
  }
  return true;
}

// El modulo LDR solo dice si hay luz o no; se manda en lux con dos valores fijos.
int leerLuz() {
  bool hayLuz = digitalRead(PIN_LUZ) == LDR_CON_LUZ;
  return hayLuz ? LUX_CON_LUZ : LUX_SIN_LUZ;
}

// ---- envio ----

Resultado enviarLectura(float humedad, int lux, float temperatura) {
  String cuerpo = String("{\"dispositivo\":\"") + CODIGO_SENSOR + "\",\"momento\":\"" + momentoAhora() +
                  "\",\"lecturas\":{\"humedad\":" + String(humedad, 1) + ",\"luz\":" + String(lux) +
                  ",\"temperatura\":" + String(temperatura, 1) + "}}";
  HTTPClient http;
  prepararPeticion(http, String(API_BASE) + "/dispositivos/" + CODIGO_SENSOR + "/lecturas");
  http.addHeader("Authorization", String("Bearer ") + token);
  int estado = http.POST(cuerpo);
  String respuesta = estado > 0 ? http.getString() : String();
  http.end();

  Serial.printf("Enviado %s -> ", cuerpo.c_str());
  if (estado == 201) {
    Serial.printf("201, la planta está %s.\n", campoDespues(respuesta, "\"diagnostico\"", "estado").c_str());
    return ENVIADA;
  }
  if (estado < 0) {
    Serial.printf("sin respuesta (%s). Revise la red y API_BASE.\n", HTTPClient::errorToString(estado).c_str());
    return FALLO;
  }
  String error = campoDespues(respuesta, "{", "error");
  if (estado == 401 && error == "CREDENCIAL_DISPOSITIVO_INVALIDA") {
    Serial.println("401: el token venció o lo reemplazó otro canje. Se canjea la clave otra vez.");
    return TOKEN_VENCIDO;
  }
  Serial.printf("%d %s: %s\n", estado, error.c_str(), campoDespues(respuesta, "{", "mensaje").c_str());
  return FALLO;
}

// ---- programa ----

void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(PIN_LED, OUTPUT);
  pinMode(PIN_LUZ, INPUT);
  led(false);
  dht.begin();
  esp_task_wdt_init(SEGUNDOS_VIGILANCIA, true);  // reinicia la placa si loop() queda trabado
  esp_task_wdt_add(NULL);

  Serial.println();
  Serial.println("Matera inteligente · sensor " CODIGO_SENSOR);
  Serial.println("API: " API_BASE);
  // La primera lectura del DHT11 despues de encenderlo suele salir mal: se descarta.
  delay(2000);
  dht.readTemperature();
  if (conectarWifi() && !comprobarApi()) avisarFallo();
}

void loop() {
  esp_task_wdt_reset();
  // Resta con signo: sigue funcionando cuando millis() da la vuelta, a los 49 dias.
  if ((long)(millis() - proximoEnvio) < 0) {
    led(WiFi.status() == WL_CONNECTED);  // el LED sigue al WiFi tambien entre envios
    delay(50);
    return;
  }
  proximoEnvio = millis() + REINTENTO_MS;  // si algo falla abajo, se reintenta en REINTENTO_MS
  if (!conectarWifi() || !sincronizarHora()) {
    avisarFallo();
    return;
  }
  if (token.length() == 0 && !canjearClave()) {
    avisarFallo();
    return;
  }

  float humedad, temperatura;
  if (!leerAire(humedad, temperatura)) {
    avisarFallo();
    return;
  }
  int lux = leerLuz();

  Resultado resultado = enviarLectura(humedad, lux, temperatura);
  if (resultado == TOKEN_VENCIDO && canjearClave()) resultado = enviarLectura(humedad, lux, temperatura);
  if (resultado != ENVIADA) {
    if (resultado == TOKEN_VENCIDO) token = "";
    avisarFallo();
    return;
  }
  proximoEnvio = millis() + (unsigned long)INTERVALO_MS;
}
