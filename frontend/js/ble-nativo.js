// El cliente BLE de la app Android: los métodos de BleClient (@capacitor-community/bluetooth-le) que usa
// BluetoothNativo, con las mismas firmas, sobre el plugin nativo «BluetoothLe».
// ¿Por qué no se importa BleClient del paquete npm? Porque importa @capacitor/core por su nombre y eso pide un
// empaquetador, y el front se sirve tal cual (sin compilar), igual en la web que en la app. Lo que hace
// BleClient y aquí se repite: una operación a la vez (su cola), un oyente por evento («disconnected|<id>» y
// «notification|<id>|<servicio>|<característica>»), y los bytes como texto hexadecimal hacia y desde el plugin
// nativo. Con un BleClient falso del mismo contrato se prueba BluetoothNativo sin celular.
import { pluginNativo } from "./plataforma.js";

// DataView o Uint8Array -> «0a1bff»
function aHexadecimal(valor) {
  const bytes = valor instanceof Uint8Array ? valor : new Uint8Array(valor.buffer, valor.byteOffset, valor.byteLength);
  return Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
}

// «0a 1b ff» -> DataView. Como BleClient, ignora lo que no sea un dígito hexadecimal (los espacios).
function deHexadecimal(texto) {
  const limpio = typeof texto === "string" ? texto.replace(/[^0-9a-f]/gi, "") : "";
  const bytes = new Uint8Array(limpio.length >> 1);
  for (let i = 0; i < bytes.length; i += 1) bytes[i] = Number.parseInt(limpio.slice(i * 2, i * 2 + 2), 16);
  return new DataView(bytes.buffer);
}

export function crearClienteBle(plugin = pluginNativo("BluetoothLe")) {
  let cola = Promise.resolve();
  const enCola = (tarea) => {
    const turno = cola.then(tarea);
    cola = turno.catch(() => {});
    return turno;
  };
  const oyentes = new Map();
  async function escuchar(evento, alLlegar) {
    await oyentes.get(evento)?.remove();
    oyentes.set(evento, await plugin.addListener(evento, alLlegar));
  }

  return {
    disponible: Boolean(plugin),
    initialize: (opciones) => enCola(() => plugin.initialize(opciones)),
    isEnabled: () => enCola(async () => (await plugin.isEnabled()).value === true),
    requestEnable: () => enCola(() => plugin.requestEnable()),
    setDisplayStrings: (textos) => enCola(() => plugin.setDisplayStrings(textos)),
    requestDevice: (opciones) => enCola(() => plugin.requestDevice(opciones)),
    connect: (deviceId, alDesconectarse, opciones = {}) => enCola(async () => {
      if (alDesconectarse) await escuchar(`disconnected|${deviceId}`, () => alDesconectarse(deviceId));
      await plugin.connect({ deviceId, ...opciones });
    }),
    disconnect: (deviceId) => enCola(() => plugin.disconnect({ deviceId })),
    startNotifications: (deviceId, service, characteristic, alLlegar) => enCola(async () => {
      await escuchar(`notification|${deviceId}|${service}|${characteristic}`, (evento) => alLlegar(deHexadecimal(evento?.value)));
      await plugin.startNotifications({ deviceId, service, characteristic });
    }),
    // Escritura con respuesta (write request), como BleClient.write.
    write: (deviceId, service, characteristic, valor) =>
      enCola(() => plugin.write({ deviceId, service, characteristic, value: aHexadecimal(valor) })),
  };
}
