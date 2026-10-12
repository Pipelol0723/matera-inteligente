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
