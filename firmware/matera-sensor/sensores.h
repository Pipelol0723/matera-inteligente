// Sensores de esta placa:
//   DHT11 en GPIO26: temperatura y humedad DEL AIRE. La API espera la humedad del sustrato; para la demo
//     se manda la del aire, y se avisa en la presentacion.
//   Modulo LDR (LM393) en GPIO18: solo dice si hay luz o no. Se manda en lux, con LUX_CON_LUZ o LUX_SIN_LUZ.
#pragma once

#include <Arduino.h>

// Lo que se manda a la API en cada lectura.
struct Lectura {
  float humedad;
  int luz;
  float temperatura;
};

// Prepara los pines y el DHT11. Tarda 2 s: la primera lectura del DHT11 sale mal y se descarta.
void sensoresIniciar();

// Lee los dos sensores. Devuelve false si el DHT11 no respondio.
bool sensoresLeer(Lectura &lectura);
