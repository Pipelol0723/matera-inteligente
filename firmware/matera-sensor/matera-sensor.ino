// Matera inteligente: firmware de la placa, para la ESP32 con DHT11, modulo LDR y pantalla OLED
// (DevKit con CH340), en el Arduino IDE 2 o con arduino-cli.
//
// La placa tiene identidad propia. Su codigo (MT-0000-XX) sale de su MAC, y su clave la crea ella misma la
// primera vez y la guarda en su memoria (NVS). La app solo conoce la huella SHA-256 de esa clave: crea la
// matera con el codigo y la huella, y desde ahi el canje de la placa funciona (es el esquema de PKCE).
//
// La red y las direcciones del servidor se las da la app en el modo de conexion: por la red propia de la
// placa (red_propia.h), un WiFi WPA2 con una clave nueva cada vez que se abre, que la pantalla muestra en un
// QR; o por Bluetooth LE (bluetooth.h), con la misma clave. Los dos hablan el mismo contrato (api_local.h).
// Se abre sin red guardada, al mantener BOOT 5 s, si no entra a su WiFi en 60 s o si el servidor no
// responde en 2 minutos.
//
// Etapas, cada una con su pantalla:
//   SIN_RED            sin red: muestra el QR de su red propia y espera a la app.
//   CONECTANDO         se une a la red WiFi guardada.
//   BUSCANDO_SERVIDOR  prueba cada direccion sin la clave: el canje con {} tiene que dar el 400 en JSON de
//                      la API. Solo entonces canjea alli con la clave; cualquier respuesta JSON de ese canje,
//                      incluido un 401, dice que ese es el servidor.
//   ESPERANDO_MATERA   «Agregame en la app» y el codigo. Reintenta el canje cada 5 s mientras la API
//                      responda 401: la matera todavia no existe.
//   CONECTADA          una lectura cada INTERVALO_MS con su token, y la carita con lo que responde la API.
//                      Si el token deja de servir, vuelve a canjear; si la clave ya no sirve (le cambiaron el
//                      sensor a la matera o la borraron), vuelve a ESPERANDO_MATERA.
// BOOT 5 s olvida la red y los servidores, pero conserva la clave; BOOT 15 s, ademas, crea una clave nueva.
// La placa no decide ninguna regla: el estado, lo que necesita y las recomendaciones los calcula la API.
// Si un admin le pone a la matera un estado de prueba desde la app, la respuesta 201 lo trae en "prueba" y
// la pantalla lo muestra en vez de lo real, hasta que vuelva a llegar null.
// Las rutas estan en api_matera.h, los sensores en sensores.h y lo que guarda la placa en memoria.h.

#include <WiFi.h>
#include <esp_task_wdt.h>
#include <time.h>

#include "ajustes.h"
#include "api_matera.h"
#include "bluetooth.h"
#include "identidad.h"
#include "lector_json.h"
#include "memoria.h"
#include "pantalla.h"
#include "red_propia.h"
#include "sensores.h"

// Va aqui arriba: el IDE pone los prototipos de las funciones antes que el resto.
enum class Etapa : uint8_t { SIN_RED, CONECTANDO, BUSCANDO_SERVIDOR, ESPERANDO_MATERA, CONECTADA };

// ---- tiempos ----
const unsigned long ESPERA_WIFI_MS = 60000;     // cuanto se intenta entrar a la red antes de abrir la red propia
const unsigned long ESPERA_SERVIDOR_MS = 120000;  // sin respuesta de la API (con la red propia cerrada), la abre
const unsigned long REINTENTO_RED_MS = 60000;   // SIN_RED: cada cuanto vuelve a probar la red guardada
const unsigned long ESPERA_REINTENTO_MS = 20000;  // ese reintento dura menos: la red propia sigue abierta
const unsigned long CIERRE_RED_PROPIA_MS = 600000;  // ya en su WiFi, se cierra sola si nadie la usa en 10 min
const unsigned long BOOT_RED_MS = 5000;         // BOOT 5 s: olvida la red
const unsigned long BOOT_CLAVE_MS = 15000;      // BOOT 15 s: ademas, clave nueva
const unsigned long BOOT_CUENTA_MS = 1000;      // desde aqui la pantalla muestra la cuenta
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
unsigned long ultimaRespuestaApi = 0;  // desde aqui cuentan los 2 minutos sin servidor
volatile uint8_t razonDesconexion = 0;  // la ultima razon que dio el WiFi al cortar
volatile uint8_t fallosDeClave = 0;     // cortes que suelen ser por la clave del WiFi

// ---- red propia ----
bool esperandoApp = false;      // la red propia esta abierta para que la app entregue la red: se ve el QR
bool reintentoDeFondo = false;  // CONECTANDO a la red guardada con la red propia abierta, sin que la app lo pidiera
unsigned long redPropiaUsadaEn = 0;  // cuando se abrio, llego una configuracion o habia alguien unido

// ---- boton BOOT: lo mide una interrupcion, asi la cuenta es justa aunque loop() espere una respuesta HTTP ----
volatile bool bootApretado = false;
volatile unsigned long bootDesde = 0;
volatile bool bootSoltado = false;
volatile unsigned long bootDuracion = 0;

// ---- un mensaje que tapa la pantalla unos segundos ----
String mensajeTitulo, mensajeDestacado, mensajePie;
unsigned long mensajeHasta = 0;
bool hayMensaje = false;

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

// ---- la orden «prueba» del monitor serie: dibuja un estado de prueba sin la API ----
bool hayPruebaDeConsola = false;
PruebaMatera pruebaDeConsola;

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

void conectarWifi(const String &motivo) {
  redPropiaCortarBusqueda();  // la lista de redes se renueva sola: no tiene que cruzarse con este intento
  razonDesconexion = 0;
  fallosDeClave = 0;
  reintentoDeFondo = false;
  WiFi.disconnect();
  WiFi.begin(conexion.red.c_str(), conexion.claveRed.length() > 0 ? conexion.claveRed.c_str() : nullptr);
  cambiarEtapa(Etapa::CONECTANDO, motivo);
}

// Abre la red propia para que la app entregue la red o el servidor. Con `claveNueva`, aunque ya estuviera
// abierta la vuelve a abrir con otra clave; sin ella, si ya estaba abierta no corta a quien este unido.
void abrirRedPropia(bool claveNueva) {
  if (claveNueva || !redPropiaAbierta()) redPropiaAbrir(codigo, huella);
  esperandoApp = true;
  redPropiaUsadaEn = millis();
}

// No pudo entrar a la red en el plazo, o la red rechazo la clave: abre la red propia y espera a la app.
void redNoDisponible(const String &motivo) {
  Serial.printf("No se pudo conectar a «%s»: %s.\n", conexion.red.c_str(), motivo.c_str());
  WiFi.disconnect();  // deja de intentar: buscar la red cambia de canal y corta a quien este en la red propia
  reintentoDeFondo = false;
  abrirRedPropia(false);
  cambiarEtapa(Etapa::SIN_RED, motivo);
}

// La app entrego la red y los servidores por POST /configurar.
void aplicarConfiguracion(const Conexion &nueva) {
  conexion = nueva;
  memoriaGuardarConexion(conexion);
  servidor = "";
  token = "";
  hayEstado = false;
  esperandoApp = false;  // la red propia sigue abierta hasta POST /cerrar, pero ya no muestra el QR
  redPropiaUsadaEn = millis();
  Serial.printf("La app entregó la red «%s» y %d dirección(es) del servidor.\n", conexion.red.c_str(), conexion.cuantos);
  conectarWifi("");
}

// BOOT 5 s olvida la red y los servidores; BOOT 15 s, ademas, crea una clave nueva. En los dos casos se abre
// la red propia con otra clave.
void olvidarRed(bool claveNueva) {
  if (claveNueva) {
    claveSensor = memoriaNuevaClaveSensor();
    huella = huellaDe(claveSensor);
    Serial.printf("BOOT 15 s: clave nueva. Huella %s. La matera anterior deja de recibir lecturas hasta usar "
                  "«Cambiar sensor».\n", huella.c_str());
  } else {
    Serial.println("BOOT 5 s: la placa olvida la red y los servidores. Su clave queda.");
  }
  memoriaOlvidarConexion();
  conexion = Conexion();
  servidor = "";
  token = "";
  hayEstado = false;
  WiFi.disconnect();
  abrirRedPropia(true);
  cambiarEtapa(Etapa::SIN_RED, claveNueva ? "clave nueva: elige el WiFi en la app" : "red olvidada: elige el WiFi en la app");
  mensajeTitulo = claveNueva ? "Clave nueva" : "Red olvidada";
  mensajeDestacado = codigo;
  mensajePie = claveNueva ? "usa «Cambiar sensor» en la app" : "la clave del sensor se conserva";
  mensajeHasta = millis() + 4000;
  hayMensaje = true;
}

void ARDUINO_ISR_ATTR alCambiarBoot() {
  const bool apretado = digitalRead(PIN_BOOT) == LOW;
  const unsigned long ahora = millis();
  if (apretado && !bootApretado) {
    bootApretado = true;
    bootDesde = ahora;
  } else if (!apretado && bootApretado) {
    // Los rebotes del boton dan pulsaciones de milisegundos: no llegan a los 5 s y no hacen nada.
    bootApretado = false;
    bootDuracion = ahora - bootDesde;
    bootSoltado = true;
  }
}

void revisarBoot() {
  if (!bootSoltado) return;
  bootSoltado = false;
  const unsigned long duracion = bootDuracion;
  if (duracion >= BOOT_CLAVE_MS) olvidarRed(true);
  else if (duracion >= BOOT_RED_MS) olvidarRed(false);
}

// «prueba <cara> <condicion> <etapa> <dormida> [necesidad]» dibuja ese estado de prueba sin la API, en
// cualquier etapa, para ver cada combinacion en la pantalla. «prueba fin» vuelve a la pantalla de la etapa.
void ordenPrueba(String argumentos) {
  const char *uso = "Consola: prueba <SALUDABLE|EN_RIESGO|CRITICO> <SANA|DECAIDA|MARCHITA> "
                    "<SEMILLA|BROTE|PLANTA|FLORECIDA> <si|no> [SED|EXCESO_AGUA|FRIO|CALOR|POCA_LUZ|MUCHA_LUZ], "
                    "o «prueba fin».";
  argumentos.trim();
  argumentos.toUpperCase();
  if (argumentos == "FIN") {
    Serial.println(hayPruebaDeConsola ? "Consola: se quita la prueba; la pantalla vuelve a la etapa."
                                      : "Consola: no había una prueba de la consola.");
    hayPruebaDeConsola = false;
    return;
  }
  String partes[6];
  int cuantas = 0;
  while (argumentos.length() > 0 && cuantas < 6) {
    const int espacio = argumentos.indexOf(' ');
    partes[cuantas++] = espacio < 0 ? argumentos : argumentos.substring(0, espacio);
    argumentos = espacio < 0 ? String() : argumentos.substring(espacio + 1);
    argumentos.trim();
  }
  const bool caraValida = partes[0] == "SALUDABLE" || partes[0] == "EN_RIESGO" || partes[0] == "CRITICO";
  const bool condicionValida = partes[1] == "SANA" || partes[1] == "DECAIDA" || partes[1] == "MARCHITA";
  const bool etapaValida =
      partes[2] == "SEMILLA" || partes[2] == "BROTE" || partes[2] == "PLANTA" || partes[2] == "FLORECIDA";
  const bool dormidaValida = partes[3] == "SI" || partes[3] == "NO";
  const bool sinNecesidad = partes[4].length() == 0 || partes[4] == "-" || partes[4] == "NULL";
  const bool necesidadValida = sinNecesidad || textoNecesidad(partes[4]).length() > 0;
  if (cuantas < 4 || cuantas > 5 || argumentos.length() > 0 || !caraValida || !condicionValida || !etapaValida ||
      !dormidaValida || !necesidadValida) {
    Serial.println(uso);
    return;
  }
  PruebaMatera prueba;
  prueba.activa = true;
  prueba.cara = partes[0];
  prueba.condicion = partes[1];
  prueba.etapa = partes[2];
  prueba.dormida = partes[3] == "SI";
  prueba.necesidad = sinNecesidad ? String() : partes[4];
  pruebaDeConsola = prueba;
  hayPruebaDeConsola = true;
  Serial.printf("Consola: la pantalla muestra la prueba %s, sin la API. «prueba fin» la quita.\n",
                resumenPrueba(prueba).c_str());
}

// Ordenes por el monitor serie, para probar el modo de conexion sin apretar BOOT ni olvidar la red, y la
// pantalla del estado de prueba sin la API.
void revisarConsola() {
  static String linea;
  while (Serial.available() > 0) {
    const char c = (char)Serial.read();
    if (c != '\n' && c != '\r') {
      if (linea.length() < 96) linea += c;
      continue;
    }
    linea.trim();
    if (linea == "prueba" || linea.startsWith("prueba ")) {
      ordenPrueba(linea.substring(6));
    } else if (linea == "conexion") {
      if (redPropiaAbierta()) {
        Serial.println("Consola: el modo de conexión ya está abierto.");
      } else {
        Serial.println("Consola: se abre el modo de conexión sin olvidar la red.");
        abrirRedPropia(false);
      }
    } else if (linea == "cerrar") {
      if (!redPropiaAbierta()) {
        Serial.println("Consola: el modo de conexión ya está cerrado.");
      } else if (!conexion.hayRed()) {
        Serial.println("Consola: la placa no tiene red guardada; su red propia sigue abierta.");
      } else {
        Serial.println("Consola: se cierra el modo de conexión.");
        redPropiaCerrar();
      }
    } else if (linea == "memoria") {
      redPropiaImprimirRecursos("ahora");
    } else if (linea.length() > 0) {
      Serial.println("Consola: las órdenes son «conexion», «cerrar», «memoria» y «prueba».");
    }
    linea = "";
  }
}

// ---- servidor ----

void respondio() {
  fallosSeguidos = 0;
  ultimaRespuestaApi = millis();
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
  // Si la red propia se abrio por una falla y la placa se recupero sola, ya no hace falta.
  if (redPropiaAbierta() && esperandoApp && redPropiaClientes() == 0) {
    redPropiaCerrar();
    esperandoApp = false;
  }
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

// SIN_RED: si hay una red guardada, cada minuto la vuelve a probar, mientras nadie este en la red propia.
void pasoSinRed() {
  if (!conexion.hayRed()) return;
  if (redPropiaClientes() > 0) {
    desdeEtapa = millis();  // alguien esta configurando la placa: no se le corta la red
    return;
  }
  if (millis() - desdeEtapa < REINTENTO_RED_MS) return;
  Serial.printf("Se prueba otra vez la red «%s».\n", conexion.red.c_str());
  const String motivo = detalle;
  conectarWifi(motivo);
  reintentoDeFondo = true;
}

void pasoConectando() {
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("Conectada a «%s». IP de la placa: %s\n", conexion.red.c_str(), WiFi.localIP().toString().c_str());
    configTime(0, 0, "pool.ntp.org", "time.google.com");  // la hora en UTC: la API rechaza una lectura sin hora
    reintentoDeFondo = false;
    ultimaRespuestaApi = millis();  // los 2 minutos del servidor empiezan aqui
    buscarServidor();
    return;
  }
  if (razonDesconexion != 0) detalle = motivoWifi();
  // Si en un reintento de fondo alguien se une a la red propia, se deja de buscar la red para no cortarlo.
  if (reintentoDeFondo && redPropiaClientes() > 0) {
    redNoDisponible(detalle.length() > 0 ? detalle : motivoWifi());
    return;
  }
  const unsigned long plazo = reintentoDeFondo ? ESPERA_REINTENTO_MS : ESPERA_WIFI_MS;
  // Dos cortes por la clave seguidos: no vale la pena esperar el minuto.
  if (fallosDeClave >= 2 || millis() - desdeEtapa >= plazo) redNoDisponible(motivoWifi());
}

void pasoBuscandoServidor() {
  if (WiFi.status() != WL_CONNECTED) {
    conectarWifi("se perdió la red");
    return;
  }
  // 2 minutos sin respuesta: abre la red propia sin dejar el WiFi (AP_STA), para recibir otra direccion.
  // Mientras la red propia este abierta no cuenta: si la app corre en un PC unido a ella, el servidor es
  // inalcanzable hasta que la app la cierra. Los 2 minutos empiezan al cerrarla.
  if (!redPropiaAbierta() && millis() - ultimaRespuestaApi >= ESPERA_SERVIDOR_MS) {
    Serial.println("El servidor no responde hace 2 minutos: la placa abre su red para recibir otra dirección.");
    abrirRedPropia(false);
  }
  if (!llego(proximaAccion)) return;
  if (enOrden == 0) {
    abrirRedPropia(false);
    cambiarEtapa(Etapa::SIN_RED, "no hay direcciones del servidor");
    return;
  }
  // Un servidor por vuelta: uno que no existe tarda hasta 4 s en no contestar.
  const String base = orden[turno];
  detalle = sinEsquema(base);
  actualizarPantalla();
  RespuestaApi respuesta;
  String nuevoToken;
  // Primero sin la clave: solo una direccion que responde como la API la recibe.
  Canje canje = Canje::NO_ES_LA_API;
  if (apiProbarServidor(base, codigo, respuesta)) canje = apiCanjear(base, codigo, claveSensor, nuevoToken, respuesta);
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
      avisarCambioDePrueba(hayEstado ? estadoMatera.prueba : PruebaMatera(), nuevo.prueba);
      estadoMatera = nuevo;
      ultimaLectura = lectura;
      hayEstado = true;
      problema = "";
      Serial.printf("Lectura %.1f %% · %d lux · %.1f °C -> 201: «%s» está %s%s%s%s\n", lectura.humedad, lectura.luz,
                    lectura.temperatura, nuevo.apodo.c_str(), nuevo.estado.c_str(),
                    nuevo.necesidad.length() > 0 ? ", necesita " : "", nuevo.necesidad.c_str(),
                    nuevo.prueba.activa ? " (la pantalla muestra la prueba)" : "");
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

// La condicion del estado de prueba, con su tilde.
String textoCondicion(const String &condicion) {
  if (condicion == "DECAIDA") return "DECAÍDA";
  return condicion;  // SANA, MARCHITA
}

// Para el monitor serie: «FLORECIDA, MARCHITA, cara CRITICO, necesita EXCESO_AGUA» o «SEMILLA, SANA, cara
// SALUDABLE, dormida».
String resumenPrueba(const PruebaMatera &prueba) {
  String texto = prueba.etapa + ", " + prueba.condicion + ", cara " + prueba.cara;
  if (prueba.dormida) texto += ", dormida";
  if (prueba.necesidad.length() > 0) texto += ", necesita " + prueba.necesidad;
  return texto;
}

// Dice en el monitor serie cuando llega un estado de prueba (o cambia) y cuando se quita.
void avisarCambioDePrueba(const PruebaMatera &antes, const PruebaMatera &ahora) {
  if (ahora.activa) {
    const String resumen = resumenPrueba(ahora);
    if (!antes.activa || resumenPrueba(antes) != resumen) {
      Serial.printf("Estado de prueba: %s. La pantalla lo muestra en vez de lo real.\n", resumen.c_str());
    }
  } else if (antes.activa) {
    Serial.println("Se quitó el estado de prueba: la pantalla vuelve a lo real.");
  }
}

// El estado de prueba en vez de lo real: la carita de prueba.cara (o dormida), la etapa, la condicion y abajo
// el globo de su necesidad o el estado de la cara. Lo que falla ahora (`problema`) va antes que todo eso.
// Devuelve si la pantalla parpadea: con la cara CRITICO, salvo que duerma.
bool dibujarPrueba(const PruebaMatera &prueba, const String &problema) {
  String etapaEnMinusculas = prueba.etapa;
  etapaEnMinusculas.toLowerCase();
  String linea;
  bool globo = false;
  if (problema.length() > 0) {
    linea = problema;
  } else if (prueba.dormida) {
    linea = "zzz... dormida";  // la letra no tiene «…»: va en la chica, 70 puntos
  } else {
    const String necesita = textoNecesidad(prueba.necesidad);
    globo = necesita.length() > 0;
    linea = globo ? necesita : textoEstado(prueba.cara);
  }
  const Cara cara = prueba.dormida ? Cara::DORMIDA : caraDe(prueba.cara);
  pantallaPrueba(cara, etapaEnMinusculas, textoCondicion(prueba.condicion), linea, globo);
  return !prueba.dormida && prueba.cara == "CRITICO";
}

void actualizarPantalla() {
  bool parpadea = false;
  // Lo que se esta haciendo con BOOT, o un aviso de unos segundos, va antes que la etapa.
  const unsigned long apretado = bootApretado ? millis() - bootDesde : 0;
  if (apretado >= BOOT_CUENTA_MS) {
    pantallaBoot(apretado, BOOT_RED_MS, BOOT_CLAVE_MS);
    pantallaParpadeo(false);
    return;
  }
  if (hayMensaje && !llego(mensajeHasta)) {
    pantallaAviso(mensajeTitulo, mensajeDestacado, mensajePie);
    pantallaParpadeo(false);
    return;
  }
  hayMensaje = false;
  // La orden «prueba» del monitor serie tapa la etapa, incluido el QR, hasta «prueba fin».
  if (hayPruebaDeConsola) {
    pantallaParpadeo(dibujarPrueba(pruebaDeConsola, ""));
    return;
  }
  // Con la red propia abierta para la app, el QR.
  if (redPropiaAbierta() && esperandoApp) {
    pantallaRedPropia(redPropiaNombre(), redPropiaClave());
    pantallaParpadeo(false);
    return;
  }
  switch (etapa) {
    case Etapa::SIN_RED:
      pantallaAviso("Sin red WiFi", codigo, detalle.length() > 0 ? detalle : String("BOOT 5 s: abrir su red"));
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
      } else if (estadoMatera.prueba.activa) {
        parpadea = dibujarPrueba(estadoMatera.prueba, problema);
      } else {
        const String necesita = textoNecesidad(estadoMatera.necesidad);
        const bool globo = problema.length() == 0 && necesita.length() > 0;
        const String linea = problema.length() > 0 ? problema : (globo ? necesita : textoAire(ultimaLectura));
        pantallaMatera(caraDe(estadoMatera.estado), estadoMatera.apodo, textoEstado(estadoMatera.estado), linea, globo);
        parpadea = estadoMatera.estado == "CRITICO";
      }
      break;
  }
  pantallaParpadeo(parpadea);
}

// Lo que dice GET /estado de la API local, ademas de la etapa.
String detalleParaApp() {
  switch (etapa) {
    case Etapa::SIN_RED:
      return detalle.length() > 0 ? detalle : String("sin red guardada: elige el WiFi en la app");
    case Etapa::CONECTANDO:
      if (detalle.length() > 0) return "Conectando a «" + conexion.red + "»: " + detalle;
      return "Conectando a «" + conexion.red + "»";
    case Etapa::BUSCANDO_SERVIDOR:
      if (esperandoApp) return "el servidor no responde: la placa espera otra dirección";
      return "probando " + detalle;
    case Etapa::ESPERANDO_MATERA:
      if (detalle.length() > 0) return detalle;
      return "servidor " + sinEsquema(servidor) + ": falta crear la matera de " + codigo;
    case Etapa::CONECTADA:
      if (problema.length() > 0) return problema;
      if (!hayEstado) return "tomando la primera lectura";
      return "«" + estadoMatera.apodo + "» está " + estadoMatera.estado;
  }
  return "";
}

// Parpadeo rapido = la red propia espera a la app; lento = conectandose al WiFi; fijo = conectada al WiFi;
// apagado = sin WiFi.
void actualizarLed() {
  bool encendido;
  if (redPropiaAbierta() && esperandoApp) encendido = (millis() / 150) % 2 == 1;
  else if (etapa == Etapa::CONECTANDO) encendido = (millis() / 500) % 2 == 1;
  else encendido = WiFi.status() == WL_CONNECTED;
  digitalWrite(PIN_LED, encendido ? HIGH : LOW);
}

// La red propia: atiende a la app, aplica lo que entrega y se cierra sola cuando ya no hace falta.
void atenderRedPropia() {
  static bool estabaAbierta = false;
  if (redPropiaAbierta()) {
    redPropiaEstado(nombreEtapa(etapa), detalleParaApp());
    redPropiaAtender();  // aqui se cierra, medio segundo despues de un POST /cerrar
    Conexion nueva;
    if (redPropiaConfiguracion(nueva)) aplicarConfiguracion(nueva);
    if (redPropiaClientes() > 0) redPropiaUsadaEn = millis();
    // Si nadie la usa en 10 minutos y la placa ya esta en su WiFi, se cierra sola. Si la abrio porque el
    // servidor no responde, sigue abierta: espera otra direccion.
    const bool enSuWifi =
        etapa == Etapa::BUSCANDO_SERVIDOR || etapa == Etapa::ESPERANDO_MATERA || etapa == Etapa::CONECTADA;
    const bool esperaDireccion = etapa == Etapa::BUSCANDO_SERVIDOR && esperandoApp;
    if (redPropiaAbierta() && enSuWifi && !esperaDireccion && redPropiaClientes() == 0 &&
        millis() - redPropiaUsadaEn >= CIERRE_RED_PROPIA_MS) {
      Serial.println("La red propia lleva 10 minutos sin uso: se cierra.");
      redPropiaCerrar();
    }
  }
  if (estabaAbierta && !redPropiaAbierta()) {
    // Recien cerrada, por la app o sola: desde ahora la placa puede alcanzar el servidor, y desde ahora
    // cuentan los 2 minutos sin respuesta.
    esperandoApp = false;
    ultimaRespuestaApi = millis();
  }
  estabaAbierta = redPropiaAbierta();
}

// ---- programa ----

void setup() {
  Serial.begin(115200);
  delay(300);
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, LOW);
  pinMode(PIN_BOOT, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(PIN_BOOT), alCambiarBoot, CHANGE);
  esp_task_wdt_init(SEGUNDOS_VIGILANCIA, true);  // reinicia la placa si loop() queda trabado
  esp_task_wdt_add(NULL);
  bluetoothPreparar();

  uint8_t mac[6];
  const String textoMac = macDeLaPlaca(mac);
  codigo = codigoDesdeMac(mac);
  Serial.println();
  Serial.printf("Matera inteligente · sensor %s · MAC %s\n", codigo.c_str(), textoMac.c_str());
  autopruebaIdentidad();
  autopruebaJson();
  autopruebaApi();

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

  redPropiaImprimirRecursos("al arrancar");
  conexion = memoriaConexion();
  if (!conexion.hayRed()) {
    Serial.println("Sin red guardada: la placa abre su red para que la app le entregue el WiFi.");
    abrirRedPropia(true);
    cambiarEtapa(Etapa::SIN_RED, "");
    return;
  }
  Serial.printf("Red «%s», %s. Servidores:", conexion.red.c_str(), conexion.deConfigH ? "de config.h" : "de la memoria");
  for (int i = 0; i < conexion.cuantos; i++) Serial.printf(" %s", conexion.servidores[i].c_str());
  Serial.println();
  conectarWifi("");
}

void loop() {
  esp_task_wdt_reset();
  revisarBoot();
  revisarConsola();
  atenderRedPropia();
  switch (etapa) {
    case Etapa::SIN_RED:
      pasoSinRed();
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
