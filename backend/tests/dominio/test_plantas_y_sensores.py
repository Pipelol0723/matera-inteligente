"""Reglas de la planta, del codigo del sensor y del registro del historial. Sin base de datos."""
from datetime import datetime, timezone

import pytest

from dominio.errores_usuarios import ApodoInvalido, CodigoSensorInvalido
from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.evaluador import EvaluadorPlanta
from dominio.historial import RegistroMedicion
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.plantas import Planta
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.sensores import CodigoSensor
from tests.dobles import medicion, sansevieria

MOMENTO = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)


def test_la_planta_guarda_el_apodo_limpio_y_la_especie_normalizada():
    planta = Planta(None, 1, "  Potos   de la sala ", " Potós ")

    assert planta.apodo == "Potos de la sala"
    assert planta.especie == "potos"


@pytest.mark.parametrize("apodo", ["", "   ", "x" * 41])
def test_un_apodo_vacio_o_muy_largo_se_rechaza(apodo):
    with pytest.raises(ApodoInvalido):
        Planta(None, 1, apodo, "potos")


def test_la_planta_sabe_de_quien_es():
    planta = Planta(3, usuario_id=1, apodo="Sala", especie="potos")

    assert planta.es_de(1)
    assert not planta.es_de(2)


def test_dos_apodos_que_solo_cambian_en_mayusculas_o_espacios_son_el_mismo():
    assert Planta(None, 1, "Potos de la sala", "potos").mismo_apodo("  potos  DE la Sala")


def test_el_codigo_del_sensor_se_acepta_en_minusculas_y_se_guarda_en_mayusculas():
    assert CodigoSensor(" mt-0042-ab ").valor == "MT-0042-AB"


@pytest.mark.parametrize("texto", ["", "MT-42-AB", "MT-0042-A1", "XX-0042-AB", "MT-0042-ABC"])
def test_un_codigo_de_sensor_con_otra_forma_se_rechaza(texto):
    with pytest.raises(CodigoSensorInvalido):
        CodigoSensor(texto)


def test_el_registro_conserva_los_estados_del_diagnostico_y_su_origen():
    diagnostico = EvaluadorPlanta(ReglaHibrida(), GeneradorRecomendaciones()).evaluar(
        sansevieria(), medicion(humedad=18, luz=800, temperatura=22)
    )

    registro = RegistroMedicion.desde(diagnostico, planta_id=5, momento=MOMENTO, origen="MT-0001-AA")

    assert registro.estado is EstadoGlobal.EN_RIESGO
    assert [(l.parametro, l.valor, l.estado) for l in registro.lecturas] == [
        (HUMEDAD, 18, EstadoParametro.BAJO),
        (LUZ, 800, EstadoParametro.OPTIMO),
        (TEMPERATURA, 22, EstadoParametro.OPTIMO),
    ]
    assert (registro.planta_id, registro.momento, registro.origen) == (5, MOMENTO, "MT-0001-AA")
