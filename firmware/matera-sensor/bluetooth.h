// Bluetooth LE de la placa: el mismo contrato de la API local (api_local.h) por un servicio GATT, para que
// un celular le entregue el WiFi y el servidor sin dejar su red (funciona aunque el celular sea el hotspot).
// Solo funciona con el modo de conexion abierto: se enciende con la red propia, se anuncia con su mismo
// nombre (Matera-7518JP) y se apaga con ella. La pila NimBLE se inicia la primera vez que se abre el modo
// de conexion y queda iniciada, callada (apagarla del todo y volver a iniciarla colgaba la placa).
//
// Servicio «Matera»  4d540001-d5b8-499f-bad6-c70b14aebec3
//   pedido     4d540002-d5b8-499f-bad6-c70b14aebec3  escritura con respuesta. Un objeto JSON en UTF-8, como
//              {"op":"info","clave":"bmc82gqg","id":"1"}; configurar lleva ademas "red", "claveRed" y
//              "servidores". Se escribe en pedazos seguidos de hasta 20 bytes (o MTU - 3, si el cliente
//              sabe su MTU): la placa los junta hasta que se cierra la llave del objeto. Sin escrituras
//              largas (prepare/execute): probado desde Windows, la segunda en una misma conexion la corta.
//   respuesta  4d540003-d5b8-499f-bad6-c70b14aebec3  notificaciones. {"op","id","http","cuerpo"}, donde
//              "http" y "cuerpo" son lo mismo que responde la ruta por la red propia (cuerpo null en un 204),
//              en trozos de hasta MTU - 6 bytes, cada uno con un encabezado de 3 bytes: el numero de la
//              respuesta (0 a 255, da la vuelta), el indice del trozo (desde 0) y el total de trozos.
// Seguridad: cada pedido lleva la clave de 8 caracteres de la pantalla, la de la red propia. Sin ella no
// se entrega ni el codigo ni la huella. Con 5 claves equivocadas seguidas, la placa corta la conexion y no
// atiende pedidos durante 60 s. Una conexion a la vez; si en 2 minutos no llega un pedido con la clave, la
// placa corta la conexion.
#pragma once

#include <Arduino.h>

// En setup(): devuelve al monton la memoria del Bluetooth clasico, que la placa no usa.
void bluetoothPreparar();

// Empieza a anunciarse con `nombre` (la primera vez, inicia la pila). Los pedidos tienen que traer `clave`.
// Devuelve false si no hay memoria para iniciarla: la red propia sigue sola.
bool bluetoothEncender(const String &nombre, const String &clave);

// Corta la conexion y deja de anunciarse. Nadie puede conectarse hasta el proximo bluetoothEncender().
void bluetoothApagar();

bool bluetoothEncendido();

// Atiende los pedidos y vuelve a anunciarse cuando nadie esta conectado. Va en cada vuelta de loop().
void bluetoothAtender();

// 1 si hay un celular conectado por Bluetooth; 0 si no.
int bluetoothConectados();
