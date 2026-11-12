// Ajustes de la placa: los pines y los valores del LDR, con los de la demo.
//
// config.h (copia de config.example.h) es opcional. Puede cambiar cualquiera de estos valores y,
// para desarrollar sin la app, dar una red y una API de respaldo (WIFI_SSID, WIFI_CLAVE y API_BASE).
// La red y los servidores que entrega la app quedan en la memoria de la placa y tienen prioridad.
#pragma once

#include <Arduino.h>

#if __has_include("config.h")
#include "config.h"
#define HAY_CONFIG_H 1
#else
#define HAY_CONFIG_H 0
#endif

// ---- pines de esta placa ----
#ifndef PIN_DHT
#define PIN_DHT 26  // DHT11: temperatura y humedad del aire
#endif
#ifndef PIN_LUZ
#define PIN_LUZ 18  // la salida digital (DO) del modulo LDR
#endif
#ifndef PIN_SDA
#define PIN_SDA 21  // pantalla OLED, I2C
#endif
#ifndef PIN_SCL
#define PIN_SCL 22
#endif
#ifndef PIN_LED
#define PIN_LED 2  // el LED azul de la placa
#endif
#ifndef PIN_BOOT
#define PIN_BOOT 0  // el boton BOOT
#endif

// ---- lecturas ----
#ifndef INTERVALO_MS
#define INTERVALO_MS 15000  // cada cuanto se envia una lectura
#endif
#ifndef LDR_CON_LUZ
#define LDR_CON_LUZ LOW  // el LM393 baja su salida cuando hay mas luz que la que marca su perilla
#endif
#ifndef LUX_CON_LUZ
#define LUX_CON_LUZ 1500
#endif
#ifndef LUX_SIN_LUZ
#define LUX_SIN_LUZ 50
#endif
