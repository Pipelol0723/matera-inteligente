// Matera inteligente: firmware de la placa, para la ESP32 con DHT11, modulo LDR y pantalla OLED
// (DevKit con CH340), en el Arduino IDE 2 o con arduino-cli.
//
// La placa tiene identidad propia. Su codigo (MT-0000-XX) sale de su MAC, y su clave la crea ella misma la
// primera vez y la guarda en su memoria (NVS). La app solo conoce la huella SHA-256 de esa clave: crea la
// matera con el codigo y la huella, y desde ahi el canje de la placa funciona (es el esquema de PKCE).
//
// Etapas, cada una con su pantalla:
//   CONECTANDO         se une a la red WiFi guardada.
//   BUSCANDO_SERVIDOR  prueba cada direccion de la API con el canje. Cualquier respuesta JSON de la API,
//                      incluido un 401, dice que ese es el servidor.
//   ESPERANDO_MATERA   «Agregame en la app» y el codigo. Reintenta el canje cada 5 s mientras la API
//                      responda 401: la matera todavia no existe.
//   CONECTADA          una lectura cada INTERVALO_MS con su token, y la carita con lo que responde la API.
//                      Si el token deja de servir, vuelve a canjear; si la clave ya no sirve (le cambiaron el
//                      sensor a la matera o la borraron), vuelve a ESPERANDO_MATERA.
//   SIN_RED            no tiene red guardada.
// La placa no decide ninguna regla: el estado, lo que necesita y las recomendaciones los calcula la API.
// Las rutas estan en api_matera.h, los sensores en sensores.h y lo que guarda la placa en memoria.h.

#include <WiFi.h>
#include <esp_task_wdt.h>
#include <time.h>

#include "ajustes.h"
#include "api_matera.h"
#include "identidad.h"
#include "lector_json.h"
#include "memoria.h"
#include "pantalla.h"
#include "sensores.h"

// Va aqui arriba: el IDE pone los prototipos de las funciones antes que el resto.
enum class Etapa : uint8_t { SIN_RED, CONECTANDO, BUSCANDO_SERVIDOR, ESPERANDO_MATERA, CONECTADA };

// ---- tiempos ----
const unsigned long ESPERA_WIFI_MS = 60000;     // cuanto se intenta entrar a la red antes de rendirse
const unsigned long REINTENTO_CANJE_MS = 5000;  // ESPERANDO_MATERA: cada cuanto pregunta si ya existe la matera
const unsigned long REINTENTO_MS = 5000;        // si falla la hora, el sensor o el envio
const unsigned long PAUSA_RONDA_MS = 5000;      // BUSCANDO_SERVIDOR: entre una ronda por los servidores y otra
const int FALLOS_PARA_BUSCAR = 3;               // envios seguidos sin respuesta antes de buscar el servidor otra vez
// Si algo traba el programa mas de este tiempo, la placa se reinicia sola. Una peticion HTTP tarda 12 s
// como mucho.
const int SEGUNDOS_VIGILANCIA = 60;
// Cualquier hora anterior a esta (2024-01-01) es la de una placa que todavia no sincronizo con NTP.
const time_t HORA_MINIMA = 1704067200;

// ---- identidad ----
String codigo;       // MT-0000-XX, de la MAC
String claveSensor;  // en la memoria; nunca se imprime
String huella;       // SHA-256 de la clave: lo unico que conoce la app

// ---- conexion ----
Conexion conexion;
String orden[MAX_SERVIDORES];  // los servidores en el orden en que se prueban: el elegido primero
int enOrden = 0;
int turno = 0;
String servidor;  // la base de la API que respondio
String token;     // el JWT del ultimo canje; vacio hasta canjear
int fallosSeguidos = 0;
volatile uint8_t razonDesconexion = 0;  // la ultima razon que dio el WiFi al cortar
volatile uint8_t fallosDeClave = 0;     // cortes que suelen ser por la clave del WiFi

// ---- etapa ----
Etapa etapa = Etapa::SIN_RED;
String detalle;  // lo que se ve abajo en la pantalla
unsigned long desdeEtapa = 0;
unsigned long proximaAccion = 0;
String ultimoAviso;  // para no repetir lo mismo en el monitor serie cada 5 s

// ---- lo ultimo que respondio la API en CONECTADA ----
bool hayEstado = false;
EstadoMatera estadoMatera;
Lectura ultimaLectura;
String problema;  // lo que falla ahora; vacio si nada

// ---- utilidades ----

const char *nombreEtapa(Etapa cual) {
  switch (cual) {
    case Etapa::SIN_RED: return "sin-red";
    case Etapa::CONECTANDO: return "conectando";
    case Etapa::BUSCANDO_SERVIDOR: return "buscando-servidor";
    case Etapa::ESPERANDO_MATERA: return "esperando-matera";
    case Etapa::CONECTADA: return "conectada";
  }
  return "?";
}

// Resta con signo: sigue funcionando cuando millis() da la vuelta, a los 49 dias.
bool llego(unsigned long momento) {
  return (long)(millis() - momento) >= 0;
}

void cambiarEtapa(Etapa nueva, const String &nuevoDetalle) {
  etapa = nueva;
  detalle = nuevoDetalle;
  desdeEtapa = millis();
  proximaAccion = millis();
  ultimoAviso = "";
  Serial.printf("[%s] %s\n", nombreEtapa(nueva), nuevoDetalle.c_str());
}

// Al monitor serie, sin repetir el mismo aviso en cada intento.
void avisar(const String &texto) {
  if (texto == ultimoAviso) return;
  ultimoAviso = texto;
  Serial.println(texto);
}

String sinEsquema(const String &base) {
  return base.startsWith("http://") ? base.substring(7) : base;
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

// ---- red WiFi ----

// Corre en la tarea del WiFi: solo guarda la razon.
void alDesconectarse(arduino_event_id_t evento, arduino_event_info_t info) {
  const uint8_t razon = info.wifi_sta_disconnected.reason;
  if (razon == WIFI_REASON_ASSOC_LEAVE) return;  // la corto la placa
  razonDesconexion = razon;
  if (razon == WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT || razon == WIFI_REASON_AUTH_FAIL ||
      razon == WIFI_REASON_HANDSHAKE_TIMEOUT) {
    fallosDeClave++;
  }
}

String motivoWifi() {
  switch (razonDesconexion) {
    case 0:
      return "la red no respondió";
    case WIFI_REASON_NO_AP_FOUND:
      return "no ve la red: ¿es de 2,4 GHz?";
    case WIFI_REASON_4WAY_HANDSHAKE_TIMEOUT:
    case WIFI_REASON_AUTH_FAIL:
    case WIFI_REASON_HANDSHAKE_TIMEOUT:
      return "la clave del WiFi no es correcta";
    case WIFI_REASON_ASSOC_FAIL:
    case WIFI_REASON_ASSOC_TOOMANY:
      return "la red no la dejó entrar: ¿límite de dispositivos?";
    default:
      return "no pudo entrar (motivo " + String(razonDesconexion) + ")";
  }
}

// Las redes que ve la placa: sirve para saber si la red esta al alcance y es de 2,4 GHz.
void mostrarRedes() {
  esp_task_wdt_reset();
  const int cuantas = WiFi.scanNetworks();
  Serial.printf("La placa ve %d redes:\n", cuantas);
  for (int i = 0; i < cuantas && i < 10; i++) {
    Serial.printf("  «%s», canal %d, señal %d dBm\n", WiFi.SSID(i).c_str(), WiFi.channel(i), WiFi.RSSI(i));
  }
  WiFi.scanDelete();
}

void conectarWifi(const String &motivo) {
  razonDesconexion = 0;
  fallosDeClave = 0;
  WiFi.disconnect();
  WiFi.begin(conexion.red.c_str(), conexion.claveRed.length() > 0 ? conexion.claveRed.c_str() : nullptr);
  cambiarEtapa(Etapa::CONECTANDO, motivo);
}

// No pudo entrar a la red en el plazo, o la clave esta mal.
void redNoDisponible(const String &motivo) {
  Serial.printf("No se pudo conectar a «%s»: %s.\n", conexion.red.c_str(), motivo.c_str());
  WiFi.disconnect();
  mostrarRedes();
  conectarWifi(motivo);
}

// ---- servidor ----

void respondio() {
  fallosSeguidos = 0;
}

void buscarServidor() {
  enOrden = 0;
  for (int i = 0; i < conexion.cuantos; i++) {
    if (conexion.servidores[i] == conexion.elegido) orden[enOrden++] = conexion.servidores[i];
  }
  for (int i = 0; i < conexion.cuantos && enOrden < MAX_SERVIDORES; i++) {
    if (conexion.servidores[i] != conexion.elegido) orden[enOrden++] = conexion.servidores[i];
  }
  turno = 0;
  token = "";
  fallosSeguidos = 0;
  cambiarEtapa(Etapa::BUSCANDO_SERVIDOR, enOrden > 0 ? sinEsquema(orden[0]) : String());
}

// La API no contesto. Despues de varios intentos seguidos, se buscan otra vez todos los servidores.
void sinRespuesta(const RespuestaApi &respuesta) {
  fallosSeguidos++;
  problema = "la API no responde";
  Serial.printf("La API no respondió en %s: %s.\n", servidor.c_str(), respuesta.resumen().c_str());
  proximaAccion = millis() + REINTENTO_MS;
  if (fallosSeguidos >= FALLOS_PARA_BUSCAR) buscarServidor();
}

void entrarConectada() {
  hayEstado = false;
  problema = "";
  cambiarEtapa(Etapa::CONECTADA, "");
}

void esperarMatera(const String &motivo) {
  if (etapa != Etapa::ESPERANDO_MATERA) {
    cambiarEtapa(Etapa::ESPERANDO_MATERA, motivo);
    Serial.printf("La API no conoce %s con esta clave: falta agregar la matera en la app (huella %s).\n",
                  codigo.c_str(), huella.c_str());
  }
  detalle = motivo;
  if (motivo.length() > 0) avisar(motivo);
  proximaAccion = millis() + REINTENTO_CANJE_MS;
}

// Lo que sigue despues de un canje que la API contesto, en BUSCANDO_SERVIDOR o ESPERANDO_MATERA.
void tratarCanje(Canje canje, const String &nuevoToken, const RespuestaApi &respuesta) {
  switch (canje) {
    case Canje::ACEPTADO:
      token = nuevoToken;
      Serial.println("Canje listo: la matera existe y la placa tiene su token.");
      entrarConectada();
      return;
    case Canje::CLAVE_RECHAZADA:
      esperarMatera("");
      return;
    case Canje::CUENTA_EN_PAUSA:
      esperarMatera("la cuenta del dueño está en pausa");
      return;
    default:
      esperarMatera("API: " + respuesta.resumen());
      return;
  }
}

// ---- pasos de cada etapa ----

void pasoConectando() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("Conectada a «%s». IP de la placa: %s\n", conexion.red.c_str(), WiFi.localIP().toString().c_str());
    configTime(0, 0, "pool.ntp.org", "time.google.com");  // la hora en UTC: la API rechaza una lectura sin hora
    buscarServidor();
    return;
  }
  if (razonDesconexion != 0) detalle = motivoWifi();
  // Dos cortes por la clave seguidos: no vale la pena esperar el minuto.
  if (fallosDeClave >= 2 || millis() - desdeEtapa >= ESPERA_WIFI_MS) redNoDisponible(motivoWifi());
}

void pasoBuscandoServidor() {
  if (WiFi.status() != WL_CONNECTED) {
    conectarWifi("se perdió la red");
    return;
  }
  if (!llego(proximaAccion)) return;
  if (enOrden == 0) {
    cambiarEtapa(Etapa::SIN_RED, "no hay direcciones del servidor");
    return;
  }
  // Un servidor por vuelta: uno que no existe tarda hasta 4 s en no contestar.
  const String base = orden[turno];
  detalle = sinEsquema(base);
  actualizarPantalla();
  RespuestaApi respuesta;
  String nuevoToken;
  const Canje canje = apiCanjear(base, codigo, claveSensor, nuevoToken, respuesta);
  if (canje == Canje::SIN_RESPUESTA || canje == Canje::NO_ES_LA_API) {
    Serial.printf("%s: %s\n", base.c_str(), respuesta.resumen().c_str());
    turno = (turno + 1) % enOrden;
    if (turno == 0) proximaAccion = millis() + PAUSA_RONDA_MS;
    return;
  }
  servidor = base;
  conexion.elegido = base;
  if (!conexion.deConfigH) memoriaGuardarElegido(base);
  Serial.printf("Servidor encontrado: %s (%s).\n", base.c_str(), respuesta.resumen().c_str());
  respondio();
  tratarCanje(canje, nuevoToken, respuesta);
}

void pasoEsperandoMatera() {
  if (WiFi.status() != WL_CONNECTED) {
    conectarWifi("se perdió la red");
    return;
  }
  if (!llego(proximaAccion)) return;
  RespuestaApi respuesta;
  String nuevoToken;
  const Canje canje = apiCanjear(servidor, codigo, claveSensor, nuevoToken, respuesta);
  if (canje == Canje::SIN_RESPUESTA || canje == Canje::NO_ES_LA_API) {
    sinRespuesta(respuesta);
    if (etapa == Etapa::ESPERANDO_MATERA) detalle = problema;
    return;
  }
  respondio();
  tratarCanje(canje, nuevoToken, respuesta);
}

// Se asegura de tener un token. Si no puede, deja lista la etapa o el problema y devuelve false.
bool asegurarToken() {
  if (token.length() > 0) return true;
  RespuestaApi respuesta;
  String nuevoToken;
  switch (apiCanjear(servidor, codigo, claveSensor, nuevoToken, respuesta)) {
    case Canje::ACEPTADO:
      respondio();
      token = nuevoToken;
      Serial.println("Canje listo: token nuevo.");
      return true;
    case Canje::CLAVE_RECHAZADA:
      respondio();
      Serial.println("401: la API ya no reconoce la clave (le cambiaron el sensor a la matera, o la borraron).");
      hayEstado = false;
      esperarMatera("");
      return false;
    case Canje::CUENTA_EN_PAUSA:
      respondio();
      problema = "cuenta en pausa";
      avisar("403: la cuenta del dueño de la matera está desactivada. La placa espera.");
      proximaAccion = millis() + INTERVALO_MS;
      return false;
    case Canje::OTRA_RESPUESTA:
      respondio();
      problema = "API: " + respuesta.resumen();
      avisar("Canje: " + respuesta.resumen() + " " + respuesta.mensaje);
      proximaAccion = millis() + REINTENTO_MS;
      return false;
    default:
      sinRespuesta(respuesta);
      return false;
  }
}

void pasoConectada() {
  if (WiFi.status() != WL_CONNECTED) {
    conectarWifi("se perdió la red");
    return;
  }
  if (!llego(proximaAccion)) return;
  if (time(nullptr) < HORA_MINIMA) {
    problema = "esperando la hora (NTP)";
    avisar("Sin hora todavía: la red tiene que dar salida a internet (puerto 123 de NTP).");
    proximaAccion = millis() + 1000;
    return;
  }
  if (!asegurarToken()) return;

  Lectura lectura;
  if (!sensoresLeer(lectura)) {
    problema = "el DHT11 no responde";
    proximaAccion = millis() + REINTENTO_MS;
    return;
  }
  EstadoMatera nuevo;
  RespuestaApi respuesta;
  Envio envio = apiEnviarLectura(servidor, codigo, token, momentoAhora(), lectura, nuevo, respuesta);
  if (envio == Envio::TOKEN_VENCIDO) {
    Serial.println("401: el token venció o lo reemplazó otro canje. Se canjea la clave otra vez.");
    token = "";
    if (!asegurarToken()) return;
    envio = apiEnviarLectura(servidor, codigo, token, momentoAhora(), lectura, nuevo, respuesta);
  }
  switch (envio) {
    case Envio::ACEPTADA:
      respondio();
      estadoMatera = nuevo;
      ultimaLectura = lectura;
      hayEstado = true;
      problema = "";
      Serial.printf("Lectura %.1f %% · %d lux · %.1f °C -> 201: «%s» está %s%s%s\n", lectura.humedad, lectura.luz,
                    lectura.temperatura, nuevo.apodo.c_str(), nuevo.estado.c_str(),
                    nuevo.necesidad.length() > 0 ? ", necesita " : "", nuevo.necesidad.c_str());
      proximaAccion = millis() + INTERVALO_MS;
      return;
    case Envio::TOKEN_VENCIDO:
      token = "";
      problema = "la API rechazó el token";
      proximaAccion = millis() + REINTENTO_MS;
      return;
    case Envio::CUENTA_EN_PAUSA:
      respondio();
      problema = "cuenta en pausa";
      avisar("403: la cuenta del dueño de la matera está desactivada. La placa espera.");
      proximaAccion = millis() + INTERVALO_MS;
      return;
    case Envio::RECHAZADA:
      respondio();
      problema = "API: " + respuesta.resumen();
      Serial.printf("Lectura rechazada: %s. %s\n", respuesta.resumen().c_str(), respuesta.mensaje.c_str());
      proximaAccion = millis() + INTERVALO_MS;
      return;
    case Envio::SIN_RESPUESTA:
      sinRespuesta(respuesta);
      return;
  }
}

// ---- pantalla y LED ----

Cara caraDe(const String &estado) {
  if (estado == "SALUDABLE") return Cara::FELIZ;
  if (estado == "CRITICO") return Cara::TRISTE;
  return Cara::PREOCUPADA;
}

String textoEstado(const String &estado) {
  if (estado == "EN_RIESGO") return "EN RIESGO";
  if (estado == "CRITICO") return "CRÍTICO";
  return estado;
}

// El globo con lo que necesita, tal como lo dice la API. Vacio si no necesita nada.
String textoNecesidad(const String &necesidad) {
  if (necesidad == "SED") return "¡tengo sed!";
  if (necesidad == "EXCESO_AGUA") return "¡me ahogo!";
  if (necesidad == "FRIO") return "¡tengo frío!";
  if (necesidad == "CALOR") return "¡tengo calor!";
  if (necesidad == "POCA_LUZ") return "¡poca luz!";
  if (necesidad == "MUCHA_LUZ") return "¡mucha luz!";
  return "";
}

// Por ejemplo «24,5°C 53%».
String textoAire(const Lectura &lectura) {
  String temperatura = String(lectura.temperatura, 1);
  temperatura.replace('.', ',');
  return temperatura + "°C " + String((int)lroundf(lectura.humedad)) + "%";
}

void actualizarPantalla() {
  switch (etapa) {
    case Etapa::SIN_RED:
      pantallaAviso("Sin red WiFi", codigo, detalle.length() > 0 ? detalle : String("falta config.h con la red"));
      break;
    case Etapa::CONECTANDO:
      pantallaConectando(conexion.red, detalle);
      break;
    case Etapa::BUSCANDO_SERVIDOR:
      pantallaBuscandoServidor(conexion.red, detalle);
      break;
    case Etapa::ESPERANDO_MATERA:
      pantallaEsperandoMatera(codigo, detalle);
      break;
    case Etapa::CONECTADA:
      if (!hayEstado) {
        pantallaConectada(codigo, problema.length() > 0 ? problema : String("tomando la primera lectura..."));
      } else {
        const String necesita = textoNecesidad(estadoMatera.necesidad);
        const bool globo = problema.length() == 0 && necesita.length() > 0;
        const String linea = problema.length() > 0 ? problema : (globo ? necesita : textoAire(ultimaLectura));
        pantallaMatera(caraDe(estadoMatera.estado), estadoMatera.apodo, textoEstado(estadoMatera.estado), linea, globo);
      }
      break;
  }
  pantallaParpadeo(etapa == Etapa::CONECTADA && hayEstado && estadoMatera.estado == "CRITICO");
}

// Parpadeo lento = conectandose al WiFi; fijo = conectada al WiFi; apagado = sin WiFi.
void actualizarLed() {
  const bool encendido = etapa == Etapa::CONECTANDO ? (millis() / 500) % 2 == 1 : WiFi.status() == WL_CONNECTED;
  digitalWrite(PIN_LED, encendido ? HIGH : LOW);
}

// ---- programa ----

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  esp_task_wdt_init(SEGUNDOS_VIGILANCIA, true);  // reinicia la placa si loop() queda trabado
  esp_task_wdt_add(NULL);

  uint8_t mac[6];
  const String textoMac = macDeLaPlaca(mac);
  codigo = codigoDesdeMac(mac);
  Serial.println();
  Serial.printf("Matera inteligente · sensor %s · MAC %s\n", codigo.c_str(), textoMac.c_str());
  autopruebaIdentidad();
  autopruebaJson();

  pantallaIniciar();
  pantallaBienvenida(codigo);

  // La radio se enciende antes de crear la clave: con ella, esp_random es aleatorio de verdad.
  String nombre = "matera-" + codigo.substring(3, 7) + codigo.substring(8);
  nombre.toLowerCase();
  WiFi.persistent(false);  // la red vive en la memoria de la placa, no en la del WiFi
  WiFi.setHostname(nombre.c_str());
  WiFi.onEvent(alDesconectarse, ARDUINO_EVENT_WIFI_STA_DISCONNECTED);
  WiFi.mode(WIFI_STA);

  memoriaIniciar();
  claveSensor = memoriaClaveSensor();
  huella = huellaDe(claveSensor);
  Serial.printf("Huella de su clave (SHA-256): %s\n", huella.c_str());
#if defined(CODIGO_SENSOR) || defined(CLAVE_SENSOR)
  Serial.println("config.h define CODIGO_SENSOR o CLAVE_SENSOR: se ignoran. La placa usa el código de su MAC y su clave.");
#endif

  sensoresIniciar();  // 2 s: descarta la primera lectura del DHT11

  conexion = memoriaConexion();
  if (!conexion.hayRed()) {
    cambiarEtapa(Etapa::SIN_RED, "");
    Serial.println("Sin red guardada: copie config.example.h como config.h con WIFI_SSID, WIFI_CLAVE y API_BASE.");
    return;
  }
  Serial.printf("Red «%s», %s. Servidores:", conexion.red.c_str(), conexion.deConfigH ? "de config.h" : "de la memoria");
  for (int i = 0; i < conexion.cuantos; i++) Serial.printf(" %s", conexion.servidores[i].c_str());
  Serial.println();
  conectarWifi("");
}

void loop() {
  esp_task_wdt_reset();
  switch (etapa) {
    case Etapa::SIN_RED:
      break;
    case Etapa::CONECTANDO:
      pasoConectando();
      break;
    case Etapa::BUSCANDO_SERVIDOR:
      pasoBuscandoServidor();
      break;
    case Etapa::ESPERANDO_MATERA:
      pasoEsperandoMatera();
      break;
    case Etapa::CONECTADA:
      pasoConectada();
      break;
  }
  actualizarPantalla();
  actualizarLed();
  delay(10);
}
