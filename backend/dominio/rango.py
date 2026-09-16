"""Rango optimo de un parametro para una especie."""
from dataclasses import dataclass

from dominio.errores import RangoInvalido
from dominio.estados import EstadoParametro


@dataclass(frozen=True)
class Rango:
    """Intervalo [minimo, maximo]. Los dos limites cuentan como OPTIMO."""

    minimo: float
    maximo: float

    def __post_init__(self) -> None:
        if not self.minimo < self.maximo:
            raise RangoInvalido(self.minimo, self.maximo)

    @property
    def ancho(self) -> float:
        return self.maximo - self.minimo

    def clasificar(self, valor: float) -> EstadoParametro:
        if valor < self.minimo:
            return EstadoParametro.BAJO
        if valor > self.maximo:
            return EstadoParametro.ALTO
        return EstadoParametro.OPTIMO

    def desviacion(self, valor: float) -> float:
        """Distancia del valor al limite mas cercano, medida en anchos del rango.

        Es 0 dentro del rango. Dividir por el ancho permite comparar lux, grados
        y porcentaje con un mismo umbral.
        """
        if valor < self.minimo:
            return (self.minimo - valor) / self.ancho
        if valor > self.maximo:
            return (valor - self.maximo) / self.ancho
        return 0.0
