"""Lo que reportan los sensores: una lectura por parametro."""
import math
from dataclasses import dataclass

from dominio.errores import MedicionInvalida, ValorFisicamenteImposible
from dominio.parametros import Parametro


@dataclass(frozen=True)
class Lectura:
    """Valor medido de un parametro.

    No se puede crear fuera de los limites fisicos: la regla vive aqui y no en
    el borde HTTP, para que cualquier entrada (HTTP hoy, MQTT manana) la cumpla.
    """

    parametro: Parametro
    valor: float

    def __post_init__(self) -> None:
        p = self.parametro
        if not math.isfinite(self.valor) or not p.minimo_fisico <= self.valor <= p.maximo_fisico:
            raise ValorFisicamenteImposible(p, self.valor)


@dataclass(frozen=True)
class Medicion:
    """Conjunto de lecturas tomadas al mismo tiempo, como maximo una por parametro."""

    lecturas: tuple[Lectura, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "lecturas", tuple(self.lecturas))
        if not self.lecturas:
            raise MedicionInvalida("La medición no trae ninguna lectura.")
        nombres = [lectura.parametro.nombre for lectura in self.lecturas]
        if len(set(nombres)) != len(nombres):
            raise MedicionInvalida("La medición repite un parámetro.")
