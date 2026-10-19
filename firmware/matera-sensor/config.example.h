// Configuración del sensor de la matera.
// Copie este archivo como config.h, en la misma carpeta, y complete sus datos.
// config.h no se sube al repositorio (está en .gitignore): lleva la clave del WiFi y la del sensor.
#pragma once

// Red WiFi de 2,4 GHz: la ESP32 no ve las redes de 5 GHz. Para la demo, el hotspot del celular
// (en iPhone, con «Maximizar compatibilidad» encendido).
#define WIFI_SSID "nombre-de-la-red"
#define WIFI_CLAVE "clave-de-la-red"

// La IP del PC que corre el backend con MATERA_HOST=0.0.0.0 (en Windows: ipconfig, «Dirección IPv4»).
// El hotspot puede darle otra IP al PC cada vez que se conecta: revísela antes de cada demo.
#define API_BASE "http://192.168.43.10:5000/api/v1"

// El código con el que se creó la matera en Mis materas y la clave que la API mostró una sola vez.
// Si se pierde la clave, «Cambiar sensor» con el mismo código entrega otra.
#define CODIGO_SENSOR "MT-0001-AA"
#define CLAVE_SENSOR "pegue-aqui-la-clave"

// Cada cuánto se envía una medición, en milisegundos. Para la demo se puede bajar a 15000.
#define INTERVALO_MS 60000

// Calibración del sensor de humedad: la lectura cruda (0 a 4095) que muestra el monitor serie con
// el sensor al aire (seco) y con el sensor en un vaso de agua hasta la línea (mojado).
#define HUMEDAD_SECO 2800
#define HUMEDAD_MOJADO 1300
