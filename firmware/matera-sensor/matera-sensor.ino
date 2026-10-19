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
#include <esp_task_wdt.h>

#include <Adafruit_AHTX0.h>  // Adafruit AHTX0 (el gestor instala también Adafruit BusIO y Unified Sensor)
#include <BH1750.h>          // BH1750, de Christopher Laws

#if __has_include("config.h")
#include "config.h"
#else
#error "Falta config.h: copie config.example.h como config.h, en esta misma carpeta, y complete sus datos."
#endif

#if HUMEDAD_SECO <= HUMEDAD_MOJADO
#error "En config.h, HUMEDAD_SECO (la lectura al aire) tiene que ser mayor que HUMEDAD_MOJADO (en agua)."
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
// Un sensor conectado da lecturas parejas. Un pin suelto da cualquier cosa: casi 0, casi 4095 o
// lecturas que saltan de una muestra a otra. Con una resistencia de 1 MΩ entre GPIO34 y GND, un
// cable suelto lee casi 0 y se detecta siempre (ver firmware/README.md).
const int CRUDO_MINIMO = 200;
const int CRUDO_MAXIMO = 3900;
const int SALTO_MAXIMO = 300;                // diferencia entre la muestra mayor y la menor
// Con el modo de alta resolucion, el BH1750 entrega como mucho 65535 / 1,2 = 54 612 lux: ahi se satura.
const float LUZ_MAXIMA = 54600.0;
// Si algo traba el programa mas de este tiempo (un sensor que se suelta justo mientras mide), la placa
// se reinicia sola. Tiene margen sobre las esperas normales: el WiFi (20 s) y una peticion HTTP (15 s).
const int SEGUNDOS_VIGILANCIA = 60;

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

// Las redes que ve la placa: sirve para saber si el hotspot está al alcance y en 2,4 GHz.
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
    luzListo = medidorLuz.begin(BH1750::ONE_TIME_HIGH_RES_MODE, 0x23, &Wire);
    Serial.println(luzListo ? "BH1750 listo (luz)." : "No responde el BH1750 en el bus I2C (0x23).");
  }
}

// La humedad en %, entre la calibración seca y la mojada; -1 si el sensor no está conectado.
// Siempre muestra la lectura cruda: con ella se calibra HUMEDAD_SECO y HUMEDAD_MOJADO.
float leerHumedad() {
  long suma = 0;
  int menor = 4095;
  int mayor = 0;
  for (int i = 0; i < MUESTRAS_HUMEDAD; i++) {
    int muestra = analogRead(PIN_HUMEDAD);
    suma += muestra;
    menor = min(menor, muestra);
    mayor = max(mayor, muestra);
    delay(5);
  }
  int crudo = suma / MUESTRAS_HUMEDAD;
  Serial.printf("Humedad: lectura cruda %d, salto %d (seco %d, mojado %d).\n", crudo, mayor - menor, HUMEDAD_SECO,
                HUMEDAD_MOJADO);
  if (crudo < CRUDO_MINIMO || crudo > CRUDO_MAXIMO || mayor - menor > SALTO_MAXIMO) return -1;
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

// Una medicion por lectura: se le pide al BH1750 cada vez. Si se reinicio por un falso contacto,
// queda apagado y en modo continuo devolveria 0 lux para siempre; asi vuelve a medir.
bool leerLuz(float &lux) {
  if (!luzListo) return false;
  if (!medidorLuz.configure(BH1750::ONE_TIME_HIGH_RES_MODE)) {
    luzListo = false;
    return false;
  }
  medidorLuz.measurementReady(true);  // espera lo que tarda una medicion (hasta 180 ms)
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
  esp_task_wdt_init(SEGUNDOS_VIGILANCIA, true);  // reinicia la placa si loop() queda trabado
  esp_task_wdt_add(NULL);

  Serial.println();
  Serial.println("Matera inteligente · sensor " CODIGO_SENSOR);
  Serial.println("API: " API_BASE);
  iniciarSensores();
  if (conectarWifi() && !comprobarApi()) avisarFallo();
}

void loop() {
  esp_task_wdt_reset();
  // Resta con signo: sigue funcionando cuando millis() da la vuelta, a los 49 días.
  if ((long)(millis() - proximoEnvio) < 0) {
    led(WiFi.status() == WL_CONNECTED);  // el LED sigue al WiFi también entre envíos
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
    String faltan[3];
    int cuantos = 0;
    if (humedad < 0) faltan[cuantos++] = "la humedad";
    if (!hayTemperatura) faltan[cuantos++] = "la temperatura";
    if (!hayLuz) faltan[cuantos++] = "la luz";
    String lista = faltan[0];
    for (int i = 1; i < cuantos; i++) lista += (i == cuantos - 1 ? " y " : ", ") + faltan[i];
    Serial.printf("No se envía: falta %s. Se reintenta en %lu s.\n", lista.c_str(), REINTENTO_MS / 1000);
    avisarFallo();
    proximoEnvio = millis() + REINTENTO_MS;
    return;
  }

  bool enviada = enviarMedicion(humedad, lux, temperatura);
  if (!enviada) avisarFallo();
  proximoEnvio = millis() + (enviada ? (unsigned long)INTERVALO_MS : REINTENTO_MS);
}
