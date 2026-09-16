"""Reglas de agregacion: como pasar de los estados de cada parametro al estado global (RF3).

ReglaAgregacion es la abstraccion. Cambiar de regla es escribir otra clase y
cambiar una linea en main.py; el evaluador no se modifica (OCP).
"""
from abc import ABC, abstractmethod
from collections.abc import Sequence

from dominio.diagnostico import ResultadoParametro
from dominio.estados import EstadoGlobal


class ReglaAgregacion(ABC):
    @abstractmethod
    def agregar(self, resultados: Sequence[ResultadoParametro]) -> EstadoGlobal:
        """Decide el estado global a partir del resultado de cada parametro."""


class ReglaHibrida(ReglaAgregacion):
    """Regla elegida por el equipo: cuenta cuantos parametros fallan y cuanto se desvian.

    - SALUDABLE: todos los parametros en OPTIMO.
    - CRITICO: dos o mas fuera de rango, o alguno desviado mas que el umbral.
    - EN_RIESGO: exactamente uno fuera, con desviacion menor o igual al umbral.
    """

    def __init__(self, umbral: float = 0.5):
        if umbral <= 0:
            raise ValueError("El umbral de desviación debe ser mayor que cero.")
        self._umbral = umbral

    def agregar(self, resultados: Sequence[ResultadoParametro]) -> EstadoGlobal:
        fuera = [r for r in resultados if r.fuera_de_rango]
        if not fuera:
            return EstadoGlobal.SALUDABLE
        if len(fuera) >= 2 or any(r.desviacion > self._umbral for r in fuera):
            return EstadoGlobal.CRITICO
        return EstadoGlobal.EN_RIESGO


class ReglaConteo(ReglaAgregacion):
    """Alternativa descartada: solo cuenta los parametros fuera de rango.

    Se conserva para mostrar que la regla se puede cambiar sin tocar el evaluador.
    """

    def agregar(self, resultados: Sequence[ResultadoParametro]) -> EstadoGlobal:
        fuera = sum(1 for r in resultados if r.fuera_de_rango)
        if fuera == 0:
            return EstadoGlobal.SALUDABLE
        if fuera == 1:
            return EstadoGlobal.EN_RIESGO
        return EstadoGlobal.CRITICO
