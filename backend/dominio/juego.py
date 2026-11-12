"""El puntaje del juego y quien participa en la tabla de posiciones (corte 3).

Todo vive en archivos nuevos: el juego solo lee el EstadoGlobal que ya calcula
la regla hibrida del corte 1, y ningun archivo existente del dominio cambia
(principio abierto/cerrado). Las reglas de la matera Tamagotchi estan en
dominio.mascota.
"""
import re
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from types import MappingProxyType

from dominio.errores_juego import ApodoInvalido, ParticipacionRequerida
from dominio.estados import EstadoGlobal


class ReglaDeCuidado:
    """Cuanto vale cada lectura aceptada, segun el estado global de la planta.

    Restar 5 en EN_RIESGO es decision del equipo: el profesor dijo que lo normal
    no suma ni resta. Si lo confirma asi, se cambia solo esta tabla.
    """

    PUNTOS = MappingProxyType({
        EstadoGlobal.SALUDABLE: 10,
        EstadoGlobal.EN_RIESGO: -5,
        EstadoGlobal.CRITICO: -10,
    })

    def puntos(self, estado: EstadoGlobal) -> int:
        return self.PUNTOS[estado]

    def movimiento(self, usuario_id: int, planta_id: int, momento: datetime, estado: EstadoGlobal) -> "MovimientoPuntaje":
        """El movimiento que deja una lectura. El momento es la hora del servidor, no la del dispositivo."""
        return MovimientoPuntaje(usuario_id, planta_id, momento, estado, self.puntos(estado))


@dataclass(frozen=True)
class MovimientoPuntaje:
    """Lo que sumo o resto una lectura aceptada.

    planta_id es None cuando la planta ya se borro: sus puntos siguen siendo del
    dueno, pero no pasan a una planta nueva que reciba el mismo id.
    """

    usuario_id: int
    planta_id: int | None
    momento: datetime
    estado: EstadoGlobal
    puntos: int


_FORMA_APODO = re.compile(r"[A-Za-z0-9_-]+")


@dataclass(frozen=True, eq=False)
class ApodoJugador:
    """Como aparece alguien en la tabla de posiciones, sin mostrar su nombre ni su correo.

    Se guarda como lo escribio, pero 'Pipe_Verde' y 'pipe_verde' son el mismo
    apodo: la igualdad y el hash usan la clave en minusculas.
    """

    valor: str

    MINIMO = 3
    MAXIMO = 20

    def __post_init__(self) -> None:
        texto = self.valor.strip() if isinstance(self.valor, str) else ""
        if not self.MINIMO <= len(texto) <= self.MAXIMO or not _FORMA_APODO.fullmatch(texto):
            raise ApodoInvalido(self.valor, self.MINIMO, self.MAXIMO)
        object.__setattr__(self, "valor", texto)

    @property
    def clave(self) -> str:
        """La forma de comparar apodos: sin importar mayusculas."""
        return self.valor.lower()

    def __eq__(self, otro: object) -> bool:
        return isinstance(otro, ApodoJugador) and self.clave == otro.clave

    def __hash__(self) -> int:
        return hash(self.clave)


class EstadoParticipacion(str, Enum):
    SIN_DECIDIR = "SIN_DECIDIR"
    PARTICIPA = "PARTICIPA"
    NO_PARTICIPA = "NO_PARTICIPA"


@dataclass(frozen=True)
class Participacion:
    """Si alguien aparece en la tabla de posiciones, y con que apodo.

    Solo quien participa tiene apodo: al dejar de participar, el apodo queda
    libre para otro. Quien no participa conserva su puntaje y sus materas.
    """

    usuario_id: int
    estado: EstadoParticipacion
    apodo: ApodoJugador | None = None

    def __post_init__(self) -> None:
        if (self.estado is EstadoParticipacion.PARTICIPA) != (self.apodo is not None):
            raise ValueError("Solo quien participa tiene apodo de jugador, y quien participa tiene uno.")

    @classmethod
    def sin_decidir(cls, usuario_id: int) -> "Participacion":
        """Todavia no respondio la pregunta de la app: no aparece en la tabla."""
        return cls(usuario_id, EstadoParticipacion.SIN_DECIDIR)

    @classmethod
    def participa(cls, usuario_id: int, apodo: ApodoJugador) -> "Participacion":
        return cls(usuario_id, EstadoParticipacion.PARTICIPA, apodo)

    @classmethod
    def no_participa(cls, usuario_id: int) -> "Participacion":
        return cls(usuario_id, EstadoParticipacion.NO_PARTICIPA)

    @property
    def en_tabla(self) -> bool:
        return self.estado is EstadoParticipacion.PARTICIPA

    def exigir_participacion(self) -> None:
        """La regla «quien no participa no ve la tabla», venga el pedido por HTTP o por otro medio."""
        if not self.en_tabla:
            raise ParticipacionRequerida()
