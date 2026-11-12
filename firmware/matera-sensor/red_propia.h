// Red propia de la placa: un punto de acceso WPA2 con su API local en 192.168.4.1, para que la app le
// entregue la red WiFi y las direcciones del servidor.
//
// Nombre: «Matera-» y los digitos y las letras del codigo (MT-7518-JP abre Matera-7518JP). Clave: 8
// caracteres al azar de abcdefghjkmnpqrstuvwxyz23456789 (unos 40 bits), nuevos cada vez que se abre. Solo
// aparecen en la pantalla, con el QR de WiFi WIFI:T:WPA;S:<nombre>;P:<clave>;;
//
// API local: solo JSON, con CORS abierto, y solo para quien esta unido a la red propia.
//   GET  /info        -> 200 {"codigo","huella","redes":[{"nombre","senal","segura"}]}
//   POST /configurar  {"red","claveRed","servidores":[...]} -> 202 {"etapa","detalle"}
//   GET  /estado      -> 200 {"etapa": "conectando|buscando-servidor|esperando-matera|conectada|sin-red",
//                             "detalle": "..."}
//   POST /cerrar      -> 204, y apaga la red propia (409 si la placa todavia no tiene red)
//   OPTIONS           -> 204, la consulta previa de CORS
//   /                 -> una pagina minima que pide volver a la app
// Ademas, un DNS que responde todo con 192.168.4.1 y las pruebas de conexion de Android, iPhone y Windows,
// para que el celular no abandone la red por «no tener internet».
#pragma once

#include <Arduino.h>

#include "memoria.h"

// Abre la red propia con una clave nueva (si ya estaba abierta, la cierra antes). Primero mira las redes
// WiFi que hay, para GET /info: asi esa busqueda no corta a nadie.
void redPropiaAbrir(const String &codigo, const String &huella);

void redPropiaCerrar();

bool redPropiaAbierta();

// Atiende el DNS y la API local. Va en cada vuelta de loop().
void redPropiaAtender();

const String &redPropiaNombre();
const String &redPropiaClave();

// Cuantos celulares o PC estan unidos a la red propia.
int redPropiaClientes();

// Lo que responde GET /estado. La placa lo actualiza en cada vuelta.
void redPropiaEstado(const char *etapa, const String &detalle);

// La configuracion que llego por POST /configurar, una sola vez. Se entrega un momento despues de responder
// 202, para que la respuesta salga antes de que la placa cambie de canal al unirse al WiFi.
bool redPropiaConfiguracion(Conexion &conexion);
