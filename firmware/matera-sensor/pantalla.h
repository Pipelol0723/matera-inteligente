// Pantalla OLED de 0,96" (NFP1315-157B, SSD1315, 128 x 64 puntos) en I2C: SDA GPIO21, SCL GPIO22, 0x3C.
// Usa U8g2 con letras que traen tildes, «», ¡ y °. Si la pantalla no esta, la placa sigue sin ella y
// todo queda en el monitor serie.
//
// Cada funcion dibuja una pantalla completa. Si se pide lo mismo que ya se ve, no la vuelve a mandar.
#pragma once

#include <Arduino.h>

enum class Cara : uint8_t { FELIZ, PREOCUPADA, TRISTE };

// Busca la pantalla en 0x3C (y 0x3D). Devuelve false si no responde.
bool pantallaIniciar();

// Al arrancar: el nombre del proyecto y el codigo de la placa.
void pantallaBienvenida(const String &codigo);

// «Conectando a «red»...», con el detalle abajo (por ejemplo, por que no entra).
void pantallaConectando(const String &red, const String &detalle);

// «Conectada a «red»», «buscando el servidor...» y la direccion que esta probando.
void pantallaBuscandoServidor(const String &red, const String &detalle);

// «Agregame en la app» y el codigo grande.
void pantallaEsperandoMatera(const String &codigo, const String &detalle);

// Conectada, antes de la primera respuesta 201.
void pantallaConectada(const String &codigo, const String &detalle);

// La carita a la izquierda; a la derecha el apodo, el estado y una linea: la temperatura y la humedad, un
// aviso, o el globo con lo que necesita (`globo` = true).
void pantallaMatera(Cara cara, const String &apodo, const String &estado, const String &linea, bool globo);

// Un mensaje de tres lineas: un titulo, una linea en negrita y un pie chico.
void pantallaAviso(const String &titulo, const String &destacado, const String &pie);

// Mientras `activo` sea true, invierte la pantalla cada medio segundo. Se llama en cada vuelta de loop().
void pantallaParpadeo(bool activo);
