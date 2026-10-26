# Firmware del sensor (ESP32)

`matera-sensor/` es el programa de la placa. Lee la temperatura y la humedad del aire (DHT11) y si hay luz (módulo LDR), y le habla a la API igual que el simulador (`simulador/simulador_esp32.py`), en dos pasos:

1. **Canje.** Al arrancar, cambia la clave del sensor por un token de alcance «lecturas», que vence a las 24 horas:

   ```http
   POST /api/v1/dispositivos/MT-0001-AA/token
   Content-Type: application/json

   {"clave":"<la clave que dio la API al crear la matera>"}
   ```

2. **Lecturas.** Cada 15 segundos manda una lectura con ese token y la hora en que la tomó:

   ```http
   POST /api/v1/dispositivos/MT-0001-AA/lecturas
   Content-Type: application/json
   Authorization: Bearer <el token del canje>

   {"dispositivo":"MT-0001-AA","momento":"2026-10-22T15:04:05Z","lecturas":{"humedad":53.0,"luz":1500,"temperatura":25.5}}
   ```

Si la API responde que el token ya no sirve (venció, o lo reemplazó otro canje), la placa vuelve a canjear la clave sola. La placa no decide nada: el backend calcula el estado y las recomendaciones, guarda la lectura y la muestra en Mis materas.

## Placa y conexiones

ESP32 clásica de doble núcleo (DevKit, ESP32-D0WD-V3, con puente USB CH340). Todo va a 3,3 V.

| Sensor | Pin del sensor | Pin de la ESP32 | Nota |
|---|---|---|---|
| DHT11 (temperatura y humedad del aire) | DATA · VCC · GND | GPIO26 · 3V3 · GND | La primera lectura después de encenderlo sale mal: el programa la descarta. No se lee más de una vez cada 2 segundos. |
| Módulo LDR con LM393 (luz) | DO · VCC · GND | GPIO18 · 3V3 · GND | Solo tiene salida digital: dice si hay luz o no. La perilla azul fija desde cuánta luz cuenta como «con luz». |
| LED de estado | — | GPIO2 | El LED azul de la placa. |

**Lo que se manda a la API.** La API espera la humedad del sustrato, en %, y la luz, en lux.
- **Humedad:** el DHT11 mide la del aire, así que para la demo se manda la del aire, y se avisa en la presentación.
- **Luz:** se manda en lux con dos valores fijos, 1500 con luz y 50 sin luz.

Con el potos (humedad de 40 a 70 %, luz de 270 a 2150 lux y temperatura de 16 a 29 °C), un cuarto a 25 °C y 53 % de humedad da «saludable». Al tapar el sensor de luz llegan 50 lux, y el estado cambia en la pantalla.

## Instalación en el Arduino IDE 2

1. **Placa:** el soporte de Espressif para ESP32, versión 2.0.14. En *Herramientas → Placa* se elige **ESP32 Dev Module**, y el puerto que aparezca al conectar la placa (en este PC, COM4).
2. **Librerías**, desde el gestor de librerías: **DHT sensor library**, de Adafruit (se probó con la 1.4.7). El gestor ofrece instalar también Adafruit Unified Sensor: hay que aceptarlo. `WiFi.h`, `HTTPClient.h` y la hora por NTP (`time.h`) vienen con la placa. El JSON se arma a mano, sin ArduinoJson.
3. **Configuración:** se copia `matera-sensor/config.example.h` como `matera-sensor/config.h` y se completa. Git ignora `config.h`, porque lleva la clave del WiFi y la del sensor.

| Dato | Qué va |
|---|---|
| `WIFI_SSID`, `WIFI_CLAVE` | La red de 2,4 GHz. Para la demo, el hotspot del celular. La ESP32 no ve las redes de 5 GHz; en iPhone hay que encender «Maximizar compatibilidad». La red tiene que dar salida a internet, porque la hora sale de NTP. |
| `API_BASE` | `http://<IP del PC>:5000/api/v1`. La IP sale de `ipconfig` («Dirección IPv4» del adaptador WiFi). |
| `CODIGO_SENSOR` | El código con el que se creó la matera en Mis materas, por ejemplo `MT-0001-AA`. |
| `CLAVE_SENSOR` | La clave que la API mostró una sola vez al crear la matera. Si se perdió, «Cambiar sensor» con el mismo código da otra, y la anterior deja de servir con su token. |
| `INTERVALO_MS` | Cada cuánto se envía una lectura: 15 000, es decir, 15 segundos. |
| `LDR_CON_LUZ` | `LOW` o `HIGH`: lo que da la salida del módulo cuando hay luz. En la mayoría es `LOW`. Para saberlo, se tapa el sensor y se mira el monitor serie. |
| `LUX_CON_LUZ`, `LUX_SIN_LUZ` | Los lux que se mandan con luz y sin luz: 1500 y 50. |

4. **Subir el programa:** *Subir* en el IDE. Esta placa reinicia sola al modo de descarga, así que no hay que apretar BOOT. Subir el programa borra el que tenga la placa.

## El backend para la demo

El backend tiene que escuchar en la red, no solo en el PC. Los comandos están en la sección «Mediciones de un ESP32 en la red» del README principal: arrancar con `MATERA_HOST=0.0.0.0` y permitir el puerto en el firewall.

- Windows suele marcar el hotspot del celular como red **pública**, y la regla del firewall del README es para redes **privadas**. Una vez conectado el PC al hotspot, se marca la red como privada como administrador: `Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private`.
- El hotspot puede darle otra IP al PC cada vez que se conecta. Antes de cada demo se revisa con `ipconfig`; si cambió, se corrige `API_BASE` y se vuelve a subir el programa.

## Qué dice la placa

El monitor serie va a **115 200 baudios**.

| LED | Significa |
|---|---|
| Parpadeo lento | Conectándose al WiFi. |
| Fijo | Conectada al WiFi. |
| Apagado | Sin WiFi: espera 30 segundos y vuelve a intentar. |
| Cinco parpadeos rápidos | Algo falló, por ejemplo: sin WiFi, sin hora, la API no responde, la clave fue rechazada o el DHT11 no respondió. El monitor serie dice qué. |

Si algo traba el programa más de un minuto, la placa se reinicia sola y vuelve a empezar.

Al arrancar, la placa:
1. Muestra su código y la dirección de la API.
2. Se conecta al WiFi y pide `GET /parametros`, para comprobar que llega al backend.
3. Toma la hora por NTP y canjea la clave.

Después, en cada vuelta, muestra lo que envió y lo que respondió la API: `201, la planta está SALUDABLE`, o el error con su código (por ejemplo, `400 MOMENTO_INVALIDO` si la hora de la placa está mal).

Si no se conecta al WiFi, el monitor serie dice el motivo y lista las redes que ve la placa, con el nombre entre «». El nombre de `WIFI_SSID` tiene que ser exacto, con sus espacios: Windows puede mostrar el del hotspot sin un espacio del final.

## Para probar sin la placa

`simulador/simulador_esp32.py` hace lo mismo que la placa, desde el PC: el canje, las lecturas con su hora y, además, los casos fuera de rango y los datos inválidos. El README principal explica cómo usarlo. Conviene darle su propia matera: cada canje deja sin efecto el token anterior del mismo sensor.
