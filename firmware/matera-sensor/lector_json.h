// Un lector de JSON minimo, sin libreria: busca un campo por su ruta («planta.apodo») sin cargar el
// documento entero. Entiende los escapes de los textos (\" \\ \n á...) y salta los objetos y las
// listas que no le interesan. Solo lo usan las respuestas de la API y lo que manda la app.
#pragma once

#include <Arduino.h>

// true si el texto es un objeto JSON bien formado, como {"error": "..."}.
bool jsonEsObjeto(const String &json);

// El texto en `ruta` («diagnostico.estado»). false si no esta o si no es un texto (null, un numero...).
bool jsonTexto(const String &json, const char *ruta, String &valor);

// true si en `ruta` hay un objeto, como {"prueba": {...}}. false si es null, otro valor o no esta.
bool jsonHayObjeto(const String &json, const char *ruta);

// El true o false en `ruta`. false si no esta o si no es un booleano (null, "true", un numero...).
bool jsonBooleano(const String &json, const char *ruta, bool &valor);

// Los textos de la lista en `ruta`, hasta `maximo`. Devuelve cuantos tiene la lista, o -1 si no es una
// lista de textos.
int jsonTextos(const String &json, const char *ruta, String destino[], int maximo);

// El texto entre comillas, con sus escapes, listo para armar un JSON.
String jsonComillas(const String &texto);

// Revisa el lector con respuestas de ejemplo de la API y lo imprime.
bool autopruebaJson();
