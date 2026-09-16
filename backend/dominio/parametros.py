"""Parametros que se miden en una planta.

El resto del sistema recorre PARAMETROS en vez de nombrar humedad, luz o
temperatura. Agregar un parametro nuevo (por ejemplo el pH) es agregar una
constante y sumarla a PARAMETROS; el evaluador y la regla no cambian (OCP).
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Parametro:
    """Una magnitud medible, con su unidad y los limites de lo fisicamente posible."""

    nombre: str
    unidad: str
    minimo_fisico: float
    maximo_fisico: float


# Humedad del sustrato: es un porcentaje, no puede salir de 0 a 100.
HUMEDAD = Parametro("humedad", "%", 0.0, 100.0)

# El sol directo al mediodia ronda los 100 000 lux; se deja margen.
LUZ = Parametro("luz", "lux", 0.0, 150_000.0)

# Fuera de este intervalo el dato es una falla del sensor, no una planta.
TEMPERATURA = Parametro("temperatura", "C", -50.0, 60.0)

PARAMETROS: tuple[Parametro, ...] = (HUMEDAD, LUZ, TEMPERATURA)
