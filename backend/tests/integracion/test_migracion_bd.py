"""La migracion de una base de antes de la fase 2: se saca una copia, se cambia la sesion y los datos quedan."""
import sqlite3

from infraestructura.sqlite.base_datos import ESQUEMA, VERSION, BaseDatos


def _base_de_antes(ruta) -> None:
    """Una base como la de antes de la fase 2: sin numero de version y con la sesion por huella del token opaco."""
    esquema = ESQUEMA.read_text(encoding="utf-8").replace("token_id   TEXT PRIMARY KEY,", "hash_token TEXT PRIMARY KEY,")
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
        assert conexion.execute("SELECT codigo, hash_clave FROM sensor").fetchall() == [("MT-0001-AA", "huella-clave")]
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
