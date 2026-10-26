// Configuración del sensor de la matera.
// Copie este archivo como config.h, en la misma carpeta, y complete sus datos.
// config.h no se sube al repositorio (está en .gitignore): lleva la clave del WiFi y la del sensor.
#pragma once

// Red WiFi de 2,4 GHz: la ESP32 no ve las redes de 5 GHz. Para la demo, el hotspot del celular
// (en iPhone, con «Maximizar compatibilidad» encendido). El nombre va exacto, con sus espacios:
// Windows puede mostrarlo sin un espacio del final. Si no conecta, el monitor serie lista las redes
// que ve la placa, con el nombre entre «». La red tiene que dar salida a internet: la hora sale de NTP.
#define WIFI_SSID "nombre-de-la-red"
#define WIFI_CLAVE "clave-de-la-red"

// La IP del PC que corre el backend con MATERA_HOST=0.0.0.0 (en Windows: ipconfig, «Dirección IPv4»).
// El hotspot puede darle otra IP al PC cada vez que se conecta: revísela antes de cada demo.
#define API_BASE "http://192.168.43.10:5000/api/v1"

// El código con el que se creó la matera en Mis materas y la clave que la API mostró una sola vez.
// La placa canjea la clave por su token al arrancar. Si se pierde la clave, «Cambiar sensor» con el
// mismo código entrega otra (y la anterior, con su token, deja de servir).
#define CODIGO_SENSOR "MT-0001-AA"
#define CLAVE_SENSOR "pegue-aqui-la-clave"

// Cada cuánto se envía una lectura, en milisegundos.
#define INTERVALO_MS 15000

// El módulo LDR solo dice si hay luz: con luz, su salida queda en LDR_CON_LUZ. Para saber cuál es,
// tape el sensor y mire la luz del módulo o el monitor serie; si da al revés, cambie LOW por HIGH.
// La perilla azul del módulo fija desde cuánta luz cuenta como «con luz».
#define LDR_CON_LUZ LOW

// Lo que se manda a la API, en lux, con luz y sin luz.
#define LUX_CON_LUZ 1500
#define LUX_SIN_LUZ 50
