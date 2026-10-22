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
TABLAS_DE_REFERENCIA = ("bd", "csv")


@dataclass(frozen=True)
class Configuracion:
    puerto: int
    # Archivo SQLite. Git lo ignora; si el repositorio esta en una carpeta sincronizada
    # (Google Drive, OneDrive), conviene apuntarlo afuera con MATERA_RUTA_BD.
    ruta_bd: Path
    origenes_cors: tuple[str, ...]
    duracion_sesion: timedelta = timedelta(days=7)
    # El token de un dispositivo dura menos que una sesion: la placa lo vuelve a canjear con su clave.
    duracion_token_dispositivo: timedelta = timedelta(hours=24)
    # Las pruebas bajan este numero: con 600 000 iteraciones cada registro tarda casi un segundo.
    iteraciones_contrasena: int = ITERACIONES_RECOMENDADAS
    # Por defecto la API solo responde en este PC. Para que un ESP32 del mismo WiFi la alcance,
    # MATERA_HOST=0.0.0.0 la abre a la red (y hay que permitir el puerto en el firewall).
    host: str = "127.0.0.1"
    # Con que se firman los JWT. Si falta, se usa el del archivo ruta_secreto_jwt (y se crea si no existe).
    secreto_jwt: str | None = None
    # De donde sale la tabla de especies (R4): "bd" (SQLite) o "csv" (la copia de solo lectura).
    tabla_referencia: str = "bd"
    # La copia en CSV. Sin ruta, va junto a la base; desde_entorno usa la del repositorio.
    ruta_csv: Path | None = None

    def __post_init__(self) -> None:
        if self.tabla_referencia not in TABLAS_DE_REFERENCIA:
            raise ValueError(
                f"MATERA_TABLA_REFERENCIA debe ser bd o csv, no '{self.tabla_referencia}'."
            )

    @property
    def ruta_tabla_csv(self) -> Path:
        return self.ruta_csv or self.ruta_bd.with_name("especies.csv")

    @property
    def ruta_secreto_jwt(self) -> Path:
        """Junto a la base: matera.sqlite -> matera.sqlite.secreto-jwt. Git lo ignora."""
        return self.ruta_bd.with_name(self.ruta_bd.name + ".secreto-jwt")

    @classmethod
    def desde_entorno(cls) -> "Configuracion":
        origenes = os.environ.get("MATERA_ORIGENES_CORS", _ORIGENES_POR_DEFECTO)
        return cls(
            puerto=int(os.environ.get("MATERA_PUERTO", "5000")),
            ruta_bd=Path(os.environ.get("MATERA_RUTA_BD", _BACKEND / "datos" / "matera.sqlite")),
            origenes_cors=tuple(origen.strip() for origen in origenes.split(",") if origen.strip()),
            duracion_sesion=timedelta(days=float(os.environ.get("MATERA_DIAS_SESION", "7"))),
            duracion_token_dispositivo=timedelta(hours=float(os.environ.get("MATERA_HORAS_TOKEN_DISPOSITIVO", "24"))),
            host=os.environ.get("MATERA_HOST", "127.0.0.1").strip(),
            secreto_jwt=os.environ.get("MATERA_JWT_SECRETO", "").strip() or None,
            tabla_referencia=os.environ.get("MATERA_TABLA_REFERENCIA", "bd").strip().lower(),
            ruta_csv=Path(os.environ.get("MATERA_RUTA_CSV", _BACKEND / "datos" / "especies.csv")),
        )
