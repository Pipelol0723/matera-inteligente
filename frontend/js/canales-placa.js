// El punto de composición de los canales con la placa, como main.py en el backend: qué adaptadores del
// puerto CanalPlaca ofrece el asistente y en qué orden (el primero disponible es el recomendado). El
// asistente solo pide esta lista: no importa ningún adaptador.
// En la app Android va primero BluetoothNativo: su WebView no tiene navigator.bluetooth, así que BluetoothWeb
// no se ofrece allí. En el navegador es al revés: BluetoothWeb, y nunca BluetoothNativo.
import { BluetoothNativo } from "./canal-bluetooth-nativo.js";
import { BluetoothWeb } from "./canal-bluetooth-web.js";
import { RedDeLaPlaca } from "./canal-red-placa.js";
import { EN_APP } from "./plataforma.js";

export function crearCanales() {
  return EN_APP ? [new BluetoothNativo(), new RedDeLaPlaca()] : [new BluetoothWeb(), new RedDeLaPlaca()];
}
