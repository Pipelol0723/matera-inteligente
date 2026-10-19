# Firmware del sensor (ESP32)

`matera-sensor/` es el programa de la placa. Lee la humedad del sustrato, la temperatura y la luz, y cada minuto manda una medición a la API, igual que cualquier otro cliente HTTP:

```http
POST /api/v1/sensores/MT-0001-AA/mediciones
Content-Type: application/json
X-Clave-Sensor: <la clave que dio la API>

{"humedad":41.5,"luz":820.0,"temperatura":22.3}
```

La placa no decide nada. El backend calcula el estado y las recomendaciones, guarda la medición y la muestra en vivo en Mis materas. Si falta uno de los tres sensores, la placa no envía nada, porque la API exige los tres valores. Lo dice por el monitor serie y vuelve a intentarlo cada 30 segundos.

## Placa y conexiones

ESP32 clásica de doble núcleo (DevKit WROOM-32, con puente USB CP2102). Todo va a 3,3 V.

| Sensor | Pin del sensor | Pin de la ESP32 | Nota |
|---|---|---|---|
| Humedad capacitivo v1.2 | AOUT · VCC · GND | GPIO34 · 3V3 · GND | GPIO34 es del ADC1, que sigue funcionando con el WiFi encendido. Conviene una resistencia de 1 MΩ entre GPIO34 y GND (ver abajo). |
| AHT20 (temperatura) | SDA · SCL · VCC · GND | GPIO21 · GPIO22 · 3V3 · GND | Bus I2C, dirección 0x38. |
| BH1750 (luz) | SDA · SCL · VCC · GND · ADDR | GPIO21 · GPIO22 · 3V3 · GND · GND | El mismo bus I2C, dirección 0x23. En el modo que usa el programa mide hasta unos 54 600 lux: a pleno sol se satura. |
| LED de estado | — | GPIO2 | El LED azul de la placa. |

## Instalación en el Arduino IDE 2

1. **Placa:** el soporte de Espressif para ESP32, versión 2.0.14. Con esa versión el programa compila para ESP32 Dev Module; falta probarlo en la placa con las librerías reales. En *Herramientas → Placa* se elige **ESP32 Dev Module**, y el puerto que aparezca al conectar la placa (en este PC, COM3).
2. **Librerías**, desde el gestor de librerías:
   - **Adafruit AHTX0**. El gestor ofrece instalar también Adafruit BusIO y Adafruit Unified Sensor: hay que aceptarlo.
   - **BH1750**, de Christopher Laws.

   `WiFi.h` y `HTTPClient.h` vienen con la placa. El JSON se arma a mano, sin ArduinoJson.
3. **Configuración:** se copia `matera-sensor/config.example.h` como `matera-sensor/config.h` y se completa. Git ignora `config.h`, porque lleva la clave del WiFi y la del sensor.

| Dato | Qué va |
|---|---|
| `WIFI_SSID`, `WIFI_CLAVE` | La red de 2,4 GHz. Para la demo, el hotspot del celular. La ESP32 no ve las redes de 5 GHz; en iPhone hay que encender «Maximizar compatibilidad». |
| `API_BASE` | `http://<IP del PC>:5000/api/v1`. La IP sale de `ipconfig` («Dirección IPv4» del adaptador WiFi). |
| `CODIGO_SENSOR` | El código con el que se creó la matera en Mis materas, por ejemplo `MT-0001-AA`. |
| `CLAVE_SENSOR` | La clave que la API mostró una sola vez al crear la matera. Si se perdió, «Cambiar sensor» con el mismo código da otra. |
| `INTERVALO_MS` | Cada cuánto se envía: 60 000 (un minuto). Para la demo se puede bajar a 15 000. |
| `HUMEDAD_SECO`, `HUMEDAD_MOJADO` | La calibración del sensor de humedad (ver abajo). |

4. **Subir el programa:** *Subir* en el IDE. Si se queda en `Connecting...`, hay que mantener apretado el botón **BOOT** de la placa hasta que empiece a escribir. Con esta placa el reinicio automático al modo de descarga no siempre funciona. Subir el programa borra el que tenga la placa.

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
| Cinco parpadeos rápidos | Algo falló: sin WiFi, la API no responde, la clave fue rechazada o falta un sensor. El monitor serie dice qué. |

Si algo traba el programa más de un minuto (por ejemplo, un sensor que se suelta justo mientras mide), la placa se reinicia sola y vuelve a empezar.

Al arrancar, la placa muestra su código y la dirección de la API, revisa los sensores, se conecta al WiFi y pide `GET /parametros` para comprobar que llega al backend. **Sin los sensores ya se puede probar todo esto**: el hotspot, la IP del PC, el firewall y que la API responda. Después, en cada vuelta, muestra la lectura cruda de la humedad, lo que envió y lo que respondió la API (`201, la planta está SALUDABLE`, o el error).

## Calibración de la humedad

El sensor capacitivo entrega un número crudo, de 0 a 4095: más alto cuanto más seco. El monitor serie lo muestra en cada vuelta (`Humedad: lectura cruda 2795, salto 12 …`).

1. Con el sensor al aire, se anota la lectura: es `HUMEDAD_SECO`.
2. Con el sensor en un vaso de agua hasta la línea que marca la placa (sin mojar los componentes), se anota la lectura: es `HUMEDAD_MOJADO`.
3. Se ponen los dos números en `config.h` y se vuelve a subir el programa. La placa convierte a porcentaje entre esos dos puntos. Si `HUMEDAD_SECO` no es mayor que `HUMEDAD_MOJADO`, el programa no compila y lo dice.

**Sensor de humedad desconectado.** GPIO34 no tiene resistencia interna: con el cable suelto, el pin «flota» y lee cualquier cosa. La placa lo da por desconectado si la lectura cruda es menor que 200 o mayor que 3900, o si salta más de 300 entre la muestra mayor y la menor. Eso detecta casi siempre un pin flotante, pero no siempre. Para que se detecte siempre, se pone una resistencia de 1 MΩ entre GPIO34 y GND: con el cable suelto el pin lee casi 0, y con el sensor conectado la lectura no cambia. Después se vuelve a calibrar.

## Para probar sin la placa

`backend/herramientas/enviar_medicion.py` manda la misma petición que la placa, desde el PC. Es una herramienta de desarrollo, no parte de la app. El README principal explica cómo usarla.
