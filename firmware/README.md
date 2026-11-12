# Firmware de la placa (ESP32)

`matera-sensor/` es el programa de la placa. Lee la temperatura y la humedad del aire (DHT11) y si hay luz (módulo LDR), se las manda a la API y muestra en su pantalla OLED lo que la API responde: una carita, el estado y lo que necesita la planta.

Desde el corte 3 la placa **se conecta sola**: no hay que tocar `config.h` ni volver a subir el programa. En su **modo de conexión** la placa abre su propia red WiFi, muestra un QR y se anuncia por Bluetooth LE. La app le entrega el WiFi y la dirección del servidor por cualquiera de los dos caminos (uniéndose a su red, o por Bluetooth sin dejar la suya), y después crea la matera con el código y la huella de la placa.

## Identidad de la placa

| Dato | De dónde sale |
|---|---|
| **Código** `MT-0000-XX` | De la MAC: FNV-1a de 32 bits sobre sus 6 bytes, en el orden en que se imprimen. Los 4 dígitos son `n % 10000`; con `i = (n / 10000) % 676`, las letras son `'A' + i / 26` y `'A' + i % 26`. El backend no sabe nada de MAC: recibe el código de siempre. |
| **Clave del sensor** | La crea la placa la primera vez: 32 bytes de `esp_random` en base64url sin relleno (43 caracteres, como `secrets.token_urlsafe(32)` del backend), con la radio encendida para que sean aleatorios de verdad. Queda en su memoria (NVS) y solo sale de la placa en el canje, hacia una dirección que ya respondió como la API. |
| **Huella** | El SHA-256 del texto de la clave, en hexadecimal minúscula. Es lo único que conoce la app: la manda al crear la matera, y la API ya guarda las claves así. Después la placa canjea su clave y la API la reconoce (es el esquema de PKCE). |

Al arrancar, la placa imprime su código, su MAC y su huella, y revisa estos vectores (en el monitor serie sale `Autoprueba: ... -> bien`):

| Entrada | Resultado |
|---|---|
| MAC `30:76:f5:91:d9:9c` (la placa de COM4) | `MT-5500-BA` |
| MAC `70:4b:ca:30:e4:dc` | `MT-7518-JP` |
| MAC `00:00:00:00:00:00` | `MT-9933-JD` |
| SHA-256 de `abc` | `ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad` |
| base64url de los bytes 0 a 31 | `AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8` |

También revisa el lector de JSON con una respuesta 201 de ejemplo.

## Etapas y pantallas

| Etapa (`GET /estado`) | Pantalla | Qué hace |
|---|---|---|
| `sin-red` | El QR de su red, y a la derecha la red y la clave en texto. | Espera que la app le entregue el WiFi, por su red o por Bluetooth. Si tiene una red guardada, cada minuto la vuelve a intentar mientras nadie esté unido a su red ni conectado por Bluetooth. |
| `conectando` | «Conectando a «red»...» y el motivo, si la red lo rechaza. | Se une al WiFi. Si no entra en 60 s, o la red rechaza la clave dos veces, abre su red otra vez. |
| `buscando-servidor` | «Conectada a «red»», «buscando el servidor...» y la dirección que prueba. | Prueba cada dirección, empezando por la que respondió la última vez, primero **sin la clave**: el canje con el cuerpo `{}` tiene que dar el 400 en JSON de la API, con su campo `error`. Solo entonces canjea allí con la clave, y cualquier respuesta JSON de ese canje, incluido un 401, dice que ese es el servidor. Así la clave nunca va a una dirección equivocada (la lista de la app puede traer IPs de adaptadores virtuales). |
| `esperando-matera` | «Agrégame en la app» y el código grande. | Reintenta el canje cada 5 s mientras la API responda 401: la matera todavía no existe. Con 403 `CUENTA_DESACTIVADA` dice «cuenta en pausa». |
| `conectada` | La carita a la izquierda; a la derecha el apodo, el estado y la temperatura y la humedad, o el globo de lo que necesita. | Manda una lectura cada `INTERVALO_MS` (15 s). Si el token deja de servir, vuelve a canjear; si la clave ya no sirve (le cambiaron el sensor a la matera, o la borraron), vuelve a `esperando-matera`. |

En `conectada` todo sale de la respuesta 201 de la lectura: el apodo de `planta.apodo`, el estado de `diagnostico.estado` y el globo del campo `necesidad`. La placa no decide ninguna regla.

| `diagnostico.estado` | Carita | Texto |
|---|---|---|
| `SALUDABLE` | feliz | SALUDABLE |
| `EN_RIESGO` | preocupada | EN RIESGO |
| `CRITICO` | triste, y la pantalla parpadea (se invierte cada medio segundo) | CRÍTICO |

| `necesidad` | Globo |
|---|---|
| `SED` | ¡tengo sed! |
| `EXCESO_AGUA` | ¡me ahogo! |
| `FRIO` | ¡tengo frío! |
| `CALOR` | ¡tengo calor! |
| `POCA_LUZ` | ¡poca luz! |
| `MUCHA_LUZ` | ¡mucha luz! |
| `null`, o no viene | sin globo: la temperatura y la humedad, por ejemplo `24,5°C 53%` |

Si algo falla mientras está conectada (la API no responde, el DHT11 no contesta, falta la hora), esa línea lo dice. Después de 3 envíos seguidos sin respuesta, vuelve a buscar el servidor.

## La red propia

- **Nombre:** `Matera-` y los dígitos y las letras del código. `MT-7518-JP` abre `Matera-7518JP`.
- **Clave:** WPA2, 8 caracteres al azar de `abcdefghjkmnpqrstuvwxyz23456789` (unos 40 bits), nuevos cada vez que se abre. Solo aparecen en la pantalla.
- **Una persona a la vez:** acepta un solo celular o PC unido. Así nadie más en el salón puede leer `/info` (el código y la huella) y registrar la placa primero en su cuenta.
- **QR:** `WIFI:T:WPA;S:<nombre>;P:<clave>;;`, versión 3 (29 × 29 módulos) a escala 2: 58 puntos, con 3 de borde claro dentro de un cuadro blanco de 64 × 64. La cámara de Android y la de iPhone lo leen y ofrecen unirse a la red.
- **Cuándo se abre:**
  - sin red guardada;
  - al mantener BOOT 5 s (o 15 s);
  - si no entra a su WiFi en 60 s;
  - si el servidor no responde en 2 minutos. En este caso se queda en el WiFi y abre su red a la vez (AP_STA), para recibir otra dirección. Los 2 minutos se cuentan con la red propia cerrada: mientras está abierta, un PC unido a ella no alcanza el servidor, así que la placa sigue buscándolo sin rendirse ni volver a mostrar el QR.
- **Cuándo se cierra:** con `POST /cerrar` (o `cerrar` por Bluetooth); sola, al llegar a `conectada` si se había abierto por una falla y nadie la estaba usando (la placa se recuperó sin la app); o cuando la placa ya está en su WiFi y nadie se une a la red propia ni se conecta por Bluetooth en 10 minutos. El Bluetooth se apaga con ella.

### API local, en `http://192.168.4.1`

Es un contrato con dos adaptadores: este, por HTTP en la red propia, y el de Bluetooth (sección siguiente). Las reglas (qué entrega `info`, cómo se valida `configurar`, qué dice `estado` y cuándo se puede cerrar) están una sola vez, en `api_local.cpp`; `red_propia.cpp` y `bluetooth.cpp` solo traducen.

Solo responde a quien está unido a la red propia (lo que llega por el WiFi de la casa recibe 403). Responde JSON con CORS abierto (`Access-Control-Allow-Origin: *`, métodos `GET, POST, OPTIONS`, cabecera `Content-Type`), y `OPTIONS` responde 204. Los errores son `{"error": "CODIGO", "mensaje": "texto para la persona"}`; en un 400 también va `"detalle": {"campo": "red"}`.

| Ruta | Respuesta |
|---|---|
| `GET /info` | `{"codigo": "MT-7518-JP", "huella": "<64 hex>", "redes": [{"nombre": "honor de pipe", "senal": -52, "segura": true}]}`. Las redes que ve la placa, de la mejor señal a la peor, sin repetir ni las ocultas: las 15 de mejor señal. Es la lista de la última búsqueda: la placa busca al abrir su red, cada 30 s mientras nadie está unido a ella (estar conectado por Bluetooth no cuenta) y después de cada `info` si la lista tiene más de 30 s. |
| `POST /configurar` | Con `{"red": "honor de pipe", "claveRed": "...", "servidores": ["http://10.34.101.124:5000/api/v1"]}` responde 202 `{"etapa": "conectando", "detalle": "..."}`, guarda en la memoria y se une al WiFi sin cerrar su red. El cuerpo se lee como JSON con cualquier `Content-Type`: la app lo manda como `text/plain` para evitar la consulta previa de CORS. `red` tiene de 1 a 32 bytes; `claveRed` de 8 a 63 caracteres, o va vacía si la red es abierta; `servidores` es una lista de 1 a 4 direcciones `http://`. Un cuerpo que no es JSON da 400 `SOLICITUD_INVALIDA`; si falta algo, 400 `PARAMETRO_INVALIDO` con el `campo`. |
| `GET /estado` | `{"etapa": "conectando", "detalle": "..."}`, con las etapas de la tabla de arriba. Si la clave del WiFi está mal, `sin-red` con el motivo («la clave del WiFi no es correcta»). |
| `POST /cerrar` | Sin cuerpo. 204, y apaga su red medio segundo después; la placa sigue buscando el servidor. Si la placa todavía no tiene red, 409 `SIN_RED`. |
| `GET /` | Una página mínima que pide volver a la app. |
| Otra ruta | 404 `RUTA_NO_ENCONTRADA`; un método que la ruta no acepta, 405 `METODO_NO_PERMITIDO`. |

Además, un DNS responde todos los nombres con 192.168.4.1, y la placa contesta las pruebas de conexión de los sistemas para que el celular no abandone la red por «no tener internet»: `/generate_204` y `/gen_204` (Android) responden 204; `/hotspot-detect.html` (iPhone y Mac), la página «Success»; `/connecttest.txt`, «Microsoft Connect Test», y `/ncsi.txt`, «Microsoft NCSI» (Windows).

Al unirse al WiFi, la placa pasa su red al canal de ese WiFi y el celular se desconecta un momento: la app reintenta `/estado`.

Para probarla desde el PC, se une el PC a la red `Matera-...` con la clave de la pantalla:

```powershell
Invoke-RestMethod http://192.168.4.1/info
```

### Si una red no aparece en la lista

- **La placa solo ve redes de 2,4 GHz.** Un celular que comparte internet mientras él mismo está en un WiFi de 5 GHz suele poner su hotspot en 5 GHz; en iPhone hay que encender «Maximizar compatibilidad».
- **La lista puede ser de antes de encender la red.** La placa abre su modo de conexión justamente cuando no encuentra su red guardada (por ejemplo, el hotspot apagado). Esa búsqueda no lo ve, y antes la lista solo se renovaba después de una `info`, con el resultado en la `info` siguiente: así le pasó a «honor de pipe» en la prueba del 12 de noviembre (la placa se conectó igual con «Otra red»). Ahora la lista se renueva sola cada 30 s mientras nadie está unido a la red propia, y si la app pide `info` otra vez a los pocos segundos, ya sale.
- **Con muchas redes alrededor entran las 15 de mejor señal.** En el edificio de la prueba la búsqueda encontró de 18 a 37 puntos de acceso, y la 15.ª red quedó en unos −80 dBm: una red más lejana queda fuera. Si hace falta, se escribe a mano («Otra red»).
- **El monitor serie dice qué ve la placa:** al abrir el modo de conexión imprime todas las redes que entrega `info`, con su señal y su canal, y cuántos puntos de acceso encontró; después, cada vez que una búsqueda de fondo cambia la lista. Con la red propia abierta, la búsqueda no se salta canales: en la prueba salieron redes en los canales 3, 5, 6, 7, 8 y 9, y una búsqueda de fondo (con la red propia ya abierta) encontró 27 puntos de acceso, tantos como la primera. El orden por señal también está bien.

## Bluetooth LE

Sirve para que un celular le entregue el WiFi y el servidor **sin dejar su red**: funciona aunque el celular sea el hotspot, y la app sigue con internet. Es el mismo contrato de la API local (`info`, `configurar`, `estado` y `cerrar`), con las mismas respuestas y los mismos errores, más la clave de la pantalla en cada pedido.

- **Cuándo:** solo en el modo de conexión. Se enciende al abrir la red propia, se anuncia con su mismo nombre (`Matera-7518JP`) y se apaga con ella (`cerrar`, al conectarse sola, los 10 minutos sin uso...). Fuera del modo de conexión la placa no se anuncia ni acepta conexiones. La pila NimBLE se inicia la primera vez que se abre el modo de conexión y después queda iniciada, pero callada: apagarla del todo (`NimBLEDevice::deinit`) y volver a iniciarla colgaba la placa (probado: *Guru Meditation* en el núcleo 0 al cerrar por segunda vez). Si la placa arranca con su red y nunca abre el modo de conexión, el Bluetooth ni se inicia.
- **Una conexión a la vez:** mientras alguien está conectado, la placa no se anuncia.
- **Librería:** NimBLE-Arduino 1.4.3.

| | UUID | Propiedades |
|---|---|---|
| Servicio «Matera» | `4d540001-d5b8-499f-bad6-c70b14aebec3` | Va en el anuncio; el nombre va en la respuesta al escaneo (los dos juntos no caben en 31 bytes). |
| `pedido` | `4d540002-d5b8-499f-bad6-c70b14aebec3` | Escritura con respuesta (*write request*). Cada escritura, de hasta 20 bytes (ver abajo). |
| `respuesta` | `4d540003-d5b8-499f-bad6-c70b14aebec3` | Notificaciones. Hay que activarlas **antes** de escribir el primer pedido: si no, la placa no tiene por dónde responder. |

Las dos tienen su descriptor 0x2901 («pedido» y «respuesta»), para que nRF Connect las muestre con nombre.

### Pedido

Un objeto JSON en UTF-8 con la operación (`op`), la clave de la pantalla (`clave`) y, si se quiere, un `id` (texto de hasta 32 caracteres) que vuelve en la respuesta:

```json
{"op":"info","clave":"bmc82gqg","id":"1"}
{"op":"estado","clave":"bmc82gqg"}
{"op":"configurar","clave":"bmc82gqg","red":"honor de pipe","claveRed":"...","servidores":["http://10.34.101.124:5000/api/v1"]}
{"op":"cerrar","clave":"bmc82gqg"}
```

`configurar` lleva los mismos campos que el cuerpo de `POST /configurar`, con las mismas reglas. Un pedido tiene 1024 bytes como máximo.

**El pedido se escribe en pedazos de hasta 20 bytes**, uno detrás de otro (esperando la respuesta de cada escritura): la placa junta los bytes hasta que se cierra la llave del objeto, y si el pedido queda a medias y pasan 3 s sin otro pedazo, lo descarta y responde `SOLICITUD_INVALIDA`. Se parte por bytes, sin cuidar los caracteres: la placa junta los bytes antes de leer el UTF-8. Si el cliente sabe su MTU (Capacitor en Android), puede escribir pedazos de hasta MTU − 3 bytes. Lo que no se debe usar son las **escrituras largas** (más de MTU − 3 bytes de una vez, que el sistema hace con *prepare write* y *execute write*): probado desde Windows con NimBLE 1.4.3, la primera funciona, pero la segunda en la misma conexión la corta. Con 20 bytes nunca hay escritura larga, con cualquier MTU. Medido desde el PC: `info` (50 bytes, 3 escrituras) tarda unos 0,2 s y un `configurar` de 221 bytes (12 escrituras), entre 0,4 y 0,9 s. Se pueden mandar varios pedidos seguidos: se responden en orden.

```js
async function escribirPedido(escribir, pedido) { // escribir(bytes): una escritura con respuesta
  const bytes = new TextEncoder().encode(JSON.stringify(pedido));
  for (let i = 0; i < bytes.length; i += 20) await escribir(bytes.slice(i, i + 20));
}
```

### Respuesta

Siempre un objeto JSON:

```json
{"op":"info","id":"1","http":200,"cuerpo":{"codigo":"MT-7518-JP","huella":"37ac...","redes":[...]}}
```

`http` y `cuerpo` son exactamente lo que respondería la ruta HTTP: su código y su JSON. En un 204 (`cerrar`), `cuerpo` es `null`. `op` e `id` repiten los del pedido.

Llega **en trozos**, uno por notificación, porque `info` (hasta 15 redes, unos 1,7 KB) no cabe en una. Cada notificación empieza con 3 bytes:

| Byte | Qué es |
|---|---|
| 0 | El número de la respuesta: sube de a uno con cada respuesta (de 255 vuelve a 0). |
| 1 | El índice del trozo, desde 0. |
| 2 | El total de trozos de esa respuesta. |

Después vienen hasta MTU − 6 bytes del JSON. La placa parte por bytes, no por caracteres: hay que juntar los bytes de todos los trozos y recién ahí decodificar el UTF-8 (las tildes y las comillas «» ocupan 2 bytes). Con el MTU mínimo de BLE (23) son 17 bytes por trozo; la placa ofrece 255 (249 por trozo) y Android y Chrome suelen aceptar eso. La placa no descarta trozos: si su cola de salida está llena, espera. Igual, el cliente debe revisar que lleguen todos los índices; si falta uno o pasan 15 s, vuelve a mandar el mismo pedido (todos se pueden repetir).

Para juntar la respuesta en JavaScript (sirve igual con Web Bluetooth y con `@capacitor-community/bluetooth-le`, que entregan un `DataView`):

```js
const enCamino = new Map(); // numero de respuesta -> { total, partes }
function alNotificar(vista) {
  const bytes = new Uint8Array(vista.buffer, vista.byteOffset, vista.byteLength);
  const [numero, indice, total] = bytes;
  const r = enCamino.get(numero) ?? { total, partes: [] };
  r.partes[indice] = bytes.slice(3); // copia: el buffer puede reutilizarse
  enCamino.set(numero, r);
  if (r.partes.filter(Boolean).length < total) return;
  enCamino.delete(numero);
  const todo = new Uint8Array(r.partes.reduce((n, p) => n + p.length, 0));
  let i = 0;
  for (const p of r.partes) { todo.set(p, i); i += p.length; }
  entregar(JSON.parse(new TextDecoder().decode(todo))); // {op, id, http, cuerpo}
}
```

- **Web Bluetooth (Chrome o Edge, con HTTPS o `localhost`):** `navigator.bluetooth.requestDevice({filters: [{namePrefix: "Matera-"}], optionalServices: ["4d540001-d5b8-499f-bad6-c70b14aebec3"]})`, o con `filters: [{services: [...]}]`. Después `startNotifications()` en `respuesta`, el evento `characteristicvaluechanged` con `event.target.value`, y `writeValueWithResponse()` en `pedido`, de a 20 bytes. Web Bluetooth no dice el MTU, y no hace falta: la placa parte las respuestas.
- **Capacitor (`@capacitor-community/bluetooth-le`):** `BleClient.requestDevice` con el mismo filtro (`namePrefix` y `optionalServices`), `BleClient.startNotifications(id, SERVICIO, RESPUESTA, alNotificar)` y `BleClient.write(id, SERVICIO, PEDIDO, pedazo)` por cada pedazo (un `DataView`).
- **Probado** desde el PC con `bleak` (Python, Windows 11, MTU 255): `info` con y sin clave, la clave en mayúsculas, `estado`, una operación inexistente, algo que no es JSON, `configurar` con datos inválidos, pedidos de hasta 1000 bytes en pedazos, el bloqueo con 5 claves equivocadas, el corte a los 2 minutos sin pedidos, y abrir y cerrar el modo de conexión 5 veces seguidas (con conexiones entre medio) sin perder RAM. Falta probarlo desde un celular (nRF Connect, Chrome y la app).

### Errores propios del Bluetooth

Además de los de la API local (`SOLICITUD_INVALIDA`, `PARAMETRO_INVALIDO`, `SIN_RED`), por Bluetooth están estos. Todos con la forma de siempre, `{"error","mensaje"}`, dentro de `cuerpo`:

| `http` | `error` | Cuándo |
|---|---|---|
| 401 | `CLAVE_INCORRECTA`, con `detalle.campo` = `clave` | Falta la clave o no es la de la pantalla. El mensaje dice cuántos intentos quedan. |
| 429 | `DEMASIADOS_INTENTOS` | Hubo 5 claves equivocadas seguidas: la placa corta la conexión y durante 60 s responde esto a todo, aunque la clave sea la correcta. El mensaje dice cuántos segundos faltan. |
| 400 | `PARAMETRO_INVALIDO`, con `detalle.campo` = `op` | Falta `op`, o no es `info`, `configurar`, `estado` ni `cerrar`. |
| 400 | `SOLICITUD_INVALIDA` | No es un objeto JSON, pasa de 1024 bytes o quedó a medias 3 s sin otro pedazo. Va sin `op` ni `id`. |

### Seguridad

- **La clave de la pantalla.** Cada pedido lleva los 8 caracteres de la red propia (sin importar mayúsculas). Sin ella la placa no entrega ni el código ni la huella, ni acepta una red: solo quien tiene la matera enfrente la configura. La clave cambia cada vez que se abre el modo de conexión, y se compara sin cortar en la primera letra distinta.
- **Intentos:** 5 claves equivocadas seguidas cortan la conexión y bloquean los pedidos 60 s, para cualquiera. Con unos 40 bits de clave y 5 intentos por minuto, adivinarla no es posible.
- **Una conexión a la vez**, y si en 2 minutos no llega un pedido con la clave, la placa corta la conexión: nadie puede quedarse conectado para no dejar entrar al dueño. Mientras espera, la app pide `estado` cada pocos segundos; si la conexión se corta, se vuelve a conectar.
- **El enlace no va cifrado.** La placa no pide emparejar (sería un diálogo más en el celular, y cada sistema lo maneja distinto con Web Bluetooth), así que lo que viaja por Bluetooth, incluidas la clave de la pantalla y la del WiFi, va en claro: alguien con un analizador de BLE a pocos metros podría leerlo. Es un nivel parecido al de la red propia, cuya clave WPA2 de 8 caracteres también se puede atacar si se captura el saludo. Si hiciera falta más, el paso siguiente es exigir LE Secure Connections (características con `WRITE_ENC`).

### Probar con nRF Connect (Android)

1. Abrir el modo de conexión de la placa (sin red guardada, BOOT 5 s, o la orden `conexion` por el monitor serie) y anotar la clave de la pantalla.
2. En nRF Connect, **Scanner**: aparece `Matera-7518JP`. **Connect**.
3. En el servicio `4d540001-...`, la característica `respuesta` (`4d540003-...`): tocar el ícono de las tres flechas para activar las notificaciones.
4. En `pedido` (`4d540002-...`): tocar la flecha hacia arriba, elegir **TEXT**, escribir `{"op":"info","clave":"<la de la pantalla>"}` y **Send** (como *request*). nRF Connect lo manda en una sola escritura: sirve mientras el pedido quepa en el MTU que negoció (nRF Connect suele pedir el máximo, y la placa acepta 255, o sea 252 bytes). Un `configurar` más largo se puede mandar en dos o tres escrituras seguidas, cada una con un pedazo del texto.
5. En `respuesta` aparece el valor: los 3 primeros bytes son el encabezado (por ejemplo `01-00-07`: respuesta 1, trozo 0 de 7) y después el texto del JSON. nRF Connect muestra el último trozo; el registro (**Log**, deslizando a la derecha) muestra todos.
6. Probar también sin clave (`{"op":"info"}` da 401), `estado`, y `configurar` con el WiFi real. En el monitor serie se ve cada pedido, por ejemplo `Bluetooth: «info» -> 200 (1234 bytes en 6 trozo(s), MTU 247).`

## El botón BOOT

| Cuánto se mantiene | Qué hace al soltarlo |
|---|---|
| Menos de 5 s | Nada. |
| 5 s | Olvida la red y los servidores, pero conserva su clave: sigue siendo la misma placa de su matera. Abre su red propia con una clave nueva. |
| 15 s | Además crea una clave nueva, y lo avisa en la pantalla. Sirve para dársela a otra persona: la matera anterior deja de recibir lecturas hasta que use «Cambiar sensor». |

Mientras se mantiene, la pantalla muestra los segundos y una barra con la marca de los 5 s. Con `config.h`, al reiniciar vuelve a usar la red de `config.h` (ver abajo).

## Órdenes por el monitor serie

Para probar el modo de conexión sin apretar BOOT ni olvidar la red, se escribe en el monitor serie (115 200 baudios, con salto de línea al final):

| Orden | Qué hace |
|---|---|
| `conexion` | Abre el modo de conexión (red propia y Bluetooth) sin olvidar la red, como cuando el servidor no responde. Se cierra solo a los 10 minutos sin uso, como siempre. |
| `cerrar` | Lo cierra, si la placa tiene una red guardada. |
| `memoria` | Imprime el flash que usa el programa y la RAM libre. |

## Lo que manda a la API

Las mismas dos rutas del simulador (`simulador/simulador_esp32.py`):

1. **Canje.** Cambia la clave del sensor por un token de alcance «lecturas», que vence a las 24 horas:

   ```http
   POST /api/v1/dispositivos/MT-7518-JP/token
   Content-Type: application/json

   {"clave":"<la clave de la placa>"}
   ```

2. **Lecturas.** Cada 15 segundos, una lectura con ese token y la hora en que la tomó (por NTP):

   ```http
   POST /api/v1/dispositivos/MT-7518-JP/lecturas
   Content-Type: application/json
   Authorization: Bearer <el token del canje>

   {"dispositivo":"MT-7518-JP","momento":"2026-10-22T15:04:05Z","lecturas":{"humedad":53.0,"luz":1500,"temperatura":25.5}}
   ```

**Humedad:** el DHT11 mide la del aire, y para la demo se manda esa, y se avisa en la presentación. **Luz:** el módulo LDR solo dice si hay luz o no, así que se mandan 1500 lux con luz y 50 sin luz.

## Placa y conexiones

ESP32 clásica de doble núcleo (DevKit WROOM-32, ESP32-D0WD-V3, 4 MB, puente USB CH340). Todo va a 3,3 V.

| Pieza | Pin de la pieza | Pin de la ESP32 | Nota |
|---|---|---|---|
| DHT11 (temperatura y humedad del aire) | DATA · VCC · GND | GPIO26 · 3V3 · GND | La primera lectura después de encenderlo sale mal: el programa la descarta. No se lee más de una vez cada 2 segundos. |
| Módulo LDR con LM393 (luz) | DO · VCC · GND | GPIO18 · 3V3 · GND | Solo tiene salida digital. La perilla azul fija desde cuánta luz cuenta como «con luz». |
| Pantalla OLED de 0,96" (NFP1315-157B, SSD1315, I2C) | GND · VCC · SCL · SDA | GND · 3V3 · GPIO22 · GPIO21 | Dirección 0x3C. VCC va a 3V3, no a 5V. Si la pantalla no responde, la placa sigue sin ella y todo queda en el monitor serie. |
| Botón BOOT | — | GPIO0 | El de la placa. |
| LED de estado | — | GPIO2 | El LED azul de la placa. |

**Con la placa de expansión** (la base negra con filas de tres pines G · V · S por cada GPIO):
- Cada pieza va a su fila: `S` es la señal (el GPIO), `V` la alimentación y `G` la tierra. El orden de los pines del sensor (por ejemplo GND · DATA · VCC) no siempre coincide con G · V · S: se conecta cable por cable, mirando las letras.
- **Los pines `V` solo tienen corriente si el jumper «JUMP» une el pin del medio (V) con 3V.** Sin ese jumper, un sensor conectado a `V` queda apagado y el monitor serie dice «El DHT11 no respondió». Pasó en la prueba del 12 de noviembre: se resolvió llevando el VCC del DHT11 a un pin de 3V3. No usar la posición 5V: la ESP32 no aguanta 5 V en sus pines de datos.
- El conector de 4 pines (D22 · D21 · VCC · GND) de la pantalla tiene su propio VCC, por eso la pantalla funciona aunque falte el jumper.

## Compilar y subir

- **Placa:** el soporte de Espressif para ESP32, versión **2.0.14**, con *ESP32 Dev Module* (`esp32:esp32:esp32`) y el esquema de particiones **Huge APP** (ver abajo).
- **Librerías:** **U8g2** (la pantalla, con tildes; se probó con la 2.36.19), **DHT sensor library** de Adafruit (1.4.7, con Adafruit Unified Sensor) y **NimBLE-Arduino** de h2zero (**1.4.3**, el Bluetooth). Lo demás viene con la placa: `WiFi`, `HTTPClient`, `WebServer`, `DNSServer`, `Preferences` (NVS), mbedtls (SHA-256), `esp_random` y el generador de QR de ESP-IDF (`esp_qrcode_generate`). No se usa ArduinoJson: el JSON se lee con `lector_json.cpp`.
- **Por qué NimBLE 1.4.3 y no la 2.x:** NimBLE ocupa mucho menos flash y RAM que el Bluetooth que trae la placa (Bluedroid). La línea 1.4 es la que se hizo para el soporte 2.0.x de la placa; la 2.x apunta al soporte 3.x, y su registro de cambios arregla en la 2.3.2 errores de compilación con ESP-IDF 4.x (el de la 2.0.14). Con esta placa, la 1.4.3 es la apuesta segura. Se instala con `arduino-cli lib install "NimBLE-Arduino@1.4.3"`.
- El QR sale del generador que trae la placa y no de la librería QRCode de Richard Moore: las dos usan el archivo `qrcode.h`, y el de la placa tapa al de la librería, que entonces no compila.

Desde la raíz del repositorio, con el `arduino-cli` que trae el Arduino IDE 2:

```powershell
& "$env:LOCALAPPDATA\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn esp32:esp32:esp32 --board-options PartitionScheme=huge_app --build-path "$env:TEMP\matera-build" --config-file "$env:USERPROFILE\.arduinoIDE\arduino-cli.yaml" firmware/matera-sensor
```

```powershell
& "$env:LOCALAPPDATA\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" upload -p COM5 --fqbn esp32:esp32:esp32 --board-options PartitionScheme=huge_app --input-dir "$env:TEMP\matera-build" --config-file "$env:USERPROFILE\.arduinoIDE\arduino-cli.yaml" firmware/matera-sensor
```

En el Arduino IDE es *Herramientas → Partition Scheme → Huge APP (3MB No OTA/1MB SPIFFS)*. El puerto cambia (COM3, COM4, COM5...): se revisa antes de subir. Esta placa reinicia sola al modo de descarga, así que no hay que apretar BOOT. Subir el programa borra el que tenga la placa, pero no su memoria: la clave del sensor y la red quedan. La primera compilación con NimBLE tarda mucho (en este PC, más de una hora, porque las librerías están en OneDrive); las siguientes, con el mismo `--build-path`, solo recompilan lo que cambió.

### Particiones «Huge APP»

Con el Bluetooth, el programa necesita más espacio que el 1,25 MB del esquema de siempre, o queda muy justo. «Huge APP» le da 3 MB a cambio de la actualización por el aire (OTA), que la placa no usa. **La NVS queda en el mismo lugar**, así que al subir el programa nuevo la placa conserva su red, sus servidores y la clave del sensor:

| Partición | De siempre (`default`) | Huge APP (`huge_app`) |
|---|---|---|
| `nvs` (la memoria de la placa) | 0x9000, 20 KB | 0x9000, 20 KB |
| `otadata` | 0xE000, 8 KB | 0xE000, 8 KB |
| `app0` (el programa) | 0x10000, 1,25 MB | 0x10000, 3 MB |
| `app1` (la otra copia, para OTA) | 0x150000, 1,25 MB | — |
| `spiffs` | 0x290000, 1,375 MB | 0x310000, 896 KB |
| `coredump` | 0x3F0000, 64 KB | 0x3F0000, 64 KB |

Subir escribe el arranque (0x1000), la tabla de particiones (0x8000), `boot_app0` (0xE000) y el programa (0x10000): nunca toca de 0x9000 a 0xDFFF. Se comprobó con la placa de COM5 el 12 de noviembre: la tabla leída con `esptool read_flash 0x8000 0xC00` era la de siempre antes de subir y la de Huge APP después, con la NVS en 0x9000 las dos veces, y al arrancar la placa seguía con su red («honor de pipe», de la memoria) y la misma huella de su clave.

**Flash:** con el Bluetooth, el programa usa unos 1 278 000 bytes, el 40 % de los 3 MB, y las variables globales 64 080 bytes (19 %). Sin el Bluetooth eran 1 020 097 bytes (el 77 % de 1,25 MB) y 50 328 bytes.

**RAM libre (el montón), medida en la placa:**

| Momento | Libre | Bloque mayor |
|---|---|---|
| Al arrancar (WiFi, sin el modo de conexión) | 170 040 bytes | 110 580 |
| Modo de conexión abierto: WiFi en AP_STA, red propia, DNS, servidor web y Bluetooth anunciándose | 124 608 bytes | 110 580 |
| Lo mismo, con un celular conectado por Bluetooth y pidiendo `info` | 116 600 bytes como mínimo | 110 580 |
| Modo de conexión cerrado, con la pila del Bluetooth ya iniciada | 128 540 bytes | 110 580 |

Todo cabe a la vez con más de 100 KB de margen, así que el Bluetooth y la red propia funcionan juntos. La placa lo imprime al arrancar y al abrir y cerrar el modo de conexión, y la orden `memoria` lo imprime cuando se quiera.

Los archivos del programa:

| Archivo | Qué tiene |
|---|---|
| `matera-sensor.ino` | `setup()`, `loop()` y las etapas. |
| `identidad.*` | El código desde la MAC, la clave al azar, la huella y la autoprueba. |
| `memoria.*` | La red, los servidores y la clave en la NVS, y el respaldo de `config.h`. |
| `api_local.*` | El contrato de la API local: `info`, `configurar`, `estado` y `cerrar`, sus validaciones y las redes que ve la placa. Lo usan los dos adaptadores. |
| `red_propia.*` | El modo de conexión: la red propia, su DNS y el adaptador HTTP de la API local. Enciende y apaga el Bluetooth. |
| `bluetooth.*` | El adaptador Bluetooth LE de la API local (NimBLE): la clave, los intentos, los pedidos y las respuestas en trozos. |
| `api_matera.*` | El canje y las lecturas. |
| `sensores.*` | El DHT11 y el LDR. |
| `pantalla.*` | Las pantallas, la carita, el globo, el QR y el parpadeo. |
| `lector_json.*` | El lector de JSON mínimo. |
| `ajustes.h` | Los pines y los valores del LDR, que `config.h` puede cambiar. |

## `config.h`, opcional

Se copia `matera-sensor/config.example.h` como `matera-sensor/config.h` solo para cambiar algo. Git lo ignora, porque puede llevar la clave del WiFi.

| Dato | Qué hace |
|---|---|
| `WIFI_SSID`, `WIFI_CLAVE`, `API_BASE` | Respaldo de desarrollo: si la memoria no tiene red, la placa usa esta red y esta dirección (`http://<IP del PC>:5000/api/v1`) sin pasar por la app. No se guardan en la memoria. Los tres tienen que estar. |
| `INTERVALO_MS` | Cada cuánto se envía una lectura: 15 000, es decir, 15 segundos. |
| `LDR_CON_LUZ` | `LOW` o `HIGH`: lo que da el módulo LDR cuando hay luz. En este módulo es `LOW` (comprobado tapándolo). |
| `LUX_CON_LUZ`, `LUX_SIN_LUZ` | Los lux que se mandan con luz y sin luz: 1500 y 50. |
| `PIN_DHT`, `PIN_LUZ`, `PIN_SDA`, `PIN_SCL`, `PIN_LED`, `PIN_BOOT` | Los pines, si se cablea distinto. |

`CODIGO_SENSOR` y `CLAVE_SENSOR`, del firmware anterior, ya no se usan: si están, el monitor serie avisa que se ignoran. La placa usa siempre el código de su MAC y su propia clave.

## El backend para la demo

El backend tiene que escuchar en la red, no solo en el PC: se arranca con `MATERA_HOST=0.0.0.0` y se permite el puerto en el firewall (sección «Mediciones de un ESP32 en la red» del README principal). Windows suele marcar el hotspot del celular como red **pública**: o la regla del firewall permite redes públicas, o se marca la red como privada como administrador (`Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private`). La ESP32 no ve las redes de 5 GHz; en iPhone hay que encender «Maximizar compatibilidad». La red tiene que dar salida a internet, porque la hora sale de NTP.

## Qué dice la placa

El monitor serie va a **115 200 baudios**: el código, la MAC y la huella al arrancar, la autoprueba, cada cambio de etapa (`[conectando] ...`), cada lectura con la respuesta de la API (`201: «sala» está SALUDABLE`) y los errores con su código. Al arrancar y al abrir y cerrar el modo de conexión imprime la memoria (`Memoria, modo de conexión abierto (...): programa ... de 3145728 bytes (40 %); RAM libre ... bytes (mínima ..., bloque mayor ...)`). Con el Bluetooth encendido imprime cada conexión, cada pedido con su código (`Bluetooth: «info» -> 200 ...`) y cada clave equivocada (nunca la clave).

| LED | Significa |
|---|---|
| Parpadeo rápido | La red propia está abierta y espera a la app. |
| Parpadeo lento | Conectándose al WiFi. |
| Fijo | Conectada al WiFi. |
| Apagado | Sin WiFi. |

Si algo traba el programa más de un minuto, la placa se reinicia sola y vuelve a empezar.

## Para probar sin la placa

`simulador/simulador_esp32.py` hace lo mismo que la placa, desde el PC: el canje, las lecturas con su hora y, además, los casos fuera de rango y los datos inválidos. El README principal explica cómo usarlo. Conviene darle su propia matera: cada canje deja sin efecto el token anterior del mismo sensor.
