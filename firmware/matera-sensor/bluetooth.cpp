#include "bluetooth.h"

#include <NimBLEDevice.h>
#include <esp_bt.h>
#include <esp_task_wdt.h>

#include "ajustes.h"
#include "api_local.h"
#include "lector_json.h"

namespace {

const char *const UUID_SERVICIO = "4d540001-d5b8-499f-bad6-c70b14aebec3";
const char *const UUID_PEDIDO = "4d540002-d5b8-499f-bad6-c70b14aebec3";
const char *const UUID_RESPUESTA = "4d540003-d5b8-499f-bad6-c70b14aebec3";

const size_t LARGO_ENCABEZADO = 3;  // numero de respuesta, indice del trozo y total de trozos
const size_t MAX_VALOR = 512;       // lo maximo de un atributo BLE: una escritura o una notificacion
const size_t MAX_TROZOS = 255;
const size_t MAX_ENTRADA = 2 * MAX_PEDIDO_LOCAL;  // lo que puede esperar a que loop() lo atienda
const size_t MAX_ID = 32;
const unsigned long ESPERA_PEDIDO_MS = 3000;  // un pedido a medias se descarta si en 3 s no llega otro pedazo
const int MAX_FALLIDOS = 5;                   // claves equivocadas seguidas antes del bloqueo
const unsigned long BLOQUEO_MS = 60000;
// Los plazos sin pedidos con la clave (BLE_SIN_CLAVE_MS y BLE_INACTIVIDAD_MS) estan en ajustes.h.
const unsigned long ESPERA_TROZO_MS = 2000;   // la cola de salida llena mas que esto: se abandona la respuesta
const unsigned long ENVIO_MAXIMO_MS = 10000;
const unsigned long DEMORA_CORTE_MS = 300;    // entre responder y cortar la conexion
// La pila y el controlador piden unos 40 KB al iniciarse: con menos de esto libre, no se inician.
const uint32_t MONTON_MINIMO = 60000;

// ---- compartido con la tarea de NimBLE (sus avisos corren alli). Lo protege el cerrojo ----
portMUX_TYPE cerrojo = portMUX_INITIALIZER_UNLOCKED;
uint8_t entrada[MAX_ENTRADA];  // lo escrito en la caracteristica del pedido, todavia sin leer
size_t enEntrada = 0;
bool entradaDesbordada = false;
volatile uint16_t conexion = BLE_HS_CONN_HANDLE_NONE;
volatile bool suscrito = false;      // el celular activo las notificaciones de la respuesta
volatile bool conexionNueva = false;

// encendido: el modo de conexion lo usa (se anuncia y atiende). Lo lee tambien la tarea de NimBLE.
volatile bool encendido = false;

// ---- solo de loop() ----
bool iniciada = false;  // la pila NimBLE: se inicia la primera vez y queda iniciada
String claveVigente;
NimBLEServer *servidor = nullptr;
NimBLECharacteristic *respuesta = nullptr;
unsigned long anuncioFallaDesde = 0;  // 0: se esta anunciando, o no hizo falta
bool anuncioFallaAvisada = false;
bool estabaConectado = false;
String pendiente;  // los bytes recibidos que todavia no forman un pedido completo
unsigned long ultimaLlegada = 0;  // cuando llego el ultimo pedazo
uint8_t numeroRespuesta = 0;
int fallidos = 0;
bool bloqueada = false;
unsigned long bloqueadaDesde = 0;
// El plazo de la conexion cuenta desde aqui: al conectarse y despues de cada pedido con la clave.
unsigned long plazoDesde = 0;
// La conexion ya mando un pedido con la clave de la pantalla. Hasta entonces tiene BLE_SIN_CLAVE_MS: asi
// alguien que se conecta y no manda nada (o solo claves malas) no ocupa la unica conexion por 2 minutos.
bool claveValidada = false;
bool cortarPronto = false;
unsigned long cortarDesde = 0;

// ---- avisos de NimBLE (corren en su tarea) ----

class AlConectar : public NimBLEServerCallbacks {
  // Una conexion a la vez. Al conectarse alguien la placa deja de anunciarse, asi que una segunda conexion
  // no deberia llegar; si llega, se corta.
  void onConnect(NimBLEServer *srv, ble_gap_conn_desc *desc) override {
    // Fuera del modo de conexion no se atiende a nadie (por si alguien se conecto justo al cerrarlo).
    if (!encendido || conexion != BLE_HS_CONN_HANDLE_NONE) {
      srv->disconnect(desc->conn_handle);
      return;
    }
    suscrito = false;
    conexion = desc->conn_handle;
    conexionNueva = true;
  }

  void onDisconnect(NimBLEServer *srv, ble_gap_conn_desc *desc) override {
    if (desc->conn_handle != conexion) return;
    conexion = BLE_HS_CONN_HANDLE_NONE;
    suscrito = false;
  }
};

class AlEscribir : public NimBLECharacteristicCallbacks {
  void onWrite(NimBLECharacteristic *caracteristica, ble_gap_conn_desc *desc) override {
    if (!encendido || desc->conn_handle != conexion) return;
    const NimBLEAttValue valor = caracteristica->getValue();
    portENTER_CRITICAL(&cerrojo);
    if (enEntrada + valor.size() <= MAX_ENTRADA) {
      memcpy(entrada + enEntrada, valor.data(), valor.size());
      enEntrada += valor.size();
    } else {
      entradaDesbordada = true;
    }
    portEXIT_CRITICAL(&cerrojo);
  }
};

class AlSuscribirse : public NimBLECharacteristicCallbacks {
  void onSubscribe(NimBLECharacteristic *caracteristica, ble_gap_conn_desc *desc, uint16_t valor) override {
    if (desc->conn_handle == conexion) suscrito = valor != 0;
  }
};

AlConectar alConectar;
AlEscribir alEscribir;
AlSuscribirse alSuscribirse;

// ---- utilidades ----

// Compara sin cortar en la primera diferencia: el tiempo no dice cuantas letras acerto.
bool mismaClave(const String &recibida, const String &vigente) {
  if (vigente.length() == 0 || recibida.length() != vigente.length()) return false;
  uint8_t diferencia = 0;
  for (size_t i = 0; i < vigente.length(); i++) diferencia |= (uint8_t)recibida[i] ^ (uint8_t)vigente[i];
  return diferencia == 0;
}

// El largo del primer objeto JSON de `texto`, que empieza con '{': 0 si todavia no se cierra.
size_t largoDelObjeto(const String &texto) {
  int profundidad = 0;
  bool enTexto = false;
  bool escape = false;
  for (size_t i = 0; i < texto.length(); i++) {
    const char c = texto[i];
    if (enTexto) {
      if (escape) escape = false;
      else if (c == '\\') escape = true;
      else if (c == '"') enTexto = false;
    } else if (c == '"') {
      enTexto = true;
    } else if (c == '{' || c == '[') {
      profundidad++;
    } else if (c == '}' || c == ']') {
      if (--profundidad == 0) return i + 1;
    }
  }
  return 0;
}

void quitarEspaciosDelInicio(String &texto) {
  size_t i = 0;
  while (i < texto.length() && (texto[i] == ' ' || texto[i] == '\t' || texto[i] == '\r' || texto[i] == '\n' || texto[i] == '\0')) {
    i++;
  }
  if (i > 0) texto.remove(0, i);
}

void cortar(const char *motivo) {
  const uint16_t actual = conexion;
  if (actual == BLE_HS_CONN_HANDLE_NONE || servidor == nullptr) return;
  Serial.printf("Bluetooth: se corta la conexión (%s).\n", motivo);
  servidor->disconnect(actual);
}

// Un trozo por notificacion. Si la cola de salida de NimBLE esta llena, espera a que el controlador la
// despache: asi no se pierde ningun trozo.
bool enviarTrozo(uint16_t destino, const uint8_t *datos, size_t largo) {
  const unsigned long desde = millis();
  while (millis() - desde < ESPERA_TROZO_MS) {
    if (conexion != destino) return false;
    os_mbuf *paquete = ble_hs_mbuf_from_flat(datos, largo);
    if (paquete != nullptr) {
      const int rc = ble_gattc_notify_custom(destino, respuesta->getHandle(), paquete);  // consume el paquete
      if (rc == 0) return true;
      if (rc != BLE_HS_ENOMEM) return false;
    }
    delay(5);
  }
  return false;
}

// La respuesta en trozos: [numero][indice][total] y hasta MTU - 6 bytes del JSON.
void enviar(const String &json, const String &op, int http) {
  const uint16_t destino = conexion;
  if (destino == BLE_HS_CONN_HANDLE_NONE) return;
  if (!suscrito) {
    Serial.println("Bluetooth: hay una respuesta, pero el celular no activó las notificaciones de la respuesta.");
    return;
  }
  size_t mtu = servidor->getPeerMTU(destino);
  if (mtu < 23) mtu = 23;  // el minimo de BLE
  const size_t util = mtu - 3 > MAX_VALOR ? MAX_VALOR : mtu - 3;
  const size_t carga = util - LARGO_ENCABEZADO;
  const size_t total = (json.length() + carga - 1) / carga;
  if (total > MAX_TROZOS) {  // no pasa: info, la mas larga, cabe en unos 100 trozos con el MTU minimo
    Serial.printf("Bluetooth: la respuesta tiene %u bytes y no cabe en %u trozos.\n", json.length(), MAX_TROZOS);
    return;
  }
  numeroRespuesta++;
  uint8_t trozo[MAX_VALOR];
  const unsigned long desde = millis();
  for (size_t i = 0; i < total; i++) {
    const size_t inicio = i * carga;
    const size_t largo = json.length() - inicio < carga ? json.length() - inicio : carga;
    trozo[0] = numeroRespuesta;
    trozo[1] = (uint8_t)i;
    trozo[2] = (uint8_t)total;
    memcpy(trozo + LARGO_ENCABEZADO, json.c_str() + inicio, largo);
    esp_task_wdt_reset();
    if (!enviarTrozo(destino, trozo, LARGO_ENCABEZADO + largo) || millis() - desde > ENVIO_MAXIMO_MS) {
      Serial.printf("Bluetooth: no se pudo enviar el trozo %u de %u.\n", i + 1, total);
      return;
    }
  }
  Serial.printf("Bluetooth: «%s» -> %d (%u bytes en %u trozo(s), MTU %u).\n", op.c_str(), http, json.length(), total, mtu);
}

// La misma respuesta que da la ruta HTTP, con el codigo HTTP adentro: {"op","id","http","cuerpo"}.
String sobre(const String &op, const String &id, const RespuestaLocal &respuestaLocal) {
  String texto = "{";
  if (op.length() > 0) texto += "\"op\":" + jsonComillas(op) + ",";
  if (id.length() > 0) texto += "\"id\":" + jsonComillas(id) + ",";
  texto += "\"http\":" + String(respuestaLocal.http) + ",\"cuerpo\":";
  texto += respuestaLocal.cuerpo.length() > 0 ? respuestaLocal.cuerpo : String("null");
  texto += "}";
  return texto;
}

// El 429 del bloqueo: los segundos que faltan van en el mensaje y en "detalle": {"segundos": N}.
RespuestaLocal demasiadosIntentos(unsigned long segundos) {
  return apiLocalErrorConEspera(429, "DEMASIADOS_INTENTOS",
                                "Demasiadas claves equivocadas: espere " + String(segundos) +
                                    " s y vuelva a intentarlo.",
                                segundos);
}

// La clave, el bloqueo y la operacion. Las reglas de cada operacion estan en api_local.
RespuestaLocal resolver(const String &pedido, const String &op) {
  if (pedido.length() > MAX_PEDIDO_LOCAL || !jsonEsObjeto(pedido)) {
    return apiLocalError(400, "SOLICITUD_INVALIDA",
                         "La placa no entendió el pedido: debe ser un objeto JSON de 1024 bytes como máximo.");
  }
  if (bloqueada) {
    // bluetoothAtender() levanta el bloqueo antes de atender, asi que faltan entre 1 y 60 s. Si el plazo se
    // cumplio justo entre medio, se dice 1 s: la resta sin signo no puede dar la vuelta.
    const unsigned long pasaron = millis() - bloqueadaDesde;
    return demasiadosIntentos(pasaron >= BLOQUEO_MS ? 1 : (BLOQUEO_MS - pasaron + 999) / 1000);
  }
  String clave;
  jsonTexto(pedido, "clave", clave);
  clave.trim();
  clave.toLowerCase();  // la clave solo tiene minusculas: el teclado del celular puede poner una mayuscula
  if (!mismaClave(clave, claveVigente)) {
    fallidos++;
    if (fallidos >= MAX_FALLIDOS) {
      bloqueada = true;
      bloqueadaDesde = millis();
      cortarPronto = true;
      cortarDesde = millis();
      Serial.printf("Bluetooth: %d claves equivocadas seguidas. No atiende pedidos durante %lu s.\n", fallidos,
                    BLOQUEO_MS / 1000);
      return demasiadosIntentos(BLOQUEO_MS / 1000);
    }
    Serial.printf("Bluetooth: pedido con una clave equivocada (%d de %d).\n", fallidos, MAX_FALLIDOS);
    const int quedan = MAX_FALLIDOS - fallidos;  // de 1 a 4: con 0 ya se bloqueo arriba
    String intentos = "Queda 1 intento.";
    if (quedan != 1) intentos = "Quedan " + String(quedan) + " intentos.";
    return apiLocalError(401, "CLAVE_INCORRECTA", "La clave no es la que muestra la pantalla de la placa. " + intentos,
                         "clave");
  }
  fallidos = 0;
  claveValidada = true;
  plazoDesde = millis();
  if (op == "info") return apiLocalInfo();
  if (op == "configurar") return apiLocalConfigurar(pedido);
  if (op == "estado") return apiLocalEstado();
  if (op == "cerrar") return apiLocalCerrar();
  return apiLocalError(400, "PARAMETRO_INVALIDO",
                       op.length() > 0 ? "La operación «" + op + "» no existe: use info, configurar, estado o cerrar."
                                       : String("Falta la operación: info, configurar, estado o cerrar."),
                       "op");
}

void atender(const String &pedido) {
  String op, id;
  if (pedido.length() <= MAX_PEDIDO_LOCAL) {
    jsonTexto(pedido, "op", op);
    if (jsonTexto(pedido, "id", id) && id.length() > MAX_ID) id = "";
  }
  const RespuestaLocal respuestaLocal = resolver(pedido, op);
  enviar(sobre(op, id, respuestaLocal), op, respuestaLocal.http);
}

// Pasa lo escrito por el celular a `pendiente` y atiende cada pedido completo.
void recibir() {
  // Un byte mas para el 0 del final: en el core 2.0.14, String::concat(const char *, largo) copia largo + 1
  // bytes (cuenta con ese 0). Sin el, con MAX_ENTRADA bytes pendientes leia uno fuera de la copia.
  static uint8_t copia[MAX_ENTRADA + 1];
  portENTER_CRITICAL(&cerrojo);
  const size_t llegaron = enEntrada;
  memcpy(copia, entrada, llegaron);
  copia[llegaron] = 0;
  enEntrada = 0;
  const bool desbordada = entradaDesbordada;
  entradaDesbordada = false;
  portEXIT_CRITICAL(&cerrojo);

  if (desbordada) {
    pendiente = "";
    enviar(sobre("", "", apiLocalError(400, "SOLICITUD_INVALIDA",
                                       "Llegaron demasiados datos juntos: un pedido tiene 1024 bytes como máximo.")),
           "", 400);
    return;
  }
  if (llegaron > 0) {
    pendiente.concat((const char *)copia, llegaron);
    ultimaLlegada = millis();
  }
  while (true) {
    quitarEspaciosDelInicio(pendiente);
    if (pendiente.length() == 0) return;
    if (pendiente[0] != '{') {
      pendiente = "";
      atender("x");  // no es un objeto: responde SOLICITUD_INVALIDA
      return;
    }
    const size_t largo = largoDelObjeto(pendiente);
    if (largo == 0) {
      // Todavia no se cierra: faltan pedazos. Con un MTU chico, 1024 bytes son unas 50 escrituras, asi que
      // el plazo cuenta desde el ultimo pedazo, no desde el primero.
      if (pendiente.length() > MAX_PEDIDO_LOCAL || millis() - ultimaLlegada > ESPERA_PEDIDO_MS) {
        pendiente = "";
        atender("x");
      }
      return;
    }
    const String pedido = pendiente.substring(0, largo);
    pendiente.remove(0, largo);
    atender(pedido);
  }
}

void olvidarConexion() {
  portENTER_CRITICAL(&cerrojo);
  enEntrada = 0;
  entradaDesbordada = false;
  portEXIT_CRITICAL(&cerrojo);
  pendiente = "";
  cortarPronto = false;
  claveValidada = false;  // cada conexion nueva tiene que volver a mandar la clave
}

// La pila NimBLE, el servidor, el servicio y el anuncio. Una sola vez: con NimBLE 1.4.3 y el core 2.0.14,
// apagarla (NimBLEDevice::deinit) y volver a iniciarla colgaba la placa (Guru Meditation en el nucleo 0),
// asi que al cerrar el modo de conexion la pila queda iniciada, pero callada: sin anuncio ni conexiones.
bool iniciar(const String &nombre) {
  if (iniciada) return true;
  if (ESP.getFreeHeap() < MONTON_MINIMO) {
    Serial.printf("Bluetooth: no se enciende, quedan %u bytes de RAM libres. La red propia sigue sola.\n",
                  ESP.getFreeHeap());
    return false;
  }
  NimBLEDevice::init(nombre.c_str());
  servidor = NimBLEDevice::createServer();
  servidor->setCallbacks(&alConectar, false);
  servidor->advertiseOnDisconnect(false);  // loop() decide si se vuelve a anunciar
  NimBLEService *servicio = servidor->createService(UUID_SERVICIO);
  NimBLECharacteristic *pedido = servicio->createCharacteristic(UUID_PEDIDO, NIMBLE_PROPERTY::WRITE, MAX_VALOR);
  pedido->setCallbacks(&alEscribir);
  pedido->createDescriptor("2901", NIMBLE_PROPERTY::READ, 20)->setValue((const uint8_t *)"pedido", 6);
  respuesta = servicio->createCharacteristic(UUID_RESPUESTA, NIMBLE_PROPERTY::NOTIFY, MAX_VALOR);
  respuesta->setCallbacks(&alSuscribirse);
  respuesta->createDescriptor("2901", NIMBLE_PROPERTY::READ, 20)->setValue((const uint8_t *)"respuesta", 9);
  servicio->start();
  // El UUID del servicio va en el anuncio (31 bytes) y el nombre en la respuesta al escaneo: los dos juntos
  // no caben. Web Bluetooth filtra por cualquiera de los dos.
  NimBLEAdvertising *anuncio = NimBLEDevice::getAdvertising();
  anuncio->addServiceUUID(UUID_SERVICIO);
  anuncio->setScanResponse(true);
  iniciada = true;
  return true;
}

}  // namespace

void bluetoothPreparar() {
  // La placa solo usa BLE: los ~30 KB del Bluetooth clasico vuelven al monton desde el arranque.
  esp_bt_controller_mem_release(ESP_BT_MODE_CLASSIC_BT);
}

bool bluetoothEncender(const String &nombre, const String &clave) {
  if (encendido) bluetoothApagar();
  if (!iniciar(nombre)) return false;
  conexion = BLE_HS_CONN_HANDLE_NONE;
  suscrito = false;
  conexionNueva = false;
  olvidarConexion();
  claveVigente = clave;
  fallidos = 0;
  bloqueada = false;
  anuncioFallaDesde = 0;
  anuncioFallaAvisada = false;
  estabaConectado = false;
  encendido = true;
  if (NimBLEDevice::getAdvertising()->start()) {
    Serial.printf("Bluetooth: se anuncia como «%s» (servicio %s).\n", nombre.c_str(), UUID_SERVICIO);
  } else {
    anuncioFallaDesde = millis();
    Serial.println("Bluetooth: no pudo empezar a anunciarse; lo vuelve a intentar.");
  }
  return true;
}

void bluetoothApagar() {
  if (!encendido) return;
  NimBLEDevice::getAdvertising()->stop();
  const uint16_t actual = conexion;
  if (actual != BLE_HS_CONN_HANDLE_NONE) {
    servidor->disconnect(actual);
    // Se espera el corte un momento: asi el celular sabe que la placa se fue, en vez de esperar su plazo.
    const unsigned long desde = millis();
    while (conexion != BLE_HS_CONN_HANDLE_NONE && millis() - desde < 500) delay(10);
  }
  // La pila queda iniciada (ver iniciar()): sin anuncio ni conexion, la radio del Bluetooth no transmite.
  conexion = BLE_HS_CONN_HANDLE_NONE;
  suscrito = false;
  conexionNueva = false;
  olvidarConexion();
  claveVigente = "";
  encendido = false;
  Serial.println("Bluetooth: deja de anunciarse y no acepta conexiones.");
}

bool bluetoothEncendido() {
  return encendido;
}

void bluetoothAtender() {
  if (!encendido) return;
  if (bloqueada && millis() - bloqueadaDesde >= BLOQUEO_MS) {
    bloqueada = false;
    fallidos = 0;
  }
  if (conexionNueva) {
    conexionNueva = false;
    olvidarConexion();
    plazoDesde = millis();
    estabaConectado = true;
    Serial.println("Bluetooth: se conectó un celular.");
  }
  if (conexion == BLE_HS_CONN_HANDLE_NONE) {
    if (estabaConectado) {
      estabaConectado = false;
      olvidarConexion();
      Serial.println("Bluetooth: el celular se desconectó.");
    }
    NimBLEAdvertising *anuncio = NimBLEDevice::getAdvertising();
    if (!anuncio->isAdvertising() && servidor->getConnectedCount() == 0) {
      if (anuncio->start()) {
        anuncioFallaDesde = 0;
        anuncioFallaAvisada = false;
      } else if (anuncioFallaDesde == 0) {
        anuncioFallaDesde = millis();  // justo despues de un corte suele fallar una vez: se reintenta
      } else if (!anuncioFallaAvisada && millis() - anuncioFallaDesde > 3000) {
        anuncioFallaAvisada = true;
        Serial.println("Bluetooth: no puede anunciarse hace 3 s; lo sigue intentando.");
      }
    }
    return;
  }
  // Con alguien conectado no se anuncia: asi nadie mas se conecta.
  if (NimBLEDevice::getAdvertising()->isAdvertising()) NimBLEDevice::getAdvertising()->stop();
  if (cortarPronto) {
    if (millis() - cortarDesde >= DEMORA_CORTE_MS) {
      cortarPronto = false;
      cortar("demasiadas claves equivocadas");
    }
    return;
  }
  // Sin la clave, BLE_SIN_CLAVE_MS desde que se conecto; con la clave, BLE_INACTIVIDAD_MS desde el ultimo
  // pedido con ella. Asi la unica conexion no queda tomada por alguien que no tiene la matera enfrente.
  const unsigned long plazo = claveValidada ? BLE_INACTIVIDAD_MS : BLE_SIN_CLAVE_MS;
  if (millis() - plazoDesde >= plazo) {
    plazoDesde = millis();
    cortar((String(plazo / 1000) + (claveValidada ? " s sin un pedido con la clave" : " s sin mandar la clave")).c_str());
    return;
  }
  recibir();
}

int bluetoothConectados() {
  return encendido && conexion != BLE_HS_CONN_HANDLE_NONE ? 1 : 0;
}
