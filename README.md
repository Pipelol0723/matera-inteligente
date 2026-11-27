# Matera inteligente

Matera inteligente es una API que diagnostica el estado de una planta a partir de su especie y de una medición de humedad del sustrato, luz y temperatura, con un front web estático que la consume.

- **Corte 2:** cada persona tiene su cuenta (con JWT) y sus materas, y un administrador gestiona las cuentas y agrega especies.
- **Sensor:** cada matera nace con su sensor, que puede ser un ESP32 o el simulador. El sensor canjea su clave por un token propio y reporta lecturas con la hora en que las tomó.
- **Historial:** solo el sensor escribe en él.
- **Pantalla del dueño:** se actualiza sola. Consulta la API cada 10 segundos y, además, recibe cada lectura al instante por WebSocket.
- **Corte 3, el juego:** cada matera es un Tamagotchi. Crece con el tiempo que pasa bien cuidada, se marchita si la descuidan, dice qué necesita y avisa cuando está mal. Cada lectura suma o resta puntos, y quien quiere compite en una tabla de posiciones con un apodo. Ver [La matera Tamagotchi](#la-matera-tamagotchi).
- **Corte 3, la conexión:** la placa se conecta sola. Muestra un QR con su propia red y se anuncia por Bluetooth; la app le entrega el WiFi y la dirección del servidor por cualquiera de los dos caminos, y crea la matera con el código y la huella de la clave que creó la placa. Nadie toca `config.h`. Ver [Conectar una matera](#conectar-una-matera).
- **Corte 3, la app Android:** el mismo front dentro de una app, con Capacitor, que usa el Bluetooth y las notificaciones del celular. Ver [La app móvil](#la-app-móvil).
- **Corte 3, el modo prueba:** un administrador le pone a una matera suya un estado de mentira para mostrar cada dibujo en la demo, en la app y en la pantalla de la placa. Ver [Modo prueba](#modo-prueba-solo-administradores).

Proyecto de Arquitectura de Software, semestre 2026-03. El corte 1, tal como se entregó, está en el tag `corte-1`. La fase 2 organiza el backend en puertos y adaptadores (arquitectura hexagonal): ver [Arquitectura](#arquitectura-puertos-y-adaptadores). El corte 3 agrega el juego sin modificar ningún archivo del núcleo: ver [La prueba de cambio del corte 3](#la-prueba-de-cambio-del-corte-3).

## Estructura

```
backend/
  main.py            raíz de composición: el único archivo que elige clases concretas
  crear_admin.py     da el rol de administrador a una cuenta, desde la consola
  exportar_especies_csv.py  escribe la copia en CSV de la tabla de especies, desde la base
  datos/             esquema.sql, carga.sql y ritmos.sql de la base SQLite, y especies.csv (la copia de solo lectura)
  dominio/           entidades, reglas de negocio y puertos; no importa flask, sqlite3, csv, jwt, json ni http
  aplicacion/        casos de uso: cada uno implementa su puerto de entrada
  presentacion/      adaptadores de entrada: rutas REST del front y de los dispositivos, el WebSocket,
                     los decoradores que verifican el JWT y la conversión entre JSON y objetos del dominio
  infraestructura/   adaptadores de salida: SQLite, la copia en CSV, JWT (PyJWT), contraseñas, reloj,
                     el aviso en vivo, configuración, Flask y CORS
  tests/
    dominio/         reglas de negocio con dobles de prueba, sin servidor ni base de datos
    aplicacion/      casos de uso con dobles de prueba
    integracion/     API, repositorios, JWT, migración, CSV, el servidor real, el WebSocket y el simulador
simulador/
  simulador_esp32.py manda lecturas a la API como el ESP32, sin hardware (ver «Simulador del ESP32»)
frontend/            HTML, CSS y JavaScript estáticos, servidos aparte
  index.html         la cabecera, las pantallas y los diálogos
  fuentes/           Bricolage Grotesque y DM Sans, locales y con su licencia OFL (sin CDN)
  css/fuentes.css    las dos fuentes
  css/variables.css  los dos estilos (Profesional y Juego) y los colores de cada tema, con contraste AA
  css/componentes.css  botones, campos, tarjetas, pastillas, cifras, errores, avisos y diálogos
  css/armazon.css    la cabecera, las pestañas (arriba en el PC y abajo en el celular), el puntaje y la cuenta
  css/estilos.css    Mis materas, la matera Tamagotchi y Juego
  css/diagnostico.css  Diagnóstico: el menú de materas, el Tamagotchi grande y la última lectura revisada por la API
  css/asistente.css  el asistente «Conectar sensor», con sus dos vías (Bluetooth y la red de la placa)
  css/modo-prueba.css  el panel del modo prueba (solo administradores) y su marca
  css/cuenta.css     Ingresar, Mi cuenta y el diálogo de participar en la tabla de posiciones
  css/especies.css   el catálogo de especies y el formulario para agregar una
  css/historial.css  el historial de una matera
  css/admin.css      la administración de cuentas
  css/app-movil.css  la tarjeta del QR para la app (web) y la del servidor (app), y la línea «Servidor» de Ingresar
  js/apariencia.js   el estilo y el tema elegidos, antes de pintar (se recuerdan en este equipo)
  js/config.js       dónde está la API (en la web, el mismo equipo que abrió el front; en la app, la guardada) y la placa
  js/plataforma.js   si el front corre en el navegador o dentro de la app Android, y sus plugins nativos
  js/api.js          peticiones a la API, con el token en las rutas privadas
  js/app.js          arranque, navegación y pantallas que exigen sesión
  js/sesion.js       token de la sesión, en sessionStorage
  js/consulta-periodica.js  vuelve a pedir los datos de la pantalla cada 10 s
  js/tiempo-real.js  el WebSocket que trae las mediciones en vivo, con su reconexión
  js/diagnostico.js  pantalla de diagnóstico
  js/especies.js     catálogo de especies y, para el admin, agregar una
  js/acceso.js       ingresar y crear cuenta
  js/cuenta.js       mi cuenta, cerrar sesión y participar en la tabla de posiciones
  js/materas.js      mis materas: crearlas con su sensor, cambiarles el sensor y su matera Tamagotchi
  js/juego.js        el juego: pantalla Juego, puntaje de la cabecera y consulta de GET /juego/...
  js/dibujo-planta.js  el dibujo SVG de la matera Tamagotchi (etapa, condición, cara y globo)
  js/participacion.js  la pregunta de participar en la tabla de posiciones
  js/avisos.js       los avisos del juego: notificación del navegador o aviso dentro de la página
  js/avisos-nativos.js  en la app Android, los mismos avisos como notificaciones del celular
  js/conectar-sensor.js  el asistente «Conectar sensor»: lleva una placa nueva a su WiFi y a su matera
  js/canal-placa.js  el puerto CanalPlaca: lo que el asistente le pide a la placa (info, configurar, estado, cerrar)
  js/canal-red-placa.js     su adaptador por la red propia de la placa (HTTP en 192.168.4.1)
  js/canal-bluetooth.js     el contrato Bluetooth LE: pedidos en pedazos de 20 bytes y respuestas en trozos
  js/canal-bluetooth-web.js su adaptador por Web Bluetooth (Chrome o Edge)
  js/canal-bluetooth-nativo.js  su adaptador por el Bluetooth de la app Android
  js/ble-nativo.js   los métodos de BleClient que usa ese adaptador, sobre el plugin nativo
  js/canales-placa.js       qué canales ofrece el asistente: el punto de composición del lado del cliente
  js/direccion-api.js  la dirección de la API en la app: guardarla, normalizarla y el enlace del QR
  js/servidor-app.js la app Android: pedir, probar y cambiar la dirección de la API, y recibir el enlace del QR
  js/qr.js           un generador mínimo de códigos QR, sin librerías de afuera
  js/qr-servidor.js  en la web, el QR de Mi cuenta para apuntar la app a este servidor
  js/historial.js    historial de una planta
  js/admin.js        administración de cuentas
  js/formularios.js  errores de la API en los formularios
  js/lecturas.js     texto de unas lecturas y de su origen
  js/escala.js       la escala de cada parámetro: dónde van la banda óptima y la marca del valor
  js/formato.js      textos, colores y ayudas para crear nodos
app/                 la app Android: el mismo front dentro de una WebView, con Capacitor (ver «La app móvil»)
  capacitor.config.json  webDir ../frontend, CapacitorHttp y la configuración de los plugins
  android/           el proyecto Android (Gradle), con su AndroidManifest.xml; lo que se compila no se sube
firmware/
  matera-sensor/     el programa de la ESP32: su código y su clave, la red propia con el QR, la pantalla
                     y las lecturas (ver firmware/README.md)
docs/
  diagramas/         la vista hexagonal, casos de uso, paquetes, clases, entidad-relación y secuencias
                     (fuente .mmd, SVG y PNG)
  entrega/           documentos de arquitectura, bitácoras de uso de IA y el guion de la sustentación, en PDF
                     (corte 3: bitacora-ia-corte3.pdf y guion-sustentacion-corte3.pdf, con lo que cambió
                     respecto al corte 2 y qué pasó con el núcleo; fase 2: documento-arquitectura-fase2.pdf
                     y bitacora-ia-fase2.pdf; documento-arquitectura.pdf es el anterior a la fase 2)
```

## Arquitectura: puertos y adaptadores

Las carpetas son las del corte 1, y cada una tiene su lugar en la vista hexagonal:

| Carpeta | En la vista hexagonal |
|---|---|
| `dominio/` y `aplicacion/` | El núcleo: reglas de negocio y casos de uso. No conocen Flask, SQLite, el CSV, JWT, JSON ni HTTP. |
| `dominio/puertos_entrada.py` | Los puertos de entrada: una clase abstracta por caso de uso, con el mismo nombre que el caso de uso de `aplicacion/` que la implementa. Lo que entra y sale de ellos está en `dominio/resultados.py`. |
| `dominio/puertos.py` y `dominio/puertos_usuarios.py` | Los puertos de salida: lo que el núcleo necesita de afuera, cada uno con pocos métodos. |
| `dominio/puertos_juego.py` | Los puertos del juego (corte 3), en un archivo nuevo: cinco de entrada (`ConsultarMascotas`, `ConsultarPuntaje`, `ConsultarParticipacion`, `ElegirParticipacion` y `ConsultarTablaPosiciones`) y tres de salida (`MovimientosPuntaje`, `RegistroJugadores` y `RitmosCrecimiento`). Lo que devuelven está en `dominio/resultados_juego.py`. |
| `presentacion/` | Los adaptadores de entrada: las rutas del front, las del juego, las de los dispositivos y el WebSocket. Dependen de los puertos de entrada, nunca de los casos de uso. |
| `infraestructura/` | Los adaptadores de salida: implementan los puertos de salida con SQLite, el CSV, PyJWT, PBKDF2, el reloj y el WebSocket. `red_local.py` busca las IPv4 del PC para `GET /red`. |
| `main.py` | El único punto de composición: elige qué adaptador se conecta a cada puerto. `crear_admin.py` y `exportar_especies_csv.py` le piden sus piezas (`construir_consola`). |

Las dependencias apuntan hacia el núcleo. `tests/dominio/test_arquitectura.py` lo comprueba en cada corrida:
- El dominio y la aplicación no importan ni el framework, ni la persistencia, ni la criptografía, ni las otras capas.
- `presentacion/` no importa `aplicacion/` ni `infraestructura/`.
- Solo `infraestructura/tokens_jwt.py` importa `jwt`, y solo `infraestructura/repositorio_especies_csv.py` importa `csv`.

El diagrama está en [docs/diagramas](docs/diagramas/README.md#vista-hexagonal) (`hexagonal.mmd`).

**La prueba de cambio de la fase 2.** El adaptador de dispositivos y el simulador entraron en el commit `d41ca34` sin tocar ningún archivo del núcleo. Lo muestra este comando, que no lista ningún archivo:

```bash
git show --stat d41ca34 -- backend/dominio backend/aplicacion
```

El núcleo ya tenía, desde el commit `13a3c1b`, los puertos de entrada `RegistrarLectura` y `CanjearClaveDispositivo`, probados con dobles. Lo mismo pasó con la tabla en CSV (commit `9c7ce5e`), que es otro adaptador de los puertos del corte 1.

### La prueba de cambio del corte 3

**El juego entró solo agregando archivos.** El commit `1dac8d8` trae el núcleo del juego: las reglas, los puertos y los casos de uso. En `dominio/` y `aplicacion/` solo agrega archivos (`A`), ninguno modificado (`M`):

```bash
git show --name-status 1dac8d8 -- backend/dominio backend/aplicacion
```

```
A	backend/aplicacion/avisos.py
A	backend/aplicacion/juego.py
A	backend/dominio/errores_juego.py
A	backend/dominio/juego.py
A	backend/dominio/mascota.py
A	backend/dominio/puertos_juego.py
A	backend/dominio/resultados_juego.py
```

Es el principio abierto/cerrado: el juego solo lee lo que ya existía (el `EstadoGlobal` de la regla híbrida, `Planta`, `RegistroMedicion` y los puertos de plantas, historial y cuentas). Se engancha así:
- `DiagnosticarPlantaDeUsuario` no cambió: después de guardar cada lectura avisa por un solo `NotificadorDiagnosticos`, como en la fase 2.
- `main.py` le entrega `AvisarATodos([PuntuarLectura, NotificadorWebSocket])` (`aplicacion/avisos.py`). Reparte el aviso en ese orden: primero se guardan los puntos y después sale el mensaje en vivo, así el front no pide `GET /juego/...` antes de tiempo. Si un suscriptor falla, el error va al log y el otro igual recibe el aviso; la lectura ya quedó guardada.
- Sumar otro suscriptor (por ejemplo, Web Push) es agregarlo a esa lista en `main.py`.

Los commits siguientes del juego (`1b43072` y las revisiones) solo cambian esos archivos nuevos.

**La conexión sí cambió las firmas de dos puertos de entrada** (commit `9167a8f`). En el corte 2 la clave del sensor la creaba la API y la mostraba una vez. Desde el corte 3 la crea la placa, y la app solo trae su huella SHA-256 (el esquema de PKCE: primero se registra la huella y después se presenta el secreto). El contrato de entrada de crear la matera cambia, porque ahora puede llegar la huella en vez de pedirle la clave a la API:
- `RegistrarPlanta.ejecutar(usuario, apodo, especie, codigo, huella=None)` y `ReemplazarSensor.ejecutar(usuario, planta_id, codigo, huella=None)`, en `dominio/puertos_entrada.py`.
- `SensorVinculado.clave` pasa a ser `str | None`, en `dominio/resultados.py`: con huella no hay clave que devolver.
- Los casos de uso de `aplicacion/plantas.py` y `aplicacion/sensores.py` guardan la huella tal cual. Sin huella, crean la clave como antes.

Ninguna regla cambia: especie, apodo, sensor libre, propiedad de la planta y revocación de la clave y del token. El parámetro es opcional, así que el simulador, «Conectar a mano» y las pruebas de antes siguen igual. El dominio trata la huella como texto: el formato (64 caracteres hexadecimales en minúscula) lo revisa `presentacion/esquemas_usuarios.py`, y SHA-256 solo existe en `infraestructura/seguridad.py` y en el firmware. Es el único commit del corte 3 que modifica archivos del núcleo que ya existían, y va aparte, con su motivo. Este comando lo comprueba para todo el corte (solo los cuatro archivos de `9167a8f` salen con `M`):

```bash
git diff --name-status b574752 HEAD -- backend/dominio backend/aplicacion
```

**`GET /red` no pasa por el núcleo.** No tiene ninguna regla de negocio: solo dice por qué direcciones alcanza una placa al servidor. `main.py` le pasa a `presentacion/rutas_red.py` las funciones de `RedLocal` (`infraestructura/red_local.py`), así presentación sigue sin importar infraestructura.

**El modo prueba también entró solo agregando archivos** (commit `8c44b1d`). `MascotasConPrueba` y `LecturaConPrueba` implementan los mismos puertos que envuelven (`ConsultarMascotas` y `RegistrarLectura`), y `main.py` los pone en lugar de los casos de uso de siempre, que no cambian:

```bash
git show --name-status 8c44b1d -- backend/dominio backend/aplicacion
```

```
A	backend/aplicacion/modo_prueba.py
A	backend/dominio/modo_prueba.py
A	backend/dominio/puertos_prueba.py
```

**El cliente también es puertos y adaptadores.** El asistente que conecta la placa solo conoce el puerto `CanalPlaca` (`frontend/js/canal-placa.js`), y `canales-placa.js` elige sus adaptadores: la red de la placa, Web Bluetooth y el Bluetooth de la app Android. La app entró como un adaptador más, sin cambiar el asistente (ver [Conectar una matera](#conectar-una-matera)).

Los diagramas del corte 3 están en [docs/diagramas](docs/diagramas/README.md): `hexagonal`, `clases-juego`, `clases-modo-prueba`, `secuencia-puntaje`, `secuencia-conexion-placa`, `secuencia-conexion-bluetooth` y `secuencia-modo-prueba`.

## Requisitos

- Python 3.11 o superior.
- Un navegador.

En Windows, si `python` no se reconoce, use `py` o la ruta completa del intérprete.

## Ejecutar el backend

Desde la carpeta `backend/`:

```bash
python -m pip install -r requirements.txt
python main.py
```

La API queda en `http://127.0.0.1:5000/api/v1`. Se puede configurar con variables de entorno:

| Variable | Por defecto |
|---|---|
| `MATERA_HOST` | `127.0.0.1`: solo este PC. Con `0.0.0.0` la API queda abierta a la red, ver [Mediciones de un ESP32](#mediciones-de-un-esp32-en-la-red) |
| `MATERA_PUERTO` | `5000` |
| `MATERA_PUERTO_FRONT` | `5500`: con `MATERA_HOST=0.0.0.0`, el front también se acepta desde `http://<ip del PC>:5500` (CORS y WebSocket), para abrirlo desde el celular en la misma red |
| `MATERA_RUTA_BD` | `backend/datos/matera.sqlite` |
| `MATERA_ORIGENES_CORS` | `http://localhost:5500,http://127.0.0.1:5500`. Para el WebSocket de la app Android se agrega `https://localhost` (ver [La app móvil](#la-app-móvil)) |
| `MATERA_DIAS_SESION` | `7`: cuánto dura el token de una sesión |
| `MATERA_HORAS_TOKEN_DISPOSITIVO` | `24`: cuánto dura el token de un sensor; después, el sensor vuelve a canjear su clave |
| `MATERA_JWT_SECRETO` | Sin valor: el secreto con que se firman los JWT se genera la primera vez y se guarda junto a la base (`matera.sqlite.secreto-jwt`, que Git ignora). Así un reinicio no cierra las sesiones. Si se pierde, todos vuelven a ingresar. |
| `MATERA_TABLA_REFERENCIA` | `bd`: la tabla de especies sale de la base. Con `csv`, sale de la copia en CSV (ver [Tabla de referencia](#tabla-de-referencia-csv-o-base-de-datos)) |
| `MATERA_RUTA_CSV` | `especies.csv`, en la carpeta de la base. Con la base por defecto es `backend/datos/especies.csv`; con una base fuera de Google Drive, la copia queda afuera con ella |
| `MATERA_MINUTOS_POR_DIA_JUEGO` | `1440`: cuántos minutos reales dura un día del juego (el tiempo real). Para la demo, `6`: una hora de juego dura 15 segundos, lo mismo que tarda la placa entre una lectura y otra, así que cada hora de juego tiene su lectura y la matera crece y se marchita en minutos (un potos bien cuidado llega a brote a los 6 minutos). Con menos de 6 quedan horas sin lectura y crece más lento. Debe ser un número mayor que 0. Cada lectura queda en su hora de juego al llegar: cambiar este valor no reagrupa las que ya llegaron |
| `MATERA_MINUTOS_SIN_LECTURAS` | `30`: minutos reales sin lecturas para que la matera se duerma. No cambian con el reloj del juego. Debe ser un número mayor que 0 |

Al arrancar, el backend escribe en la consola qué tabla de referencia usa, crea las tablas que falten y, si no hay ninguna especie, carga las de `datos/carga.sql` con su ritmo de crecimiento (`datos/ritmos.sql`). Si una variable tiene un valor que no sirve, no arranca y dice cuál es. Git ignora el archivo de la base.

Una base de antes de la fase 2 se migra sola la primera vez. Antes de migrarla, el backend saca una copia al lado (`matera.respaldo-v0.sqlite`). Usuarios, plantas, sensores, especies e historial no cambian, pero las sesiones abiertas se cierran, porque los tokens de antes no eran JWT: cada usuario vuelve a ingresar. La clave de cada sensor sigue sirviendo.

Una base de la fase 2 (versión 3) pasa sola a la versión 4, la del juego, y antes deja la copia `matera.respaldo-v3.sqlite`. Solo se agregan tablas: `movimiento_puntaje` (un movimiento por lectura), `jugador`, `ritmo_crecimiento` (con los ritmos de las especies que haya) y tres que suman al guardar cada movimiento, para que el juego no recorra todo el historial en cada consulta: `cuidado_por_hora` (lecturas y puntos de cada matera en cada hora de juego, con el reloj del juego que había cuando llegaron), `horas_por_tramo` (cuántas horas terminaron con cada cantidad de lecturas y suma) y `puntaje_total` (el total de cada usuario). Nada de lo que había cambia, las sesiones siguen abiertas y todos empiezan con 0 puntos.

Si el repositorio está en una carpeta sincronizada (Google Drive, OneDrive), ponga la base afuera: SQLite escribe a cada rato y la sincronización puede bloquear el archivo. En PowerShell:

```powershell
$env:MATERA_RUTA_BD = "$env:USERPROFILE\matera\matera.sqlite"
python main.py
```

### El primer administrador

El registro siempre crea usuarios comunes, y la API no tiene ninguna ruta que dé el rol de admin si no lo pide otro admin. El primero se crea por consola, desde `backend/`, con una cuenta ya registrada y la misma `MATERA_RUTA_BD` del servidor:

```bash
python crear_admin.py correo@ejemplo.com
```

### Tabla de referencia: CSV o base de datos

La tabla de especies sale de la base de datos (`MATERA_TABLA_REFERENCIA=bd`, por defecto) o de su copia en CSV (`csv`). Se cambia con la variable y reiniciando, sin tocar código. Desde `backend/`, en PowerShell:

```powershell
python exportar_especies_csv.py
```

```powershell
$env:MATERA_TABLA_REFERENCIA = "csv"
python main.py
```

El CSV es una copia de la base, de solo lectura:
- **Con `csv`:** el diagnóstico, el catálogo y las materas usan el archivo. Agregar una especie responde `409 TABLA_SOLO_LECTURA`.
- **Con `bd`:** cada especie que agrega el admin también se escribe en la copia, así el CSV queda al día.
- **`exportar_especies_csv.py`:** escribe la copia desde la base de `MATERA_RUTA_BD`.
- **Al arrancar con `csv`,** el backend compara la copia con la tabla de la base. Si no tienen las mismas especies y rangos, no arranca, dice cuáles faltan, sobran o cambiaron, y pide correr `exportar_especies_csv.py`. Así una planta nunca se queda sin su especie en la copia.

Para volver a la base, se borra la variable (`Remove-Item Env:MATERA_TABLA_REFERENCIA`) o se pone en `bd`, y se reinicia.

### Mediciones de un ESP32 en la red

Por defecto la API solo responde en el mismo PC (`127.0.0.1`), así que un ESP32 conectado al WiFi no la alcanza. Para la demo con la placa, el PC y el ESP32 tienen que estar en la misma red, y se arranca así, desde `backend/`:

```powershell
$env:MATERA_HOST = "0.0.0.0"
python main.py
```

Al arrancar, Flask muestra una línea `Running on http://192.168.x.x:5000` con la dirección del PC en la red. Si el PC tiene una VPN o varias redes, puede mostrar otra; la buena es la «Dirección IPv4» del adaptador WiFi que muestra `ipconfig`. Desde el corte 3 no hay que copiarla en la placa: el asistente se la pide a `GET /red` y se la entrega (ver [Conectar una matera](#conectar-una-matera)). Solo hace falta para el respaldo de `config.h` y para abrir el front desde el celular.

El firewall de Windows bloquea el puerto para otros equipos. Se abre una vez, en una PowerShell como administrador, con la red WiFi marcada como privada:

```powershell
New-NetFirewallRule -DisplayName "Matera API 5000" -Direction Inbound -Protocol TCP -LocalPort 5000 -Action Allow -Profile Private
```

Windows suele marcar el hotspot del celular como red pública, y entonces esa regla no aplica. Con el PC conectado al hotspot, se marca la red como privada, también como administrador:

```powershell
Set-NetConnectionProfile -InterfaceAlias "Wi-Fi" -NetworkCategory Private
```

Para cerrarlo después de la demo:

```powershell
Remove-NetFirewallRule -DisplayName "Matera API 5000"
```

El ESP32 le habla a la API en dos pasos, con su código y su clave. Desde el corte 3 la clave la crea la placa y la API solo guarda su huella; con «Conectar a mano», en cambio, la clave la entrega Mis materas al crear la matera. Primero canjea la clave por su token, de alcance «lecturas», que vence a las 24 horas:

```http
POST http://192.168.x.x:5000/api/v1/dispositivos/MT-0001-AA/token
Content-Type: application/json

{"clave": "<la clave del sensor>"}
```

Después manda cada lectura con ese token y la hora en que la tomó, en UTC:

```http
POST http://192.168.x.x:5000/api/v1/dispositivos/MT-0001-AA/lecturas
Content-Type: application/json
Authorization: Bearer <el token del canje>

{"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:04:05Z", "lecturas": {"humedad": 53, "luz": 1500, "temperatura": 25.5}}
```

Sin la cabecera `Content-Type: application/json`, la API no lee el cuerpo y responde `400 SOLICITUD_INVALIDA`. Al ESP32 no le aplica CORS, porque no es un navegador. El programa de la placa y las conexiones de los sensores están en [firmware/README.md](firmware/README.md).

Con `0.0.0.0`, cualquiera en esa red puede llamar la API, y los tokens y la clave del sensor viajan sin cifrar, porque es HTTP. Además el servidor de Flask es de desarrollo. Sirve para la demo en una red de confianza; al terminar, cierre la terminal (la variable se borra con ella) y el puerto del firewall.

### Simulador del ESP32

`simulador/simulador_esp32.py` manda lecturas a la API como el ESP32, sin hardware. Hace lo mismo que la placa (el canje, el token y las lecturas con su hora), y además genera lecturas fuera de rango y datos inválidos. Es un script aparte: no importa nada del backend y solo usa la biblioteca estándar de Python.

Conviene darle su propia matera en Mis materas, distinta de la de la placa, porque cada canje deja sin efecto el token anterior del mismo sensor. Créela con el enlace «Conectar a mano» del formulario de Mis materas, que pide el código (por ejemplo, `MT-0002-AB`) y muestra la clave una sola vez, y con la especie **potos**: los valores «normales» del simulador están dentro de sus rangos, así salen saludables, y las lecturas fuera de rango se distinguen. Con otra especie, por ejemplo la sansevieria, las normales también pueden salir en riesgo. Desde la raíz del repositorio, con el backend corriendo:

```powershell
python simulador/simulador_esp32.py MT-0002-AB --clave=<clave> --intervalo 5 --fuera-de-rango 0.2 --invalidas 0.1
```

```powershell
python simulador/simulador_esp32.py MT-0002-AB --clave=<clave> --casos
```

- **Modo continuo** (el primero): manda una lectura cada `--intervalo` segundos (5 por defecto) hasta Ctrl+C, o `--veces` lecturas.
  - Los valores cambian poco a poco, como en una matera de verdad: la humedad baja despacio y sube de golpe cuando se «riega».
  - `--fuera-de-rango` y `--invalidas` son la parte de las lecturas, de 0 a 1, que sale fuera de rango (valores posibles que la especie no tolera) o con un dato inválido.
  - Al terminar, dice cuántas mandó de cada tipo.
  - Si la API deja de responder (un corte del WiFi, o el backend que se reinicia para cambiar a la tabla en CSV), lo dice y vuelve a intentar en la vuelta siguiente: no hay que lanzarlo otra vez. Si el token venció, canjea la clave de nuevo, también antes de un dato inválido.
- **`--casos`**: manda una vez cada caso de error y dice si la API respondió lo esperado. Los casos son:
  - humedad de 150 %;
  - un texto en vez de un número;
  - un parámetro que falta;
  - una hora en el futuro o sin zona horaria;
  - un JSON mal formado;
  - una lectura de otro sensor, en el cuerpo o en la URL;
  - un envío sin token, con el token alterado o con un token que otro canje dejó sin efecto;
  - una clave equivocada en el canje.

  Termina con «12 de 12 como se esperaba». El caso del alcance (un token de usuario en la ruta del sensor, `403 ALCANCE_INVALIDO`) no está, porque el simulador no tiene cuenta de usuario: lo cubren las pruebas de integración.
- **La clave:** si no se da `--clave`, se pide en la consola sin mostrarla, así no queda en el historial de la terminal. También sirve la variable `MATERA_CLAVE_SENSOR`. Va con signo igual (`--clave=<clave>`) porque una clave puede empezar con guion.
- **Otras opciones:** `--api` cambia la dirección (por defecto `http://127.0.0.1:5000/api/v1`) y `--semilla` repite la misma secuencia de valores.
- **Código de salida:** 0 si todo salió como se esperaba; 1 si la API respondió algo inesperado o rechazó la clave; 2 si no se pudo contactar la API al empezar.

### La demo de la sustentación

**Antes de empezar.** Desde `backend/`, el backend abierto a la red, con el reloj de la demo y el origen de la app Android para el WebSocket:

```powershell
$env:MATERA_HOST = "0.0.0.0"
$env:MATERA_MINUTOS_POR_DIA_JUEGO = "6"
$env:MATERA_ORIGENES_CORS = "http://localhost:5500,http://127.0.0.1:5500,https://localhost"
python main.py
```

- El front en otra terminal (ver [Ejecutar el front](#ejecutar-el-front)), el puerto 5000 abierto en el firewall y el 5500 si el front se abre desde otro equipo.
- El PC, el Honor y la placa en el mismo WiFi de 2,4 GHz (el hotspot del celular sirve).
- Una cuenta admin para el modo prueba (`python crear_admin.py <correo>`) y una matera de **potos** con la placa y el sensor del suelo calibrado (`firmware/README.md`): con la luz encendida y la sonda en tierra húmeda (el potos pide de 40 a 70 %) queda SALUDABLE; con la sonda al aire pide agua, y metida en un vaso de agua marca exceso de agua.
- La app instalada en el Honor (ver [Compilar e instalar](#compilar-e-instalar)) y apuntada al PC con el QR de Mi cuenta.

**Corte 3.** Lo nuevo se muestra así:

1. **La matera Tamagotchi con el reloj acelerado.** Con 6 minutos por día, una hora de juego dura 15 segundos, lo mismo que tarda la placa entre una lectura y otra: un potos bien cuidado llega a brote a los 6 minutos. Para verla decaer sin esperar, se usa el simulador sobre otra matera de potos con `--fuera-de-rango 1`: con esa especie, la mayoría de esas lecturas salen CRITICO. La cara se pone triste, llega el aviso «pasó a CRÍTICO» y, cuando el promedio de las 6 horas de juego queda por debajo de −5, «se marchitó» (ver [La matera Tamagotchi](#la-matera-tamagotchi)).
2. **Cada estado, con el modo prueba.** Con la cuenta admin, en Mis materas, «Modo prueba» en la matera de la placa: por ejemplo FLORECIDA, MARCHITA, cara CRÍTICO y globo SED, y «Ver este estado». La app lo dibuja al momento, con la marca «Modo prueba», y la pantalla de la placa en su próxima lectura (como mucho 15 s). Los puntos y el diagnóstico siguen siendo los reales. «Volver a lo normal» la deja como es (ver [Modo prueba](#modo-prueba-solo-administradores)). Una cuenta que no es admin recibe `403 PERMISO_DENEGADO`, aunque llame a la API directo (con `$api` y `$beto` del punto 3 de «Lo de siempre», más abajo):

   ```powershell
   $prueba = @{ etapa = "SEMILLA"; condicion = "SANA"; cara = "SALUDABLE"; dormida = $false; necesidad = $null } | ConvertTo-Json
   try { Invoke-RestMethod -Method Put "$api/juego/materas/1/prueba" -Headers @{ Authorization = "Bearer $beto" } -ContentType "application/json" -Body $prueba } catch { $_.ErrorDetails.Message }
   ```

   Lo decide `Usuario.exigir_admin`, en el dominio.
3. **La tabla de posiciones con dos cuentas.** Una participa con un apodo y la otra no. La que no participa no aparece en la tabla ni la ve: su pantalla Juego la invita a participar, y `GET /juego/tabla` le responde `403 PARTICIPACION_REQUERIDA`. Lo decide `Participacion.exigir_participacion`, en el dominio.
4. **La placa se conecta por Bluetooth desde el celular.** Con la placa en su modo de conexión (sin red guardada, o BOOT 5 s), en la app del Honor: «Agregar matera», «Por Bluetooth», la clave de la pantalla, elegir `Matera-…`, el WiFi y su clave. Funciona aunque el Honor sea el hotspot, porque no deja su red (ver [Conectar por Bluetooth](#conectar-por-bluetooth)). Si el Bluetooth falla, el mismo asistente sigue por la red de la placa desde el PC.
5. **La app en el Honor.** Es el mismo front: Mis materas, el Tamagotchi, el Juego y los avisos como notificaciones de Android (se activan en Juego). Muestra que la app es otro adaptador del cliente: el asistente no cambió, solo se agregó `BluetoothNativo` en `canales-placa.js` (ver [La app móvil](#la-app-móvil)).
6. **La prueba de cambio del corte 3.** `git show --name-status 1dac8d8 -- backend/dominio backend/aplicacion` solo lista archivos agregados, y lo mismo el modo prueba con `8c44b1d` (ver [La prueba de cambio del corte 3](#la-prueba-de-cambio-del-corte-3)).

Si el profesor confirma que una lectura EN_RIESGO no debe restar, solo cambia la tabla `ReglaDeCuidado.PUNTOS` de `dominio/juego.py` (y sus pruebas).

**Lo de siempre (fase 2).** El enunciado de la fase 2 pide cuatro cosas, que siguen valiendo. Las tres primeras se hacen así, desde la raíz del repositorio y con el backend corriendo:

1. **El simulador enviando lecturas en vivo.** Con Mis materas abierta en el navegador, cada lectura aparece al instante (ver [Simulador del ESP32](#simulador-del-esp32)). Con `--fuera-de-rango` y `--invalidas` se ven también los rechazos.
2. **El cambio de CSV a BD por configuración.** `exportar_especies_csv.py`, `MATERA_TABLA_REFERENCIA=csv` y reiniciar el backend (ver [Tabla de referencia](#tabla-de-referencia-csv-o-base-de-datos)). El simulador sigue solo cuando el backend vuelve. Agregar una especie (en Especies, con la cuenta admin) responde `409 TABLA_SOLO_LECTURA`.
3. **Un acceso a una planta ajena, que falla.** Otra cuenta pide el historial de una matera que no es suya. En PowerShell, con `curl.exe` (viene con Windows):

   ```powershell
   $api = "http://127.0.0.1:5000/api/v1"
   $cuenta = @{ nombre = "Beto"; correo = "beto@correo.co"; contrasena = "clave-de-beto" } | ConvertTo-Json
   Invoke-RestMethod -Method Post "$api/usuarios" -ContentType "application/json" -Body $cuenta
   $beto = (Invoke-RestMethod -Method Post "$api/sesiones" -ContentType "application/json" -Body $cuenta).token
   curl.exe -s -w " (estado %{http_code})" "$api/plantas/1/historial" -H "Authorization: Bearer $beto"
   ```

   El id 1 es la primera matera de la base, que no es de Beto. La respuesta es `{"error": "PLANTA_NO_ENCONTRADA", ...}` con estado 404, la misma que con un id que no existe (`/plantas/999/historial`): no revela que esa matera exista. Lo decide `Planta.exigir_dueno`, en el dominio.

La cuarta es la pregunta de cambio (MQTT u OAuth). El análisis va en el documento de arquitectura, que redacta el equipo. Para ubicarla en el código:
- **MQTT** sería otro adaptador de entrada, al lado de `presentacion/rutas_dispositivos.py`, que llama al mismo puerto `RegistrarLectura`; y, si el aviso también sale por MQTT, otro suscriptor de `NotificadorDiagnosticos` en la lista de `AvisarATodos`, en `main.py`. El núcleo no cambia.
- **OAuth** cambia quién emite y verifica el token de usuario, en el borde: `Autenticacion.con_usuario` y los puertos `EmisorTokens` y `VerificadorTokens`, que hoy implementa `TokensJwt`. Los casos de uso siguen recibiendo una `IdentidadUsuario`.

## Ejecutar el front

En otra terminal, desde la raíz del repositorio:

```bash
python -m http.server 5500 --directory frontend
```

Abra `http://localhost:5500`. El front se tiene que servir por HTTP; abrir `index.html` con doble clic no funciona porque usa módulos de JavaScript.

El front busca la API en el mismo equipo desde el que se abrió: `http://<equipo>:5000/api/v1`. En el PC es `localhost`; desde un celular en la misma red se abre `http://<IP del PC>:5500`, con el backend arrancado con `MATERA_HOST=0.0.0.0` y el puerto 5500 abierto en el firewall (ver «Abrir el front desde el celular», en [Conectar una matera](#conectar-una-matera)). Si cambia el puerto del backend, ajuste `frontend/js/config.js`.

El front no tiene rangos, umbrales ni reglas. Los parámetros, las especies, los estados y las recomendaciones salen de la API. Del juego tampoco calcula nada: los puntos, la etapa, la condición, la cara, la necesidad, el aviso y quién ve la tabla vienen de `GET /juego/...`, y el front solo los dibuja.

Tiene dos estilos, Profesional (por defecto en el PC) y Juego (por defecto en el celular), y cuatro temas: claro, oscuro, AMOLED y el del sistema. Se eligen en el botón de la paleta de la cabecera o en Mi cuenta, y se recuerdan en ese equipo. Las pestañas van en este orden, arriba en el PC y abajo en el celular: Mis materas, Diagnóstico, Juego, Historial, Especies y, para el admin, Administración. Después de ingresar se entra a Mis materas, y el título de la pestaña del navegador dice en qué pantalla se está.

| Pantalla | Acceso | Qué hace |
|---|---|---|
| Diagnóstico | con sesión | Elige una de sus materas y muestra su Tamagotchi (`GET /juego/materas`) y su última lectura real, enviada a `POST /diagnosticos` (R1), con el estado de cada parámetro y las recomendaciones. Se actualiza sola cada 10 s y con el WebSocket. No hay valores escritos a mano (el corte 3 pide reducir lo manual). No guarda nada. |
| Especies | con sesión | Muestra el catálogo de `GET /especies` con bandas escaladas según los límites físicos de `GET /parametros`. Al admin le muestra además «Agregar especie»: el nombre, el nombre científico y un mínimo y un máximo por parámetro, con una vista previa de la banda (`POST /admin/especies`). Los rangos los revisa la API, y a quien no es admin le responde 403. |
| Ingresar / Crear cuenta | pública | Una tarjeta con dos pestañas, Ingresar y Crear cuenta. Al entrar guarda el token y vuelve a la pantalla privada que se había pedido, o a Mis materas. |
| Mis materas | con sesión | Las materas del usuario con su última medición, que se actualiza sola (ver abajo). «Agregar matera» pide apodo y especie y abre el asistente «Conectar sensor» (ver [Conectar una matera](#conectar-una-matera)); «Cambiar sensor», en cada tarjeta, abre el mismo asistente y conserva el historial. Para el simulador y las placas con el programa de la fase 2 (código y clave en `config.h`) queda «Conectar a mano»: se escribe el código del sensor y la clave se muestra una sola vez (va en `--clave=` o en `config.h`); con el mismo código, da una clave nueva y la anterior deja de servir con su token. Cada tarjeta también permite ver el historial y eliminar la matera. Desde el front no se escriben mediciones. Cada tarjeta muestra además la matera Tamagotchi (ver [La matera Tamagotchi](#la-matera-tamagotchi)) con los puntos de esa matera y sus horas de juego bien cuidada. |
| Historial | con sesión | El resumen (cuántas mediciones hay en cada estado y la última), la gráfica y la lista de las mediciones de una matera, con el estado que calculó la API en su momento. Se actualiza solo, igual que Mis materas. |
| Juego | con sesión | Sus puntos: el total, los puntos de cada matera y los últimos 20 movimientos («+10 · sala · SALUDABLE · 14:03:15»); en el celular se ven 10 y «Ver más» muestra el resto. A quien participa le muestra la tabla de posiciones con su fila resaltada; a quien no, lo invita a participar desde Mi cuenta. También dice cómo llegan los avisos y tiene el botón para activar las notificaciones del navegador. |
| Mi cuenta | con sesión | Nombre, correo, rol, cantidad de plantas y cerrar sesión. En «Tabla de posiciones», participar con un apodo de jugador, cambiarlo o dejar de participar (`PUT /juego/participacion`); los errores del apodo los responde la API. En «Apariencia», el estilo y el tema. |
| Administración | solo admin | Las cifras de las cuentas y, en cada una, activar, desactivar, dar o quitar el rol y eliminar (hay que escribir su correo para confirmar). Las especies se agregan en Especies. La pestaña solo aparece para un admin, pero los permisos los revisa la API. |

Todas las pantallas menos Ingresar exigen sesión (R7): sin ella, el front lleva a Ingresar y no llama a la API. Si la API responde `401 SESION_INVALIDA`, el front borra el token y lleva a Ingresar.

Mis materas y el Historial se actualizan solos de dos maneras:
- **Consulta periódica.** Mientras la pantalla y la pestaña están a la vista, `js/consulta-periodica.js` vuelve a pedir `GET /plantas` (o el historial) cada 10 segundos. Solo se vuelven a pintar las tarjetas que cambiaron. Debajo del título se ve la hora de la última consulta.
- **En vivo.** Mientras hay una sesión, `js/tiempo-real.js` mantiene abierto el WebSocket `/api/v1/tiempo-real`, y la barra muestra «En vivo». Cada lectura aparece al instante, sin esperar la próxima consulta. Si la conexión se cae, reintenta con esperas de 1 a 30 segundos, y mientras tanto la consulta periódica mantiene la pantalla al día.
- **Las dos a la vez.** Si una respuesta de la consulta llega después de una medición en vivo más reciente, la pantalla no retrocede, y el Historial no repite una medición que ya tenía. Una petición que no termina en 15 segundos se da por perdida, así una conexión colgada no detiene la consulta periódica.

El juego (`js/juego.js`) también se actualiza solo: mientras hay sesión, en cualquier pantalla, pide `GET /juego/materas` y `GET /juego/puntaje` cada 10 segundos y cada vez que llega un mensaje del WebSocket (el backend guarda los puntos antes de avisar). Así cambian solos el dibujo de cada matera, sus puntos, el puntaje de la cabecera y la tabla. Al cerrar la sesión se borra todo lo del juego. Las reglas están en [La matera Tamagotchi](#la-matera-tamagotchi), y el asistente que conecta una placa, en [Conectar una matera](#conectar-una-matera).

## La matera Tamagotchi

Es el pedido del profesor para el corte 3: volver la planta un Tamagotchi. Cada matera tiene un dibujo que cambia con su estado, y cada dueño gana o pierde puntos con cada lectura. Todo lo decide el dominio, en `dominio/juego.py` y `dominio/mascota.py` (`ReglaDeCuidado` y `CuidadoDeMascota`): el front pide `GET /juego/materas` y solo dibuja lo que recibe. El diagrama está en [docs/diagramas](docs/diagramas/README.md#clases-del-juego) (`clases-juego.mmd`).

**Puntos.** Cada lectura aceptada (la que responde 201) deja un movimiento en el puntaje del dueño:

| Estado de la lectura | Puntos |
|---|---|
| `SALUDABLE` | +10 |
| `EN_RIESGO` | −5 |
| `CRITICO` | −10 |

- El estado es el de la regla híbrida del corte 1: el juego solo lo lee.
- Una lectura rechazada (400, 401 o 403) no cuenta.
- El movimiento lleva la hora del servidor, no la de la placa.
- El puntaje puede quedar negativo, y cada matera suma por su lado. Los puntos de una matera borrada siguen en el total del dueño.
- Todos empiezan en 0 con la versión 4 de la base: las lecturas de antes no cuentan.
- Restar 5 en `EN_RIESGO` es decisión del equipo: el profesor dijo que lo normal no suma ni resta. Si se cambia, solo cambia `ReglaDeCuidado.PUNTOS`.

El dibujo tiene cinco capas, y cada una sale de un dato distinto:

| Capa | Sale de | Valores |
|---|---|---|
| Tamaño (`etapa`) | Las horas de juego bien cuidada, al ritmo de su especie. | `SEMILLA`, `BROTE`, `PLANTA`, `FLORECIDA` |
| Condición (`condicion`): color y postura de las hojas | El promedio de puntos de las lecturas de las 6 horas de juego que terminan en la última lectura. | `SANA`, `DECAIDA`, `MARCHITA` |
| Cara (`cara`) | El estado de la última lectura. | feliz (`SALUDABLE`), preocupada (`EN_RIESGO`), triste (`CRITICO`), o dormida |
| Globo (`necesidad`) | El parámetro fuera de rango de la última lectura. | «¡tengo sed!», «¡me ahogo!», «¡tengo frío!», «¡tengo calor!», «¡poca luz!», «¡mucha luz!» |
| Aviso (`aviso`) | Lo que cambió con la última lectura. | `PASO_A_CRITICO`, `SE_MARCHITO` |

**Tamaño.** Cuenta cada hora de juego en la que la matera tuvo lecturas y su promedio fue de −5 o más. Una hora con una sola lectura `EN_RIESGO` cuenta; una hora marchita no, y una hora sin lecturas tampoco: si la descuidan, deja de crecer. Cada especie tiene su ritmo, en días de juego bien cuidada (tabla `ritmo_crecimiento`, cargada desde `datos/ritmos.sql`). Son valores de juego, no botánicos:

| Especie | Brote | Planta | Florecida |
|---|---|---|---|
| potos | 1 día | 3 días | 6 días |
| helecho | 1 día | 3 días | 7 días |
| lavanda | 1 día | 4 días | 8 días |
| sansevieria | 2 días | 5 días | 10 días |
| suculenta | 2 días | 6 días | 12 días |
| una especie que agrega el admin | 1 día | 3 días | 7 días |

**Condición.** El promedio de puntos de las lecturas de las 6 horas de juego que terminan en la última lectura:
- mayor que 0: sana;
- de 0 a −5, los dos incluidos: decaída. Una matera que siempre está `EN_RIESGO` queda aquí y sigue creciendo;
- menor que −5: marchita.

La ventana se cuenta desde la última lectura y no desde la hora de la consulta: mientras no llegan lecturas, la condición no cambia.

**Globo.** Si hay varios parámetros fuera de rango, primero el agua, después la temperatura y después la luz (`necesidad_principal`). La misma regla llena el campo `necesidad` de la respuesta 201, con el que la pantalla de la placa dibuja su globo.

**Avisos.** `SE_MARCHITO` sale cuando la matera queda marchita y antes no lo estaba. `PASO_A_CRITICO` sale cuando la última lectura es `CRITICO` y la anterior no lo era. Si pasan las dos cosas con la misma lectura, gana `SE_MARCHITO`.
- En la app (`js/avisos.js`), cada aviso sale una sola vez por lectura («sala pasó a CRÍTICO», «sala se marchitó»). Las ya avisadas se guardan en `localStorage`, por usuario: la consulta cada 10 s, recargar o volver a ingresar no lo repiten.
- Con contexto seguro (por ejemplo, `http://localhost`) y el permiso concedido, es una notificación del navegador. El permiso se pide con un botón de la pantalla Juego o del aviso, nunca al cargar.
- Si no (por ejemplo, el celular que abre el front por la red local, en http), el aviso aparece dentro de la página y el celular vibra.
- En la placa, la pantalla parpadea mientras el estado sea `CRITICO`.

**Dormida.** Si no llegan lecturas en 30 minutos reales (`MATERA_MINUTOS_SIN_LECTURAS`), la matera duerme: cara dormida, sin globo y sin aviso, porque la última lectura ya es vieja. Sin lecturas no suma ni resta. Una matera que nunca tuvo lecturas es una semilla dormida.

**El reloj del juego.** `MATERA_MINUTOS_POR_DIA_JUEGO` dice cuántos minutos reales dura un día de juego. Con 1440, el valor por defecto, es el tiempo real. Para la demo se usa 6: una hora de juego dura 15 segundos, lo mismo que tarda la placa entre una lectura y otra, así que cada hora tiene su lectura y la matera crece y se marchita en minutos. Con menos de 6 quedan horas sin lectura y crece más lento. Las reglas no cambian, solo la escala.
- Cada lectura queda en su hora de juego al llegar (tabla `cuidado_por_hora`): cambiar el reloj no reagrupa las horas que ya pasaron, y ninguna matera crece de golpe.
- Los 30 minutos para dormirse son reales y no cambian con el reloj.

```powershell
$env:MATERA_MINUTOS_POR_DIA_JUEGO = "6"
python main.py
```

**Cambiar el reloj sin reiniciar (solo administradores).** En Administración, la tarjeta «Reloj del juego» dice cuánto dura hoy una hora de juego y la cambia al instante.
- **Opciones:** tres atajos (tiempo real; 1 hora = 1 minuto, con días de 24 minutos; y 1 hora = 15 segundos, la demo) o un valor a mano en segundos, minutos u horas. Si la hora de juego dura menos que los 15 s entre lecturas de la placa, la tarjeta avisa que quedarán horas sin lecturas.
- **Quién lo ve:** la pantalla Juego muestra el reloj vigente a todos.
- **Rutas:**
  - `GET /api/v1/juego/reloj`, con cualquier sesión, responde `{"minutosPorDia", "segundosPorHora"}`;
  - `PUT /api/v1/juego/reloj` con `{"minutosPorDia": 24}`. Quien no es admin recibe `403 PERMISO_DENEGADO` (`Usuario.exigir_admin`), y una duración que no sirve, `400 RELOJ_INVALIDO`.
- **Se guarda en la base** (tabla `reloj_juego`, migración v5) y sigue después de reiniciar. `MATERA_MINUTOS_POR_DIA_JUEGO` queda como valor inicial, mientras ningún admin lo cambie.
- **El pasado no cambia:** las lecturas que ya llegaron conservan su hora de juego, y las nuevas se agrupan con la escala nueva.
- **Archivos:** entra como archivos nuevos (`dominio/reloj_juego.py`, `dominio/puertos_reloj.py` y `aplicacion/reloj_juego.py`). `RelojDeJuegoAjustable` tiene la misma forma que `RelojDeJuego`, y `main.py` se lo pasa al puntaje y a la matera Tamagotchi.

**La tabla de posiciones.** Solo para quien decide participar:
- La primera vez que entra alguien que todavía no decidió (`SIN_DECIDIR`), un diálogo de la página le pregunta si quiere aparecer en la tabla. Si dice que sí, pide un apodo de jugador. «Decidir después» no responde a la API: se vuelve a preguntar en la próxima sesión. En Mi cuenta se puede participar, cambiar el apodo o dejar de participar.
- El apodo tiene de 3 a 20 caracteres (letras sin tildes, números, `_` y `-`) y no se repite, sin importar mayúsculas. Los errores los responde la API: `400 APODO_JUGADOR_INVALIDO` y `409 APODO_JUGADOR_REPETIDO`.
- Quien no participa conserva su puntaje, sus movimientos y su matera Tamagotchi, pero no aparece en la tabla y no la ve: `GET /juego/tabla` le responde `403 PARTICIPACION_REQUERIDA`. Lo decide `Participacion.exigir_participacion`, en el dominio.
- Las cuentas desactivadas no aparecen. Con los mismos puntos, misma posición (1, 2, 2, 4), y entre ellas, por apodo. La fila de quien pregunta viene con `soyYo`.

**Dónde se ve.** En Mis materas, el dibujo de cada tarjeta (`js/dibujo-planta.js`, un SVG con los colores de `css/variables.css` y su descripción accesible). En la cabecera, el puntaje total. En la pantalla Juego, los puntos de cada matera, los últimos 20 movimientos y la tabla. Las rutas están en la [API](#cuentas-plantas-y-sensores-corte-2), y el recorrido de una lectura hasta los puntos, en [`secuencia-puntaje`](docs/diagramas/README.md#secuencia-del-puntaje).

### Modo prueba (solo administradores)

Sirve para mostrar en la demo cada estado de la matera Tamagotchi sin esperar a que la planta llegue a él. En Mis materas, un admin abre «Modo prueba» en una matera suya, elige el tamaño, la condición, la cara, si duerme y el globo, y toca «Ver este estado». «Volver a lo normal» la deja como es.

- **Solo cambia el dibujo:** en la app y en la pantalla de la placa, que lo muestra en su siguiente lectura. Los puntos, las lecturas y el diagnóstico siguen siendo los reales, y no sale ningún aviso.
- **Rutas:**
  - `PUT /api/v1/juego/materas/{id}/prueba` con `{"etapa", "condicion", "cara", "dormida", "necesidad"}`;
  - `DELETE /api/v1/juego/materas/{id}/prueba`.
  - `GET /juego/materas` y la respuesta 201 a la placa traen el campo `prueba`, que es `null` si la matera se ve como es.
- **Quién puede usarlo** lo decide el dominio:
  - si la cuenta no es admin, la API responde `403 PERMISO_DENEGADO` (`Usuario.exigir_admin`);
  - si la matera es ajena o no existe, responde `404` (`Planta.exigir_dueno`).
- **Sin cambiar archivos existentes del núcleo:** entra como archivos nuevos (`dominio/modo_prueba.py`, `dominio/puertos_prueba.py` y `aplicacion/modo_prueba.py`), que envuelven `ConsultarMascotas` y `RegistrarLectura` en `main.py`.
- **Se borra al reiniciar el backend:** el estado de prueba vive en memoria (`infraestructura/estados_prueba_memoria.py`) y no en la base.
- **Diagramas:** [`clases-modo-prueba`](docs/diagramas/README.md#clases-del-modo-prueba) y [`secuencia-modo-prueba`](docs/diagramas/README.md#secuencia-del-modo-prueba).

## Conectar una matera

Desde el corte 3, una placa nueva se conecta sin tocar `config.h` ni volver a subir el programa. La placa saca su código de la MAC (`MT-0000-XX`, como siempre), crea su propia clave, abre una red WiFi con un QR en su pantalla y se anuncia por Bluetooth. La app le entrega el WiFi y la dirección del servidor por Bluetooth o uniéndose a esa red, y crea la matera con el código y la huella de esa clave. Todo lo de la placa (etapas, pantallas, API local en `192.168.4.1`, Bluetooth LE, botón BOOT y cómo compilar) está en [firmware/README.md](firmware/README.md).

Antes de empezar:
- El backend tiene que escuchar en la red, con `MATERA_HOST=0.0.0.0` y el puerto 5000 abierto en el firewall (ver [Mediciones de un ESP32](#mediciones-de-un-esp32-en-la-red)).
- La placa y el PC van en el mismo WiFi, de 2,4 GHz y con salida a internet (la placa toma la hora por NTP).

**El recorrido del asistente.** «Agregar matera» pide apodo y especie y abre el asistente «Conectar sensor» (`js/conectar-sensor.js`); «Cambiar sensor», en una tarjeta, abre el mismo asistente y conserva el historial. Son seis pasos:
1. **Preparar.** Mientras el equipo sigue en su WiFi, la app pide `GET /red` y anota a qué direcciones mandará la placa sus lecturas (como máximo 4). Si la lista viene vacía (el backend escucha solo en `127.0.0.1`), muestra el aviso de la API y no sigue. Después se elige el camino: **por Bluetooth** (el recomendado: el equipo no deja su WiFi) o **por la red de la placa**. Bluetooth solo se ofrece si el navegador tiene Web Bluetooth: Chrome o Edge, con el front en `localhost` o con HTTPS. Si no, el asistente dice por qué y ofrece solo la red de la placa. En la app Android, Bluetooth se ofrece siempre, con el Bluetooth del celular (ver [La app móvil](#la-app-móvil)).
2. **Encontrar la placa** (por Bluetooth) **o unirse a ella** (por su red). La pantalla de la matera muestra un QR con su red (`Matera-` y el código, por ejemplo `Matera-5500BA`) y una clave WPA2 de 8 caracteres, nueva cada vez.
   - Por Bluetooth se escribe esa clave en la app, el navegador (o Android, en la app) muestra la lista de placas cercanas y se elige la que se llama como la red. La app pide `info` con la clave.
   - Por la red de la placa, se escanea el QR con la cámara del celular, o en el PC se elige esa red y se escribe la clave. La app encuentra la placa sola en `http://192.168.4.1` (`GET /info`).
   - En los dos casos la placa responde su código, la huella de su clave y las redes que ve.
3. **Elegir el WiFi.** La red y su clave van directo a la placa (`configurar`), con las direcciones del paso 1. La app sigue sus etapas con `estado`: `conectando`, `buscando-servidor` y `esperando-matera`. La placa prueba cada dirección primero sin la clave, y solo se la manda a la que responde como la API.
4. **Volver a su red** (o, por Bluetooth, **cerrar la conexión**). La placa apaga su red y su Bluetooth (`cerrar`). Con la red de la placa, la app espera a que la API vuelva a responder.
5. **Crear la matera** (`POST /plantas`) o **cambiar el sensor** (`PUT /plantas/{id}/sensor`), con el código y la huella. La respuesta no trae clave: la clave nunca sale de la placa, salvo hacia la API en el canje.
6. **Primera lectura.** La placa canjea su clave cada 5 s hasta que la API reconoce la matera, y manda su primera lectura. La app la espera y muestra su estado. La pantalla de la placa pasa de «Agrégame en la app» a la carita.

**Dos caminos, un puerto.** Es puertos y adaptadores también del lado del cliente. El asistente solo conoce el puerto `CanalPlaca` (`js/canal-placa.js`), con las cuatro operaciones de la API local de la placa: `info`, `configurar`, `estado` y `cerrar`. Cada adaptador lo hereda y lo traduce a su transporte:
- `RedDeLaPlaca` (`js/canal-red-placa.js`): HTTP en `192.168.4.1`.
- `BluetoothWeb` (`js/canal-bluetooth-web.js`): Web Bluetooth. El contrato común de Bluetooth está en `CanalBluetooth` (`js/canal-bluetooth.js`): cada pedido se escribe en pedazos de 20 bytes, sin escrituras largas; la respuesta llega en trozos con 3 bytes de cabecera y se junta antes de leer el UTF-8; las notificaciones se activan antes del primer pedido, y mientras la clave sirve se pide `estado` cada 45 s para que la placa no corte la conexión.
- `BluetoothNativo` (`js/canal-bluetooth-nativo.js`): el Bluetooth de la app Android, con el plugin `@capacitor-community/bluetooth-le`. Hereda de `CanalBluetooth` y solo pone su transporte: `initialize` con `androidNeverForLocation`, la lista de Android filtrada por el servicio de la placa, `connect` con su aviso de desconexión, las notificaciones de la respuesta antes del primer pedido y escrituras con respuesta de 20 bytes. Traduce los errores del plugin a los del canal (`CONEXION_CANCELADA`, `BLUETOOTH_APAGADO`, `BLUETOOTH_NO_DISPONIBLE` y `BLUETOOTH_CORTADO`).

`js/canales-placa.js` es el punto de composición, como `main.py` en el backend: dice qué adaptadores se ofrecen y en qué orden. El asistente no importa ninguno. Cada canal declara si deja la red (mientras tanto no hay API) y si pide la clave de la pantalla, y el asistente solo mira eso. En el navegador la lista es `BluetoothWeb` y `RedDeLaPlaca`; en la app, `BluetoothNativo` y `RedDeLaPlaca` (su WebView no tiene Web Bluetooth). El asistente es el mismo en los dos: agregar la app no lo cambió.

**Si un camino falla.** Los errores de la placa llegan con su código, igual por los dos caminos:
- `401 CLAVE_INCORRECTA` dice cuántos intentos quedan, y se corrige la clave sin volver a la lista de placas.
- `429 DEMASIADOS_INTENTOS` (5 claves equivocadas) bloquea la placa 60 s: el botón espera con la cuenta atrás de `detalle.segundos`.
- Si la placa corta la conexión (20 s sin un pedido con la clave correcta, 2 minutos sin pedidos después, o un corte), el siguiente pedido se reconecta solo a la misma placa.
- Cerrar la lista de placas sin elegir no es un error: se puede volver a buscar.
- Con el Bluetooth apagado o caído, el asistente lo dice y ofrece **seguir por la red de la placa**. Se conserva lo ya escrito: el apodo, la clave de la pantalla (que es la misma de la red) y la red y la clave del WiFi. Desde la red de la placa también se puede pasar a Bluetooth.

El avance se guarda en `sessionStorage`, porque al cambiar de red la página puede recargarse. Se guardan el paso y el camino, nunca la clave del WiFi ni la de la pantalla: si la página se recarga por Bluetooth, se vuelve a escribir la clave. El código, la huella y las etapas los decide la placa, y el estado lo calcula la API: el asistente solo los muestra. La secuencia completa está en [`secuencia-conexion-placa`](docs/diagramas/README.md#secuencia-de-la-conexión-de-una-placa). Para probarlo sin la placa, se abre el front con `?placa=http://127.0.0.1:8099` y se pone ahí un doble de la API local de la placa; solo se acepta una dirección de este mismo equipo o de la red de la placa (192.168.4.x), para que un enlace con `?placa=` no pueda llevarse la clave del WiFi a otro equipo.

**Abrir el front desde el celular.** Hace falta si el asistente se usa desde un celular, o para mostrar la app en él:
1. Arrancar el backend con `MATERA_HOST=0.0.0.0`. Así, además de escuchar en la red, acepta el front desde `http://<IP del PC>:5500` en CORS y en el WebSocket (el puerto sale de `MATERA_PUERTO_FRONT`).
2. Servir el front como siempre (`python -m http.server 5500 --directory frontend`): escucha en todas las redes del PC.
3. Abrir también el puerto 5500 en el firewall, como administrador:

   ```powershell
   New-NetFirewallRule -DisplayName "Matera front 5500" -Direction Inbound -Protocol TCP -LocalPort 5500 -Action Allow -Profile Private
   ```

   Para cerrarlo después: `Remove-NetFirewallRule -DisplayName "Matera front 5500"`.
4. En el celular, abrir `http://<IP del PC>:5500`. La IP es la de `GET /red` o la «Dirección IPv4» de `ipconfig`. El front busca la API en ese mismo equipo, en el puerto 5000.

Por la red local el front va en http, así que el celular no muestra notificaciones del navegador: los avisos del juego aparecen dentro de la página y el celular vibra.

**Límites conocidos.**
- **El celular que hace de hotspot no puede unirse a la red de la placa.** Por Bluetooth sí funciona, si el navegador lo permite, y siempre desde la app Android. Si no, el asistente se usa desde el PC (con el front en `localhost`, la app sigue alcanzando la API al cambiar de red) o desde el celular de otra persona.
- **Web Bluetooth necesita HTTPS o `localhost`.** Con el front abierto desde el celular por `http://<IP del PC>:5500`, el navegador no lo ofrece y queda la red de la placa. En Windows, el Bluetooth de Chrome a veces no conecta: el asistente reintenta y, si sigue fallando, ofrece la red de la placa.
- **El enlace Bluetooth no va cifrado**, igual que la red propia con su clave de 8 caracteres (ver «Seguridad» en el README del firmware).
- **Apagar los datos móviles** mientras el celular está en la red de la placa: con ellos encendidos, Android puede mandar las peticiones por los datos y no llegar a `192.168.4.1`.
- **Chrome puede pedir permiso para buscar dispositivos de la red local.** Hay que elegir Permitir; el asistente lo recuerda en sus pistas.
- La red de la placa acepta un solo equipo a la vez, y no tiene internet: es normal.
- Al unirse al WiFi, la placa cambia el canal de su red y el equipo se desconecta un momento: la app vuelve a preguntar sola.
- La ESP32 no ve las redes de 5 GHz. En el hotspot de un iPhone hay que encender «Maximizar compatibilidad».

**El respaldo: «Conectar a mano».** Es el enlace del formulario de Mis materas y de los primeros pasos del asistente. Se escribe el código del sensor y la API crea la clave y la muestra una sola vez, como en la fase 2. Sirve para el simulador (`--clave=`) y para las placas con el programa de la fase 2, que llevan el código y la clave en `config.h`. El programa actual ya no usa `CODIGO_SENSOR` ni `CLAVE_SENSOR`: su `config.h` es opcional y solo ajusta pines, los valores del LDR y una red de respaldo para desarrollo.

### Conectar por Bluetooth

Es el camino recomendado: el equipo no deja su WiFi, así que sirve aunque el celular sea el hotspot.

| Desde | Qué hace falta |
|---|---|
| La app Android | El Bluetooth del celular encendido. La primera vez, Android pide el permiso «Dispositivos cercanos» (ver [Permisos](#permisos)). |
| Chrome o Edge en el PC | El front en `http://localhost:5500` (Web Bluetooth exige `localhost` o HTTPS) y el Bluetooth del PC encendido. |
| Chrome en el celular, por `http://<IP del PC>:5500` | No se ofrece, porque no es HTTPS: queda la red de la placa, o la app. |

1. «Agregar matera» (o «Cambiar sensor») y elegir «Por Bluetooth», la opción recomendada.
2. Escribir la clave de 8 caracteres de la pantalla de la placa (la misma de su red) y tocar «Buscar la placa». En la lista, elegir la que se llama como la red de la pantalla (`Matera-…`).
3. Elegir el WiFi en la lista que manda la placa y escribir su clave. La placa se une, encuentra el servidor y espera la matera.
4. La app cierra la conexión, crea la matera con el código y la huella, y espera la primera lectura.

- **Plazos de la placa:** una conexión que en 20 s no manda un pedido con la clave correcta se corta; después de una clave válida, a los 2 minutos sin pedidos (la app pide `estado` cada 45 s). Si se corta, el siguiente pedido se reconecta solo.
- **Claves equivocadas:** el `401` dice cuántos intentos quedan; a la quinta, el `429` bloquea la placa 60 s y el botón espera con la cuenta atrás de `detalle.segundos`.
- **El contrato** (el servicio, los pedidos en pedazos de 20 bytes, las respuestas en trozos y los errores) está en [firmware/README.md](firmware/README.md#bluetooth-le), y el recorrido completo, en [`secuencia-conexion-bluetooth`](docs/diagramas/README.md#secuencia-de-la-conexión-por-bluetooth).
- **Seguridad:** el enlace no va cifrado, y la app no puede comprobar que le habla a la placa de verdad. La protección de fondo, emparejar con una clave numérica que muestre la pantalla, está pendiente de decidir (ver «Seguridad» en el README del firmware).
- **Lo probado:** el firmware, desde el PC con `bleak`; el canal del front (`CanalBluetooth`, `BluetoothWeb` y `BluetoothNativo`), en Node contra una placa BLE falsa. El 17 de noviembre se probó de punta a punta desde el celular (HONOR Magic5 Lite, Android 13, app 1.4, `BluetoothNativo`): BOOT 5 s en la placa, «Cambiar sensor» por Bluetooth con la clave de la pantalla, el WiFi del hotspot, y la placa volvió a canjear su clave y a mandar lecturas. Con la misma prueba se comprobaron el enlace del QR (el diálogo propone el servidor y lo guarda), el modo prueba en la pantalla de la placa, el reloj del juego y la notificación de Android al pasar a CRÍTICO («prueba pasó a CRÍTICO · ¡tengo sed!», con el sensor junto a la salida de aire del PC).

## La app móvil

La app Android es el mismo front dentro de una WebView nativa, con Capacitor, en la carpeta `app/`. `webDir` apunta a `../frontend`: el front no se copia a mano, y la web y la app son el mismo código. La página vive en el celular (`https://localhost`) y la API sigue en el PC, así que se mantiene RA2, y ninguna regla pasa al JavaScript.

Paquete `co.edu.usergioarboleda.matera`, Capacitor 8.6.0 con `@capacitor-community/bluetooth-le` 8.3.0, `@capacitor/local-notifications` 8.3.1 y `@capacitor/app` 8.1.2 (el enlace del QR). En la app solo cambian algunos adaptadores, y cada uno pregunta a `js/plataforma.js` si está en la app:

| Qué | En la web | En la app |
|---|---|---|
| La dirección de la API | El mismo equipo que abrió el front, puerto 5000 (`config.js`) | La que elige la persona la primera vez (`servidor-app.js`) |
| Bluetooth con la placa | `BluetoothWeb` (Chrome o Edge) | `BluetoothNativo`, con el Bluetooth del celular |
| Avisos de las materas | Notificación del navegador, o un aviso en la página | Notificación de Android (`avisos-nativos.js`), o un aviso en la pantalla |
| Peticiones a la API | `fetch` del navegador, con CORS | `fetch` nativo (`CapacitorHttp`): sin CORS ni contenido mixto |

El front no usa empaquetador, así que los plugins se usan por el puente que Capacitor pone en la página (`window.Capacitor.Plugins`). `BleClient` del plugin de Bluetooth importa `@capacitor/core` por su nombre y no se puede cargar sin empaquetador: `js/ble-nativo.js` tiene los métodos que se usan, con las mismas firmas, su cola y la conversión a hexadecimal del plugin nativo.

### Compilar e instalar

Desde PowerShell, en una copia fuera de OneDrive y con ruta corta (Gradle lo pide):

```powershell
. C:\dev\tools\env.ps1                  # JDK 21 y SDK de Android, en cada sesión
cd C:\dev\matera\app
npm install                             # la primera vez
npx cap sync android                    # copia el front y los plugins al proyecto
cd android
.\gradlew.bat assembleDebug             # APK en app\build\outputs\apk\debug\app-debug.apk
adb devices                             # el celular, con la depuración USB activa y el diálogo aceptado
adb install -r app\build\outputs\apk\debug\app-debug.apk
```

- Se instala **sin `-g`**: así los permisos se piden como los vería cualquiera, en el momento en que se usan.
- El APK de depuración se firma con la llave de depuración de siempre. El `versionCode` de `app/android/app/build.gradle` sube con cada APK que se reparte.
- Lo que se genera al compilar (`build/`, `.gradle/`, `node_modules/`, `assets/public/` y los APK) no se sube.

### Apuntarla al servidor

**La primera vez** la app pregunta dónde está la API. Basta con la IP del PC (`10.34.101.124`): el puerto 5000 y `/api/v1` se agregan solos. También acepta la dirección completa, otro puerto o `https`. Antes de guardarla, la prueba: pide `GET /parametros` sin token y espera el 401 en JSON de la API (R7), así que no hace falta una cuenta ni se escribe nada. La dirección queda guardada en el celular. Se ve y se cambia en Ingresar («Servidor: … · Cambiar») y en Mi cuenta (tarjeta «Servidor»). Cambiarla cierra la sesión, porque el token es de la otra API.

**El QR de Mi cuenta.** En la web, Mi cuenta tiene la tarjeta «App del celular». Muestra un QR con el enlace `co.edu.usergioarboleda.matera://servidor?api=<dirección de la API>`:
- La dirección sale de `GET /red`, con la de la ruta por defecto primero. Las otras direcciones del PC (como máximo 4) quedan como botones, por si el celular está en otra red.
- Con la cámara del celular se abre la app, y la app **pregunta** si usa ese servidor. Un enlace así puede venir de cualquier página o QR, y la app le mandaría a ese servidor el correo y la contraseña: por eso nunca lo cambia sola.
- Si la cámara no ofrece abrir la app, la dirección está escrita al lado, para escribirla.
- En un celular con la app instalada, «Abrir en la app» hace lo mismo sin la cámara.
- El QR lo dibuja `js/qr.js`, un generador mínimo escrito en el proyecto (sin CDN ni librerías de afuera). Se comprobó decodificándolo con OpenCV.

### El backend para la app

- Como siempre para la red: `MATERA_HOST=0.0.0.0` y el puerto 5000 abierto en el firewall.
- **HTTP sin cifrar:** las peticiones salen por `CapacitorHttp`, así que no hay CORS ni bloqueo por contenido mixto. El manifiesto permite tráfico sin cifrar, porque la API va por `http` en la red local. `js/plataforma.js` hace que ese `fetch` nativo respete la cancelación, como el del navegador: así se cumplen los plazos de 15 s de la API y los de la placa.
- **El WebSocket no pasa por `CapacitorHttp`.** La WebView lo abre con `Origin: https://localhost`, y el backend rechaza los orígenes que no conoce (403 `ORIGEN_NO_PERMITIDO`). Para tener las mediciones en vivo en la app, se agrega ese origen:

  ```powershell
  $env:MATERA_HOST = "0.0.0.0"
  $env:MATERA_ORIGENES_CORS = "http://localhost:5500,http://127.0.0.1:5500,https://localhost"
  python main.py
  ```

  Sin eso, la app funciona igual con la consulta cada 10 s (R6), y el indicador dice «En vivo: reconectando…». El `ws://` desde una página `https` se permite porque la app tiene `allowMixedContent`; la WebView solo avisa que está desaconsejado.

### Notificaciones

- Los avisos `PASO_A_CRITICO` y `SE_MARCHITO` salen con `@capacitor/local-notifications`, en un canal propio («Avisos de las materas»). Son inmediatos, nunca programados (`isExactNotification: false`).
- El permiso de Android 13 (`POST_NOTIFICATIONS`) se pide solo cuando la persona toca «Activar notificaciones» en Juego, o «Avisarme con notificaciones» en un aviso. Tocar la notificación lleva a Mis materas.
- **MagicOS (y otros Android) cierran las apps en segundo plano**, así que los avisos llegan mientras la app está abierta. La pantalla Juego explica cómo dejarla sin optimizar.

### Permisos

| Permiso | Para qué |
|---|---|
| `INTERNET` | La API y el WebSocket |
| `BLUETOOTH_SCAN` (con `neverForLocation`) y `BLUETOOTH_CONNECT` | Android 12 o más: buscar la placa y conectarse. Se piden la primera vez que se busca la placa |
| `BLUETOOTH`, `BLUETOOTH_ADMIN`, `ACCESS_FINE_LOCATION` y `ACCESS_COARSE_LOCATION` | Solo Android 11 o menos (`maxSdkVersion` 30), que exige la ubicación para buscar por Bluetooth |
| `POST_NOTIFICATIONS` | Los avisos de las materas |

Los plugins declaran además `SCHEDULE_EXACT_ALARM`, `RECEIVE_BOOT_COMPLETED` y `WAKE_LOCK`, para notificaciones programadas: se quitan en el manifiesto con `tools:node="remove"`, porque aquí no se programa nada.

### Límites conocidos

- La sesión va en `sessionStorage`, como en la web: si Android cierra la app, se vuelve a ingresar.
- Los registros de Capacitor están apagados (`loggingBehavior: "none"`). Así ni la clave de la pantalla de la placa ni la del WiFi salen por la consola ni por `adb logcat`.
- La red de la placa (el otro camino del asistente) también se ofrece en la app, pero el celular que hace de hotspot no puede unirse a ella: ahí se usa Bluetooth.

## Pruebas

Desde la carpeta `backend/`:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest
```

Para correr solo las pruebas del dominio:

```bash
python -m pytest tests/dominio
```

**Dominio y aplicación.**
- No levantan el servidor ni abren la base de datos. Usan dobles en memoria de cada puerto (`tests/dobles.py`, `tests/dobles_usuarios.py` y `tests/dobles_juego.py`), incluidos unos tokens falsos que no son JWT, y siguen pasando aunque se borre la carpeta `infraestructura/`.
- Cubren lecturas en rango, fuera de rango e inválidas, la regla de propiedad, la hora del reporte, el canje y los tokens anulados.
- Del corte 3, el juego (`test_juego.py` y `test_mascota.py`, con un reloj fijo): los puntos y el total negativo, el tamaño con el reloj real y con el acelerado, los umbrales de la condición, el orden del globo, dormida, los dos avisos, la tabla solo con participantes activos, el apodo repetido y `AvisarATodos` con un suscriptor que falla. Y la conexión (`tests/aplicacion/test_plantas_y_sensores.py`): la huella en `RegistrarPlanta` y `ReemplazarSensor`.
- `tests/aplicacion/test_puertos_entrada.py` comprueba que cada puerto de entrada lo implementa el caso de uso de su mismo nombre.
- `tests/dominio/test_arquitectura.py` comprueba las reglas de dependencias de la sección [Arquitectura](#arquitectura-puertos-y-adaptadores).

**Integración.** Usan una base SQLite temporal.

| Prueba | Qué cubre |
|---|---|
| `test_tokens_jwt.py` | El adaptador de JWT con la librería de verdad: la firma, el vencimiento, el algoritmo (rechaza `none`), los reclamos y el alcance. |
| `test_api_dispositivos.py` | Cada respuesta de la ruta de los dispositivos. |
| `test_tabla_referencia.py` | El cambio entre CSV y base de datos. |
| `test_migracion_bd.py` | La migración de una base de antes de la fase 2, y de la versión 3 a la 4 con las tablas del juego y los ritmos. |
| `test_servidor_real.py` | Levanta el servidor con hilos, como `python main.py`, y detecta un error que el cliente de pruebas de Flask no ve: usar una misma conexión de `sqlite3` desde varios hilos. |
| `test_websocket.py` | Ese mismo servidor, con un cliente WebSocket de verdad. |
| `test_simulador.py` | El simulador contra ese servidor, en sus dos modos. |
| `test_arquitectura_adaptadores.py` | Que `jwt` y `csv` solo los importe su adaptador. Va aquí porque mira la carpeta `infraestructura/`. |
| `test_api_juego.py` | Las rutas del juego: los puntos de cada lectura 201 y su `necesidad`, una lectura rechazada que no cuenta, la matera que crece de semilla a brote y se marchita con el reloj acelerado, dormida, el 401 sin JWT, cada cuenta solo con lo suyo, el 403 de la tabla, el 400 y el 409 del apodo, y los puntos ya guardados cuando sale el aviso en vivo. |
| `test_repositorio_juego_sqlite.py` | Los tres adaptadores SQLite del juego, comparados con sus dobles: las horas de juego, las ventanas de la condición, el reloj que no reagrupa el pasado, los puntos de una matera borrada, el apodo único en la base y los ritmos de las cinco especies. |
| `test_api_huella.py` | Crear la matera y cambiarle el sensor con la huella de una clave que creó la placa, y la huella mal formada (400). |
| `test_red_local.py` | `GET /red`, las IPv4 del PC y los orígenes de la red local en CORS. |

El firmware no tiene pruebas automáticas en el PC. Al arrancar revisa sus propios vectores (el código desde la MAC, SHA-256, base64url y el lector de JSON; ver [firmware/README.md](firmware/README.md)), y el resto se prueba en la placa, con el monitor serie.

## API

Desde la fase 2 (R7), estas tres rutas del corte 1 también exigen el JWT de usuario en `Authorization: Bearer <token>`. Sin él responden `401 SESION_INVALIDA`. Las respuestas no cambian.

### `GET /api/v1/especies`

```json
[
  {
    "nombre": "sansevieria",
    "nombreCientifico": "Dracaena trifasciata",
    "rangos": {
      "humedad": { "min": 20.0, "max": 45.0, "unidad": "%" },
      "luz": { "min": 270.0, "max": 2150.0, "unidad": "lux" },
      "temperatura": { "min": 21.0, "max": 32.0, "unidad": "C" }
    }
  }
]
```

### `GET /api/v1/parametros`

Los parámetros que se miden, en orden, con su unidad y sus límites físicos:

```json
[
  { "nombre": "humedad", "unidad": "%", "minimoFisico": 0.0, "maximoFisico": 100.0 },
  { "nombre": "luz", "unidad": "lux", "minimoFisico": 0.0, "maximoFisico": 150000.0 },
  { "nombre": "temperatura", "unidad": "C", "minimoFisico": -50.0, "maximoFisico": 60.0 }
]
```

### `POST /api/v1/diagnosticos`

```json
{ "especie": "sansevieria", "humedad": 18, "luz": 800, "temperatura": 22 }
```

Los valores pueden llegar como números o como texto numérico (`"32.5"` o `"32,5"`).

```json
{
  "especie": "sansevieria",
  "estado": "EN_RIESGO",
  "parametros": [
    { "nombre": "humedad", "valor": 18.0, "unidad": "%", "rangoOptimo": [20.0, 45.0], "estado": "BAJO", "desviacion": 0.08 },
    { "nombre": "luz", "valor": 800.0, "unidad": "lux", "rangoOptimo": [270.0, 2150.0], "estado": "OPTIMO", "desviacion": 0.0 },
    { "nombre": "temperatura", "valor": 22.0, "unidad": "C", "rangoOptimo": [21.0, 32.0], "estado": "OPTIMO", "desviacion": 0.0 }
  ],
  "recomendaciones": [
    "La humedad del sustrato está por debajo del rango recomendado: riegue moderadamente."
  ]
}
```

### Cuentas, plantas y sensores (corte 2)

Todas van bajo `/api/v1`, y hay dos clases de token, los dos JWT firmados por el servidor:
- **El del usuario:** lo entrega `POST /sesiones`, con alcance «usuario». Todas las rutas del front lo piden en la cabecera `Authorization: Bearer <token>`: las del corte 1, las de la sesión, las de las plantas y las de administración. Solo crear cuenta e iniciar sesión no lo piden.
- **El del sensor:** lo entrega `POST /dispositivos/{codigo}/token` a cambio de la clave, con alcance «lecturas». Solo sirve para reportar lecturas de ese sensor.

Un token no sirve en las rutas del otro (`403 ALCANCE_INVALIDO`). El servidor guarda el id de cada token:
- Cerrar sesión o desactivar la cuenta anula el token del usuario. Además, los sensores de una cuenta desactivada quedan en pausa: el canje y las lecturas responden `403 CUENTA_DESACTIVADA` hasta que el admin la reactive.
- Un canje nuevo o un cambio de sensor anula el token del sensor.

En los dos casos el token deja de servir aunque no haya vencido.

| Ruta | Quién | Responde |
|---|---|---|
| `POST /usuarios` | pública | 201 · `{id, nombre, correo, rol}`; el rol siempre es USUARIO |
| `POST /sesiones` | pública | 201 · `{token, venceEn, usuario}`; el token es el JWT de la sesión |
| `DELETE /sesiones/actual` | sesión | 200 · `{mensaje}` |
| `GET /usuarios/yo` | sesión | 200 · `{id, nombre, correo, rol, plantas}` |
| `GET /plantas` | sesión | 200 · lista con `sensor` y `ultimaMedicion` |
| `POST /plantas` | sesión | 201 · `{planta, codigo, clave}`. El cuerpo lleva `{apodo, especie, codigo}`: la matera nace con su sensor, y la clave solo aparece aquí. Con `huella` opcional (SHA-256 de la clave que creó la placa, 64 caracteres hexadecimales en minúscula) no hay `clave` en la respuesta: la API nunca la ve |
| `DELETE /plantas/{id}` | sesión | 200 · borra también su sensor y su historial |
| `PUT /plantas/{id}/sensor` | sesión | 200 · `{planta, codigo, clave}` (sin `clave` si el cuerpo trae `huella`). Cambia el sensor, o da una clave nueva con el mismo código; el historial se conserva, y la clave anterior y su token dejan de servir |
| `GET /red` | sesión | 200 · `{servidores: ["http://<ip>:5000/api/v1", ...]}`: las bases de la API por las que una placa de la red local alcanza este backend (según `MATERA_HOST` y `MATERA_PUERTO`). Primero va la de la ruta por defecto del PC (la red donde está la placa) y después las demás, como las de VirtualBox o la conexión compartida: la placa las prueba en ese orden. Si no hay ninguna (host de loopback), trae un `aviso` |
| `GET /plantas/{id}/historial?limite=30` | sesión | 200 · `{planta, registros}`, el más reciente primero |
| `POST /dispositivos/{codigo}/token` | la clave del sensor, en el cuerpo `{clave}` | 200 · `{token, venceEn}`: el JWT del sensor. Deja sin efecto el token anterior del mismo sensor |
| `POST /dispositivos/{codigo}/lecturas` | token del sensor | 201 · `{planta, momento, diagnostico, necesidad}`. El cuerpo lleva `{dispositivo, momento, lecturas}`; se guarda con la hora del cuerpo y el código como origen, suma o resta puntos y se avisa en vivo. `necesidad` es lo que más le falta a la planta para el globo de la pantalla (`SED`, `EXCESO_AGUA`, `FRIO`, `CALOR`, `POCA_LUZ` o `MUCHA_LUZ`), o `null` |
| `WS /tiempo-real` | token en el primer mensaje | WebSocket: una medición nueva de las plantas del usuario por mensaje (ver abajo) |
| `GET /juego/materas` | sesión | 200 · `{materas: [{plantaId, etapa, condicion, cara, dormida, necesidad, aviso, puntos, horasCuidada, ultimaLectura}]}`: la matera Tamagotchi de cada planta propia. `condicion` y `aviso` se miden en las 6 horas de juego que terminan en la última lectura, así que no cambian mientras no llegan lecturas; `cara`, `dormida` y `ultimaLectura` salen de la última lectura que sumó puntos, con la hora del servidor (no la de la placa). Dormida, `necesidad` y `aviso` son `null` |
| `GET /juego/puntaje` | sesión | 200 · `{puntos, materas: [{planta, puntos}], movimientos: [{momento, planta, estado, puntos}]}`. Los puntos de una matera borrada siguen en el total, y en sus movimientos `planta` es `null` |
| `GET /juego/participacion` | sesión | 200 · `{estado, apodo}`; `estado` es `SIN_DECIDIR`, `PARTICIPA` o `NO_PARTICIPA` |
| `PUT /juego/participacion` | sesión | 200 · `{estado, apodo}`. El cuerpo lleva `{participa: true, apodo}` o `{participa: false}` |
| `GET /juego/tabla` | sesión, y participar | 200 · `{posiciones: [{posicion, apodo, puntos, soyYo}]}`: solo quienes participan con la cuenta activa |
| `GET /admin/usuarios` | admin | 200 · lista de `{id, correo, nombre, rol, activo, cantidadPlantas}` |
| `PATCH /admin/usuarios/{id}` | admin | 200 · el cuerpo lleva `{activo}` o `{rol}` |
| `DELETE /admin/usuarios/{id}` | admin | 200 · borra la cuenta con sus plantas, sensores e historial |
| `POST /admin/especies` | admin | 201 · la especie, con la misma forma que en `GET /especies` |

Las reglas de la lectura de un sensor:
- **El cuerpo:** `{"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:04:05Z", "lecturas": {"humedad": 53, "luz": 1500, "temperatura": 25.5}}`. Las lecturas tienen la forma de `POST /diagnosticos`, sin la especie, que es la de la planta.
- **La hora:** va en ISO 8601 con zona horaria y se guarda en UTC. La API rechaza una hora sin zona o más de 2 minutos por delante de la suya.
- **El sensor:** `dispositivo` tiene que ser el mismo sensor del token y de la URL.

Una planta de otro usuario responde 404, igual que una que no existe. No hay medición a mano: el historial solo guarda lo que mandó un sensor. Las mediciones a mano que se guardaron antes conservan el origen `MANUAL`.

### Tiempo real: `WS /api/v1/tiempo-real`

El navegador no deja poner la cabecera `Authorization` en un WebSocket, y un token en la URL quedaría en registros e historiales. Por eso el token va en el primer mensaje:

```json
{"tipo": "autenticar", "token": "<token de la sesión>"}
```

Después solo habla el servidor. Todos los mensajes son JSON:

| Mensaje | Cuándo |
|---|---|
| `{"tipo": "listo", "usuario": {id, nombre}}` | El token sirvió. |
| `{"tipo": "medicion", "planta", "medicion", "diagnostico"}` | Llegó una medición de una planta del usuario. `medicion` tiene la forma de `ultimaMedicion` en `GET /plantas`, y `diagnostico`, la de `POST /diagnosticos`, con sus recomendaciones. |
| `{"tipo": "error", "error", "mensaje"}` | Puede ser: el primer mensaje no era `autenticar` (`SOLICITUD_INVALIDA`); el token no sirve o no llegó en 5 segundos (`SESION_INVALIDA`); es el token de un sensor (`ALCANCE_INVALIDO`); o la sesión se cerró o venció con la conexión abierta. Después el servidor cierra con el código 1008. |

Cada medición llega solo a las conexiones de su dueño, y cada conexión revisa la sesión antes de cada mensaje: una cuenta borrada o desactivada recibe `SESION_INVALIDA` en vez de la medición. Se avisa después de guardar: si el aviso falla o nadie está conectado, la medición igual queda en el historial. Cada pestaña tiene su propia cola, así que una que deja de leer no traba el POST del sensor; si su cola se llena, se corta esa conexión. Un error inesperado también llega en JSON (`ERROR_INTERNO`, cierre 1011). El servidor revisa el `Origin` antes de aceptar la conexión (CORS no aplica a los WebSocket) y manda un ping cada 25 segundos.

### Errores

Todas las respuestas de error, incluidas las de rutas inexistentes, tienen la forma `{ "error", "mensaje", "detalle" }`. El backend nunca responde HTML.

| Caso | HTTP | `error` | `detalle` |
|---|---|---|---|
| Especie desconocida | 404 | `ESPECIE_NO_SOPORTADA` | `especie` |
| Parámetro ausente | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo: "ausente"` |
| Valor no numérico | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo: "no_numerico"` |
| Valor físicamente imposible | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo: "fuera_de_rango_fisico"`, `minimo`, `maximo` |
| El cuerpo no es JSON estricto: no es JSON, trae `NaN`, `Infinity` o un número que no cabe en un float, un texto con un carácter inválido, o está anidado miles de veces | 400 | `SOLICITUD_INVALIDA` | vacío |
| Ruta inexistente / método no permitido | 404 / 405 | `RUTA_NO_ENCONTRADA` / `METODO_NO_PERMITIDO` | `ruta` |
| Error inesperado | 500 | `ERROR_INTERNO` | vacío |
| Correo, nombre, contraseña, apodo, rango o huella inválidos (la huella: 64 caracteres hexadecimales en minúscula) | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo` |
| Código de sensor con otra forma (no `MT-0000-XX`) al crear la matera o al cambiarle el sensor | 400 | `CODIGO_SENSOR_INVALIDO` | `campo`, `motivo`, `texto` |
| La hora de una lectura que no es ISO 8601 o que no se puede pasar a UTC (por ejemplo, el año 1 con zona) | 400 | `PARAMETRO_INVALIDO` | `campo: "momento"`, `motivo: "formato"` |
| La hora de una lectura sin zona horaria o más de 2 minutos en el futuro | 400 | `MOMENTO_INVALIDO` | `campo: "momento"`, `motivo: "invalido"` |
| Correo o contraseña incorrectos (el mismo en los dos casos) | 401 | `CREDENCIALES_INVALIDAS` | vacío |
| Sin token de usuario, con la firma alterada, vencido, con la sesión cerrada o de una cuenta desactivada | 401 | `SESION_INVALIDA` | vacío |
| Sensor inexistente, código mal formado o clave incorrecta en el canje (el mismo en los tres casos) | 401 | `CLAVE_SENSOR_INVALIDA` | vacío |
| Sin token del sensor, con la firma alterada, vencido o anulado por otro canje o por un cambio de sensor: la placa vuelve a canjear | 401 | `CREDENCIAL_DISPOSITIVO_INVALIDA` | vacío |
| Cuenta desactivada al iniciar sesión, o el sensor de una matera suya canjea o reporta | 403 | `CUENTA_DESACTIVADA` | vacío |
| Acción de administración sin ser admin | 403 | `PERMISO_DENEGADO` | vacío |
| La tabla de posiciones, sin participar en ella | 403 | `PARTICIPACION_REQUERIDA` | vacío |
| Un apodo de jugador que no tiene de 3 a 20 caracteres (letras sin tildes, números, `_` o `-`) | 400 | `APODO_JUGADOR_INVALIDO` | `campo`, `motivo`, `minimo`, `maximo` |
| Un apodo de jugador que ya usa otra persona, sin importar mayúsculas | 409 | `APODO_JUGADOR_REPETIDO` | `campo`, `apodo` |
| Un token válido de otro alcance: el de un sensor en una ruta de usuario o al revés | 403 | `ALCANCE_INVALIDO` | `esperado` |
| Un sensor que reporta por otro (en la URL o en el cuerpo) | 403 | `DISPOSITIVO_AJENO` | `autenticado`, `reportado` |
| Abrir el WebSocket desde un origen que no es el del front | 403 | `ORIGEN_NO_PERMITIDO` | `origen` |
| Un `GET` normal (sin WebSocket) a `/tiempo-real` | 400 | `SOLICITUD_INVALIDA` | `ruta` |
| Planta inexistente o de otro usuario, también si se borró mientras llegaba una lectura de su sensor | 404 | `PLANTA_NO_ENCONTRADA` | `planta_id` |
| Usuario inexistente | 404 | `USUARIO_NO_ENCONTRADO` | `referencia` |
| Correo, apodo, especie o código de sensor repetidos (el código, si es de otra planta) | 409 | `CORREO_YA_REGISTRADO`, `APODO_REPETIDO`, `ESPECIE_YA_EXISTE`, `SENSOR_YA_VINCULADO` | el dato repetido |
| Agregar una especie con la tabla de referencia en CSV | 409 | `TABLA_SOLO_LECTURA` | vacío |
| Un admin actúa sobre su propia cuenta | 409 | `ACCION_SOBRE_SI_MISMO` | vacío |

Límites físicos: humedad de 0 a 100 %, luz de 0 a 150 000 lux y temperatura de −50 a 60 °C.

## Estado global

Cada parámetro se clasifica como `BAJO`, `OPTIMO` o `ALTO` contra su rango óptimo; los límites cuentan como `OPTIMO`. También se calcula cuánto se desvió: la distancia al límite más cercano dividida por el ancho del rango. Así lux, grados y porcentaje se comparan con un mismo umbral.

| Condición | Estado |
|---|---|
| Todos los parámetros en `OPTIMO` | `SALUDABLE` |
| Uno solo fuera, con desviación ≤ 0,5 | `EN_RIESGO` |
| Dos o más fuera, o alguno con desviación > 0,5 | `CRITICO` |

La regla está en `dominio/reglas.py` (`ReglaHibrida`) y se elige en `main.py`.

## Tabla de referencia y fuentes

`backend/datos/carga.sql` llena las tablas `especie` (nombre y nombre científico) y `rango_optimo` (una fila por especie y parámetro, con su mínimo y su máximo). Son las mismas especies y rangos que tenía el CSV del corte 1, que volvió en la fase 2 como copia de solo lectura (`backend/datos/especies.csv`, exportado de una base nueva). Un administrador puede agregar otras desde la API; `carga.sql` solo se ejecuta si la tabla de especies está vacía.

| Especie | Nombre científico de referencia | Humedad % | Luz lux | Temperatura °C |
|---|---|---|---|---|
| sansevieria | *Dracaena trifasciata* (antes *Sansevieria trifasciata*) | 20–45 | 270–2150 | 21–32 |
| potos | *Epipremnum aureum* | 40–70 | 270–2150 | 16–29 |
| suculenta | *Crassula ovata* (planta de jade) | 10–30 | 10 760–107 640 | 10–24 |
| helecho | *Nephrolepis exaltata* (helecho de Boston) | 60–85 | 1080–5380 | 10–22 |
| lavanda | *Lavandula angustifolia* | 25–50 | 10 760–107 640 | 13–27 |

**Luz.** Se toma la categoría de cada planta en la tabla de la Extensión de la Universidad de Arkansas [1]: baja para sansevieria y potos, media para el helecho y muy alta para la planta de jade. La lavanda no está en esa tabla; la guía de Utah State [7] la pide a pleno sol y se ubicó en la categoría muy alta. El mínimo es el mínimo de la categoría y el máximo es el límite superior de su nivel preferido:

- baja: de 25 a 200 fc;
- media: de 100 a 500 fc;
- muy alta: de 1000 fc al pico de sol directo, unos 10 000 fc [2].

Los valores se convirtieron a lux (1 fc = 10,764 lux) y se redondearon a la decena.

**Temperatura.** Sale de la ficha de cada especie y se convirtió de °F a °C:

- sansevieria: de 70 a 90 °F [3];
- potos: de 60 a 70 °F de noche y de 70 a 85 °F de día [4];
- helecho de Boston: de 50 a 55 °F de noche y de 68 a 72 °F de día [5];
- planta de jade: de 50 a 55 °F en las noches de invierno y de 65 a 75 °F de día [6];
- lavanda: de 13 a 18 °C de noche y de 18 a 27 °C de día [8].

**Humedad del sustrato.** Ninguna de las fuentes da la humedad del sustrato como porcentaje. Por eso los rangos se tomaron del Anexo B del enunciado y se comprobó que el orden entre especies coincide con lo que dicen las fuentes:

- la planta de jade es la más seca: en invierno se deja secar entre riegos [6];
- la sansevieria se riega solo cuando el sustrato se secó por completo [3];
- la lavanda tolera muy bien la sequía y no tolera el suelo encharcado [7];
- el helecho es el más húmedo: se mantiene apenas húmedo todo el tiempo [5].

La excepción es el potos: Clemson recomienda dejar secar el sustrato entre riegos [4], así que un mínimo de 40 % puede ser alto.

1. University of Arkansas Division of Agriculture, Cooperative Extension Service. *Light and Moisture Requirements For Selected Indoor Plants*. https://www.uaex.uada.edu/yard-garden/home-landscape/docs/Light%20and%20Moisture%20Requirements.pdf
2. University of Maryland Extension. *Lighting for Indoor Plants*. https://extension.umd.edu/resource/lighting-indoor-plants
3. Steil, A. J. (17 de enero de 2025). *Yard and Garden: Caring for Sansevieria*. Iowa State University Extension and Outreach. https://www.extension.iastate.edu/news/yard-and-garden-caring-sansevieria
4. Taylor, A. y Tanner, C. (30 de enero de 2026). *How to Grow Pothos Indoors (Epipremnum spp.): Care, Cultivars, and Common Problems*. Clemson Cooperative Extension, Home & Garden Information Center. https://hgic.clemson.edu/factsheet/how-to-grow-pothos-indoors-epipremnum-spp-care-cultivars-and-common-problems/
5. Russ, K. y Pertuit, A.; revisado por Smith, B. H. (2015). *Indoor Ferns*. Clemson Cooperative Extension, Home & Garden Information Center. https://hgic.clemson.edu/factsheet/indoor-ferns/
6. Russ, K. y Pertuit, A.; revisado por Smith, B. H. (2015). *Jade Plant* (HGIC 1507). Clemson Cooperative Extension, Home & Garden Information Center. https://hgic.clemson.edu/factsheet/jade-plant/
7. Crummitt, K. y Drost, D. (2020). *How to Grow English Lavender in Your Garden*. Utah State University Extension. https://extension.usu.edu/yardandgarden/research/english-lavender-in-the-garden
8. Greenhouse Grower (5 de septiembre de 2012). *Tips For Producing Lavandula*. https://www.greenhousegrower.com/crops/tips-for-producing-lavandula/
