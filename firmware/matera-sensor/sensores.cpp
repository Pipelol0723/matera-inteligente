#include "sensores.h"

#include <DHT.h>  // DHT sensor library, de Adafruit

#include "ajustes.h"

namespace {

DHT dht(PIN_DHT, DHT11);

// El modulo LDR solo dice si hay luz o no; se manda en lux con dos valores fijos.
int leerLuz() {
  const bool hayLuz = digitalRead(PIN_LUZ) == LDR_CON_LUZ;
  return hayLuz ? LUX_CON_LUZ : LUX_SIN_LUZ;
}

}  // namespace

void sensoresIniciar() {
  pinMode(PIN_LUZ, INPUT);
  dht.begin();
  // La primera lectura del DHT11 despues de encenderlo suele salir mal: se descarta.
  delay(2000);
  dht.readTemperature();
}

bool sensoresLeer(Lectura &lectura) {
  // La libreria no lo lee mas de una vez cada 2 s: antes de eso repite la lectura anterior.
  lectura.humedad = dht.readHumidity();
  lectura.temperatura = dht.readTemperature();
  lectura.luz = leerLuz();
  if (isnan(lectura.humedad) || isnan(lectura.temperatura)) {
    Serial.printf("El DHT11 no respondió: revise que esté en GPIO%d y alimentado con 3V3.\n", PIN_DHT);
    return false;
  }
  return true;
}
