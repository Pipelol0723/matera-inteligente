// Identidad de la placa: su codigo sale de la MAC y su clave la crea ella misma.
//
// Codigo: FNV-1a de 32 bits sobre los 6 bytes de la MAC, en el orden en que se imprimen.
//   Los 4 digitos son n % 10000; con i = (n / 10000) % 676, las letras son 'A' + i / 26 y 'A' + i % 26.
//   30:76:f5:91:d9:9c da MT-5500-BA, 70:4b:ca:30:e4:dc da MT-7518-JP y 00:00:00:00:00:00 da MT-9933-JD.
// Clave: 32 bytes de esp_random en base64url sin relleno (43 caracteres), como secrets.token_urlsafe(32)
//   en el backend. La app solo conoce su huella: el SHA-256 del texto de la clave, en hexadecimal minuscula.
#pragma once

#include <Arduino.h>

// La MAC WiFi de la placa, como 30:76:f5:91:d9:9c. Tambien deja sus 6 bytes en `mac`.
String macDeLaPlaca(uint8_t mac[6]);

// MT-0000-XX a partir de los 6 bytes de la MAC.
String codigoDesdeMac(const uint8_t mac[6]);

// SHA-256 del texto, en hexadecimal minuscula (64 caracteres).
String huellaDe(const String &texto);

// Una clave nueva: 32 bytes al azar en base64url sin relleno.
String claveAlAzar();

// `largo` caracteres al azar de `alfabeto`, sin sesgo.
String textoAlAzar(const char *alfabeto, int largo);

// Revisa los vectores conocidos (SHA-256 de "abc", base64url y los tres codigos) y lo imprime.
bool autopruebaIdentidad();
