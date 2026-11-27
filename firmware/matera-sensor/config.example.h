// Configuración opcional de la placa.
// La placa ya no la necesita: la red y la dirección del servidor se las da la app por la red propia de la
// placa, y su código y su clave los crea ella misma. Copie este archivo como config.h, en la misma carpeta,
// solo para cambiar algo de abajo; borre o comente lo que no quiera cambiar.
// config.h no se sube al repositorio (está en .gitignore): puede llevar la clave del WiFi.
#pragma once

// Respaldo de desarrollo: si la memoria de la placa no tiene red, usa esta red y esta dirección sin pasar
// por la app. No se guardan en la memoria. Tienen que estar los tres.
// La red es de 2,4 GHz (la ESP32 no ve las de 5 GHz) y con salida a internet, porque la hora sale de NTP.
// La dirección es la IP del PC que corre el backend con MATERA_HOST=0.0.0.0 (ipconfig, «Dirección IPv4»).
// #define WIFI_SSID "nombre-de-la-red"
// #define WIFI_CLAVE "clave-de-la-red"
// #define API_BASE "http://192.168.43.10:5000/api/v1"

// Cada cuánto se envía una lectura, en milisegundos.
// #define INTERVALO_MS 15000

// El módulo LDR solo dice si hay luz: con luz, su salida queda en LDR_CON_LUZ. En este módulo es LOW
// (comprobado tapándolo). La perilla azul del módulo fija desde cuánta luz cuenta como «con luz».
// #define LDR_CON_LUZ LOW

// Lo que se manda a la API, en lux, con luz y sin luz.
// #define LUX_CON_LUZ 1500
// #define LUX_SIN_LUZ 50

// La calibración de partida del sensor de humedad del suelo (valor crudo de 0 a 4095): con la sonda seca
// al aire (0 %) y metida en agua (100 %). Lo normal es no tocarlos y calibrar por el monitor serie con
// «calibrar seco» y «calibrar agua»: lo que se calibra así queda en la memoria y tiene prioridad.
// #define SUELO_SECO 4095
// #define SUELO_AGUA 2550

// Los pines, si se cablea distinto: DHT11, salida AO del sensor del suelo (solo GPIO32 a 39: los del ADC2
// no leen con el WiFi encendido), salida DO del LDR, pantalla (I2C), LED y botón BOOT.
// #define PIN_DHT 26
// #define PIN_SUELO 34
// #define PIN_LUZ 18
// #define PIN_SDA 21
// #define PIN_SCL 22
// #define PIN_LED 2
// #define PIN_BOOT 0
