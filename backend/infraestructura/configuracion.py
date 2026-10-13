"""Configuracion leida de variables de entorno, con valores por defecto para desarrollo."""
import os
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from infraestructura.seguridad import ITERACIONES_RECOMENDADAS

_BACKEND = Path(__file__).resolve().parent.parent

# Origenes desde los que se sirve el front. Para el navegador, localhost y
# 127.0.0.1 son origenes distintos, por eso van los dos.
_ORIGENES_POR_DEFECTO = "http://localhost:5500,http://127.0.0.1:5500"


@dataclass(frozen=True)
class Configuracion:
    puerto: int
    # Archivo SQLite. Git lo ignora; si el repositorio esta en una carpeta sincronizada
    # (Google Drive, OneDrive), conviene apuntarlo afuera con MATERA_RUTA_BD.
    ruta_bd: Path
    origenes_cors: tuple[str, ...]
    duracion_sesion: timedelta = timedelta(days=7)
    # Las pruebas bajan este numero: con 600 000 iteraciones cada registro tarda casi un segundo.
    iteraciones_contrasena: int = ITERACIONES_RECOMENDADAS
    # Por defecto la API solo responde en este PC. Para que un ESP32 del mismo WiFi la alcance,
    # MATERA_HOST=0.0.0.0 la abre a la red (y hay que permitir el puerto en el firewall).
    host: str = "127.0.0.1"

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        origenes = os.environ.get("MATERA_ORIGENES_CORS", _ORIGENES_POR_DEFECTO)
        return cls(
            puerto=int(os.environ.get("MATERA_PUERTO", "5000")),
            ruta_bd=Path(os.environ.get("MATERA_RUTA_BD", _BACKEND / "datos" / "matera.sqlite")),
            origenes_cors=tuple(origen.strip() for origen in origenes.split(",") if origen.strip()),
            duracion_sesion=timedelta(days=float(os.environ.get("MATERA_DIAS_SESION", "7"))),
            host=os.environ.get("MATERA_HOST", "127.0.0.1").strip(),
        )
