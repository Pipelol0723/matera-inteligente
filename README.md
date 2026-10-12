# Matera inteligente

Matera inteligente: una API que diagnostica el estado de una planta a partir de su especie y de una medición de humedad del sustrato, luz y temperatura, y un front web estático que la consume. Desde el corte 2, cada persona tiene su cuenta, sus plantas, un sensor por planta y el historial de mediciones; un administrador gestiona las cuentas y agrega especies.

Proyecto de Arquitectura de Software, semestre 2026-03. El corte 1, tal como se entregó, está en el tag `corte-1`.

## Estructura

```
backend/
  main.py            raíz de composición: el único archivo que elige clases concretas
  crear_admin.py     da el rol de administrador a una cuenta, desde la consola
  datos/             esquema.sql y carga.sql de la base SQLite
  dominio/           entidades y reglas de negocio; no importa flask, sqlite3, hashlib ni http
  aplicacion/        casos de uso
  presentacion/      rutas REST, autenticación y conversión entre JSON y objetos del dominio
  infraestructura/   SQLite, contraseñas y secretos, reloj, configuración, Flask y CORS
  tests/
    dominio/         reglas de negocio con dobles de prueba, sin servidor ni base de datos
    aplicacion/      casos de uso con dobles de prueba
    integracion/     API, repositorios SQLite, seguridad y el servidor real
frontend/            HTML, CSS y JavaScript estáticos, servidos aparte
  js/api.js          peticiones a la API, con el token en las rutas privadas
  js/app.js          arranque, navegación, pantallas públicas y privadas
  js/sesion.js       token de la sesión, en sessionStorage
  js/diagnostico.js  pantalla de diagnóstico
  js/especies.js     catálogo de especies
  js/acceso.js       ingresar y crear cuenta
  js/cuenta.js       mi cuenta y cerrar sesión
  js/materas.js      mis materas y medición a mano
  js/vincular.js     vincular y desvincular el sensor de una planta
  js/simulador.js    manda mediciones como lo haría el ESP32
  js/historial.js    historial de una planta
  js/admin.js        administración de cuentas y especies
  js/formularios.js  errores de la API en los formularios
  js/lecturas.js     campos de una medición y texto de unas lecturas
  js/escala.js       geometría de escalas y anillos
  js/formato.js      textos, colores y ayudas para crear nodos
docs/
  diagramas/         casos de uso, paquetes, clases, entidad-relación y secuencias,
                     del corte 1 y del diseño del corte 2 (fuente .mmd, SVG y PNG)
  entrega/           documento de arquitectura y bitácora de uso de IA (PDF)
```

Las dependencias apuntan hacia el dominio: `presentacion → aplicacion → dominio ← infraestructura`. Los puertos están declarados en `dominio/puertos.py` (corte 1) y `dominio/puertos_usuarios.py` (corte 2), y los implementan las clases de `infraestructura/sqlite/`, `infraestructura/seguridad.py` e `infraestructura/reloj.py`.

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
| Mis materas | con sesión | Las plantas del usuario con su última medición. Permite agregar y eliminar plantas y registrar una medición a mano. |
| Vincular sensor | con sesión | Vincula un sensor a una planta por su código; la clave se muestra una sola vez. Incluye el simulador, que manda una medición como lo haría el ESP32. |
| Historial | con sesión | La lista, la gráfica y el resumen de las mediciones de una planta, con el estado que calculó la API en su momento. |
| Mi cuenta | con sesión | Nombre, correo, rol, cantidad de plantas y cerrar sesión. |
| Administración | solo admin | Activar, desactivar, dar o quitar el rol y eliminar cuentas; agregar especies. La pestaña solo aparece para un admin, pero los permisos los revisa la API. |

Si la API responde `401 SESION_INVALIDA`, el front borra el token y lleva a Ingresar.

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

Las de integración usan una base SQLite temporal. `test_servidor_real.py` levanta el servidor con hilos, como `python main.py`: es la prueba que detecta un error que el cliente de pruebas de Flask no ve, usar una misma conexión de `sqlite3` desde varios hilos.

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
| `POST /plantas` | sesión | 201 · `{id, apodo, especie}` |
| `DELETE /plantas/{id}` | sesión | 200 · borra también su sensor y su historial |
| `POST /plantas/{id}/sensor` | sesión | 201 · `{planta, codigo, clave}`; la clave solo aparece aquí |
| `DELETE /plantas/{id}/sensor` | sesión | 200 · el código queda libre |
| `GET /plantas/{id}/historial?limite=30` | sesión | 200 · `{planta, registros}`, el más reciente primero |
| `POST /plantas/{id}/mediciones` | sesión | 201 · `{planta, momento, diagnostico}`; se guarda con origen MANUAL |
| `POST /sensores/{codigo}/mediciones` | clave del sensor | 201 · `{planta, momento, diagnostico}`; se guarda con el código como origen |
| `GET /admin/usuarios` | admin | 200 · lista de `{id, correo, nombre, rol, activo, cantidadPlantas}` |
| `PATCH /admin/usuarios/{id}` | admin | 200 · el cuerpo lleva `{activo}` o `{rol}` |
| `DELETE /admin/usuarios/{id}` | admin | 200 · borra la cuenta con sus plantas, sensores e historial |
| `POST /admin/especies` | admin | 201 · la especie, con la misma forma que en `GET /especies` |

Las mediciones manuales y las del sensor usan el mismo cuerpo que `POST /diagnosticos`, sin la especie: la especie es la de la planta. Una planta de otro usuario responde 404, igual que una que no existe.

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
| Código de sensor con otra forma (no `MT-0000-XX`) | 400 | `CODIGO_SENSOR_INVALIDO` | `campo`, `texto` |
| Correo o contraseña incorrectos (el mismo en los dos casos) | 401 | `CREDENCIALES_INVALIDAS` | vacío |
| Sin token, token vencido o cuenta desactivada | 401 | `SESION_INVALIDA` | vacío |
| Sensor inexistente o clave incorrecta (el mismo en los dos casos) | 401 | `CLAVE_SENSOR_INVALIDA` | vacío |
| Cuenta desactivada al iniciar sesión | 403 | `CUENTA_DESACTIVADA` | vacío |
| Acción de administración sin ser admin | 403 | `PERMISO_DENEGADO` | vacío |
| Planta inexistente o de otro usuario | 404 | `PLANTA_NO_ENCONTRADA` | `planta_id` |
| Desvincular una planta sin sensor | 404 | `PLANTA_SIN_SENSOR` | `planta_id` |
| Usuario inexistente | 404 | `USUARIO_NO_ENCONTRADO` | `referencia` |
| Correo, apodo, especie o código de sensor repetidos | 409 | `CORREO_YA_REGISTRADO`, `APODO_REPETIDO`, `ESPECIE_YA_EXISTE`, `SENSOR_YA_VINCULADO` | el dato repetido |
| La planta ya tiene sensor | 409 | `PLANTA_CON_SENSOR` | `planta_id` |
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
