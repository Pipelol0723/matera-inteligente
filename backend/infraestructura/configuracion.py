"""Configuracion leida de variables de entorno, con valores por defecto para desarrollo."""
import os
from dataclasses import dataclass
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent

# Origenes desde los que se sirve el front. Para el navegador, localhost y
# 127.0.0.1 son origenes distintos, por eso van los dos.
_ORIGENES_POR_DEFECTO = "http://localhost:5500,http://127.0.0.1:5500"


@dataclass(frozen=True)
class Configuracion:
    puerto: int
    ruta_csv: Path
    origenes_cors: tuple[str, ...]

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        origenes = os.environ.get("MATERA_ORIGENES_CORS", _ORIGENES_POR_DEFECTO)
        return cls(
            puerto=int(os.environ.get("MATERA_PUERTO", "5000")),
            ruta_csv=Path(os.environ.get("MATERA_RUTA_CSV", _BACKEND / "datos" / "especies.csv")),
            origenes_cors=tuple(origen.strip() for origen in origenes.split(",") if origen.strip()),
        )
