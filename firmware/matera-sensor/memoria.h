// Memoria de la placa (NVS, con Preferences): la red, la clave del WiFi, los servidores, la clave del sensor
// y la calibracion del sensor de humedad del suelo.
//
// La clave del sensor se crea la primera vez y se conserva aunque se olvide la red. Si la memoria no tiene
// red y config.h define WIFI_SSID, WIFI_CLAVE y API_BASE, se usan esos como respaldo de desarrollo
// (no se guardan).
#pragma once

#include <Arduino.h>

const int MAX_SERVIDORES = 4;

// Lo que la placa necesita para llegar a su API: la red WiFi y las direcciones posibles del servidor,
// por ejemplo http://10.34.101.124:5000/api/v1.
struct Conexion {
  String red;
  String claveRed;  // vacia si la red es abierta
  String servidores[MAX_SERVIDORES];
  int cuantos = 0;
  String elegido;          // el servidor que respondio la ultima vez: se prueba primero
  bool deConfigH = false;  // viene de config.h, no de la memoria

  bool hayRed() const { return red.length() > 0; }
};

void memoriaIniciar();

// La de la memoria o, si no hay, la de config.h.
Conexion memoriaConexion();

// Guarda la red y los servidores que entrego la app. Olvida el servidor elegido.
void memoriaGuardarConexion(const Conexion &conexion);

// Recuerda el servidor que respondio, para probarlo primero la proxima vez.
void memoriaGuardarElegido(const String &base);

// Olvida la red y los servidores. La clave del sensor queda.
void memoriaOlvidarConexion();

// La clave del sensor. La crea y la guarda la primera vez.
String memoriaClaveSensor();

// Reemplaza la clave del sensor por una nueva.
String memoriaNuevaClaveSensor();

// La calibracion del sensor del suelo: los valores crudos con la sonda seca y en agua. false si nunca se
// calibro. Olvidar la red (BOOT 5 s o 15 s) no la borra: el sensor sigue siendo el mismo.
bool memoriaCalibracionSuelo(int &seco, int &agua);
void memoriaGuardarCalibracionSuelo(int seco, int agua);
void memoriaOlvidarCalibracionSuelo();
