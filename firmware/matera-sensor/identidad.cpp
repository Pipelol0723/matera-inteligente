#include "identidad.h"

#include <esp_mac.h>
#include <esp_system.h>  // esp_random
#include <mbedtls/sha256.h>
#include <mbedtls/version.h>

namespace {

const char BASE64URL[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_";

uint32_t fnv1a(const uint8_t *datos, size_t largo) {
  uint32_t n = 2166136261u;
  for (size_t i = 0; i < largo; i++) {
    n ^= datos[i];
    n *= 16777619u;
  }
  return n;
}

String base64url(const uint8_t *datos, size_t largo) {
  String texto;
  texto.reserve((largo * 4 + 2) / 3);
  size_t i = 0;
  for (; i + 3 <= largo; i += 3) {
    uint32_t v = (uint32_t)datos[i] << 16 | (uint32_t)datos[i + 1] << 8 | datos[i + 2];
    texto += BASE64URL[(v >> 18) & 63];
    texto += BASE64URL[(v >> 12) & 63];
    texto += BASE64URL[(v >> 6) & 63];
    texto += BASE64URL[v & 63];
  }
  // Sin relleno: 1 byte suelto da 2 caracteres y 2 bytes dan 3.
  if (largo - i == 1) {
    uint32_t v = (uint32_t)datos[i] << 16;
    texto += BASE64URL[(v >> 18) & 63];
    texto += BASE64URL[(v >> 12) & 63];
  } else if (largo - i == 2) {
    uint32_t v = (uint32_t)datos[i] << 16 | (uint32_t)datos[i + 1] << 8;
    texto += BASE64URL[(v >> 18) & 63];
    texto += BASE64URL[(v >> 12) & 63];
    texto += BASE64URL[(v >> 6) & 63];
  }
  return texto;
}

String hexadecimal(const uint8_t *datos, size_t largo, const char *separador) {
  String texto;
  char par[3];
  for (size_t i = 0; i < largo; i++) {
    if (i > 0) texto += separador;
    snprintf(par, sizeof par, "%02x", datos[i]);
    texto += par;
  }
  return texto;
}

}  // namespace

String macDeLaPlaca(uint8_t mac[6]) {
  esp_read_mac(mac, ESP_MAC_WIFI_STA);  // la MAC base, la misma que imprime esptool
  return hexadecimal(mac, 6, ":");
}

String codigoDesdeMac(const uint8_t mac[6]) {
  uint32_t n = fnv1a(mac, 6);
  uint32_t i = (n / 10000) % 676;
  char texto[16];
  snprintf(texto, sizeof texto, "MT-%04u-%c%c", (unsigned)(n % 10000), (char)('A' + i / 26), (char)('A' + i % 26));
  return String(texto);
}

String huellaDe(const String &texto) {
  uint8_t resumen[32];
  mbedtls_sha256_context contexto;
  mbedtls_sha256_init(&contexto);
#if MBEDTLS_VERSION_NUMBER >= 0x03000000
  mbedtls_sha256_starts(&contexto, 0);
  mbedtls_sha256_update(&contexto, (const uint8_t *)texto.c_str(), texto.length());
  mbedtls_sha256_finish(&contexto, resumen);
#else
  mbedtls_sha256_starts_ret(&contexto, 0);
  mbedtls_sha256_update_ret(&contexto, (const uint8_t *)texto.c_str(), texto.length());
  mbedtls_sha256_finish_ret(&contexto, resumen);
#endif
  mbedtls_sha256_free(&contexto);
  return hexadecimal(resumen, sizeof resumen, "");
}

String claveAlAzar() {
  // esp_random es aleatorio de verdad con la radio encendida: se llama despues de WiFi.mode().
  uint8_t bytes[32];
  for (size_t i = 0; i < sizeof bytes; i += 4) {
    uint32_t azar = esp_random();
    memcpy(bytes + i, &azar, 4);
  }
  String clave = base64url(bytes, sizeof bytes);
  memset(bytes, 0, sizeof bytes);
  return clave;
}

String textoAlAzar(const char *alfabeto, int largo) {
  const uint32_t cuantos = strlen(alfabeto);
  // Se descartan los valores del final del rango que darian mas peso a las primeras letras.
  const uint32_t limite = UINT32_MAX - (UINT32_MAX % cuantos);
  String texto;
  texto.reserve(largo);
  for (int i = 0; i < largo; i++) {
    uint32_t azar;
    do {
      azar = esp_random();
    } while (azar >= limite);
    texto += alfabeto[azar % cuantos];
  }
  return texto;
}

bool autopruebaIdentidad() {
  bool bien = true;

  const String huellaAbc = huellaDe("abc");
  const bool huellaBien = huellaAbc == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad";
  Serial.printf("Autoprueba: SHA-256(\"abc\") = %s -> %s\n", huellaAbc.c_str(), huellaBien ? "bien" : "FALLA");
  bien = bien && huellaBien;

  uint8_t bytes[32];
  for (int i = 0; i < 32; i++) bytes[i] = i;
  const bool base64Bien = base64url(bytes, sizeof bytes) == "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8";
  Serial.printf("Autoprueba: base64url de los bytes 0 a 31 -> %s\n", base64Bien ? "bien" : "FALLA");
  bien = bien && base64Bien;

  struct Vector {
    uint8_t mac[6];
    const char *codigo;
  };
  const Vector vectores[] = {
      {{0x30, 0x76, 0xf5, 0x91, 0xd9, 0x9c}, "MT-5500-BA"},
      {{0x70, 0x4b, 0xca, 0x30, 0xe4, 0xdc}, "MT-7518-JP"},
      {{0x00, 0x00, 0x00, 0x00, 0x00, 0x00}, "MT-9933-JD"},
  };
  for (const Vector &v : vectores) {
    const String codigo = codigoDesdeMac(v.mac);
    const bool codigoBien = codigo == v.codigo;
    Serial.printf("Autoprueba: %s da %s -> %s\n", hexadecimal(v.mac, 6, ":").c_str(), codigo.c_str(),
                  codigoBien ? "bien" : "FALLA");
    bien = bien && codigoBien;
  }
  if (!bien) Serial.println("Autoprueba: ALGO FALLA. El codigo o la huella de esta placa no coinciden con la API.");
  return bien;
}
