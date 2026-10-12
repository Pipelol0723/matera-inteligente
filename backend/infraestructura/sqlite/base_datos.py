"""La base SQLite: abre una conexion por operacion y prepara las tablas al arrancar."""
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

_DATOS = Path(__file__).resolve().parents[2] / "datos"
ESQUEMA = _DATOS / "esquema.sql"
CARGA = _DATOS / "carga.sql"


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
        """Crea las tablas que falten y, si no hay ninguna especie, ejecuta carga.sql."""
        self._ruta.parent.mkdir(parents=True, exist_ok=True)
        with self.conexion() as conexion:
            conexion.executescript(_en_una_transaccion(esquema))
            sin_especies = conexion.execute("SELECT COUNT(*) FROM especie").fetchone()[0] == 0
            if carga is not None and sin_especies:
                conexion.executescript(_en_una_transaccion(carga))
        return self


def _en_una_transaccion(archivo: Path) -> str:
    # Suelta, cada sentencia seria su propia transaccion, con su escritura a disco:
    # en Windows, preparar una base nueva pasa de unos 2 segundos a 0,1.
    return f"BEGIN;\n{archivo.read_text(encoding='utf-8')}\nCOMMIT;"
