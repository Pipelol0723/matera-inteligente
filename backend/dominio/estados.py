"""Estados posibles de un parametro y de la planta completa."""
from enum import Enum


class EstadoParametro(str, Enum):
    """Resultado de comparar un valor contra su rango optimo (RF2)."""

    BAJO = "BAJO"
    OPTIMO = "OPTIMO"
    ALTO = "ALTO"


class EstadoGlobal(str, Enum):
    """Estado de la planta, derivado de los estados de sus parametros (RF3)."""

    SALUDABLE = "SALUDABLE"
    EN_RIESGO = "EN_RIESGO"
    CRITICO = "CRITICO"
