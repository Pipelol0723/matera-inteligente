"""Historial de una planta: lo que se midio y como quedo en ese momento (corte 2).

Guarda el estado calculado entonces, no lo recalcula al consultar: si despues
cambian los rangos de la especie, el pasado no se reescribe solo. Hay una
lectura por parametro, asi que agregar el pH no cambia esta clase.
"""
from dataclasses import dataclass
from datetime import datetime

from dominio.diagnostico import Diagnostico
from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.parametros import Parametro

# Origen de una medicion escrita a mano; la de un sensor lleva su codigo.
ORIGEN_MANUAL = "MANUAL"


@dataclass(frozen=True)
class LecturaRegistrada:
    parametro: Parametro
    valor: float
    estado: EstadoParametro


@dataclass(frozen=True)
class RegistroMedicion:
    planta_id: int
    momento: datetime
    estado: EstadoGlobal
    lecturas: tuple[LecturaRegistrada, ...]
    origen: str

    @classmethod
    def desde(cls, diagnostico: Diagnostico, planta_id: int, momento: datetime, origen: str) -> "RegistroMedicion":
        """Toma los estados del Diagnostico ya calculado. Las recomendaciones no se guardan."""
        lecturas = tuple(
            LecturaRegistrada(resultado.parametro, resultado.valor, resultado.estado)
            for resultado in diagnostico.resultados
        )
        return cls(planta_id, momento, diagnostico.estado, lecturas, origen)
