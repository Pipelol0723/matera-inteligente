"""Lo que devuelven los puertos de entrada del juego: datos sin logica, hechos con tipos del dominio.

Van aparte de dominio.resultados para que el juego entre sin modificar ningun
archivo existente. La matera Tamagotchi (Mascota) esta en dominio.mascota,
junto a la regla que la arma.
"""
from dataclasses import dataclass
from datetime import datetime

from dominio.estados import EstadoGlobal
from dominio.juego import ApodoJugador
from dominio.plantas import Planta


@dataclass(frozen=True)
class PuntajeDeMatera:
    """Lo que lleva sumado una matera que todavia existe."""

    planta: Planta
    puntos: int


@dataclass(frozen=True)
class MovimientoReciente:
    """Un movimiento del puntaje, con su planta. La planta es None si ya se borro."""

    momento: datetime
    estado: EstadoGlobal
    puntos: int
    planta: Planta | None


@dataclass(frozen=True)
class PuntajeUsuario:
    """Tus puntos: el total (incluye los de materas borradas), por matera y los ultimos movimientos."""

    total: int
    materas: list[PuntajeDeMatera]
    movimientos: list[MovimientoReciente]


@dataclass(frozen=True)
class PosicionTabla:
    """Una fila de la tabla de posiciones. soy_yo marca la de quien pregunta."""

    posicion: int
    apodo: ApodoJugador
    puntos: int
    soy_yo: bool
