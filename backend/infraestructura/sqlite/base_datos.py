"""La base SQLite: abre una conexion por operacion y prepara las tablas al arrancar."""
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_DATOS = Path(__file__).resolve().parents[2] / "datos"
ESQUEMA = _DATOS / "esquema.sql"
CARGA = _DATOS / "carga.sql"

# Version del esquema, guardada en PRAGMA user_version. Una base sin numero es de antes de la fase 2.
VERSION = 2
# Lo que hay que hacer en una base que ya tenia tablas para llegar a cada version. Despues,
# esquema.sql crea lo que falte. Una base nueva no las necesita: esquema.sql ya trae lo ultimo.
_MIGRACIONES = {
    # La sesion guarda el id del JWT, no la huella del token opaco de antes: esas sesiones ya no sirven.
    2: "DROP TABLE IF EXISTS sesion;",
}


class BaseDatos:
    """Cada operacion de un repositorio abre su propia conexion y la cierra al terminar.

    Flask atiende cada peticion en un hilo distinto, y un objeto de sqlite3 no se
    puede usar desde otro hilo: con una sola conexion compartida, el servidor real
    fallaria aunque las pruebas con test_client pasaran. Ademas, SQLite trae las
    llaves foraneas apagadas y hay que activarlas en cada conexion.
    """

    def __init__(self, ruta: str | Path):
        self._ruta = Path(ruta)

    @contextmanager
    def conexion(self) -> Iterator[sqlite3.Connection]:
        conexion = sqlite3.connect(self._ruta)
        conexion.row_factory = sqlite3.Row
        conexion.execute("PRAGMA foreign_keys = ON")
        try:
            # Confirma la transaccion si el bloque termina bien y la deshace si lanza una excepcion.
            with conexion:
                yield conexion
        finally:
            conexion.close()

    def preparar(self, esquema: Path = ESQUEMA, carga: Path | None = CARGA) -> "BaseDatos":
        """Migra una base vieja, crea las tablas que falten y, si no hay ninguna especie, ejecuta carga.sql.

        Antes de migrar una base con datos saca una copia al lado, por ejemplo
        matera.respaldo-v0.sqlite: usuarios, plantas, sensores e historial no se tocan,
        pero si algo sale mal, la copia queda.
        """
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.conexion() as conexion:
            version = conexion.execute("PRAGMA user_version").fetchone()[0]
            con_tablas = conexion.execute("SELECT 1 FROM sqlite_master WHERE name = 'usuario'").fetchone() is not None
            pendientes = [sql for numero, sql in sorted(_MIGRACIONES.items()) if numero > version] if con_tablas else []
            if pendientes:
                self._respaldar(conexion, version)
            # Todo en una transaccion: si algo falla, la base queda como estaba.
            script = "\n".join([*pendientes, _leer(esquema), f"PRAGMA user_version = {VERSION};"])
            conexion.executescript(_en_una_transaccion(script))
            sin_especies = conexion.execute("SELECT COUNT(*) FROM especie").fetchone()[0] == 0
            if carga is not None and sin_especies:
                conexion.executescript(_en_una_transaccion(_leer(carga)))
        return self

    def _respaldar(self, conexion: sqlite3.Connection, version: int) -> None:
        copia = self._ruta.with_name(f"{self._ruta.stem}.respaldo-v{version}{self._ruta.suffix}")
        if copia.exists():
            return  # se conserva la primera copia, la de antes de cualquier intento
        destino = sqlite3.connect(copia)
        try:
            conexion.backup(destino)
        finally:
            destino.close()


def _leer(archivo: Path) -> str:
    return archivo.read_text(encoding="utf-8")


def _en_una_transaccion(sql: str) -> str:
    # Suelta, cada sentencia seria su propia transaccion, con su escritura a disco:
    # en Windows, preparar una base nueva pasa de unos 2 segundos a 0,1.
    return f"BEGIN;\n{sql}\nCOMMIT;"
