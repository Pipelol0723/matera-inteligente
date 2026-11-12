#include "lector_json.h"

namespace {

// Un JSON con mas niveles que estos no es de la API ni de la app: se rechaza sin agotar la pila.
const int PROFUNDIDAD_MAXIMA = 12;

const int MAX_PRUEBA = 4;

void agregarUtf8(String &destino, uint32_t punto) {
  if (punto < 0x80) {
    destino += (char)punto;
  } else if (punto < 0x800) {
    destino += (char)(0xC0 | (punto >> 6));
    destino += (char)(0x80 | (punto & 0x3F));
  } else if (punto < 0x10000) {
    destino += (char)(0xE0 | (punto >> 12));
    destino += (char)(0x80 | ((punto >> 6) & 0x3F));
    destino += (char)(0x80 | (punto & 0x3F));
  } else {
    destino += (char)(0xF0 | (punto >> 18));
    destino += (char)(0x80 | ((punto >> 12) & 0x3F));
    destino += (char)(0x80 | ((punto >> 6) & 0x3F));
    destino += (char)(0x80 | (punto & 0x3F));
  }
}

class Lector {
 public:
  explicit Lector(const String &json) : texto_(json.c_str()), largo_(json.length()) {}

  void espacios() {
    while (pos_ < largo_ && (texto_[pos_] == ' ' || texto_[pos_] == '\t' || texto_[pos_] == '\n' || texto_[pos_] == '\r')) {
      pos_++;
    }
  }

  // Salta los espacios y dice si sigue el caracter `c` (sin avanzar sobre el).
  bool sigue(char c) {
    espacios();
    return pos_ < largo_ && texto_[pos_] == c;
  }

  void avanzar() { pos_++; }

  // Si sigue la palabra `palabra` entera (true, false), la salta. «trueish» no es «true».
  bool saltarPalabra(const char *palabra) {
    espacios();
    const size_t n = strlen(palabra);
    if (pos_ + n > largo_ || strncmp(texto_ + pos_, palabra, n) != 0) return false;
    if (pos_ + n < largo_ && isalnum((uint8_t)texto_[pos_ + n])) return false;
    pos_ += n;
    return true;
  }

  bool alFinal() {
    espacios();
    return pos_ >= largo_;
  }

  // Lee un texto a partir de su comilla. Con `destino` nulo, solo lo salta.
  bool leerTexto(String *destino) {
    if (!sigue('"')) return false;
    pos_++;
    while (pos_ < largo_) {
      const char c = texto_[pos_++];
      if (c == '"') return true;
      if ((uint8_t)c < 0x20) return false;  // un salto de linea sin escapar no es JSON
      if (c != '\\') {
        if (destino) *destino += c;
        continue;
      }
      if (pos_ >= largo_) return false;
      uint32_t punto;
      switch (texto_[pos_++]) {
        case '"': punto = '"'; break;
        case '\\': punto = '\\'; break;
        case '/': punto = '/'; break;
        case 'b': punto = '\b'; break;
        case 'f': punto = '\f'; break;
        case 'n': punto = '\n'; break;
        case 'r': punto = '\r'; break;
        case 't': punto = '\t'; break;
        case 'u':
          if (!leerUnicode(punto)) return false;
          break;
        default:
          return false;
      }
      if (destino) agregarUtf8(*destino, punto);
    }
    return false;  // falto la comilla del final
  }

  // Salta un valor cualquiera: texto, numero, true, false, null, objeto o lista.
  bool saltarValor(int profundidad) {
    if (profundidad > PROFUNDIDAD_MAXIMA) return false;
    espacios();
    if (pos_ >= largo_) return false;
    const char c = texto_[pos_];
    if (c == '"') return leerTexto(nullptr);
    if (c == '{' || c == '[') {
      const char cierre = c == '{' ? '}' : ']';
      pos_++;
      if (sigue(cierre)) {
        pos_++;
        return true;
      }
      while (true) {
        if (c == '{') {
          if (!leerTexto(nullptr) || !sigue(':')) return false;
          pos_++;
        }
        if (!saltarValor(profundidad + 1)) return false;
        if (sigue(',')) {
          pos_++;
          continue;
        }
        if (sigue(cierre)) {
          pos_++;
          return true;
        }
        return false;
      }
    }
    const size_t inicio = pos_;
    while (pos_ < largo_ && (isalnum((uint8_t)texto_[pos_]) || texto_[pos_] == '-' || texto_[pos_] == '+' || texto_[pos_] == '.')) {
      pos_++;
    }
    return pos_ > inicio;
  }

  // Con el lector en un objeto, avanza hasta el valor de `nombre`, sin entrar a los objetos de adentro.
  bool buscar(const String &nombre) {
    if (!sigue('{')) return false;
    pos_++;
    if (sigue('}')) return false;
    String campo;
    while (true) {
      campo = "";
      if (!leerTexto(&campo) || !sigue(':')) return false;
      pos_++;
      if (campo == nombre) {
        espacios();
        return true;
      }
      if (!saltarValor(1)) return false;
      if (!sigue(',')) return false;  // se acabo el objeto (o no era JSON) y no estaba
      pos_++;
    }
  }

  // Sigue una ruta separada por puntos, como «planta.apodo».
  bool ir(const char *ruta) {
    const String camino(ruta);
    int desde = 0;
    while (true) {
      const int punto = camino.indexOf('.', desde);
      if (!buscar(punto < 0 ? camino.substring(desde) : camino.substring(desde, punto))) return false;
      if (punto < 0) return true;
      desde = punto + 1;
    }
  }

 private:
  bool leerHex4(uint32_t &valor) {
    if (pos_ + 4 > largo_) return false;
    valor = 0;
    for (int i = 0; i < 4; i++) {
      const char c = texto_[pos_++];
      valor <<= 4;
      if (c >= '0' && c <= '9') valor |= c - '0';
      else if (c >= 'a' && c <= 'f') valor |= c - 'a' + 10;
      else if (c >= 'A' && c <= 'F') valor |= c - 'A' + 10;
      else return false;
    }
    return true;
  }

  // \uXXXX, y el par 🌱 de los caracteres que no caben en 16 bits.
  bool leerUnicode(uint32_t &punto) {
    if (!leerHex4(punto)) return false;
    if (punto >= 0xDC00 && punto <= 0xDFFF) {
      punto = 0xFFFD;
    } else if (punto >= 0xD800 && punto <= 0xDBFF) {
      uint32_t bajo;
      if (pos_ + 1 < largo_ && texto_[pos_] == '\\' && texto_[pos_ + 1] == 'u') {
        pos_ += 2;
        if (!leerHex4(bajo)) return false;
        punto = (bajo >= 0xDC00 && bajo <= 0xDFFF) ? 0x10000 + ((punto - 0xD800) << 10) + (bajo - 0xDC00) : 0xFFFD;
      } else {
        punto = 0xFFFD;
      }
    }
    return true;
  }

  const char *texto_;
  size_t largo_;
  size_t pos_ = 0;
};

}  // namespace

bool jsonEsObjeto(const String &json) {
  Lector lector(json);
  return lector.sigue('{') && lector.saltarValor(0) && lector.alFinal();
}

bool jsonTexto(const String &json, const char *ruta, String &valor) {
  Lector lector(json);
  String leido;
  if (!lector.ir(ruta) || !lector.leerTexto(&leido)) return false;
  valor = leido;
  return true;
}

bool jsonHayObjeto(const String &json, const char *ruta) {
  Lector lector(json);
  return lector.ir(ruta) && lector.sigue('{');
}

bool jsonBooleano(const String &json, const char *ruta, bool &valor) {
  Lector lector(json);
  if (!lector.ir(ruta)) return false;
  if (lector.saltarPalabra("true")) {
    valor = true;
    return true;
  }
  if (lector.saltarPalabra("false")) {
    valor = false;
    return true;
  }
  return false;
}

int jsonTextos(const String &json, const char *ruta, String destino[], int maximo) {
  Lector lector(json);
  if (!lector.ir(ruta) || !lector.sigue('[')) return -1;
  lector.avanzar();
  if (lector.sigue(']')) return 0;
  int cuantos = 0;
  while (true) {
    String leido;
    if (!lector.leerTexto(&leido)) return -1;
    if (cuantos < maximo) destino[cuantos] = leido;
    cuantos++;
    if (lector.sigue(',')) {
      lector.avanzar();
      continue;
    }
    return lector.sigue(']') ? cuantos : -1;
  }
}

String jsonComillas(const String &texto) {
  String salida;
  salida.reserve(texto.length() + 2);
  salida += '"';
  for (size_t i = 0; i < texto.length(); i++) {
    const char c = texto[i];
    if (c == '"' || c == '\\') {
      salida += '\\';
      salida += c;
    } else if ((uint8_t)c < 0x20) {
      char escape[7];
      snprintf(escape, sizeof escape, "\\u%04x", (uint8_t)c);
      salida += escape;
    } else {
      salida += c;
    }
  }
  salida += '"';
  return salida;
}

bool autopruebaJson() {
  // Una respuesta 201 como la de la API: el "estado" de los parametros va antes del global, y el apodo
  // trae una tilde escapada y unas comillas.
  const String respuesta =
      "{\"planta\": {\"id\": 7, \"apodo\": \"Sal\\u00f3n \\\"grande\\\"\", \"especie\": \"helecho\"},"
      " \"momento\": \"2026-11-11T15:04:05+00:00\","
      " \"diagnostico\": {\"especie\": \"helecho\", \"parametros\": [{\"nombre\": \"humedad\", \"estado\": \"BAJO\","
      " \"rangoOptimo\": [60, 85]}], \"estado\": \"CRITICO\", \"recomendaciones\": [\"Riegue: {no es JSON}\"]},"
      " \"necesidad\": \"SED\"}";
  String apodo, estado, necesidad;
  bool bien = jsonEsObjeto(respuesta) && jsonTexto(respuesta, "planta.apodo", apodo) &&
              apodo == "Sal\xC3\xB3n \"grande\"" && jsonTexto(respuesta, "diagnostico.estado", estado) &&
              estado == "CRITICO" && jsonTexto(respuesta, "necesidad", necesidad) && necesidad == "SED";

  // necesidad en null, o sin el campo: no hay globo.
  String nada;
  bien = bien && !jsonTexto("{\"planta\":{},\"necesidad\":null}", "necesidad", nada);
  bien = bien && !jsonTexto("{\"planta\":{\"necesidad\":\"SED\"}}", "necesidad", nada);

  // El estado de prueba: un objeto con un booleano y un null adentro; null o sin el campo, no hay objeto.
  const String conPrueba =
      "{\"necesidad\": \"SED\", \"prueba\": {\"cara\": \"CRITICO\", \"dormida\": true, \"necesidad\": null}}";
  bool dormida = false;
  bien = bien && jsonHayObjeto(conPrueba, "prueba") && jsonBooleano(conPrueba, "prueba.dormida", dormida) && dormida &&
         jsonTexto(conPrueba, "prueba.cara", nada) && nada == "CRITICO" && !jsonTexto(conPrueba, "prueba.necesidad", nada);
  bien = bien && !jsonHayObjeto("{\"prueba\": null}", "prueba") && !jsonHayObjeto("{\"planta\": {}}", "prueba") &&
         !jsonHayObjeto("{\"planta\": {\"prueba\": {}}}", "prueba");
  bien = bien && jsonBooleano("{\"a\": false}", "a", dormida) && !dormida && !jsonBooleano("{\"a\": \"true\"}", "a", dormida) &&
         !jsonBooleano("{\"a\": null}", "a", dormida) && !jsonBooleano("{\"a\": 1}", "a", dormida);

  // Lo que manda la app a POST /configurar.
  String servidores[MAX_PRUEBA];
  const String configurar = "{\"red\":\"honor de pipe\",\"claveRed\":\"x\",\"servidores\":[\"http://10.0.0.2:5000/api/v1\",\"b\"]}";
  bien = bien && jsonTextos(configurar, "servidores", servidores, MAX_PRUEBA) == 2 &&
         servidores[0] == "http://10.0.0.2:5000/api/v1" && servidores[1] == "b";
  bien = bien && jsonTextos("{\"servidores\":[1]}", "servidores", servidores, MAX_PRUEBA) == -1;

  // Lo que no es un objeto JSON entero.
  bien = bien && !jsonEsObjeto("<html></html>") && !jsonEsObjeto("{\"a\":1") && !jsonEsObjeto("{\"a\":1} x");
  bien = bien && jsonComillas("di \"hola\"\n") == "\"di \\\"hola\\\"\\u000a\"";

  Serial.printf("Autoprueba: lector de JSON -> %s\n", bien ? "bien" : "FALLA");
  return bien;
}
