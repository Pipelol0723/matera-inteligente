import pytest

from dominio.diagnostico import ResultadoParametro
from dominio.estados import EstadoGlobal
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.rango import Rango
from dominio.reglas import ReglaConteo, ReglaHibrida


def _resultado(parametro, rango, valor):
    return ResultadoParametro(parametro, valor, rango, rango.clasificar(valor), rango.desviacion(valor))


def _sansevieria(humedad, luz, temperatura):
    """Resultados con los rangos de ejemplo: humedad 20-45, luz 200-1500, temperatura 15-29."""
    return (
        _resultado(HUMEDAD, Rango(20, 45), humedad),
        _resultado(LUZ, Rango(200, 1500), luz),
        _resultado(TEMPERATURA, Rango(15, 29), temperatura),
    )


@pytest.mark.parametrize(
    ("humedad", "luz", "temperatura", "esperado"),
    [
        (30, 800, 22, EstadoGlobal.SALUDABLE),
        (18, 800, 22, EstadoGlobal.EN_RIESGO),  # uno fuera, desviacion 0.08
        (7.5, 800, 22, EstadoGlobal.EN_RIESGO),  # justo en el umbral: 0.5 no es mayor que 0.5
        (1, 800, 22, EstadoGlobal.CRITICO),  # uno fuera, desviacion 0.76
        (18, 1600, 22, EstadoGlobal.CRITICO),  # dos fuera, aunque sean leves
    ],
)
def test_regla_hibrida(humedad, luz, temperatura, esperado):
    assert ReglaHibrida(umbral=0.5).agregar(_sansevieria(humedad, luz, temperatura)) is esperado


@pytest.mark.parametrize(
    ("humedad", "luz", "temperatura", "esperado"),
    [
        (30, 800, 22, EstadoGlobal.SALUDABLE),
        (1, 800, 22, EstadoGlobal.EN_RIESGO),  # la debilidad que llevo a elegir la hibrida
        (18, 1600, 22, EstadoGlobal.CRITICO),
    ],
)
def test_regla_conteo(humedad, luz, temperatura, esperado):
    assert ReglaConteo().agregar(_sansevieria(humedad, luz, temperatura)) is esperado


@pytest.mark.parametrize("umbral", [0, -0.5])
def test_la_regla_hibrida_exige_un_umbral_positivo(umbral):
    with pytest.raises(ValueError):
        ReglaHibrida(umbral=umbral)
