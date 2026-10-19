# Diagramas

La fuente de cada diagrama es su archivo `.mmd` (Mermaid). El `.svg` y el `.png` son exportaciones de esa fuente, listas para pegar en el documento.

Hay diagramas de dos momentos:

- **Corte 1**: el sistema entregado, en el tag `corte-1` (commit `8c37f83`). Estos diagramas quedan como registro del antes y no se actualizan.
- **Corte 2**: el sistema actual, con usuarios, administración, sensores, historial y tiempo real. Se ajustaron al código el 12 de octubre de 2026 y otra vez el 18 de octubre, cuando la matera pasó a nacer con su sensor, se quitó la medición a mano y se agregó el WebSocket. Corresponden uno a uno con el repositorio.

## Índice

| Diagrama | Corte 1: entregado | Corte 2: código actual |
|---|---|---|
| [Casos de uso](#casos-de-uso) | [`casos-de-uso-corte1`](casos-de-uso-corte1.png) | [`casos-de-uso-corte2`](casos-de-uso-corte2.png) |
| [Paquetes](#paquetes) | [`paquetes`](paquetes.png) | [`paquetes-corte2`](paquetes-corte2.png) |
| [Clases: dominio](#clases-del-dominio) | [`clases-dominio-corte1`](clases-dominio-corte1.png) | [`clases-dominio`](clases-dominio.png) |
| [Clases: puertos e implementaciones](#puertos-e-implementaciones) | [`clases-puertos-corte1`](clases-puertos-corte1.png) | [`clases-puertos`](clases-puertos.png) |
| [Clases: diagnóstico, plantas y sensores](#presentación-y-aplicación-diagnóstico-plantas-y-sensores) | [`clases-aplicacion-corte1`](clases-aplicacion-corte1.png) | [`clases-aplicacion`](clases-aplicacion.png) |
| [Clases: cuentas y administración](#presentación-y-aplicación-cuentas-y-administración) | no existía | [`clases-cuentas`](clases-cuentas.png) |
| [Entidad-relación](#entidad-relación) | [`entidad-relacion-corte1`](entidad-relacion-corte1.png) | [`entidad-relacion-corte2`](entidad-relacion-corte2.png) |
| [Secuencia: un diagnóstico](#secuencia-de-un-diagnóstico) | [`secuencia-diagnostico`](secuencia-diagnostico.png) | igual, con otro repositorio de especies |
| [Secuencia: medición del sensor](#secuencia-de-una-medición-del-sensor) | no existía | [`secuencia-medicion-sensor`](secuencia-medicion-sensor.png) |
| [Secuencia: tiempo real](#secuencia-del-tiempo-real) | no existía | [`secuencia-tiempo-real`](secuencia-tiempo-real.png) |
| [Secuencia: login y «mis plantas»](#secuencia-de-login-y-mis-plantas) | no existía | [`secuencia-login`](secuencia-login.png) |
| [Secuencia: el admin agrega una especie](#secuencia-del-admin-que-agrega-una-especie) | no existía | [`secuencia-admin-especie`](secuencia-admin-especie.png) |

Al final está además la [vista general](#vista-general-diagrama-de-clases-del-backend) de Roger: el backend completo en un solo diagrama de PlantUML.

Los cuatro diagramas de clases del corte 2 no llevan sufijo porque muestran los dos cortes a la vez: **borde fino = corte 1, borde grueso = se agregó en el corte 2**. Los `-corte1` muestran solo lo del corte 1.

## Convenciones

- **Clases:** el color indica la capa. Son los colores del diagrama de clases de Roger: morado para presentación, amarillo para aplicación, verde para dominio y azul para infraestructura.
- **Paquetes:** conservan los colores del diagrama entregado en el corte 1. En el del corte 2, los nodos nuevos son verdes y punteados.
- **Casos de uso del corte 2:** gris es un caso del corte 1, verde uno nuevo y oscuro uno exclusivo del administrador.
- **Nombres:** los de clases, atributos, métodos y archivos son los del código. Si el código cambia, se actualizan aquí (ver [Si cambia el código](#si-cambia-el-código)).

---

## Casos de uso

Mermaid no tiene diagrama de casos de uso. Se dibujan como un flujo: los actores son cajas, los casos son óvalos y el recuadro es el sistema.

### Corte 1

![Casos de uso del corte 1](casos-de-uso-corte1.png)

Fuente: [`casos-de-uso-corte1.mmd`](casos-de-uso-corte1.mmd).

- Hay un solo actor, anónimo, con dos casos: consultar las especies con sus rangos (RF5) y diagnosticar una planta (RF1 a RF4).
- Las recomendaciones no son un caso aparte: vienen incluidas en cada diagnóstico.

### Corte 2

![Casos de uso del corte 2](casos-de-uso-corte2.png)

Fuente: [`casos-de-uso-corte2.mmd`](casos-de-uso-corte2.mmd).

- **Cuatro actores.** El *visitante* es la persona anónima del corte 1, que ahora además puede crear una cuenta e iniciar sesión. El *usuario registrado* también es visitante. El *administrador* también es usuario, y por eso también tiene plantas. El *sensor ESP32* es un actor sin persona.
- **El sensor no tiene su propia lógica de diagnóstico.** «Enviar una medición» *incluye* «Diagnosticar una planta», el mismo caso de uso del corte 1, e incluye «Guardar en el historial».
- **Solo el sensor escribe en el historial.** Desde el 18 de octubre no hay medición a mano. «Enviar una medición» también incluye «Avisar la medición al dueño», que actualiza «Ver mis materas en vivo» sin que el usuario recargue.
- **La matera nace con su sensor.** «Crear una matera con su sensor» pide el código del dispositivo. «Cambiar el sensor de una matera» reemplaza a vincular y desvincular, y conserva el historial.
- **Casos exclusivos del administrador:** «Administrar usuarios» agrupa listar, desactivar y reactivar, dar y quitar el rol de admin, y eliminar cuentas. «Agregar especies» solo lo puede hacer el admin.

## Paquetes

### Corte 1

![Diagrama de paquetes](paquetes.png)

Fuente: [`paquetes.mmd`](paquetes.mmd).

- Cada caja es una carpeta real del repositorio y lista todos sus archivos, menos los `__init__.py`.
- Las flechas continuas son `import` del código de producción, en la dirección de la dependencia. Se sacaron leyendo los imports de cada archivo, no a mano.
- Las flechas punteadas son `main.py`, que arma todas las capas, y las pruebas.
- Ninguna flecha sale de `dominio/`.

### Corte 2

![Diagrama de paquetes del corte 2](paquetes-corte2.png)

Fuente: [`paquetes-corte2.mmd`](paquetes-corte2.mmd).

- **Las flechas entre capas son las mismas del corte 1.** El corte 2 no agrega ninguna dependencia nueva entre capas: cambia el contenido de cada carpeta.
- Cada caja separa lo que ya estaba de lo `nuevo:` y de lo que `se eliminó`. El dominio conserva sus 12 módulos sin cambios.
- **Hay una segunda entrada:** el ESP32 (`firmware/matera-sensor`), o la herramienta de desarrollo `enviar_medicion.py`, llega a la capa de presentación igual que el front, pero con su clave en la cabecera `X-Clave-Sensor` en lugar del token.
- **El tiempo real tampoco agrega dependencias entre capas.** El front abre un WebSocket con `presentacion/tiempo_real.py`. El aviso sale de `infraestructura/tiempo_real.py`, que implementa un puerto del dominio, y `main.py` le pasa a la ruta los mismos canales: presentación no importa infraestructura.
- **`especies.csv` desaparece.** En su lugar están `esquema.sql` y `carga.sql`, y la base `matera.sqlite`, que vive fuera de Google Drive (se configura con `MATERA_RUTA_BD`).
- `crear_admin.py` es una segunda raíz de composición, para la consola, igual que `main.py` lo es para la web.

## Clases

Son cuatro diagramas, porque en uno solo no se leían las más de 60 clases. Juntan el diagrama de clases que Roger armó en PlantUML (commits `3987f72` y `6c43769`) con el corte 2.

| Se tomó del diagrama de Roger | Se tomó del diseño o se corrigió contra el código |
|---|---|
| Las capas como paquetes con color | Los nombres exactos del código (`minimo_fisico`, `fuera_de_rango`…) |
| Presentación e infraestructura dentro del diagrama | `Medicion` con `1..*` lecturas; `Especie` compuesta por sus `Rango`; retornos «o None» |
| La nota con los errores del dominio | Las flechas que faltaban: `ResultadoParametro → Rango` y `esquemas → Medicion` |
| Las dependencias por constructor, con el nombre del rol (`regla`, `evaluador`, `servicio`) | Las clases del corte 2 dentro de su capa, no en un paquete «usuarios» aparte |
| `ReglaAgregacion` como interfaz, y la reutilización de `ServicioDiagnostico` destacada | El formato Mermaid del resto de la carpeta, con SVG y PNG |

En estos diagramas los colores van en líneas `style`, una por clase. Mermaid acepta `classDef` y `cssClass` en diagramas de clases, pero no los dibuja.

### Clases del dominio

![Clases del dominio, corte 1 y corte 2](clases-dominio.png)

Fuentes: [`clases-dominio.mmd`](clases-dominio.mmd) (los dos cortes) y [`clases-dominio-corte1.mmd`](clases-dominio-corte1.mmd) ([imagen](clases-dominio-corte1.png), solo el corte 1).

- **A la derecha, el núcleo del corte 1.** `ServicioDiagnostico` usa a `EvaluadorPlanta`, que aplica una `ReglaAgregacion` (la híbrida o la de conteo) y el `GeneradorRecomendaciones` a una `Especie` y una `Medicion`, y crea un `Diagnostico`.
- **A la izquierda, lo nuevo.** `Usuario` con su `Rol`, `Sesion`, `Planta`, `Sensor` con su `CodigoSensor`, y `RegistroMedicion` para el historial, con su origen: el código del sensor (las mediciones a mano de antes conservan MANUAL).
- **Ninguna flecha sale de una clase del corte 1 hacia una nueva.** Son las nuevas las que dependen de las viejas: `Planta` apunta a `Especie` y `RegistroMedicion` se construye desde un `Diagnostico`. Por eso el corte 2 no modifica ningún módulo del dominio actual.
- **`Usuario.exigir_admin()` es la regla de permisos de todo el sistema.** Si el usuario no es ADMIN, lanza `PermisoDenegado`. `Usuario.exigir_otro_usuario()` impide que un admin actúe sobre su propia cuenta.
- Las dos notas amarillas listan los errores de cada corte. Todos heredan de `ErrorDominio`.

### Puertos e implementaciones

![Puertos e implementaciones, corte 2](clases-puertos.png)

Fuentes: [`clases-puertos.mmd`](clases-puertos.mmd) y [`clases-puertos-corte1.mmd`](clases-puertos-corte1.mmd) ([imagen](clases-puertos-corte1.png)).

- **Todas las flechas van de infraestructura hacia el dominio (RA5, DIP).** El dominio declara la interfaz, e infraestructura la implementa.
- En el corte 1 hay dos puertos, `ConsultaRangos` y `CatalogoEspecies`, y los implementa `RepositorioEspeciesCsv`. En el corte 2 hay doce.
- **`RepositorioEspeciesSqlite` reemplaza al CSV.** Implementa los mismos dos puertos más `RegistroEspecies`, el que usa el admin para agregar especies. Es el escenario 5.2 del documento: una clase nueva y ningún cambio en el dominio.
- **`RepositorioPlantas` solo encuentra una planta de dos formas:** por su dueño, `por_id(usuario_id, planta_id)`, o por un sensor ya autenticado, `vinculada_a(sensor)`. Ahí vive el aislamiento entre usuarios. `vinculada_a` exige que el sensor siga siendo el mismo (código, planta y huella de la clave): una clave recién revocada no puede escribir en la planta que tomó su código.
- **Una matera no existe sin sensor.** `guardar_con_sensor()` crea la planta y su sensor en una sola transacción, y `reemplazar(usuario_id, sensor)` cambia el sensor en otra, solo si la planta sigue siendo de ese usuario. No hay un `guardar()` que cree una planta sola.
- **`NotificadorDiagnosticos` es el puerto del tiempo real.** Lo implementa `NotificadorWebSocket`, que arma el mensaje y se lo pasa a `CanalesTiempoReal`, el registro de las conexiones abiertas de cada usuario. Cambiar el WebSocket por MQTT sería escribir otra implementación del puerto, sin tocar el caso de uso.
- `Cifrador`, `GeneradorSecretos` y `Reloj` son puertos para que el dominio y la aplicación no importen `hashlib`, `secrets` ni la hora del sistema. En las pruebas, cada interfaz tiene un doble en memoria.
- **`BaseDatos` abre una conexión por operación** y activa `PRAGMA foreign_keys`. Flask atiende cada petición en un hilo y `sqlite3` no deja usar una conexión desde otro hilo: con una sola conexión compartida, el servidor real fallaba aunque las pruebas con `test_client` pasaran.

### Presentación y aplicación: diagnóstico, plantas y sensores

![Presentación y aplicación del diagnóstico, las plantas y los sensores](clases-aplicacion.png)

Fuentes: [`clases-aplicacion.mmd`](clases-aplicacion.mmd) y [`clases-aplicacion-corte1.mmd`](clases-aplicacion-corte1.mmd) ([imagen](clases-aplicacion-corte1.png)).

- **Las rutas públicas del corte 1 no cambian.** `rutas` llama a `DiagnosticarPlanta`, `ListarEspecies` y `ListarParametros`.
- **`esquemas` crea la `Medicion`.** Esa es la línea donde el dato deja de saber que llegó por HTTP (RA6). En el corte 2 se extrae `medicion_desde_json()` para que la use también `rutas_sensores`.
- `rutas_plantas` exige sesión a través de `Autenticacion`. `rutas_sensores` no usa el token: el sensor se identifica con su propia clave.
- **`RegistrarPlanta` y `ReemplazarSensor` devuelven un `SensorVinculado`,** la planta con el código y la clave. Es la única vez que la clave sale del backend.
- **La reutilización del núcleo:** la medición del sensor (`RecibirMedicionDeSensor`) pasa por `DiagnosticarPlantaDeUsuario`, que busca la planta por su dueño y llama a `ServicioDiagnostico`, el mismo del corte 1, sin cambios. Después de guardar, avisa por el puerto `NotificadorDiagnosticos`; si el aviso falla, la medición ya quedó guardada.
- **`tiempo_real` es la ruta del WebSocket.** Autentica con el primer mensaje usando `IdentificarUsuario`, el mismo caso de uso de las rutas HTTP, y crea un `CanalWebSocket` por pestaña. Cada canal tiene su cola y su hilo emisor, y revisa la sesión antes de cada mensaje.

### Presentación y aplicación: cuentas y administración

![Presentación y aplicación de las cuentas y la administración](clases-cuentas.png)

Fuente: [`clases-cuentas.mmd`](clases-cuentas.mmd). Solo existe en el corte 2.

- `rutas_usuarios` maneja el registro, las sesiones y «Mi cuenta». `rutas_admin` maneja todo lo que es solo para el admin, bajo `/api/v1/admin`.
- **Cada caso de uso de administración llama primero a `actor.exigir_admin()`.** La ruta no revisa el rol, y esconder la pestaña en el front no protege nada: la regla está en el dominio.
- **Siempre queda al menos un admin**, porque un admin no puede desactivarse, quitarse el rol ni eliminarse a sí mismo.
- `crear_admin` es el script de consola que crea el primer administrador. No pasa por la API.

Qué puertos usa cada caso de uso nuevo (en negrita, lo que ya existía en el corte 1):

| Caso de uso | Archivo en `aplicacion/` | Depende de |
|---|---|---|
| `RegistrarUsuario` | `cuentas.py` | RepositorioUsuarios, Cifrador |
| `IniciarSesion` | `cuentas.py` | RepositorioUsuarios, RepositorioSesiones, Cifrador, GeneradorSecretos, Reloj |
| `CerrarSesion` | `cuentas.py` | RepositorioSesiones, GeneradorSecretos |
| `IdentificarUsuario` | `cuentas.py` | RepositorioSesiones, RepositorioUsuarios, GeneradorSecretos, Reloj |
| `ConsultarCuenta` | `cuentas.py` | RepositorioPlantas, para contar las plantas |
| `RegistrarPlanta` | `plantas.py` | RepositorioPlantas, RepositorioSensores, **ConsultaRangos**, GeneradorSecretos |
| `ListarPlantas` | `plantas.py` | RepositorioPlantas, RepositorioSensores, HistorialMediciones |
| `EliminarPlanta` | `plantas.py` | RepositorioPlantas |
| `ReemplazarSensor` | `sensores.py` | RepositorioPlantas, RepositorioSensores, GeneradorSecretos |
| `RecibirMedicionDeSensor` | `sensores.py` | RepositorioSensores, RepositorioPlantas, GeneradorSecretos, DiagnosticarPlantaDeUsuario |
| `DiagnosticarPlantaDeUsuario` | `diagnosticar_planta_de_usuario.py` | RepositorioPlantas, **ServicioDiagnostico**, HistorialMediciones, Reloj, NotificadorDiagnosticos |
| `ConsultarHistorial` | `historial.py` | RepositorioPlantas, HistorialMediciones |
| `ListarUsuarios` | `administracion.py` | RepositorioUsuarios |
| `CambiarEstadoUsuario` | `administracion.py` | RepositorioUsuarios, RepositorioSesiones |
| `CambiarRol` | `administracion.py` | RepositorioUsuarios |
| `EliminarUsuario` | `administracion.py` | RepositorioUsuarios |
| `AgregarEspecie` | `administracion.py` | **ConsultaRangos**, RegistroEspecies y el catálogo de parámetros |
| `ConvertirEnAdministrador` | `administracion.py` | RepositorioUsuarios |

## Entidad-relación

### Corte 1

![Entidad-relación del corte 1](entidad-relacion-corte1.png)

Fuente: [`entidad-relacion-corte1.mmd`](entidad-relacion-corte1.mmd).

- Es el modelo **conceptual**: en el corte 1 no hay base de datos. Físicamente es un solo archivo, `datos/especies.csv`, con una fila por especie y dos columnas (`_min` y `_max`) por parámetro.
- `PARAMETRO` no es una tabla sino las constantes de `dominio/parametros.py`.

### Corte 2

![Entidad-relación del corte 2](entidad-relacion-corte2.png)

Fuente: [`entidad-relacion-corte2.mmd`](entidad-relacion-corte2.mmd).

- **Todo va en un solo archivo SQLite, con ocho tablas.** Cada usuario solo ve lo suyo porque cada planta tiene su `usuario_id`, y el puerto obliga a decir de quién es la planta que se busca.
- **`ESPECIE` y `RANGO_OPTIMO` reemplazan al CSV.** `carga.sql` las llena con las mismas especies, rangos y fuentes. Ahora `PLANTA.especie` es una llave foránea real: no se puede registrar una planta con una especie inexistente, ni borrar una especie que alguna planta use.
- **`RANGO_OPTIMO` y `LECTURA` guardan una fila por parámetro**, así que agregar el pH no cambia el esquema.
- `USUARIO.rol` es USUARIO o ADMIN, y `USUARIO.activo` permite desactivar una cuenta sin borrarla.
- **Una matera nueva nace con su `SENSOR`,** en la misma transacción. La relación sigue siendo 0..1 por las materas creadas antes de que el sensor fuera obligatorio. Cambiar el sensor reemplaza esa fila y no toca `MEDICION`. `hash_clave` y `hash_token` guardan huellas, nunca el secreto.
- `MEDICION.origen` es el código del sensor que envió la medición. Las mediciones escritas a mano antes del 18 de octubre conservan `MANUAL`.
- El esquema real está en [`backend/datos/esquema.sql`](../../backend/datos/esquema.sql).
- Borrar un usuario o una planta borra en cascada lo que depende de ellos. Las líneas punteadas llegan a `PARAMETRO`, que sigue en el código.

## Secuencias

### Secuencia de un diagnóstico

![Diagrama de secuencia](secuencia-diagnostico.png)

Fuente: [`secuencia-diagnostico.mmd`](secuencia-diagnostico.mmd).

Sigue una petición desde que la persona escribe en el front hasta que se pinta el resultado, con las funciones y clases reales. También muestra las dos salidas de error: 400 por entrada inválida y 404 por especie inexistente.

En el corte 2 este recorrido no cambia. La única diferencia es el participante `P`: en vez de `RepositorioEspeciesCsv` está `RepositorioEspeciesSqlite`, detrás del mismo puerto `ConsultaRangos`.

### Secuencia de una medición del sensor

![Secuencia de una medición del sensor](secuencia-medicion-sensor.png)

Fuente: [`secuencia-medicion-sensor.mmd`](secuencia-medicion-sensor.mmd). Corte 2.

- **HTTP termina en `rutas_sensores.py`.** De ahí en adelante viajan un código, una clave y una `Medicion`, y los límites físicos ya se validaron al crear cada `Lectura`.
- **El sensor se identifica con su clave.** `GeneradorSecretos.coincide()` la compara con la huella guardada. Un sensor inexistente y una clave incorrecta dan el mismo 401, para no revelar qué códigos existen.
- La planta se obtiene con `vinculada_a(sensor)`, porque el sensor ya se autenticó, y solo si sigue siendo el mismo sensor. Después `DiagnosticarPlantaDeUsuario` la busca por su dueño.
- **`ServicioDiagnostico` es el del corte 1, sin cambios.** El resultado se guarda como `RegistroMedicion`, con el estado que tenía en ese momento y el código del sensor como origen.
- **Después de guardar, se avisa en vivo** por el puerto `NotificadorDiagnosticos`: la pantalla del dueño se actualiza sola (ver la secuencia siguiente). Si el aviso falla, el sensor igual recibe su 201.
- Con MQTT solo cambiarían el primer participante y el adaptador que lo recibe. Desde `RecibirMedicionDeSensor` en adelante, todo queda igual.

### Secuencia del tiempo real

![Secuencia del tiempo real](secuencia-tiempo-real.png)

Fuente: [`secuencia-tiempo-real.mmd`](secuencia-tiempo-real.mmd). Corte 2, desde el 18 de octubre.

- **El Origin se revisa antes de aceptar la conexión.** CORS no aplica a los WebSocket, así que la ruta compara el Origin con los mismos orígenes del front. Otro origen recibe 403 en JSON.
- **El token va en el primer mensaje,** porque el navegador no deja poner `Authorization` en un WebSocket y una URL con el token queda en registros. Lo valida `IdentificarUsuario`, el mismo caso de uso de las rutas HTTP.
- **Primero se registra el canal y después se dice «listo».** Desde ese mensaje no se pierde ninguna medición.
- **El aviso solo llega al dueño.** `CanalesTiempoReal` agrupa las conexiones por usuario, y cada canal vuelve a revisar la sesión antes de cada mensaje. Así, una pestaña de una cuenta borrada nunca recibe las mediciones de la cuenta nueva que hereda su id (SQLite reutiliza el id más alto).
- **Una pestaña lenta no traba al sensor.** El mensaje queda en la cola de la pestaña y lo manda su propio hilo. Si la cola se llena, se corta esa conexión.
- Si la conexión se cae, el front reintenta y vuelve a pedir sus datos. La medición nunca se pierde: se guardó antes de avisar.

### Secuencia de login y «mis plantas»

![Secuencia de login y mis plantas](secuencia-login.png)

Fuente: [`secuencia-login.mmd`](secuencia-login.mmd). Corte 2.

- Si el correo no existe o la contraseña no coincide, la respuesta es el mismo 401. Una cuenta desactivada da 403, pero solo después de que la contraseña fue correcta.
- El token se devuelve una sola vez; la base guarda solo su huella y su vencimiento. El front lo guarda en `sessionStorage`.
- **`Autenticacion` (`presentacion/autenticacion.py`) es donde el token deja de saber que existe HTTP:** saca el texto de la cabecera y a `IdentificarUsuario` solo le pasa un `str`.
- `ListarPlantas` recibe el `Usuario` y el repositorio solo devuelve sus plantas.

### Secuencia del admin que agrega una especie

![Secuencia del admin que agrega una especie](secuencia-admin-especie.png)

Fuente: [`secuencia-admin-especie.mmd`](secuencia-admin-especie.mmd). Corte 2.

- **El permiso se revisa en el caso de uso, con `actor.exigir_admin()`.** Si el actor no es admin, la respuesta es 403, venga del front o de cualquier otro cliente.
- La especie se arma con las mismas clases `Especie` y `Rango` del corte 1. Un rango con el mínimo mayor o igual que el máximo se rechaza con 400 antes de llegar al caso de uso.
- `AgregarEspecie` además exige un rango por cada parámetro que se mide; si falta uno, la respuesta es 400.
- Si la especie ya existe, la respuesta es 409. Si no, se guarda con `RegistroEspecies` y aparece de inmediato en `GET /especies`, disponible para las plantas de cualquier usuario.

---

## Vista general: diagrama de clases del backend

![Diagrama de clases del backend](clases-backend-general.png)

Propuesta de Roger del 1 de octubre, **revisada el 12 de octubre de 2026** para corregir las diferencias que tenía con el diseño aprobado del corte 2. Combina en una sola imagen las cuatro capas del backend más websocket y MQTT, marcados como futuro porque el diagrama se hizo antes del tiempo real. **No reemplaza los diagramas por capa de la sección anterior**: si contradice a alguno de ellos, vale el otro.

La primera versión (commit `d00df35`) se apartaba del diseño aprobado en varios puntos; esta revisión ya los corrige:

| Tenía la propuesta original | Tiene esta revisión, igual que el diseño aprobado |
|---|---|
| `VerificadorJwt`: token JWT | Token opaco: la base guarda su huella SHA-256 y su vencimiento, como `RepositorioSesiones` en el código. |
| `RepositorioEspeciesCsv` | `RepositorioEspeciesSqlite`, igual que el código. |
| `rutas` usaba el decorador de autenticación | `rutas.py` sigue sin tocarse: Diagnóstico y Especies siguen siendo públicas. |
| Paquete «usuarios» aparte | Cada clase va en su capa real: dominio, aplicación, presentación o infraestructura. |
| `PlantaNoPertenece` (403) | `PlantaNoEncontrada` (404): una planta ajena responde igual que una inexistente. |

**Pendiente desde el 18 de octubre de 2026.** Este diagrama todavía no refleja el cambio de ese día, y Roger lo va a actualizar. Lo que ya no coincide con el código:

- El WebSocket (`presentacion/tiempo_real.py`), `NotificadorDiagnosticos` y `NotificadorWebSocket` ya existen, pero aparecen como futuro (websocket y `NotificadorWebSocket` en gris).
- El WebSocket no recibe mediciones ni llama a `DiagnosticarPlantaDeUsuario`: el front solo manda el token y el servidor empuja cada medición.
- `NotificadorDiagnosticos` es un puerto del dominio, con `publicar(usuario_id, planta, registro, diagnostico)`, no una interfaz de infraestructura con `publicar(usuarioId, diagnostico)`.
- `RegistrarPlanta` recibe también el código del sensor y devuelve un `SensorVinculado`. `VincularSensor` se reemplazó por `ReemplazarSensor`, y la medición a mano se quitó.

Puede haber más diferencias: para todo lo del 18 de octubre valen los diagramas por capa. Solo `mqtt_listener` sigue de verdad sin código (MQTT es el escenario 5.1 del documento).

**Nivel de detalle:** el corte 2 agregó unas 20 clases de caso de uso y varios repositorios SQLite; dibujar cada una por separado hacía el diagrama ilegible. Por eso, igual que el corte 1 solo mostraba `RepositorioEspeciesCsv` como único repositorio, aquí varias clases con el mismo patrón se agrupan en una sola caja (por ejemplo, `ListarUsuarios, CambiarEstadoUsuario, CambiarRol, EliminarUsuario, AgregarEspecie` comparten caja porque todas empiezan con `actor.exigir_admin()`). Para el detalle clase por clase, use los diagramas por capa de la sección anterior.

Fuente: [`clases-backend-general.puml`](clases-backend-general.puml) (PlantUML, no Mermaid). Para regenerar la imagen: `java -jar plantuml.jar -tpng clases-backend-general.puml` (si se recorta, agregar `-DPLANTUML_LIMIT_SIZE=8192`).

---

## Si cambia el código

Los diagramas del corte 2 tienen que seguir correspondiendo uno a uno con el repositorio. Si se agrega, se renombra o se mueve un archivo, o cambia un import entre capas:

1. Edite el `.mmd`.
2. Pegue su contenido en <https://mermaid.live> y exporte el SVG y el PNG con el mismo nombre. También se puede exportar con `npx @mermaid-js/mermaid-cli -i paquetes-corte2.mmd -o paquetes-corte2.svg`.

Los del corte 1 (`-corte1`, `paquetes` y `secuencia-diagnostico`) son el registro de lo entregado en el tag `corte-1`: no se actualizan.
