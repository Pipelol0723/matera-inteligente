"""La migracion de una base vieja: se saca una copia, se cambia lo que haga falta y los datos quedan."""
import sqlite3

from infraestructura.sqlite.base_datos import ESQUEMA, VERSION, BaseDatos


def _base_de_antes(ruta) -> None:
    """Una base como la de antes de la fase 2: sin numero de version, con la sesion por huella del
    token opaco y sin el token vigente de cada sensor."""
    esquema = ESQUEMA.read_text(encoding="utf-8").replace("token_id   TEXT PRIMARY KEY,", "hash_token TEXT PRIMARY KEY,")
    sin_token = esquema.split("'now')),\n    token_id     TEXT")
    assert len(sin_token) == 2, "cambio la definicion de la tabla sensor en esquema.sql"
    esquema = sin_token[0] + "'now'))" + sin_token[1].split("\n", 1)[1]
    with sqlite3.connect(ruta) as conexion:
        conexion.executescript(esquema)
        conexion.executescript(
            """
            INSERT INTO especie (nombre) VALUES ('potos');
            INSERT INTO usuario (correo, nombre, hash_contrasena) VALUES ('ana@correo.co', 'Ana', 'h');
            INSERT INTO sesion (hash_token, usuario_id, vence_en) VALUES ('huella-vieja', 1, '2026-10-30T00:00:00+00:00');
            INSERT INTO planta (usuario_id, especie, apodo) VALUES (1, 'potos', 'Sala');
            INSERT INTO sensor (codigo, planta_id, hash_clave) VALUES ('MT-0001-AA', 1, 'huella-clave');
            """
        )


def _columnas(conexion, tabla) -> list[str]:
    return [fila[1] for fila in conexion.execute(f"PRAGMA table_info({tabla})")]


def test_una_base_de_antes_se_migra_sin_perder_datos_y_deja_una_copia(tmp_path):
    ruta = tmp_path / "matera.sqlite"
    _base_de_antes(ruta)

    BaseDatos(ruta).preparar()

    with sqlite3.connect(ruta) as conexion:
        assert conexion.execute("PRAGMA user_version").fetchone()[0] == VERSION
        assert "token_id" in _columnas(conexion, "sesion") and "hash_token" not in _columnas(conexion, "sesion")
        # Las sesiones de antes no sirven con JWT: cada usuario vuelve a ingresar.
        assert conexion.execute("SELECT COUNT(*) FROM sesion").fetchone()[0] == 0
        assert conexion.execute("SELECT correo FROM usuario").fetchall() == [("ana@correo.co",)]
        assert conexion.execute("SELECT apodo FROM planta").fetchall() == [("Sala",)]
        # El sensor conserva su clave, que sirve para el canje, y todavia no tiene token vigente.
        assert conexion.execute("SELECT codigo, hash_clave, token_id FROM sensor").fetchall() == [
            ("MT-0001-AA", "huella-clave", None)
        ]
    copia = tmp_path / "matera.respaldo-v0.sqlite"
    with sqlite3.connect(copia) as conexion:
        assert conexion.execute("SELECT hash_token FROM sesion").fetchall() == [("huella-vieja",)]


def test_preparar_otra_vez_no_migra_de_nuevo_ni_saca_otra_copia(tmp_path):
    ruta = tmp_path / "matera.sqlite"
    _base_de_antes(ruta)
    BaseDatos(ruta).preparar()
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("INSERT INTO sesion (token_id, usuario_id, vence_en) VALUES ('jti', 1, '2026-10-30T00:00:00+00:00')")

    BaseDatos(ruta).preparar()

    with sqlite3.connect(ruta) as conexion:
        assert conexion.execute("SELECT token_id FROM sesion").fetchall() == [("jti",)]
    assert sorted(archivo.name for archivo in tmp_path.iterdir()) == ["matera.respaldo-v0.sqlite", "matera.sqlite"]


def test_una_base_nueva_queda_en_la_ultima_version_sin_copia(tmp_path):
    ruta = tmp_path / "matera.sqlite"

    BaseDatos(ruta).preparar()

    with sqlite3.connect(ruta) as conexion:
        assert conexion.execute("PRAGMA user_version").fetchone()[0] == VERSION
    assert [archivo.name for archivo in tmp_path.iterdir()] == ["matera.sqlite"]


MARCADOR_JUEGO = "-- Juego (corte 3, version 4)."


def _base_v3(ruta) -> None:
    """Una base de la fase 2 (version 3): el esquema de hoy sin las tablas del juego, con datos."""
    esquema = ESQUEMA.read_text(encoding="utf-8")
    assert esquema.count(MARCADOR_JUEGO) == 1, "cambio el comentario que abre las tablas del juego en esquema.sql"
    with sqlite3.connect(ruta) as conexion:
        conexion.executescript(esquema.split(MARCADOR_JUEGO)[0])
        conexion.executescript(
            """
            INSERT INTO especie (nombre) VALUES ('potos'), ('helecho'), ('orquidea');
            INSERT INTO usuario (correo, nombre, hash_contrasena) VALUES ('ana@correo.co', 'Ana', 'h');
            INSERT INTO sesion (token_id, usuario_id, vence_en) VALUES ('jti', 1, '2026-11-30T00:00:00+00:00');
            INSERT INTO planta (usuario_id, especie, apodo) VALUES (1, 'helecho', 'sala');
            INSERT INTO sensor (codigo, planta_id, hash_clave, token_id) VALUES ('MT-0001-AA', 1, 'huella-clave', 'jti-sensor');
            INSERT INTO medicion (planta_id, momento, estado, origen) VALUES (1, '2026-10-29T15:00:00.000000+00:00', 'CRITICO', 'MT-0001-AA');
            INSERT INTO lectura (medicion_id, parametro, valor, estado) VALUES (1, 'humedad', 53, 'BAJO');
            PRAGMA user_version = 3;
            """
        )


def _tablas(conexion) -> set[str]:
    return {fila[0] for fila in conexion.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}


def test_una_base_v3_pasa_a_la_v4_con_las_tablas_del_juego_sin_perder_datos(tmp_path):
    ruta = tmp_path / "matera.sqlite"
    _base_v3(ruta)

    BaseDatos(ruta).preparar()

    with sqlite3.connect(ruta) as conexion:
        assert conexion.execute("PRAGMA user_version").fetchone()[0] == VERSION == 4
        assert {"movimiento_puntaje", "jugador", "ritmo_crecimiento"} <= _tablas(conexion)
        # Las sesiones abiertas, los sensores con su token y el historial siguen igual.
        assert conexion.execute("SELECT token_id FROM sesion").fetchall() == [("jti",)]
        assert conexion.execute("SELECT codigo, hash_clave, token_id FROM sensor").fetchall() == [
            ("MT-0001-AA", "huella-clave", "jti-sensor")
        ]
        assert conexion.execute("SELECT estado FROM medicion").fetchall() == [("CRITICO",)]
        assert conexion.execute("SELECT parametro, valor FROM lectura").fetchall() == [("humedad", 53.0)]
        # Todos empiezan en 0: las lecturas viejas no dejan movimientos.
        assert conexion.execute("SELECT COUNT(*) FROM movimiento_puntaje").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM jugador").fetchone()[0] == 0
        # Solo las especies que existen reciben su ritmo; la que agrego el admin crece al ritmo por defecto.
        assert conexion.execute("SELECT * FROM ritmo_crecimiento ORDER BY especie").fetchall() == [
            ("helecho", 1, 3, 7),
            ("potos", 1, 3, 6),
        ]
    copia = tmp_path / "matera.respaldo-v3.sqlite"
    with sqlite3.connect(copia) as conexion:
        assert conexion.execute("PRAGMA user_version").fetchone()[0] == 3
        assert "jugador" not in _tablas(conexion)
        assert conexion.execute("SELECT apodo FROM planta").fetchall() == [("sala",)]


def test_los_ritmos_se_cargan_una_sola_vez(tmp_path):
    ruta = tmp_path / "matera.sqlite"
    _base_v3(ruta)
    BaseDatos(ruta).preparar()
    with sqlite3.connect(ruta) as conexion:
        conexion.execute("DELETE FROM ritmo_crecimiento WHERE especie = 'potos'")

    BaseDatos(ruta).preparar()

    with sqlite3.connect(ruta) as conexion:
        assert conexion.execute("SELECT especie FROM ritmo_crecimiento").fetchall() == [("helecho",)]
    assert sorted(archivo.name for archivo in tmp_path.iterdir()) == ["matera.respaldo-v3.sqlite", "matera.sqlite"]


def test_una_base_nueva_trae_los_ritmos_de_las_cinco_especies(tmp_path):
    ruta = tmp_path / "matera.sqlite"

    BaseDatos(ruta).preparar()

    with sqlite3.connect(ruta) as conexion:
        assert conexion.execute("SELECT * FROM ritmo_crecimiento ORDER BY especie").fetchall() == [
            ("helecho", 1, 3, 7),
            ("lavanda", 1, 4, 8),
            ("potos", 1, 3, 6),
            ("sansevieria", 2, 5, 10),
            ("suculenta", 2, 6, 12),
        ]
