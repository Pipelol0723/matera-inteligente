# Matera inteligente

Matera inteligente: una API que diagnostica el estado de una planta a partir de su especie y de una medición de humedad del sustrato, luz y temperatura, y un front web estático que la consume. Desde el corte 2, cada persona tiene su cuenta y sus materas, y un administrador gestiona las cuentas y agrega especies. Cada matera nace con su sensor (un ESP32), y solo el sensor escribe en el historial: cuando envía una medición, la pantalla del dueño se actualiza sola por WebSocket.

Proyecto de Arquitectura de Software, semestre 2026-03. El corte 1, tal como se entregó, está en el tag `corte-1`.

## Estructura

```
backend/
  main.py            raíz de composición: el único archivo que elige clases concretas
  crear_admin.py     da el rol de administrador a una cuenta, desde la consola
  datos/             esquema.sql y carga.sql de la base SQLite
  dominio/           entidades y reglas de negocio; no importa flask, sqlite3, hashlib ni http
  aplicacion/        casos de uso
  presentacion/      rutas REST, el WebSocket, autenticación y conversión entre JSON y objetos del dominio
  infraestructura/   SQLite, contraseñas y secretos, reloj, configuración, Flask, CORS y el aviso en vivo
  herramientas/      enviar_medicion.py: manda mediciones como el ESP32 (solo para desarrollo)
  tests/
    dominio/         reglas de negocio con dobles de prueba, sin servidor ni base de datos
    aplicacion/      casos de uso con dobles de prueba
    integracion/     API, repositorios SQLite, seguridad, el servidor real y el WebSocket
frontend/            HTML, CSS y JavaScript estáticos, servidos aparte
  js/api.js          peticiones a la API, con el token en las rutas privadas
  js/app.js          arranque, navegación, pantallas públicas y privadas
  js/sesion.js       token de la sesión, en sessionStorage
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
  diagramas/         casos de uso, paquetes, clases, entidad-relación y secuencias,
                     del corte 1 y del diseño del corte 2 (fuente .mmd, SVG y PNG)
  entrega/           documento de arquitectura y bitácora de uso de IA (PDF)
```

Las dependencias apuntan hacia el dominio: `presentacion → aplicacion → dominio ← infraestructura`. Los puertos están declarados en `dominio/puertos.py` (corte 1) y `dominio/puertos_usuarios.py` (corte 2), y los implementan las clases de `infraestructura/sqlite/`, `infraestructura/seguridad.py`, `infraestructura/reloj.py` e `infraestructura/tiempo_real.py`. Este último implementa `NotificadorDiagnosticos`, el puerto con el que el caso de uso avisa cada medición sin saber que existe un WebSocket.

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
| `MATERA_DIAS_SESION` | `7` |

Al arrancar, el backend crea las tablas que falten y, si no hay ninguna especie, carga las de `datos/carga.sql`. Git ignora el archivo de la base.

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

El ESP32 manda la medición así, con el código de su matera y la clave que entregó Mis materas al crearla:

```http
POST http://192.168.x.x:5000/api/v1/sensores/MT-0001-AA/mediciones
Content-Type: application/json
X-Clave-Sensor: <la clave del sensor>

{"humedad": 34.5, "luz": 820, "temperatura": 22.1}
```

Sin la cabecera `Content-Type: application/json`, la API no lee el cuerpo y responde `400 SOLICITUD_INVALIDA`. Al ESP32 no le aplica CORS, porque no es un navegador. El programa de la placa, las conexiones de los sensores y la calibración están en [firmware/README.md](firmware/README.md).

Con `0.0.0.0`, cualquiera en esa red puede llamar la API, y el token y la clave del sensor viajan sin cifrar, porque es HTTP. Además el servidor de Flask es de desarrollo. Sirve para la demo en una red de confianza; al terminar, cierre la terminal (la variable se borra con ella) y el puerto del firewall.

### Probar el tiempo real sin la placa

`herramientas/enviar_medicion.py` manda la misma petición que el ESP32, desde el PC. No es parte de la app: sirve para ver Mis materas en vivo mientras no están los sensores. Desde `backend/`, con el backend corriendo:

```powershell
python herramientas/enviar_medicion.py MT-0001-AA --humedad 30 --luz 900 --temperatura 21
python herramientas/enviar_medicion.py MT-0001-AA --cada 15
```

La herramienta pide la clave del sensor en la consola sin mostrarla, así que no queda en el historial de la terminal. Con `--cada`, manda una medición cada tantos segundos, con valores que varían un poco alrededor de los pedidos y sin pasar los límites físicos, hasta que se detiene con Ctrl+C. Para un script, la clave puede ir en la variable `MATERA_CLAVE_SENSOR` o como `--clave=<clave>`, con el signo igual porque una clave puede empezar con guion; escritas en la consola, las dos quedan en el historial.

## Ejecutar el front

En otra terminal, desde la raíz del repositorio:

```bash
python -m http.server 5500 --directory frontend
```

Abra `http://localhost:5500`. El front se tiene que servir por HTTP; abrir `index.html` con doble clic no funciona porque usa módulos de JavaScript. Si cambia el puerto del backend, ajuste `frontend/js/config.js`.

El front no tiene rangos, umbrales ni reglas. Los parámetros, las especies, los estados y las recomendaciones salen de la API.

| Pantalla | Acceso | Qué hace |
|---|---|---|
| Diagnóstico | pública | Consulta `POST /diagnosticos` mientras se escribe (espera 400 ms después de la última tecla) y muestra el estado en los anillos. Los botones Saludable, En riesgo y Crítico llenan valores de ejemplo a partir de los rangos, y la API decide el estado. El panel "Errores de la API" envía peticiones inválidas a propósito. No guarda nada. |
| Especies | pública | Muestra el catálogo de `GET /especies` con bandas escaladas según los límites físicos de `GET /parametros`. |
| Ingresar / Crear cuenta | pública | Dos formularios. Al entrar guarda el token y vuelve a la pantalla privada que se había pedido. |
| Mis materas | con sesión | Las materas del usuario con su última medición, que se actualiza sola cuando llega una nueva. «Agregar matera» pide apodo, especie y código del sensor, y muestra la clave del sensor una sola vez. Cada tarjeta permite cambiar el sensor (con el mismo código, da una clave nueva), ver el historial y eliminar la matera. Desde el front no se escriben mediciones. |
| Historial | con sesión | La lista, la gráfica y el resumen de las mediciones de una planta, con el estado que calculó la API en su momento. Una medición que llega en vivo se agrega arriba. |
| Mi cuenta | con sesión | Nombre, correo, rol, cantidad de plantas y cerrar sesión. |
| Administración | solo admin | Activar, desactivar, dar o quitar el rol y eliminar cuentas; agregar especies. La pestaña solo aparece para un admin, pero los permisos los revisa la API. |

Si la API responde `401 SESION_INVALIDA`, el front borra el token y lleva a Ingresar.

Mientras hay una sesión, `js/tiempo-real.js` mantiene abierto el WebSocket `/api/v1/tiempo-real`, y la barra muestra «En vivo». Si la conexión se cae, reintenta con esperas de 1 a 30 segundos; al volver, Mis materas y el Historial piden otra vez sus datos para no perder lo que llegó mientras tanto.

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

Las pruebas de dominio y de aplicación no levantan el servidor ni abren la base de datos: usan dobles en memoria de cada puerto (`tests/dobles.py` y `tests/dobles_usuarios.py`), y siguen pasando aunque se borre la carpeta `infraestructura/`. `tests/dominio/test_arquitectura.py` falla si algún archivo del dominio importa Flask, `sqlite3`, `hashlib`, `secrets`, HTTP u otra capa, o si la aplicación importa Flask, la base de datos o la criptografía.

Las de integración usan una base SQLite temporal. `test_servidor_real.py` levanta el servidor con hilos, como `python main.py`: es la prueba que detecta un error que el cliente de pruebas de Flask no ve, usar una misma conexión de `sqlite3` desde varios hilos. `test_websocket.py` usa ese mismo servidor y un cliente WebSocket de verdad, porque el cliente de pruebas de Flask no sabe abrir un WebSocket. `test_herramienta_enviar_medicion.py` prueba la herramienta de desarrollo contra el servidor.

El firmware no tiene pruebas automáticas: se prueba en la placa, con el monitor serie.

## API

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

Todas van bajo `/api/v1`. Las de sesión llevan la cabecera `Authorization: Bearer <token>`; la del sensor, `X-Clave-Sensor: <clave>`.

| Ruta | Quién | Responde |
|---|---|---|
| `POST /usuarios` | pública | 201 · `{id, nombre, correo, rol}`; el rol siempre es USUARIO |
| `POST /sesiones` | pública | 201 · `{token, venceEn, usuario}` |
| `DELETE /sesiones/actual` | sesión | 200 · `{mensaje}` |
| `GET /usuarios/yo` | sesión | 200 · `{id, nombre, correo, rol, plantas}` |
| `GET /plantas` | sesión | 200 · lista con `sensor` y `ultimaMedicion` |
| `POST /plantas` | sesión | 201 · `{planta, codigo, clave}`. El cuerpo lleva `{apodo, especie, codigo}`: la matera nace con su sensor, y la clave solo aparece aquí |
| `DELETE /plantas/{id}` | sesión | 200 · borra también su sensor y su historial |
| `PUT /plantas/{id}/sensor` | sesión | 200 · `{planta, codigo, clave}`. Cambia el sensor, o da una clave nueva con el mismo código; el historial se conserva y la clave anterior deja de servir |
| `GET /plantas/{id}/historial?limite=30` | sesión | 200 · `{planta, registros}`, el más reciente primero |
| `POST /sensores/{codigo}/mediciones` | clave del sensor | 201 · `{planta, momento, diagnostico}`; se guarda con el código como origen y se avisa en vivo |
| `WS /tiempo-real` | token en el primer mensaje | WebSocket: una medición nueva de las plantas del usuario por mensaje (ver abajo) |
| `GET /admin/usuarios` | admin | 200 · lista de `{id, correo, nombre, rol, activo, cantidadPlantas}` |
| `PATCH /admin/usuarios/{id}` | admin | 200 · el cuerpo lleva `{activo}` o `{rol}` |
| `DELETE /admin/usuarios/{id}` | admin | 200 · borra la cuenta con sus plantas, sensores e historial |
| `POST /admin/especies` | admin | 201 · la especie, con la misma forma que en `GET /especies` |

La medición del sensor usa el mismo cuerpo que `POST /diagnosticos`, sin la especie: la especie es la de la planta. Una planta de otro usuario responde 404, igual que una que no existe. No hay medición a mano: el historial solo guarda lo que mandó un sensor. Las mediciones a mano que se guardaron antes conservan el origen `MANUAL`.

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
| `{"tipo": "error", "error", "mensaje"}` | El primer mensaje no era `autenticar` (`SOLICITUD_INVALIDA`), el token no sirve o no llegó en 5 segundos (`SESION_INVALIDA`), o la sesión se cerró o venció con la conexión abierta. Después el servidor cierra con el código 1008. |

Cada medición llega solo a las conexiones de su dueño, y cada conexión revisa la sesión antes de cada mensaje: una cuenta borrada o desactivada recibe `SESION_INVALIDA` en vez de la medición. Se avisa después de guardar: si el aviso falla o nadie está conectado, la medición igual queda en el historial. Cada pestaña tiene su propia cola, así que una que deja de leer no traba el POST del sensor; si su cola se llena, se corta esa conexión. Un error inesperado también llega en JSON (`ERROR_INTERNO`, cierre 1011). El servidor revisa el `Origin` antes de aceptar la conexión (CORS no aplica a los WebSocket) y manda un ping cada 25 segundos.

### Errores

Todas las respuestas de error, incluidas las de rutas inexistentes, tienen la forma `{ "error", "mensaje", "detalle" }`. El backend nunca responde HTML.

| Caso | HTTP | `error` | `detalle` |
|---|---|---|---|
| Especie desconocida | 404 | `ESPECIE_NO_SOPORTADA` | `especie` |
| Parámetro ausente | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo: "ausente"` |
| Valor no numérico | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo: "no_numerico"` |
| Valor físicamente imposible | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo: "fuera_de_rango_fisico"`, `minimo`, `maximo` |
| El cuerpo no es JSON | 400 | `SOLICITUD_INVALIDA` | vacío |
| Ruta inexistente / método no permitido | 404 / 405 | `RUTA_NO_ENCONTRADA` / `METODO_NO_PERMITIDO` | `ruta` |
| Error inesperado | 500 | `ERROR_INTERNO` | vacío |
| Correo, nombre, contraseña, apodo o rango inválidos | 400 | `PARAMETRO_INVALIDO` | `campo`, `motivo` |
| Código de sensor con otra forma (no `MT-0000-XX`) al crear la matera o al cambiarle el sensor | 400 | `CODIGO_SENSOR_INVALIDO` | `campo`, `motivo`, `texto` |
| Correo o contraseña incorrectos (el mismo en los dos casos) | 401 | `CREDENCIALES_INVALIDAS` | vacío |
| Sin token, token vencido o cuenta desactivada | 401 | `SESION_INVALIDA` | vacío |
| Sensor inexistente, código mal formado o clave incorrecta en `POST /sensores/{codigo}/mediciones` (el mismo en los tres casos) | 401 | `CLAVE_SENSOR_INVALIDA` | vacío |
| Cuenta desactivada al iniciar sesión | 403 | `CUENTA_DESACTIVADA` | vacío |
| Acción de administración sin ser admin | 403 | `PERMISO_DENEGADO` | vacío |
| Abrir el WebSocket desde un origen que no es el del front | 403 | `ORIGEN_NO_PERMITIDO` | `origen` |
| Un `GET` normal (sin WebSocket) a `/tiempo-real` | 400 | `SOLICITUD_INVALIDA` | `ruta` |
| Planta inexistente o de otro usuario | 404 | `PLANTA_NO_ENCONTRADA` | `planta_id` |
| Usuario inexistente | 404 | `USUARIO_NO_ENCONTRADO` | `referencia` |
| Correo, apodo, especie o código de sensor repetidos (el código, si es de otra planta) | 409 | `CORREO_YA_REGISTRADO`, `APODO_REPETIDO`, `ESPECIE_YA_EXISTE`, `SENSOR_YA_VINCULADO` | el dato repetido |
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

`backend/datos/carga.sql` llena las tablas `especie` (nombre y nombre científico) y `rango_optimo` (una fila por especie y parámetro, con su mínimo y su máximo). Son las mismas especies y rangos que tenía el CSV del corte 1. Un administrador puede agregar otras desde la API; `carga.sql` solo se ejecuta si la tabla de especies está vacía.

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
