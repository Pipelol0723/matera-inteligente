// Matera inteligente: firmware del sensor, para una ESP32 clásica (DevKit WROOM-32) en el Arduino IDE 2.
//
// Lee la humedad del sustrato (sensor capacitivo v1.2), la temperatura (AHT20) y la luz (BH1750), y
// cada INTERVALO_MS manda una medición a la API, como cualquier otro cliente HTTP:
//   POST {API_BASE}/sensores/{CODIGO_SENSOR}/mediciones
//   Content-Type: application/json
//   X-Clave-Sensor: {CLAVE_SENSOR}
//   {"humedad":41.5,"luz":820.0,"temperatura":22.3}
// La API diagnostica, guarda la medición y la muestra en vivo en Mis materas. Aquí no hay reglas:
// el estado y las recomendaciones los calcula el backend.
//
// Solo envía si los tres sensores responden, porque la API exige los tres valores. Sin sensores, la
// placa igual se conecta al WiFi y comprueba que llega a la API (GET /parametros).
// La red, la API, el código, la clave y la calibración van en config.h (copia de config.example.h).

#include <HTTPClient.h>
#include <WiFi.h>
#include <Wire.h>

#include <Adafruit_AHTX0.h>  // Adafruit AHTX0 (el gestor instala también Adafruit BusIO y Unified Sensor)
#include <BH1750.h>          // BH1750, de Christopher Laws

#if __has_include("config.h")
#include "config.h"
#else
#error "Falta config.h: copie config.example.h como config.h, en esta misma carpeta, y complete sus datos."
#endif

// ---- pines de la ESP32 DevKit ----
const int PIN_HUMEDAD = 34;  // del ADC1: el ADC2 no funciona con el WiFi encendido
const int PIN_SDA = 21;      // bus I2C que comparten el AHT20 (0x38) y el BH1750 (0x23)
const int PIN_SCL = 22;
const int PIN_LED = 2;       // el LED azul de la placa

// ---- tiempos y límites ----
const unsigned long ESPERA_WIFI_MS = 20000;  // cuánto se intenta conectar antes de rendirse un rato
const unsigned long REINTENTO_MS = 30000;    // si falta un sensor, no hay WiFi o falló el envío
const int MUESTRAS_HUMEDAD = 16;             // se promedian para bajar el ruido del ADC
// Una lectura cruda casi en 0 o casi en 4095 es un pin sin sensor (o un sensor mal conectado).
const int CRUDO_MINIMO = 200;
const int CRUDO_MAXIMO = 3900;
// El BH1750 no mide más de esto: a pleno sol se satura.
const float LUZ_MAXIMA = 65535.0;

Adafruit_AHTX0 aht;
BH1750 medidorLuz(0x23);
bool ahtListo = false;
bool luzListo = false;
unsigned long proximoEnvio = 0;

// ---- LED: parpadeo lento = conectando, fijo = conectado, 5 parpadeos rápidos = algo falló ----

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

bool conectarWifi() {
  if (WiFi.status() == WL_CONNECTED) return true;
  Serial.printf("Conectando al WiFi «%s»", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_CLAVE);
  bool encendido = false;
  unsigned long inicio = millis();
  while (WiFi.status() != WL_CONNECTED && millis() - inicio < ESPERA_WIFI_MS) {
    encendido = !encendido;
    led(encendido);
    delay(500);
    Serial.print(".");
  }
  Serial.println();
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("No se pudo conectar. Revise WIFI_SSID y WIFI_CLAVE, y que la red sea de 2,4 GHz.");
    led(false);
    return false;
  }
  Serial.printf("Conectado. IP de la placa: %s\n", WiFi.localIP().toString().c_str());
  led(true);
  return true;
}

void prepararPeticion(HTTPClient &http, const String &url) {
  http.setConnectTimeout(5000);
  http.setTimeout(10000);
  http.begin(url);
}

// Sin sensores ya se puede probar esto: el WiFi, la IP del PC, el firewall y que el backend responda.
bool comprobarApi() {
  HTTPClient http;
  prepararPeticion(http, String(API_BASE) + "/parametros");
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

// ---- sensores ----

void iniciarSensores() {
  if (!ahtListo) {
    ahtListo = aht.begin(&Wire);
    Serial.println(ahtListo ? "AHT20 listo (temperatura)." : "No responde el AHT20 en el bus I2C (0x38).");
  }
  if (!luzListo) {
    luzListo = medidorLuz.begin(BH1750::CONTINUOUS_HIGH_RES_MODE, 0x23, &Wire);
    Serial.println(luzListo ? "BH1750 listo (luz)." : "No responde el BH1750 en el bus I2C (0x23).");
  }
}

// La humedad en %, entre la calibración seca y la mojada; -1 si el sensor no está conectado.
// Siempre muestra la lectura cruda: con ella se calibra HUMEDAD_SECO y HUMEDAD_MOJADO.
float leerHumedad() {
  long suma = 0;
  for (int i = 0; i < MUESTRAS_HUMEDAD; i++) {
    suma += analogRead(PIN_HUMEDAD);
    delay(5);
  }
  int crudo = suma / MUESTRAS_HUMEDAD;
  Serial.printf("Humedad: lectura cruda %d (seco %d, mojado %d).\n", crudo, HUMEDAD_SECO, HUMEDAD_MOJADO);
  if (crudo < CRUDO_MINIMO || crudo > CRUDO_MAXIMO) return -1;
  float porcentaje = 100.0 * (HUMEDAD_SECO - crudo) / (HUMEDAD_SECO - HUMEDAD_MOJADO);
  return constrain(porcentaje, 0.0, 100.0);
}

bool leerTemperatura(float &temperatura) {
  if (!ahtListo) return false;
  sensors_event_t humedadDelAire, temp;
  if (!aht.getEvent(&humedadDelAire, &temp)) {
    ahtListo = false;  // se vuelve a iniciar en la próxima vuelta
    return false;
  }
  temperatura = temp.temperature;
  return true;
}

bool leerLuz(float &lux) {
  if (!luzListo) return false;
  float valor = medidorLuz.readLightLevel();
  if (valor < 0) {
    luzListo = false;
    return false;
  }
  if (valor >= LUZ_MAXIMA) Serial.println("Aviso: el BH1750 está saturado; la luz real puede ser mayor.");
  lux = valor;
  return true;
}

// ---- envío ----

// El texto de un campo de la respuesta, buscado después de `desde`. Sin librería de JSON: solo
// se usa para mostrar el estado en el monitor serie.
String campoDespues(const String &json, const char *desde, const char *campo) {
  int pos = json.indexOf(desde);
  if (pos >= 0) pos = json.indexOf(String("\"") + campo + "\"", pos);
  if (pos >= 0) pos = json.indexOf(':', pos);
  if (pos >= 0) pos = json.indexOf('"', pos);
  int fin = pos >= 0 ? json.indexOf('"', pos + 1) : -1;
  return fin > pos ? json.substring(pos + 1, fin) : String("?");
}

bool enviarMedicion(float humedad, float lux, float temperatura) {
  String cuerpo = String("{\"humedad\":") + String(humedad, 1) + ",\"luz\":" + String(lux, 1) +
                  ",\"temperatura\":" + String(temperatura, 1) + "}";
  HTTPClient http;
  prepararPeticion(http, String(API_BASE) + "/sensores/" + CODIGO_SENSOR + "/mediciones");
  http.addHeader("Content-Type", "application/json");  // sin ella, la API responde 400
  http.addHeader("X-Clave-Sensor", CLAVE_SENSOR);
  int estado = http.POST(cuerpo);
  String respuesta = estado > 0 ? http.getString() : String();
  http.end();

  Serial.printf("Enviado %s -> ", cuerpo.c_str());
  if (estado == 201) {
    Serial.printf("201, la planta está %s.\n", campoDespues(respuesta, "\"diagnostico\"", "estado").c_str());
    return true;
  }
  if (estado < 0) {
    Serial.printf("sin respuesta (%s). Revise la red y API_BASE.\n", HTTPClient::errorToString(estado).c_str());
  } else if (estado == 401) {
    Serial.println("401: la API no reconoce el código o la clave. Revise CODIGO_SENSOR y CLAVE_SENSOR en config.h.");
  } else {
    Serial.printf("%d: %s\n", estado, respuesta.c_str());
  }
  return false;
}

// ---- programa ----

void setup() {
  Serial.begin(115200);
  delay(500);
  pinMode(PIN_LED, OUTPUT);
  led(false);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_HUMEDAD, ADC_11db);  // lee de 0 a casi 3,3 V
  Wire.begin(PIN_SDA, PIN_SCL);

  Serial.println();
  Serial.println("Matera inteligente · sensor " CODIGO_SENSOR);
  Serial.println("API: " API_BASE);
  iniciarSensores();
  if (conectarWifi() && !comprobarApi()) avisarFallo();
}

void loop() {
  // Resta con signo: sigue funcionando cuando millis() da la vuelta, a los 49 días.
  if ((long)(millis() - proximoEnvio) < 0) {
    delay(50);
    return;
  }
  if (!conectarWifi()) {
    avisarFallo();
    proximoEnvio = millis() + REINTENTO_MS;
    return;
  }

  iniciarSensores();
  float humedad = leerHumedad();
  float temperatura = 0;
  float lux = 0;
  bool hayTemperatura = leerTemperatura(temperatura);
  bool hayLuz = leerLuz(lux);
  if (humedad < 0 || !hayTemperatura || !hayLuz) {
    Serial.printf("No se envía: falta%s%s%s. Se reintenta en %lu s.\n",
                  humedad < 0 ? " la humedad" : "", hayTemperatura ? "" : " la temperatura",
                  hayLuz ? "" : " la luz", REINTENTO_MS / 1000);
    avisarFallo();
    proximoEnvio = millis() + REINTENTO_MS;
    return;
  }

  bool enviada = enviarMedicion(humedad, lux, temperatura);
  if (!enviada) avisarFallo();
  proximoEnvio = millis() + (enviada ? (unsigned long)INTERVALO_MS : REINTENTO_MS);
}
