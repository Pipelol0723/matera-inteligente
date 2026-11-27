// Sensores de esta placa:
//   Sensor de humedad del suelo en GPIO34, por su salida analogica (AO): la sonda resistiva HW-103 con su
//     modulo LM393 (o uno capacitivo). Da un valor crudo de 0 a 4095, que se pasa a % con la calibracion:
//     el valor con la sonda seca al aire es 0 % y el valor metida en agua es 100 %. Es la humedad del
//     sustrato que espera la API.
//   DHT11 en GPIO26: la temperatura. Tambien mide la humedad del aire, pero esa no se manda.
//   Modulo LDR (LM393) en GPIO18: solo dice si hay luz o no. Se manda en lux, con LUX_CON_LUZ o LUX_SIN_LUZ.
#pragma once

#include <Arduino.h>

// Lo que se manda a la API en cada lectura.
struct Lectura {
  float humedad;  // del suelo, en %
  int luz;
  float temperatura;
};

// Los valores crudos del sensor del suelo con la sonda seca y en agua.
struct CalibracionSuelo {
  int seco;
  int agua;
  bool guardada;  // false: son los de ajustes.h, todavia no se calibro este sensor
};

// Prepara los pines, el DHT11 y la calibracion del suelo (de la memoria, o la de ajustes.h). Tarda 2 s: la
// primera lectura del DHT11 sale mal y se descarta. Va despues de memoriaIniciar().
void sensoresIniciar();

// Lee los tres sensores. Devuelve false si el DHT11 no respondio.
bool sensoresLeer(Lectura &lectura);

// El valor crudo del suelo: el promedio de SUELO_MUESTRAS lecturas (0 a 4095).
int sensoresSueloCrudo();

CalibracionSuelo sensoresCalibracion();

// Mide el valor crudo de ahora y lo guarda como el de la sonda seca (`seco` = true) o en agua. No guarda
// nada y devuelve false si quedaria a menos de SUELO_DIFERENCIA_MINIMA del otro extremo. `crudo` es lo medido.
bool sensoresCalibrarSuelo(bool seco, int &crudo);

// Vuelve a la calibracion de ajustes.h.
void sensoresOlvidarCalibracion();

// De crudo a %: `seco` es 0 % y `agua` 100 %, en linea recta y recortado a 0-100. Sirve en los dos sentidos
// (en la sonda resistiva y en la capacitiva el valor baja con el agua, pero no tiene por que). NAN si
// seco y agua estan a menos de SUELO_DIFERENCIA_MINIMA.
float sueloPorcentaje(int crudo, int seco, int agua);

// Revisa sueloPorcentaje con valores de ejemplo.
bool autopruebaSuelo();
