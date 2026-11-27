#include "sensores.h"

#include <DHT.h>  // DHT sensor library, de Adafruit

#include "ajustes.h"
#include "memoria.h"

namespace {

DHT dht(PIN_DHT, DHT11);
CalibracionSuelo calibracion = {SUELO_SECO, SUELO_AGUA, false};

// El modulo LDR solo dice si hay luz o no; se manda en lux con dos valores fijos.
int leerLuz() {
  const bool hayLuz = digitalRead(PIN_LUZ) == LDR_CON_LUZ;
  return hayLuz ? LUX_CON_LUZ : LUX_SIN_LUZ;
}

bool calibracionSirve(int seco, int agua) {
  return abs(seco - agua) >= SUELO_DIFERENCIA_MINIMA;
}

void imprimirCalibracion() {
  if (calibracion.guardada) {
    Serial.printf("Suelo: calibrado, seco %d y agua %d.\n", calibracion.seco, calibracion.agua);
  } else {
    Serial.printf("Suelo: sin calibrar, se usan seco %d y agua %d de ajustes.h. Calibre con «calibrar seco» "
                  "(la sonda seca, al aire) y «calibrar agua» (metida en agua).\n",
                  calibracion.seco, calibracion.agua);
  }
}

}  // namespace

void sensoresIniciar() {
  pinMode(PIN_LUZ, INPUT);
  analogReadResolution(12);
  analogSetPinAttenuation(PIN_SUELO, ADC_11db);  // de 0 a unos 3,1 V
  int seco = 0;
  int agua = 0;
  if (memoriaCalibracionSuelo(seco, agua) && calibracionSirve(seco, agua)) {
    calibracion = {seco, agua, true};
  }
  imprimirCalibracion();
  dht.begin();
  // La primera lectura del DHT11 despues de encenderlo suele salir mal: se descarta.
  delay(2000);
  dht.readTemperature();
}

bool sensoresLeer(Lectura &lectura) {
  // La libreria no lo lee mas de una vez cada 2 s: antes de eso repite la lectura anterior.
  lectura.temperatura = dht.readTemperature();
  lectura.humedad = sueloPorcentaje(sensoresSueloCrudo(), calibracion.seco, calibracion.agua);
  lectura.luz = leerLuz();
  if (isnan(lectura.temperatura)) {
    Serial.printf("El DHT11 no respondió: revise que esté en GPIO%d y alimentado con 3V3.\n", PIN_DHT);
    return false;
  }
  return !isnan(lectura.humedad);  // no pasa: la calibracion se revisa antes de usarla
}

int sensoresSueloCrudo() {
  long suma = 0;
  for (int i = 0; i < SUELO_MUESTRAS; i++) {
    suma += analogRead(PIN_SUELO);
    delay(1);
  }
  return (int)(suma / SUELO_MUESTRAS);
}

CalibracionSuelo sensoresCalibracion() {
  return calibracion;
}

bool sensoresCalibrarSuelo(bool seco, int &crudo) {
  crudo = sensoresSueloCrudo();
  const int nuevoSeco = seco ? crudo : calibracion.seco;
  const int nuevaAgua = seco ? calibracion.agua : crudo;
  if (!calibracionSirve(nuevoSeco, nuevaAgua)) return false;
  calibracion = {nuevoSeco, nuevaAgua, true};
  memoriaGuardarCalibracionSuelo(nuevoSeco, nuevaAgua);
  return true;
}

void sensoresOlvidarCalibracion() {
  memoriaOlvidarCalibracionSuelo();
  calibracion = {SUELO_SECO, SUELO_AGUA, false};
  imprimirCalibracion();
}

float sueloPorcentaje(int crudo, int seco, int agua) {
  if (!calibracionSirve(seco, agua)) return NAN;
  const float porcentaje = 100.0f * (float)(seco - crudo) / (float)(seco - agua);
  return constrain(porcentaje, 0.0f, 100.0f);
}

bool autopruebaSuelo() {
  struct Caso {
    int crudo, seco, agua;
    float esperado;  // NAN: la calibracion no sirve
  };
  const Caso casos[] = {
      {4095, 4095, 2550, 0.0f},     // seca
      {2550, 4095, 2550, 100.0f},   // en agua
      {3322, 4095, 2550, 50.0f},    // en la mitad (3322,5)
      {4200, 4095, 2550, 0.0f},     // mas seca que lo calibrado: 0
      {1000, 4095, 2550, 100.0f},   // mas mojada que lo calibrado: 100
      {2000, 1000, 3000, 50.0f},    // un sensor que sube con el agua
      {2000, 2000, 2100, NAN},      // seco y agua casi iguales
  };
  bool bien = true;
  for (const Caso &c : casos) {
    const float obtenido = sueloPorcentaje(c.crudo, c.seco, c.agua);
    const bool casoBien = isnan(c.esperado) ? isnan(obtenido) : fabsf(obtenido - c.esperado) < 0.1f;
    bien = bien && casoBien;
  }
  Serial.printf("Autoprueba: humedad del suelo, de crudo a %% (%d casos) -> %s\n", (int)(sizeof casos / sizeof casos[0]),
                bien ? "bien" : "FALLA");
  return bien;
}
