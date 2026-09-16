import pytest

from dominio.errores import RangoInvalido
from dominio.estados import EstadoParametro
from dominio.rango import Rango

# Humedad optima de la sansevieria: 20 a 45 %, ancho 25.
HUMEDAD_SANSEVIERIA = Rango(20, 45)


@pytest.mark.parametrize(
    ("valor", "esperado"),
    [
        (19.9, EstadoParametro.BAJO),
        (20, EstadoParametro.OPTIMO),
        (30, EstadoParametro.OPTIMO),
        (45, EstadoParametro.OPTIMO),
        (45.1, EstadoParametro.ALTO),
    ],
)
def test_clasifica_bajo_optimo_alto_y_los_limites_cuentan_como_optimo(valor, esperado):
    assert HUMEDAD_SANSEVIERIA.clasificar(valor) is esperado


@pytest.mark.parametrize(
    ("valor", "esperada"),
    [(30, 0.0), (18, 0.08), (7.5, 0.5), (1, 0.76), (57.5, 0.5)],
)
def test_la_desviacion_se_mide_en_anchos_del_rango(valor, esperada):
    assert HUMEDAD_SANSEVIERIA.desviacion(valor) == pytest.approx(esperada)


@pytest.mark.parametrize(("minimo", "maximo"), [(45, 20), (20, 20)])
def test_un_rango_necesita_minimo_menor_que_maximo(minimo, maximo):
    with pytest.raises(RangoInvalido):
        Rango(minimo, maximo)
