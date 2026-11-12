// Modo de conexion de la placa: su red propia (un punto de acceso WPA2 con su API local en 192.168.4.1) y,
// a la vez, el Bluetooth LE con el mismo contrato (bluetooth.h), para que la app le entregue la red WiFi y
// las direcciones del servidor. Las reglas de la API local estan en api_local.h; aqui esta su adaptador HTTP.
//
// Nombre: «Matera-» y los digitos y las letras del codigo (MT-7518-JP abre Matera-7518JP); el Bluetooth se
// anuncia con el mismo nombre. Clave: 8 caracteres al azar de abcdefghjkmnpqrstuvwxyz23456789 (unos 40
// bits), nuevos cada vez que se abre. Solo aparecen en la pantalla, con el QR de WiFi
// WIFI:T:WPA;S:<nombre>;P:<clave>;; y por Bluetooth cada pedido la trae.
//
// API local por HTTP: solo JSON, con CORS abierto, y solo para quien esta unido a la red propia.
//   GET  /info        -> 200 {"codigo","huella","redes":[{"nombre","senal","segura"}]}
//   POST /configurar  {"red","claveRed","servidores":[...]} -> 202 {"etapa","detalle"}
//   GET  /estado      -> 200 {"etapa": "conectando|buscando-servidor|esperando-matera|conectada|sin-red",
//                             "detalle": "..."}
//   POST /cerrar      -> 204, y apaga la red propia y el Bluetooth (409 si la placa todavia no tiene red)
//   OPTIONS           -> 204, la consulta previa de CORS
//   /                 -> una pagina minima que pide volver a la app
// Ademas, un DNS que responde todo con 192.168.4.1 y las pruebas de conexion de Android, iPhone y Windows,
// para que el celular no abandone la red por «no tener internet».
#pragma once

#include <Arduino.h>

#include "memoria.h"

// Abre la red propia con una clave nueva (si ya estaba abierta, la cierra antes) y enciende el Bluetooth.
// Primero mira las redes WiFi que hay, para info: asi esa busqueda no corta a nadie.
void redPropiaAbrir(const String &codigo, const String &huella);

// Apaga el Bluetooth y la red propia.
void redPropiaCerrar();

bool redPropiaAbierta();

// Atiende el DNS, la API local por HTTP y el Bluetooth. Va en cada vuelta de loop().
void redPropiaAtender();

const String &redPropiaNombre();
const String &redPropiaClave();

// Cuantos celulares o PC usan el modo de conexion: unidos a la red propia o conectados por Bluetooth.
int redPropiaClientes();

// Lo que responde estado. La placa lo actualiza en cada vuelta.
void redPropiaEstado(const char *etapa, const String &detalle);

// La configuracion que llego por configurar (HTTP o Bluetooth), una sola vez. Se entrega un momento despues
// de responder 202, para que la respuesta salga antes de que la placa cambie de canal al unirse al WiFi.
bool redPropiaConfiguracion(Conexion &conexion);

// Imprime el flash que usa el programa y la RAM libre, con `momento` («modo de conexion abierto»...).
void redPropiaImprimirRecursos(const char *momento);
