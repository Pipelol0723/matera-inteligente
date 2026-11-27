// Ajustes de la placa: los pines, los valores del LDR y la calibracion inicial del sensor del suelo, con los
// de la demo.
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
#define PIN_DHT 26  // DHT11: la temperatura
#endif
#ifndef PIN_SUELO
#define PIN_SUELO 34  // la salida analogica (AO) del sensor de humedad del suelo; tiene que ser del ADC1 (32 a 39)
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

// ---- humedad del suelo ----
// El sensor da un valor crudo de 0 a 4095. SUELO_SECO es el valor con la sonda seca al aire (0 %) y
// SUELO_AGUA, metida en agua (100 %). Son los de partida: las ordenes «calibrar seco» y «calibrar agua» del
// monitor serie miden los de este sensor y los guardan en la memoria de la placa, que tienen prioridad.
#ifndef SUELO_SECO
#define SUELO_SECO 4095
#endif
#ifndef SUELO_AGUA
#define SUELO_AGUA 2550  // la sonda HW-103 del proyecto en agua de la llave, a 3,3 V (26 de noviembre)
#endif
#ifndef SUELO_DIFERENCIA_MINIMA
#define SUELO_DIFERENCIA_MINIMA 300  // seco y agua mas cerca que esto: la calibracion no sirve y se rechaza
#endif
#ifndef SUELO_MUESTRAS
#define SUELO_MUESTRAS 32  // cada lectura es el promedio de estas, para que el ruido del ADC no salte
#endif

// ---- Bluetooth del modo de conexion ----
// La placa atiende una conexion a la vez. Una conexion que todavia no mando un pedido con la clave de la
// pantalla se corta a los 20 s: quien se conecta sin la clave no puede quedarse con ella. Despues de una
// clave valida, el plazo pasa a 2 minutos sin pedidos con la clave (la app pide «estado» cada 45 s).
#ifndef BLE_SIN_CLAVE_MS
#define BLE_SIN_CLAVE_MS 20000UL
#endif
#ifndef BLE_INACTIVIDAD_MS
#define BLE_INACTIVIDAD_MS 120000UL
#endif
