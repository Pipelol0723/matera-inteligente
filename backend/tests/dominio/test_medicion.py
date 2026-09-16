import math

import pytest

from dominio.errores import MedicionInvalida, ValorFisicamenteImposible
from dominio.medicion import Lectura, Medicion
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA


@pytest.mark.parametrize("valor", [150, -1, math.nan, math.inf])
def test_una_lectura_fisicamente_imposible_no_se_puede_crear(valor):
    with pytest.raises(ValorFisicamenteImposible) as error:
        Lectura(HUMEDAD, valor)
    assert error.value.parametro is HUMEDAD


@pytest.mark.parametrize(("parametro", "valor"), [(HUMEDAD, 0), (HUMEDAD, 100), (TEMPERATURA, -50), (LUZ, 150_000)])
def test_los_limites_fisicos_son_validos(parametro, valor):
    assert Lectura(parametro, valor).valor == valor


def test_una_medicion_no_puede_estar_vacia():
    with pytest.raises(MedicionInvalida):
        Medicion(())


def test_una_medicion_no_puede_repetir_un_parametro():
    with pytest.raises(MedicionInvalida):
        Medicion((Lectura(HUMEDAD, 30), Lectura(HUMEDAD, 40)))
