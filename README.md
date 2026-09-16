# Matera inteligente

Núcleo de la matera inteligente: una API que diagnostica el estado de una planta a partir de su especie y de una medición de humedad del sustrato, luz y temperatura, y un front web estático que la consume.

Proyecto de corte de Arquitectura de Software, semestre 2026-03.

## Estructura

```
backend/
  main.py            raíz de composición: el único archivo que elige clases concretas
  datos/especies.csv tabla de referencia
  dominio/           entidades y reglas de negocio; no importa flask, csv ni http
  aplicacion/        casos de uso
  presentacion/      rutas REST y conversión entre JSON y objetos del dominio
  infraestructura/   lectura del CSV, configuración, Flask y CORS
  tests/
    dominio/         reglas de negocio con dobles de prueba, sin servidor ni CSV
    aplicacion/      casos de uso con dobles de prueba
    integracion/     API y lectura del CSV
frontend/            HTML, CSS y JavaScript estáticos, servidos aparte
  js/api.js          peticiones a la API
  js/app.js          arranque, navegación entre pantallas y estado de la conexión
  js/diagnostico.js  pantalla de diagnóstico
  js/especies.js     catálogo de especies
  js/prototipos.js   maquetas de historial, materas y vincular sensor
  js/escala.js       geometría de escalas y anillos
  js/formato.js      textos, colores y ayudas para crear nodos
```

Las dependencias apuntan hacia el dominio: `presentacion → aplicacion → dominio ← infraestructura`. Los puertos `ConsultaRangos` y `CatalogoEspecies` están declarados en `dominio/puertos.py` y los implementa `infraestructura/repositorio_especies_csv.py`.

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
| `MATERA_RUTA_CSV` | `backend/datos/especies.csv` |
| `MATERA_ORIGENES_CORS` | `http://localhost:5500,http://127.0.0.1:5500` |

## Ejecutar el front

En otra terminal, desde la raíz del repositorio:

```bash
python -m http.server 5500 --directory frontend
```

Abra `http://localhost:5500`. El front se tiene que servir por HTTP; abrir `index.html` con doble clic no funciona porque usa módulos de JavaScript. Si cambia el puerto del backend, ajuste `frontend/js/config.js`.

El front no tiene rangos, umbrales ni reglas. Los parámetros, las especies, los estados y las recomendaciones salen de la API.

| Pantalla | Qué hace |
|---|---|
| Diagnóstico | Consulta `POST /diagnosticos` mientras se escribe (espera 400 ms después de la última tecla) y muestra el estado en los anillos. Los botones Saludable, En riesgo y Crítico llenan valores de ejemplo a partir de los rangos, y la API decide el estado. El panel "Errores de la API" envía peticiones inválidas a propósito. |
| Especies | Muestra el catálogo de `GET /especies` con bandas escaladas según los límites físicos de `GET /parametros`. |
| Historial, Materas, Vincular sensor | **Prototipos fuera del alcance de este corte**, marcados en pantalla. Usan lecturas de ejemplo, pero sus estados los calcula la API. |

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

Estas pruebas no levantan el servidor ni leen el CSV, y siguen pasando aunque se borre la carpeta `infraestructura/`. `tests/dominio/test_arquitectura.py` falla si algún archivo del dominio importa Flask, `csv`, HTTP u otra capa.

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

`backend/datos/especies.csv` tiene una fila por especie con las columnas `especie`, `nombre_cientifico` (opcional), `humedad_min`, `humedad_max`, `luz_min`, `luz_max`, `temperatura_min` y `temperatura_max`.

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
