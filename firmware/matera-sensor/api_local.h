// El contrato de la API local de la placa, el mismo para sus dos adaptadores: HTTP en la red propia
// (red_propia.cpp) y Bluetooth LE (bluetooth.cpp). Aqui estan las reglas (que entrega info, como se valida
// configurar, que dice estado y cuando se puede cerrar) y las redes WiFi que ve la placa. Los adaptadores
// solo traducen: el HTTP, una ruta y su metodo; el Bluetooth, una operacion con la clave de la pantalla.
//
//   info        -> 200 {"codigo","huella","redes":[{"nombre","senal","segura"}]}
//   configurar  {"red","claveRed","servidores":[...]} -> 202 {"etapa","detalle"}
//   estado      -> 200 {"etapa": "conectando|buscando-servidor|esperando-matera|conectada|sin-red",
//                       "detalle": "..."}
//   cerrar      -> 204 sin cuerpo (409 SIN_RED si la placa todavia no tiene red)
// Los errores son {"error": "CODIGO", "mensaje": "texto para la persona"}; en un 400 tambien va
// "detalle": {"campo": "..."}, y en el 429 DEMASIADOS_INTENTOS del Bluetooth, "detalle": {"segundos": N},
// lo que falta para que la placa vuelva a atender.
#pragma once

#include <Arduino.h>

#include "memoria.h"

// Lo que responde una operacion: el codigo HTTP (el mismo que da la ruta por la red propia) y el JSON.
struct RespuestaLocal {
  int http;       // 200, 202, 204, 400, 409...
  String cuerpo;  // JSON; vacio en un 204
};

// El tamano maximo de un pedido: el cuerpo de POST /configurar o el JSON de una operacion por Bluetooth.
const size_t MAX_PEDIDO_LOCAL = 1024;

// Cuantas redes WiFi entrega info como maximo: las de mejor senal.
const int MAX_REDES = 15;

// {"error": "CODIGO", "mensaje": "..."}, y el campo que hay que corregir en un 400.
RespuestaLocal apiLocalError(int http, const char *error, const String &mensaje, const char *campo = nullptr);

// {"error": "CODIGO", "mensaje": "...", "detalle": {"segundos": N}}: cuantos segundos faltan para volver a
// intentar (el 429 de un bloqueo). La app arma su cuenta atras con ese numero, no con el texto.
RespuestaLocal apiLocalErrorConEspera(int http, const char *error, const String &mensaje, unsigned long segundos);

// Al abrir el modo de conexion: el codigo y la huella que entrega info. Olvida lo pendiente.
void apiLocalIniciar(const String &codigo, const String &huella);

// Al cerrarlo: olvida lo pendiente y corta una busqueda de redes en curso.
void apiLocalTerminar();

RespuestaLocal apiLocalInfo();
RespuestaLocal apiLocalConfigurar(const String &cuerpo);
RespuestaLocal apiLocalEstado();
RespuestaLocal apiLocalCerrar();

// Busca las redes WiFi y espera el resultado (unos segundos). Se usa al abrir el modo de conexion.
void apiLocalBuscarRedes();

// Termina una busqueda de fondo y, mientras nadie este unido a la red propia, renueva la lista cada 30 s
// (con alguien unido, solo despues de una info). Va en cada vuelta de loop().
void apiLocalRevisarBusqueda();

// Corta una busqueda de fondo: antes de entrar a una red WiFi, que no se lleva bien con buscar.
void apiLocalCortarBusqueda();

int apiLocalCuantasRedes();

// Lo que responde estado. La placa lo actualiza en cada vuelta.
void apiLocalEstadoPlaca(const char *etapa, const String &detalle);

// La configuracion que llego por configurar, una sola vez. Se entrega un momento despues de responder 202,
// para que la respuesta salga antes de que la placa cambie de canal al unirse al WiFi.
bool apiLocalConfiguracion(Conexion &conexion);

// true cuando ya paso ese momento despues de un cerrar aceptado: hay que apagar el modo de conexion.
bool apiLocalCierreVencido();
