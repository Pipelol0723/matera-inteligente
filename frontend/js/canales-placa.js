// El punto de composición de los canales con la placa, como main.py en el backend: qué adaptadores del
// puerto CanalPlaca ofrece el asistente y en qué orden (el primero disponible es el recomendado). El
// asistente solo pide esta lista: no importa ningún adaptador.
// La app Android (fase 17) agrega aquí BluetoothNativo, al principio. En su WebView no existe
// navigator.bluetooth, así que BluetoothWeb no se ofrece allí, y en Chrome no se ofrece BluetoothNativo.
import { BluetoothWeb } from "./canal-bluetooth-web.js";
import { RedDeLaPlaca } from "./canal-red-placa.js";

export function crearCanales() {
  return [new BluetoothWeb(), new RedDeLaPlaca()];
}
