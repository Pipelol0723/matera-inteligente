#include "pantalla.h"

#include <U8g2lib.h>
#include <Wire.h>

#include "ajustes.h"

namespace {

// La misma configuracion que la prueba de pantalla que funciono en la placa.
U8G2_SSD1306_128X64_NONAME_F_HW_I2C oled(U8G2_R0, U8X8_PIN_NONE, PIN_SCL, PIN_SDA);
bool presente = false;
String firmaActual;  // lo que se dibujo la ultima vez
bool invertida = false;

// Letras con el juego Latin-1 completo (_tf): tildes, ñ, ¡, «», °, ·.
const uint8_t *const LETRA = u8g2_font_6x13_tf;     // 6 puntos por letra: 21 por linea
const uint8_t *const NEGRITA = u8g2_font_7x14B_tf;  // 7 puntos: 18 por linea
const uint8_t *const CHICA = u8g2_font_5x8_tf;      // 5 puntos: 25 por linea
const uint8_t *const GRANDE = u8g2_font_10x20_tf;   // 10 puntos: el codigo MT-0000-XX cabe justo

const int ANCHO = 128;

// Empieza a dibujar si la pantalla cambia. `firma` resume todo lo que se va a dibujar.
bool empezar(const String &firma) {
  if (!presente || firma == firmaActual) return false;
  firmaActual = firma;
  oled.clearBuffer();
  oled.setDrawColor(1);
  return true;
}

void terminar() {
  oled.sendBuffer();
}

// Quita el ultimo caracter UTF-8 entero (las tildes ocupan 2 bytes).
void quitarUltimo(String &texto) {
  int fin = texto.length() - 1;
  while (fin > 0 && ((uint8_t)texto[fin] & 0xC0) == 0x80) fin--;
  texto.remove(fin < 0 ? 0 : fin);
}

// Recorta el texto, con un punto al final, si no cabe en `ancho` puntos con la letra actual.
String ajustar(const String &texto, int ancho) {
  if (oled.getUTF8Width(texto.c_str()) <= ancho) return texto;
  String recortado = texto;
  while (recortado.length() > 0) {
    quitarUltimo(recortado);
    if (oled.getUTF8Width((recortado + ".").c_str()) <= ancho) return recortado + ".";
  }
  return recortado;
}

void escribir(const uint8_t *letra, int x, int y, const String &texto, int ancho) {
  oled.setFont(letra);
  oled.drawUTF8(x, y, ajustar(texto, ancho).c_str());
}

void centrado(const uint8_t *letra, int y, const String &texto) {
  oled.setFont(letra);
  const String linea = ajustar(texto, ANCHO);
  oled.drawUTF8((ANCHO - oled.getUTF8Width(linea.c_str())) / 2, y, linea.c_str());
}

// Un pie de hasta dos lineas chicas, centradas, cortadas en los espacios.
void pie(const String &texto) {
  if (texto.length() == 0) return;
  oled.setFont(CHICA);
  if (oled.getUTF8Width(texto.c_str()) <= ANCHO) {
    centrado(CHICA, 60, texto);
    return;
  }
  // La primera linea lleva todas las palabras que quepan; el resto va abajo.
  int corte = -1;
  for (int i = 0; i < (int)texto.length(); i++) {
    if (texto[i] != ' ') continue;
    if (oled.getUTF8Width(texto.substring(0, i).c_str()) > ANCHO) break;
    corte = i;
  }
  if (corte < 0) {
    centrado(CHICA, 60, texto);
    return;
  }
  centrado(CHICA, 51, texto.substring(0, corte));
  centrado(CHICA, 61, texto.substring(corte + 1));
}

// Las caritas de la prueba de pantalla (radio 27), escaladas al radio `r`.
void dibujarCara(int cx, int cy, int r, Cara cara) {
  auto e = [r](int v) { return (v * r + 13) / 27; };
  oled.drawCircle(cx, cy, r);
  oled.drawCircle(cx, cy, r - 1);
  switch (cara) {
    case Cara::FELIZ:
      oled.drawDisc(cx - e(10), cy - e(7), e(3));
      oled.drawDisc(cx + e(10), cy - e(7), e(3));
      oled.drawCircle(cx, cy + e(1), e(13), U8G2_DRAW_LOWER_LEFT | U8G2_DRAW_LOWER_RIGHT);
      oled.drawCircle(cx, cy + e(1), e(12), U8G2_DRAW_LOWER_LEFT | U8G2_DRAW_LOWER_RIGHT);
      break;
    case Cara::PREOCUPADA:
      oled.drawDisc(cx - e(10), cy - e(7), e(3));
      oled.drawDisc(cx + e(10), cy - e(7), e(3));
      oled.drawBox(cx - e(11), cy + e(10), 2 * e(11), 2);
      break;
    case Cara::TRISTE:
      oled.drawLine(cx - e(15), cy - e(14), cx - e(6), cy - e(11));
      oled.drawLine(cx + e(15), cy - e(14), cx + e(6), cy - e(11));
      oled.drawDisc(cx - e(10), cy - e(5), e(2));
      oled.drawDisc(cx + e(10), cy - e(5), e(2));
      oled.drawCircle(cx, cy + e(20), e(11), U8G2_DRAW_UPPER_LEFT | U8G2_DRAW_UPPER_RIGHT);
      oled.drawCircle(cx, cy + e(20), e(10), U8G2_DRAW_UPPER_LEFT | U8G2_DRAW_UPPER_RIGHT);
      break;
  }
}

// Un globo de dialogo con su colita hacia la cara.
void dibujarGlobo(int x, int y, int ancho, int alto, const String &texto) {
  oled.drawRFrame(x, y, ancho, alto, 4);
  const int medio = y + alto / 2;
  oled.setDrawColor(0);
  oled.drawVLine(x, medio - 2, 5);
  oled.setDrawColor(1);
  oled.drawLine(x, medio - 3, x - 4, medio);
  oled.drawLine(x - 4, medio, x, medio + 3);
  oled.setFont(CHICA);
  const String linea = ajustar(texto, ancho - 4);
  oled.drawUTF8(x + (ancho - oled.getUTF8Width(linea.c_str())) / 2, medio + 3, linea.c_str());
}

}  // namespace

bool pantallaIniciar() {
  Wire.begin(PIN_SDA, PIN_SCL);
  uint8_t direccion = 0;
  for (uint8_t posible : {0x3C, 0x3D}) {
    Wire.beginTransmission(posible);
    if (Wire.endTransmission() == 0) {
      direccion = posible;
      break;
    }
  }
  if (direccion == 0) {
    Serial.printf("No hay pantalla en I2C (SDA GPIO%d, SCL GPIO%d): la placa sigue sin ella.\n", PIN_SDA, PIN_SCL);
    return false;
  }
  oled.setI2CAddress(direccion * 2);
  oled.begin();
  presente = true;
  Serial.printf("Pantalla OLED en 0x%02X.\n", direccion);
  return true;
}

void pantallaBienvenida(const String &codigo) {
  if (!empezar("bienvenida|" + codigo)) return;
  centrado(LETRA, 14, "Matera inteligente");
  centrado(GRANDE, 38, codigo);
  pie("iniciando...");
  terminar();
}

void pantallaConectando(const String &red, const String &detalle) {
  if (!empezar("conectando|" + red + "|" + detalle)) return;
  centrado(LETRA, 14, "Conectando a");
  centrado(NEGRITA, 33, "«" + red + "»");
  pie(detalle.length() > 0 ? detalle : String("..."));
  terminar();
}

void pantallaBuscandoServidor(const String &red, const String &detalle) {
  if (!empezar("buscando|" + red + "|" + detalle)) return;
  centrado(LETRA, 12, "Conectada a");
  centrado(NEGRITA, 29, "«" + red + "»");
  centrado(CHICA, 45, "buscando el servidor...");
  centrado(CHICA, 57, detalle);
  terminar();
}

void pantallaEsperandoMatera(const String &codigo, const String &detalle) {
  if (!empezar("esperando|" + codigo + "|" + detalle)) return;
  centrado(LETRA, 14, "Agrégame en la app");
  centrado(GRANDE, 38, codigo);
  pie(detalle);
  terminar();
}

void pantallaConectada(const String &codigo, const String &detalle) {
  if (!empezar("conectada|" + codigo + "|" + detalle)) return;
  centrado(LETRA, 14, "Conectada");
  centrado(GRANDE, 38, codigo);
  pie(detalle);
  terminar();
}

void pantallaMatera(Cara cara, const String &apodo, const String &estado, const String &linea, bool globo) {
  if (!empezar("matera|" + String((int)cara) + "|" + apodo + "|" + estado + "|" + linea + "|" + String(globo))) return;
  dibujarCara(27, 32, 25, cara);  // ocupa de x = 2 a x = 52
  const int x = 57;
  const int ancho = ANCHO - x;  // 71 puntos
  escribir(LETRA, x, 14, apodo, ancho);
  escribir(NEGRITA, x, 33, estado, ancho);
  if (globo) {
    dibujarGlobo(55, 40, ANCHO - 55, 19, linea);
  } else {
    oled.setFont(LETRA);
    escribir(oled.getUTF8Width(linea.c_str()) > ancho ? CHICA : LETRA, x, 52, linea, ancho);
  }
  terminar();
}

void pantallaAviso(const String &titulo, const String &destacado, const String &pie_) {
  if (!empezar("aviso|" + titulo + "|" + destacado + "|" + pie_)) return;
  centrado(LETRA, 14, titulo);
  centrado(NEGRITA, 34, destacado);
  pie(pie_);
  terminar();
}

void pantallaParpadeo(bool activo) {
  if (!presente) return;
  const bool invertir = activo && (millis() / 500) % 2 == 1;
  if (invertir == invertida) return;
  oled.sendF("c", invertir ? 0xA7 : 0xA6);  // modo inverso del SSD1306/SSD1315: no hay que redibujar
  invertida = invertir;
}
