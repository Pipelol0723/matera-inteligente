// La API de la matera, en las dos rutas de los dispositivos (las mismas del simulador):
//   1. Canje: cambia la clave del sensor por un token de alcance «lecturas», que vence a las 24 horas.
//        POST {base}/dispositivos/{codigo}/token     {"clave":"..."}
//        -> 200 {"token":"<JWT>","venceEn":"..."} · 401 CLAVE_SENSOR_INVALIDA si la API no conoce el codigo
//           o la clave (la matera todavia no existe, o le cambiaron el sensor) · 403 CUENTA_DESACTIVADA
//   2. Lectura, con ese token y la hora en que se tomo:
//        POST {base}/dispositivos/{codigo}/lecturas
//        Authorization: Bearer <JWT>
//        {"dispositivo":"MT-5500-BA","momento":"2026-10-22T15:04:05Z","lecturas":{"humedad":53.0,"luz":1500,"temperatura":25.5}}
//        -> 201 {"planta":{"apodo":...},"momento":...,"diagnostico":{"estado":...},"necesidad":"SED"|null}
//           · 401 CREDENCIAL_DISPOSITIVO_INVALIDA si el token vencio o lo reemplazo otro canje
// La placa no decide nada: el estado, la necesidad y las recomendaciones los calcula el backend.
#pragma once

#include <Arduino.h>

#include "sensores.h"

// Lo que respondio la API, para el monitor serie, la pantalla y GET /estado.
struct RespuestaApi {
  int http = 0;       // el codigo HTTP; negativo si no hubo respuesta (error de HTTPClient)
  bool json = false;  // el cuerpo es un objeto JSON
  String error;       // el campo "error" de la API, si vino
  String mensaje;     // el campo "mensaje" de la API, si vino

  // «401 CLAVE_SENSOR_INVALIDA» o «sin respuesta (connection refused)».
  String resumen() const;
};

enum class Canje {
  ACEPTADO,         // 200 con su token
  CLAVE_RECHAZADA,  // 401: la API no conoce este codigo con esta clave
  CUENTA_EN_PAUSA,  // 403 CUENTA_DESACTIVADA: el dueno de la matera esta desactivado
  OTRA_RESPUESTA,   // otra respuesta JSON de la API (400, 500...)
  NO_ES_LA_API,     // respondio, pero no en JSON, o 404/405: esa direccion no es la base de la API
  SIN_RESPUESTA,    // no hubo respuesta HTTP
};

// Dice si en `base` esta la API de la matera, sin mandar la clave: POST {base}/dispositivos/{codigo}/token
// con el cuerpo {} tiene que responder 400 en JSON con su campo "error". Asi la clave solo va a una
// direccion que ya demostro ser la API (la lista de la app puede traer IPs de adaptadores virtuales).
bool apiProbarServidor(const String &base, const String &codigo, RespuestaApi &respuesta);

Canje apiCanjear(const String &base, const String &codigo, const String &clave, String &token, RespuestaApi &respuesta);

// Lo que la placa muestra de la respuesta 201.
struct EstadoMatera {
  String apodo;      // planta.apodo
  String estado;     // diagnostico.estado: SALUDABLE, EN_RIESGO o CRITICO
  String necesidad;  // SED, EXCESO_AGUA, FRIO, CALOR, POCA_LUZ, MUCHA_LUZ; vacia si es null o no vino
};

enum class Envio {
  ACEPTADA,         // 201
  TOKEN_VENCIDO,    // 401 CREDENCIAL_DISPOSITIVO_INVALIDA: hay que canjear la clave otra vez
  CUENTA_EN_PAUSA,  // 403 CUENTA_DESACTIVADA
  RECHAZADA,        // otra respuesta de la API, por ejemplo 400 MOMENTO_INVALIDO
  SIN_RESPUESTA,
};

Envio apiEnviarLectura(const String &base, const String &codigo, const String &token, const String &momento,
                       const Lectura &lectura, EstadoMatera &estado, RespuestaApi &respuesta);
