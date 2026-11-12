"""Configuracion leida de variables de entorno, con valores por defecto para desarrollo."""
import math
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

from dominio.mascota import CuidadoDeMascota, RelojDeJuego
from infraestructura import red_local
from infraestructura.seguridad import ITERACIONES_RECOMENDADAS

_BACKEND = Path(__file__).resolve().parent.parent

# Origenes desde los que se sirve el front. Para el navegador, localhost y
# 127.0.0.1 son origenes distintos, por eso van los dos.
_ORIGENES_POR_DEFECTO = "http://localhost:5500,http://127.0.0.1:5500"
TABLAS_DE_REFERENCIA = ("bd", "csv")


def origenes_de_la_red(host: str, puerto_front: int) -> tuple[str, ...]:
    """Con la API abierta a la red (0.0.0.0), el front tambien se abre desde el celular: http://<ip>:<puerto>."""
    if host.strip() != "0.0.0.0":
        return ()
    return tuple(f"http://{ip}:{puerto_front}" for ip in red_local.ips_ipv4())


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
    # La copia en CSV. Sin ruta, va junto a su base: con la base por defecto es la del repositorio,
    # y con una base fuera de Google Drive (MATERA_RUTA_BD) queda afuera con ella.
    ruta_csv: Path | None = None
    # El reloj del juego (corte 3): cuantos minutos reales dura un dia de juego. 1440 es el tiempo
    # real; en la demo, con 2, una hora de juego dura 5 segundos y la matera crece en minutos.
    minutos_por_dia_juego: float = 1440
    # Sin lecturas en estos minutos reales, la matera duerme. No cambian con el reloj del juego.
    minutos_sin_lecturas: float = CuidadoDeMascota.MINUTOS_PARA_DORMIR

    def __post_init__(self) -> None:
        if self.tabla_referencia not in TABLAS_DE_REFERENCIA:
            raise ValueError(
                f"MATERA_TABLA_REFERENCIA debe ser bd o csv, no '{self.tabla_referencia}'."
            )
        # Se arma la regla con el reloj, como lo hara main.py: asi tambien se rechaza un dia tan largo
        # que la ventana de la condicion se sale del calendario, que si no fallaria en cada consulta.
        if not _positivo(self.minutos_por_dia_juego) or not _sirve(
            lambda: CuidadoDeMascota(RelojDeJuego(self.minutos_por_dia_juego))
        ):
            raise ValueError(
                "MATERA_MINUTOS_POR_DIA_JUEGO debe ser un número de minutos mayor que cero y no tan grande que "
                "6 horas de juego se salgan del calendario (1440 es el tiempo real; 2, para la demo), "
                f"no '{self.minutos_por_dia_juego}'."
            )
        if not _positivo(self.minutos_sin_lecturas) or not _sirve(
            lambda: CuidadoDeMascota(RelojDeJuego(), self.minutos_sin_lecturas)
        ):
            raise ValueError(
                f"MATERA_MINUTOS_SIN_LECTURAS debe ser un número de minutos mayor que cero, no '{self.minutos_sin_lecturas}'."
            )

    @property
    def reloj_de_juego(self) -> RelojDeJuego:
        return RelojDeJuego(self.minutos_por_dia_juego)

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
        host = os.environ.get("MATERA_HOST", "127.0.0.1").strip()
        propios = tuple(origen.strip() for origen in origenes.split(",") if origen.strip())
        de_la_red = origenes_de_la_red(host, int(os.environ.get("MATERA_PUERTO_FRONT", "5500")))
        return cls(
            puerto=int(os.environ.get("MATERA_PUERTO", "5000")),
            ruta_bd=Path(os.environ.get("MATERA_RUTA_BD", _BACKEND / "datos" / "matera.sqlite")),
            origenes_cors=propios + tuple(o for o in de_la_red if o not in propios),
            duracion_sesion=timedelta(days=float(os.environ.get("MATERA_DIAS_SESION", "7"))),
            duracion_token_dispositivo=timedelta(hours=float(os.environ.get("MATERA_HORAS_TOKEN_DISPOSITIVO", "24"))),
            host=host,
            secreto_jwt=os.environ.get("MATERA_JWT_SECRETO", "").strip() or None,
            tabla_referencia=os.environ.get("MATERA_TABLA_REFERENCIA", "bd").strip().lower(),
            ruta_csv=Path(os.environ["MATERA_RUTA_CSV"]) if os.environ.get("MATERA_RUTA_CSV", "").strip() else None,
            minutos_por_dia_juego=_minutos("MATERA_MINUTOS_POR_DIA_JUEGO", 1440),
            minutos_sin_lecturas=_minutos("MATERA_MINUTOS_SIN_LECTURAS", CuidadoDeMascota.MINUTOS_PARA_DORMIR),
        )


def _minutos(variable: str, por_defecto: float) -> float:
    """Un numero de minutos de una variable de entorno. Si no es un numero, no arranca y dice cual fallo."""
    texto = os.environ.get(variable, "").strip()
    if not texto:
        return por_defecto
    try:
        return float(texto)
    except ValueError:
        raise ValueError(
            f"{variable} debe ser un número de minutos mayor que cero, con punto decimal, no '{texto}'."
        ) from None


def _positivo(numero: float) -> bool:
    return isinstance(numero, (int, float)) and not isinstance(numero, bool) and math.isfinite(numero) and numero > 0


def _sirve(armar: Callable[[], object]) -> bool:
    """Si el dominio acepta el valor. No lo acepta, por ejemplo, si una hora de juego dura menos de un
    microsegundo, si los minutos no caben en un timedelta o si la ventana de la condicion no cabe en el calendario."""
    try:
        armar()
    except (ValueError, OverflowError):
        return False
    return True
