#include "api_matera.h"

#include <HTTPClient.h>

#include "lector_json.h"

namespace {

// Un servidor que no existe en la red tarda en no contestar: no se espera mas que esto.
const int ESPERA_CONEXION_MS = 4000;
const int ESPERA_RESPUESTA_MS = 8000;

// Hace el POST y deja en `respuesta` el codigo, si es JSON y el error de la API. Devuelve el cuerpo.
String enviar(const String &url, const String &cuerpo, const String &token, RespuestaApi &respuesta) {
  respuesta = RespuestaApi();
  HTTPClient http;
  http.setConnectTimeout(ESPERA_CONEXION_MS);
  http.setTimeout(ESPERA_RESPUESTA_MS);
  http.setReuse(false);
  if (!http.begin(url)) {  // la direccion no es una URL http://
    respuesta.http = HTTPC_ERROR_CONNECTION_REFUSED;
    return String();
  }
  http.addHeader("Content-Type", "application/json");  // sin ella, la API responde 400
  if (token.length() > 0) http.addHeader("Authorization", String("Bearer ") + token);
  respuesta.http = http.POST(cuerpo);
  String texto = respuesta.http > 0 ? http.getString() : String();
  http.end();
  respuesta.json = jsonEsObjeto(texto);
  if (respuesta.json) {
    jsonTexto(texto, "error", respuesta.error);
    jsonTexto(texto, "mensaje", respuesta.mensaje);
  }
  return texto;
}

String numero(float valor) {
  return String(valor, 1);
}

}  // namespace

String RespuestaApi::resumen() const {
  if (http <= 0) return String("sin respuesta (") + HTTPClient::errorToString(http) + ")";
  String texto(http);
  if (error.length() > 0) texto += " " + error;
  else if (!json) texto += " (no es JSON)";
  return texto;
}

bool apiProbarServidor(const String &base, const String &codigo, RespuestaApi &respuesta) {
  // Sin la clave: el canje con {} es un 400 en JSON con su "error" (falta el campo clave).
  enviar(base + "/dispositivos/" + codigo + "/token", "{}", "", respuesta);
  return respuesta.http == 400 && respuesta.json && respuesta.error.length() > 0;
}

Canje apiCanjear(const String &base, const String &codigo, const String &clave, String &token, RespuestaApi &respuesta) {
  const String cuerpo = String("{\"clave\":") + jsonComillas(clave) + "}";
  const String texto = enviar(base + "/dispositivos/" + codigo + "/token", cuerpo, "", respuesta);
  if (respuesta.http <= 0) return Canje::SIN_RESPUESTA;
  // La API responde JSON hasta en sus errores (RA1). Un 404 en JSON es otra API, o la base sin /api/v1.
  if (!respuesta.json || respuesta.http == 404 || respuesta.http == 405) return Canje::NO_ES_LA_API;
  if (respuesta.http == 200) {
    String nuevo;
    if (jsonTexto(texto, "token", nuevo) && nuevo.length() > 0) {
      token = nuevo;
      return Canje::ACEPTADO;
    }
    return Canje::OTRA_RESPUESTA;  // un 200 sin token: no se acepta
  }
  if (respuesta.http == 401) return Canje::CLAVE_RECHAZADA;
  if (respuesta.http == 403 && respuesta.error == "CUENTA_DESACTIVADA") return Canje::CUENTA_EN_PAUSA;
  return Canje::OTRA_RESPUESTA;
}

void apiLeerEstado(const String &json, EstadoMatera &estado) {
  estado = EstadoMatera();
  jsonTexto(json, "planta.apodo", estado.apodo);
  jsonTexto(json, "diagnostico.estado", estado.estado);
  jsonTexto(json, "necesidad", estado.necesidad);  // null o ausente: sin globo
  PruebaMatera &prueba = estado.prueba;
  prueba.activa = jsonHayObjeto(json, "prueba");  // null o ausente: sin prueba
  if (!prueba.activa) return;
  jsonTexto(json, "prueba.etapa", prueba.etapa);
  jsonTexto(json, "prueba.condicion", prueba.condicion);
  jsonTexto(json, "prueba.cara", prueba.cara);
  jsonBooleano(json, "prueba.dormida", prueba.dormida);
  jsonTexto(json, "prueba.necesidad", prueba.necesidad);
}

bool autopruebaApi() {
  // Con prueba: la pantalla usa la prueba, pero el estado y la necesidad reales tambien se leen.
  const String conPrueba =
      "{\"planta\": {\"id\": 7, \"apodo\": \"sala\"}, \"diagnostico\": {\"estado\": \"SALUDABLE\"}, \"necesidad\": null,"
      " \"prueba\": {\"etapa\": \"FLORECIDA\", \"condicion\": \"MARCHITA\", \"cara\": \"CRITICO\", \"dormida\": false,"
      " \"necesidad\": \"EXCESO_AGUA\"}}";
  EstadoMatera estado;
  apiLeerEstado(conPrueba, estado);
  const PruebaMatera &prueba = estado.prueba;
  bool bien = estado.apodo == "sala" && estado.estado == "SALUDABLE" && estado.necesidad.length() == 0 &&
              prueba.activa && prueba.etapa == "FLORECIDA" && prueba.condicion == "MARCHITA" && prueba.cara == "CRITICO" &&
              !prueba.dormida && prueba.necesidad == "EXCESO_AGUA";

  // Dormida y sin necesidad.
  apiLeerEstado("{\"diagnostico\": {\"estado\": \"CRITICO\"}, \"necesidad\": \"SED\", \"prueba\": {\"etapa\": \"SEMILLA\","
                " \"condicion\": \"SANA\", \"cara\": \"SALUDABLE\", \"dormida\": true, \"necesidad\": null}}",
                estado);
  bien = bien && estado.necesidad == "SED" && prueba.activa && prueba.dormida && prueba.necesidad.length() == 0;

  // "prueba": null, y una respuesta de un backend de antes, sin el campo: sin prueba.
  apiLeerEstado("{\"diagnostico\": {\"estado\": \"EN_RIESGO\"}, \"necesidad\": \"FRIO\", \"prueba\": null}", estado);
  bien = bien && estado.estado == "EN_RIESGO" && estado.necesidad == "FRIO" && !prueba.activa;
  apiLeerEstado("{\"diagnostico\": {\"estado\": \"EN_RIESGO\"}, \"necesidad\": null}", estado);
  bien = bien && estado.estado == "EN_RIESGO" && !prueba.activa && prueba.etapa.length() == 0;

  Serial.printf("Autoprueba: estado de prueba en la respuesta 201 -> %s\n", bien ? "bien" : "FALLA");
  return bien;
}

Envio apiEnviarLectura(const String &base, const String &codigo, const String &token, const String &momento,
                       const Lectura &lectura, EstadoMatera &estado, RespuestaApi &respuesta) {
  const String cuerpo = String("{\"dispositivo\":") + jsonComillas(codigo) + ",\"momento\":" + jsonComillas(momento) +
                        ",\"lecturas\":{\"humedad\":" + numero(lectura.humedad) + ",\"luz\":" + String(lectura.luz) +
                        ",\"temperatura\":" + numero(lectura.temperatura) + "}}";
  const String texto = enviar(base + "/dispositivos/" + codigo + "/lecturas", cuerpo, token, respuesta);
  if (respuesta.http <= 0) return Envio::SIN_RESPUESTA;
  if (respuesta.http == 201 && respuesta.json) {
    apiLeerEstado(texto, estado);
    return Envio::ACEPTADA;
  }
  if (respuesta.http == 401 && respuesta.error == "CREDENCIAL_DISPOSITIVO_INVALIDA") return Envio::TOKEN_VENCIDO;
  if (respuesta.http == 403 && respuesta.error == "CUENTA_DESACTIVADA") return Envio::CUENTA_EN_PAUSA;
  return Envio::RECHAZADA;
}
