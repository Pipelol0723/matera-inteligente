"""Resultado de evaluar una medicion contra los rangos de una especie."""
from dataclasses import dataclass

from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.parametros import Parametro
from dominio.rango import Rango


@dataclass(frozen=True)
class ResultadoParametro:
    """Como quedo un parametro: su valor, su rango, su estado y cuanto se desvio."""

    parametro: Parametro
    valor: float
    rango: Rango
    estado: EstadoParametro
    desviacion: float

    @property
    def fuera_de_rango(self) -> bool:
        return self.estado is not EstadoParametro.OPTIMO


@dataclass(frozen=True)
class Diagnostico:
    """Estado global de la planta, detalle por parametro y recomendaciones (RF2-RF4)."""

    especie: str
    estado: EstadoGlobal
    resultados: tuple[ResultadoParametro, ...]
    recomendaciones: tuple[str, ...]
