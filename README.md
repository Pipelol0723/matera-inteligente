# Matera inteligente

Matera inteligente es una API que diagnostica el estado de una planta a partir de su especie y de una medición de humedad del sustrato, luz y temperatura, con un front web estático que la consume.

- **Corte 2:** cada persona tiene su cuenta (con JWT) y sus materas, y un administrador gestiona las cuentas y agrega especies.
- **Sensor:** cada matera nace con su sensor, que puede ser un ESP32 o el simulador. El sensor canjea su clave por un token propio y reporta lecturas con la hora en que las tomó.
- **Historial:** solo el sensor escribe en él.
- **Pantalla del dueño:** se actualiza sola. Consulta la API cada 10 segundos y, además, recibe cada lectura al instante por WebSocket.

Proyecto de Arquitectura de Software, semestre 2026-03. El corte 1, tal como se entregó, está en el tag `corte-1`. La fase 2 organiza el backend en puertos y adaptadores (arquitectura hexagonal): ver [Arquitectura](#arquitectura-puertos-y-adaptadores).

## Estructura

```
backend/
  main.py            raíz de composición: el único archivo que elige clases concretas
  crear_admin.py     da el rol de administrador a una cuenta, desde la consola
  exportar_especies_csv.py  escribe la copia en CSV de la tabla de especies, desde la base
  datos/             esquema.sql y carga.sql de la base SQLite, y especies.csv (la copia de solo lectura)
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
  js/api.js          peticiones a la API, con el token en las rutas privadas
  js/app.js          arranque, navegación y pantallas que exigen sesión
  js/sesion.js       token de la sesión, en sessionStorage
  js/consulta-periodica.js  vuelve a pedir los datos de la pantalla cada 10 s
  js/tiempo-real.js  el WebSocket que trae las mediciones en vivo, con su reconexión
  js/diagnostico.js  pantalla de diagnóstico
  js/especies.js     catálogo de especies
  js/acceso.js       ingresar y crear cuenta
  js/cuenta.js       mi cuenta y cerrar sesión
  js/materas.js      mis materas: crearlas con su sensor y cambiarles el sensor
  js/historial.js    historial de una planta
  js/admin.js        administración de cuentas y especies
  js/formularios.js  errores de la API en los formularios
  js/lecturas.js     texto de unas lecturas y de su origen
  js/escala.js       geometría de escalas y anillos
  js/formato.js      textos, colores y ayudas para crear nodos
firmware/
  matera-sensor/     el programa de la ESP32, para el Arduino IDE 2 (ver firmware/README.md)
docs/
  diagramas/         la vista hexagonal, casos de uso, paquetes, clases, entidad-relación y secuencias
                     (fuente .mmd, SVG y PNG)
  entrega/           documentos de arquitectura y bitácoras de uso de IA, en PDF
                     (los vigentes: documento-arquitectura-fase2.pdf y bitacora-ia-fase2.pdf;
                     documento-arquitectura.pdf es el anterior a la fase 2)
```

## Arquitectura: puertos y adaptadores

Las carpetas son las del corte 1, y cada una tiene su lugar en la vista hexagonal:

| Carpeta | En la vista hexagonal |
|---|---|
| `dominio/` y `aplicacion/` | El núcleo: reglas de negocio y casos de uso. No conocen Flask, SQLite, el CSV, JWT, JSON ni HTTP. |
| `dominio/puertos_entrada.py` | Los puertos de entrada: una clase abstracta por caso de uso, con el mismo nombre que el caso de uso de `aplicacion/` que la implementa. Lo que entra y sale de ellos está en `dominio/resultados.py`. |
| `dominio/puertos.py` y `dominio/puertos_usuarios.py` | Los puertos de salida: lo que el núcleo necesita de afuera, cada uno con pocos métodos. |
| `presentacion/` | Los adaptadores de entrada: las rutas del front, las de los dispositivos y el WebSocket. Dependen de los puertos de entrada, nunca de los casos de uso. |
| `infraestructura/` | Los adaptadores de salida: implementan los puertos de salida con SQLite, el CSV, PyJWT, PBKDF2, el reloj y el WebSocket. |
| `main.py` | El único punto de composición: elige qué adaptador se conecta a cada puerto. `crear_admin.py` y `exportar_especies_csv.py` le piden sus piezas (`construir_consola`). |

Las dependencias apuntan hacia el núcleo. `tests/dominio/test_arquitectura.py` lo comprueba en cada corrida:
- El dominio y la aplicación no importan ni el framework, ni la persistencia, ni la criptografía, ni las otras capas.
- `presentacion/` no importa `aplicacion/` ni `infraestructura/`.
- Solo `infraestructura/tokens_jwt.py` importa `jwt`, y solo `infraestructura/repositorio_especies_csv.py` importa `csv`.

El diagrama está en [docs/diagramas](docs/diagramas/README.md#vista-hexagonal) (`hexagonal.mmd`).

**La prueba de cambio.** El adaptador de dispositivos y el simulador entraron en el commit `d41ca34` sin tocar ningún archivo del núcleo. Lo muestra este comando, que no lista ningún archivo:

```bash
git show --stat d41ca34 -- backend/dominio backend/aplicacion
```

El núcleo ya tenía, desde el commit `13a3c1b`, los puertos de entrada `RegistrarLectura` y `CanjearClaveDispositivo`, probados con dobles. Lo mismo pasó con la tabla en CSV (commit `9c7ce5e`), que es otro adaptador de los puertos del corte 1.

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
| `MATERA_RUTA_BD` | `backend/datos/matera.sqlite` |
| `MATERA_ORIGENES_CORS` | `http://localhost:5500,http://127.0.0.1:5500` |
| `MATERA_DIAS_SESION` | `7`: cuánto dura el token de una sesión |
| `MATERA_HORAS_TOKEN_DISPOSITIVO` | `24`: cuánto dura el token de un sensor; después, el sensor vuelve a canjear su clave |
| `MATERA_JWT_SECRETO` | Sin valor: el secreto con que se firman los JWT se genera la primera vez y se guarda junto a la base (`matera.sqlite.secreto-jwt`, que Git ignora). Así un reinicio no cierra las sesiones. Si se pierde, todos vuelven a ingresar. |
| `MATERA_TABLA_REFERENCIA` | `bd`: la tabla de especies sale de la base. Con `csv`, sale de la copia en CSV (ver [Tabla de referencia](#tabla-de-referencia-csv-o-base-de-datos)) |
| `MATERA_RUTA_CSV` | `especies.csv`, en la carpeta de la base. Con la base por defecto es `backend/datos/especies.csv`; con una base fuera de Google Drive, la copia queda afuera con ella |

Al arrancar, el backend escribe en la consola qué tabla de referencia usa, crea las tablas que falten y, si no hay ninguna especie, carga las de `datos/carga.sql`. Git ignora el archivo de la base.

Una base de antes de la fase 2 se migra sola la primera vez. Antes de migrarla, el backend saca una copia al lado (`matera.respaldo-v0.sqlite`). Usuarios, plantas, sensores, especies e historial no cambian, pero las sesiones abiertas se cierran, porque los tokens de antes no eran JWT: cada usuario vuelve a ingresar. La clave de cada sensor sigue sirviendo.

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

Al arrancar, Flask muestra una línea `Running on http://192.168.x.x:5000` con la dirección del PC en la red. Si el PC tiene una VPN o varias redes, puede mostrar otra; en ese caso la que va en el ESP32 es la «Dirección IPv4» del adaptador WiFi que muestra `ipconfig`.

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

El ESP32 le habla a la API en dos pasos, con el código de su matera y la clave que entregó Mis materas al crearla. Primero canjea la clave por su token, de alcance «lecturas», que vence a las 24 horas:

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

Conviene darle su propia matera en Mis materas, distinta de la de la placa, porque cada canje deja sin efecto el token anterior del mismo sensor. Créela con la especie **potos**: los valores «normales» del simulador están dentro de sus rangos, así salen saludables, y las lecturas fuera de rango se distinguen. Con otra especie, por ejemplo la sansevieria, las normales también pueden salir en riesgo. Desde la raíz del repositorio, con el backend corriendo:

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

El enunciado pide cuatro cosas. Las tres primeras se hacen así, desde la raíz del repositorio y con el backend corriendo:

1. **El simulador enviando lecturas en vivo.** Con Mis materas abierta en el navegador, cada lectura aparece al instante (ver [Simulador del ESP32](#simulador-del-esp32)). Con `--fuera-de-rango` y `--invalidas` se ven también los rechazos.
2. **El cambio de CSV a BD por configuración.** `exportar_especies_csv.py`, `MATERA_TABLA_REFERENCIA=csv` y reiniciar el backend (ver [Tabla de referencia](#tabla-de-referencia-csv-o-base-de-datos)). El simulador sigue solo cuando el backend vuelve. Agregar una especie en Administración responde `409 TABLA_SOLO_LECTURA`.
3. **Un acceso a una planta ajena, que falla.** Otra cuenta pide el historial de una matera que no es suya. En PowerShell, con `curl.exe` (viene con Windows):

   ```powershell
   $api = "http://127.0.0.1:5000/api/v1"
   $cuenta = @{ nombre = "Beto"; correo = "beto@correo.co"; contrasena = "clave-de-beto" } | ConvertTo-Json
   Invoke-RestMethod -Method Post "$api/usuarios" -ContentType "application/json" -Body $cuenta
   $beto = (Invoke-RestMethod -Method Post "$api/sesiones" -ContentType "application/json" -Body $cuenta).token
   curl.exe -s -w " (estado %{http_code})" "$api/plantas/1/historial" -H "Authorization: Bearer $beto"
   ```

   El id 1 es la primera matera de la base, que no es de Beto. La respuesta es `{"error": "PLANTA_NO_ENCONTRADA", ...}` con estado 404, la misma que con un id que no existe (`/plantas/999/historial`): no revela que esa matera exista. Lo decide `Planta.exigir_dueno`, en el dominio.

La cuarta es la pregunta de cambio (MQTT u OAuth), y va en el documento de arquitectura.

## Ejecutar el front

En otra terminal, desde la raíz del repositorio:

```bash
python -m http.server 5500 --directory frontend
```

Abra `http://localhost:5500`. El front se tiene que servir por HTTP; abrir `index.html` con doble clic no funciona porque usa módulos de JavaScript. Si cambia el puerto del backend, ajuste `frontend/js/config.js`.

El front no tiene rangos, umbrales ni reglas. Los parámetros, las especies, los estados y las recomendaciones salen de la API.

| Pantalla | Acceso | Qué hace |
|---|---|---|
| Diagnóstico | con sesión | Consulta `POST /diagnosticos` mientras se escribe (espera 400 ms después de la última tecla) y muestra el estado en los anillos. Los botones Saludable, En riesgo y Crítico llenan valores de ejemplo a partir de los rangos, y la API decide el estado. El panel "Errores de la API" envía peticiones inválidas a propósito. No guarda nada. |
| Especies | con sesión | Muestra el catálogo de `GET /especies` con bandas escaladas según los límites físicos de `GET /parametros`. |
| Ingresar / Crear cuenta | pública | Dos formularios. Al entrar guarda el token y vuelve a la pantalla privada que se había pedido. |
| Mis materas | con sesión | Las materas del usuario con su última medición, que se actualiza sola (ver abajo). «Agregar matera» pide apodo, especie y código del sensor, y muestra la clave del sensor una sola vez: va en `config.h` de la placa o en `--clave=` del simulador. Cada tarjeta permite cambiar el sensor (con el mismo código, da una clave nueva y la anterior deja de servir con su token), ver el historial y eliminar la matera. Desde el front no se escriben mediciones. |
| Historial | con sesión | La lista, la gráfica y el resumen de las mediciones de una planta, con el estado que calculó la API en su momento. Se actualiza solo, igual que Mis materas. |
| Mi cuenta | con sesión | Nombre, correo, rol, cantidad de plantas y cerrar sesión. |
| Administración | solo admin | Activar, desactivar, dar o quitar el rol y eliminar cuentas; agregar especies. La pestaña solo aparece para un admin, pero los permisos los revisa la API. |

Todas las pantallas menos Ingresar exigen sesión (R7): sin ella, el front lleva a Ingresar y no llama a la API. Si la API responde `401 SESION_INVALIDA`, el front borra el token y lleva a Ingresar.

Mis materas y el Historial se actualizan solos de dos maneras:
- **Consulta periódica.** Mientras la pantalla y la pestaña están a la vista, `js/consulta-periodica.js` vuelve a pedir `GET /plantas` (o el historial) cada 10 segundos. Solo se vuelven a pintar las tarjetas que cambiaron. Debajo del título se ve la hora de la última consulta.
- **En vivo.** Mientras hay una sesión, `js/tiempo-real.js` mantiene abierto el WebSocket `/api/v1/tiempo-real`, y la barra muestra «En vivo». Cada lectura aparece al instante, sin esperar la próxima consulta. Si la conexión se cae, reintenta con esperas de 1 a 30 segundos, y mientras tanto la consulta periódica mantiene la pantalla al día.
- **Las dos a la vez.** Si una respuesta de la consulta llega después de una medición en vivo más reciente, la pantalla no retrocede, y el Historial no repite una medición que ya tenía. Una petición que no termina en 15 segundos se da por perdida, así una conexión colgada no detiene la consulta periódica.

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
- No levantan el servidor ni abren la base de datos. Usan dobles en memoria de cada puerto (`tests/dobles.py` y `tests/dobles_usuarios.py`), incluidos unos tokens falsos que no son JWT, y siguen pasando aunque se borre la carpeta `infraestructura/`.
- Cubren lecturas en rango, fuera de rango e inválidas, la regla de propiedad, la hora del reporte, el canje y los tokens anulados.
- `tests/aplicacion/test_puertos_entrada.py` comprueba que cada puerto de entrada lo implementa el caso de uso de su mismo nombre.
- `tests/dominio/test_arquitectura.py` comprueba las reglas de dependencias de la sección [Arquitectura](#arquitectura-puertos-y-adaptadores).

**Integración.** Usan una base SQLite temporal.

| Prueba | Qué cubre |
|---|---|
| `test_tokens_jwt.py` | El adaptador de JWT con la librería de verdad: la firma, el vencimiento, el algoritmo (rechaza `none`), los reclamos y el alcance. |
| `test_api_dispositivos.py` | Cada respuesta de la ruta de los dispositivos. |
| `test_tabla_referencia.py` | El cambio entre CSV y base de datos. |
| `test_migracion_bd.py` | La migración de una base de antes de la fase 2. |
| `test_servidor_real.py` | Levanta el servidor con hilos, como `python main.py`, y detecta un error que el cliente de pruebas de Flask no ve: usar una misma conexión de `sqlite3` desde varios hilos. |
| `test_websocket.py` | Ese mismo servidor, con un cliente WebSocket de verdad. |
| `test_simulador.py` | El simulador contra ese servidor, en sus dos modos. |
| `test_arquitectura_adaptadores.py` | Que `jwt` y `csv` solo los importe su adaptador. Va aquí porque mira la carpeta `infraestructura/`. |

El firmware no tiene pruebas automáticas: se prueba en la placa, con el monitor serie.

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
| `POST /plantas` | sesión | 201 · `{planta, codigo, clave}`. El cuerpo lleva `{apodo, especie, codigo}`: la matera nace con su sensor, y la clave solo aparece aquí |
| `DELETE /plantas/{id}` | sesión | 200 · borra también su sensor y su historial |
| `PUT /plantas/{id}/sensor` | sesión | 200 · `{planta, codigo, clave}`. Cambia el sensor, o da una clave nueva con el mismo código; el historial se conserva, y la clave anterior y su token dejan de servir |
| `GET /plantas/{id}/historial?limite=30` | sesión | 200 · `{planta, registros}`, el más reciente primero |
| `POST /dispositivos/{codigo}/token` | la clave del sensor, en el cuerpo `{clave}` | 200 · `{token, venceEn}`: el JWT del sensor. Deja sin efecto el token anterior del mismo sensor |
| `POST /dispositivos/{codigo}/lecturas` | token del sensor | 201 · `{planta, momento, diagnostico}`. El cuerpo lleva `{dispositivo, momento, lecturas}`; se guarda con la hora del cuerpo y el código como origen, y se avisa en vivo |
| `WS /tiempo-real` | token en el primer mensaje | WebSocket: una medición nueva de las plantas del usuario por mensaje (ver abajo) |
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
| Correo, nombre, contraseña, apodo o rango inválidos | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo` |
| Código de sensor con otra forma (no `MT-0000-XX`) al crear la matera o al cambiarle el sensor | 400 | `CODIGO_SENSOR_INVALIDO` | `campo`, `motivo`, `texto` |
| La hora de una lectura que no es ISO 8601 o que no se puede pasar a UTC (por ejemplo, el año 1 con zona) | 400 | `PARAMETRO_INVALIDO` | `campo: "momento"`, `motivo: "formato"` |
| La hora de una lectura sin zona horaria o más de 2 minutos en el futuro | 400 | `MOMENTO_INVALIDO` | `campo: "momento"`, `motivo: "invalido"` |
| Correo o contraseña incorrectos (el mismo en los dos casos) | 401 | `CREDENCIALES_INVALIDAS` | vacío |
| Sin token de usuario, con la firma alterada, vencido, con la sesión cerrada o de una cuenta desactivada | 401 | `SESION_INVALIDA` | vacío |
| Sensor inexistente, código mal formado o clave incorrecta en el canje (el mismo en los tres casos) | 401 | `CLAVE_SENSOR_INVALIDA` | vacío |
| Sin token del sensor, con la firma alterada, vencido o anulado por otro canje o por un cambio de sensor: la placa vuelve a canjear | 401 | `CREDENCIAL_DISPOSITIVO_INVALIDA` | vacío |
| Cuenta desactivada al iniciar sesión, o el sensor de una matera suya canjea o reporta | 403 | `CUENTA_DESACTIVADA` | vacío |
| Acción de administración sin ser admin | 403 | `PERMISO_DENEGADO` | vacío |
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
