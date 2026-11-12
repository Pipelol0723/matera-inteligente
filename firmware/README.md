# Firmware de la placa (ESP32)

`matera-sensor/` es el programa de la placa. Lee la temperatura y la humedad del aire (DHT11) y si hay luz (módulo LDR), se las manda a la API y muestra en su pantalla OLED lo que la API responde: una carita, el estado y lo que necesita la planta.

Desde el corte 3 la placa **se conecta sola**: no hay que tocar `config.h` ni volver a subir el programa. La placa abre su propia red WiFi y muestra un QR; la app se une a esa red, le entrega el WiFi y la dirección del servidor, y después crea la matera con el código y la huella de la placa.

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
| `sin-red` | El QR de su red, y a la derecha la red y la clave en texto. | Espera que la app le entregue el WiFi. Si tiene una red guardada, cada minuto la vuelve a intentar mientras nadie esté unido a su red. |
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
- **Cuándo se cierra:** con `POST /cerrar`; sola, al llegar a `conectada` si se había abierto por una falla y nadie la estaba usando (la placa se recuperó sin la app); o cuando la placa ya está en su WiFi y nadie se une a la red propia en 10 minutos.

### API local, en `http://192.168.4.1`

Solo responde a quien está unido a la red propia (lo que llega por el WiFi de la casa recibe 403). Responde JSON con CORS abierto (`Access-Control-Allow-Origin: *`, métodos `GET, POST, OPTIONS`, cabecera `Content-Type`), y `OPTIONS` responde 204. Los errores son `{"error": "CODIGO", "mensaje": "texto para la persona"}`; en un 400 también va `"detalle": {"campo": "red"}`.

| Ruta | Respuesta |
|---|---|
| `GET /info` | `{"codigo": "MT-7518-JP", "huella": "<64 hex>", "redes": [{"nombre": "honor de pipe", "senal": -52, "segura": true}]}`. Las redes que ve la placa, de la mejor señal a la peor, sin repetir ni las ocultas. |
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

## El botón BOOT

| Cuánto se mantiene | Qué hace al soltarlo |
|---|---|
| Menos de 5 s | Nada. |
| 5 s | Olvida la red y los servidores, pero conserva su clave: sigue siendo la misma placa de su matera. Abre su red propia con una clave nueva. |
| 15 s | Además crea una clave nueva, y lo avisa en la pantalla. Sirve para dársela a otra persona: la matera anterior deja de recibir lecturas hasta que use «Cambiar sensor». |

Mientras se mantiene, la pantalla muestra los segundos y una barra con la marca de los 5 s. Con `config.h`, al reiniciar vuelve a usar la red de `config.h` (ver abajo).

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

- **Placa:** el soporte de Espressif para ESP32, versión **2.0.14**, con *ESP32 Dev Module* (`esp32:esp32:esp32`).
- **Librerías:** **U8g2** (la pantalla, con tildes; se probó con la 2.36.19) y **DHT sensor library** de Adafruit (1.4.7, con Adafruit Unified Sensor). Lo demás viene con la placa: `WiFi`, `HTTPClient`, `WebServer`, `DNSServer`, `Preferences` (NVS), mbedtls (SHA-256), `esp_random` y el generador de QR de ESP-IDF (`esp_qrcode_generate`). No se usa ArduinoJson: el JSON se lee con `lector_json.cpp`.
- El QR sale del generador que trae la placa y no de la librería QRCode de Richard Moore: las dos usan el archivo `qrcode.h`, y el de la placa tapa al de la librería, que entonces no compila.

Desde la raíz del repositorio, con el `arduino-cli` que trae el Arduino IDE 2:

```powershell
& "$env:LOCALAPPDATA\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" compile --fqbn esp32:esp32:esp32 --build-path "$env:TEMP\matera-build" --config-file "$env:USERPROFILE\.arduinoIDE\arduino-cli.yaml" firmware/matera-sensor
```

```powershell
& "$env:LOCALAPPDATA\Programs\Arduino IDE\resources\app\lib\backend\resources\arduino-cli.exe" upload -p COM4 --fqbn esp32:esp32:esp32 --input-dir "$env:TEMP\matera-build" --config-file "$env:USERPROFILE\.arduinoIDE\arduino-cli.yaml" firmware/matera-sensor
```

El puerto cambia (COM3, COM4, COM5...): se revisa antes de subir. Esta placa reinicia sola al modo de descarga, así que no hay que apretar BOOT. Subir el programa borra el que tenga la placa, pero no su memoria: la clave del sensor y la red quedan.

**Flash:** con el esquema de particiones de siempre (1,25 MB para el programa), usa 1 020 097 bytes, el 77 %, y 50 328 bytes de RAM (15 %). Hay margen, así que no hace falta «Huge APP». Si algún día pasa del 90 %, se compila y se sube con `--board-options PartitionScheme=huge_app` (3 MB para el programa, sin actualización por el aire).

Los archivos del programa:

| Archivo | Qué tiene |
|---|---|
| `matera-sensor.ino` | `setup()`, `loop()` y las etapas. |
| `identidad.*` | El código desde la MAC, la clave al azar, la huella y la autoprueba. |
| `memoria.*` | La red, los servidores y la clave en la NVS, y el respaldo de `config.h`. |
| `red_propia.*` | La red propia, su DNS y la API local. |
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

El monitor serie va a **115 200 baudios**: el código, la MAC y la huella al arrancar, la autoprueba, cada cambio de etapa (`[conectando] ...`), cada lectura con la respuesta de la API (`201: «sala» está SALUDABLE`) y los errores con su código.

| LED | Significa |
|---|---|
| Parpadeo rápido | La red propia está abierta y espera a la app. |
| Parpadeo lento | Conectándose al WiFi. |
| Fijo | Conectada al WiFi. |
| Apagado | Sin WiFi. |

Si algo traba el programa más de un minuto, la placa se reinicia sola y vuelve a empezar.

## Para probar sin la placa

`simulador/simulador_esp32.py` hace lo mismo que la placa, desde el PC: el canje, las lecturas con su hora y, además, los casos fuera de rango y los datos inválidos. El README principal explica cómo usarlo. Conviene darle su propia matera: cada canje deja sin efecto el token anterior del mismo sensor.
