-- Esquema de la base SQLite de la matera inteligente.
-- Se ejecuta en cada arranque: CREATE TABLE IF NOT EXISTS no toca las tablas que ya existen.
-- El parametro no es una tabla: los parametros son las constantes de dominio/parametros.py.

-- Tabla de referencia (escenario 5.2 del documento): una fila por especie y una por cada
-- rango, asi que agregar el pH no cambia el esquema.
CREATE TABLE IF NOT EXISTS especie (
    nombre            TEXT PRIMARY KEY,         -- normalizado: minusculas, sin tildes
    nombre_cientifico TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS rango_optimo (
    especie   TEXT NOT NULL REFERENCES especie (nombre) ON DELETE CASCADE,
    parametro TEXT NOT NULL,
    minimo    REAL NOT NULL,
    maximo    REAL NOT NULL,
    PRIMARY KEY (especie, parametro),
    CHECK (minimo < maximo)
);

-- Cuentas, plantas, sensores e historial (corte 2). Una sola base para todos los usuarios:
-- cada fila sabe de quien es. Borrar un usuario o una planta borra en cascada lo que depende de ellos.
CREATE TABLE IF NOT EXISTS usuario (
    id              INTEGER PRIMARY KEY,
    correo          TEXT NOT NULL UNIQUE,
    nombre          TEXT NOT NULL,
    hash_contrasena TEXT NOT NULL,              -- pbkdf2_sha256$iteraciones$sal$huella
    rol             TEXT NOT NULL DEFAULT 'USUARIO' CHECK (rol IN ('USUARIO', 'ADMIN')),
    activo          INTEGER NOT NULL DEFAULT 1 CHECK (activo IN (0, 1)),
    creado_en       TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now'))
);

-- Una sesion abierta por cada JWT de usuario. Se guarda su id (el reclamo jti), no el token:
-- cerrar la sesion borra la fila, y el token deja de servir aunque no haya vencido.
CREATE TABLE IF NOT EXISTS sesion (
    token_id   TEXT PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario (id) ON DELETE CASCADE,
    creada_en  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    vence_en   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS planta (
    id         INTEGER PRIMARY KEY,
    usuario_id INTEGER NOT NULL REFERENCES usuario (id) ON DELETE CASCADE,
    especie    TEXT NOT NULL REFERENCES especie (nombre),  -- sin cascada: una especie en uso no se borra
    apodo      TEXT NOT NULL COLLATE NOCASE,
    creada_en  TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    UNIQUE (usuario_id, apodo)
);

CREATE TABLE IF NOT EXISTS sensor (
    codigo       TEXT PRIMARY KEY,              -- MT-0000-XX
    planta_id    INTEGER NOT NULL UNIQUE REFERENCES planta (id) ON DELETE CASCADE,
    hash_clave   TEXT NOT NULL,                 -- SHA-256 de la clave: la clave no se guarda
    vinculado_en TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%SZ', 'now')),
    token_id     TEXT                           -- el id (jti) del JWT vigente; NULL hasta el primer canje
);

CREATE TABLE IF NOT EXISTS medicion (
    id        INTEGER PRIMARY KEY,
    planta_id INTEGER NOT NULL REFERENCES planta (id) ON DELETE CASCADE,
    momento   TEXT NOT NULL,                    -- ISO 8601 en UTC
    estado    TEXT NOT NULL,                    -- el estado global calculado en ese momento
    origen    TEXT NOT NULL                     -- el codigo del sensor (MANUAL en las mediciones a mano de antes)
);

CREATE INDEX IF NOT EXISTS medicion_por_planta ON medicion (planta_id, momento);

CREATE TABLE IF NOT EXISTS lectura (
    medicion_id INTEGER NOT NULL REFERENCES medicion (id) ON DELETE CASCADE,
    parametro   TEXT NOT NULL,
    valor       REAL NOT NULL,
    estado      TEXT NOT NULL,
    PRIMARY KEY (medicion_id, parametro)
);

-- Juego (corte 3, version 4). Tres tablas nuevas: las de arriba no cambian.

-- Un movimiento por cada lectura aceptada: lo que sumo o resto. Borrar la cuenta borra sus
-- movimientos. Borrar la planta los deja sin planta (SET NULL): siguen sumando en el total de su
-- dueno, pero no pasan a otra planta que reciba el mismo id (SQLite reutiliza el id mas alto).
CREATE TABLE IF NOT EXISTS movimiento_puntaje (
    id         INTEGER PRIMARY KEY,           -- orden de guardado: desempata dos con el mismo momento
    usuario_id INTEGER NOT NULL REFERENCES usuario (id) ON DELETE CASCADE,
    planta_id  INTEGER REFERENCES planta (id) ON DELETE SET NULL,
    momento    TEXT NOT NULL,                 -- ISO 8601 en UTC, con microsegundos: la hora del servidor
    momento_us INTEGER NOT NULL,              -- el mismo momento en microsegundos desde 1970-01-01 UTC
    estado     TEXT NOT NULL CHECK (estado IN ('SALUDABLE', 'EN_RIESGO', 'CRITICO')),
    puntos     INTEGER NOT NULL
);

-- Con momento_us, la hora de juego es la misma division entera que hace RelojDeJuego.numero_de_hora.
CREATE INDEX IF NOT EXISTS movimiento_por_planta ON movimiento_puntaje (planta_id, momento_us);
CREATE INDEX IF NOT EXISTS movimiento_por_usuario ON movimiento_puntaje (usuario_id, momento_us);

-- Quien respondio la pregunta de la tabla de posiciones. Solo quien participa tiene apodo de
-- jugador, y el apodo no se repite sin importar mayusculas (NOCASE: el apodo solo admite letras
-- sin tildes, numeros, _ y -). Al dejar de participar, el apodo queda libre.
CREATE TABLE IF NOT EXISTS jugador (
    usuario_id INTEGER PRIMARY KEY REFERENCES usuario (id) ON DELETE CASCADE,
    estado     TEXT NOT NULL CHECK (estado IN ('SIN_DECIDIR', 'PARTICIPA', 'NO_PARTICIPA')),
    apodo      TEXT COLLATE NOCASE,
    CHECK ((estado = 'PARTICIPA') = (apodo IS NOT NULL))
);

CREATE UNIQUE INDEX IF NOT EXISTS jugador_por_apodo ON jugador (apodo);

-- Cuantos dias de juego bien cuidada necesita cada especie para cada etapa. Va aparte de la
-- tabla especie del corte 1. Una especie sin fila, como una que agrego el admin, crece a 1/3/7.
CREATE TABLE IF NOT EXISTS ritmo_crecimiento (
    especie        TEXT PRIMARY KEY REFERENCES especie (nombre) ON DELETE CASCADE,
    dias_brote     INTEGER NOT NULL,
    dias_planta    INTEGER NOT NULL,
    dias_florecida INTEGER NOT NULL,
    CHECK (0 < dias_brote AND dias_brote < dias_planta AND dias_planta < dias_florecida)
);
