import pytest

from dominio.errores import ParametroSinRango
from dominio.especie import Especie, normalizar_nombre
from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.evaluador import EvaluadorPlanta
from dominio.medicion import Lectura, Medicion
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA, Parametro
from dominio.rango import Rango
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from tests.dobles import medicion, sansevieria


@pytest.fixture
def evaluador():
    return EvaluadorPlanta(ReglaHibrida(umbral=0.5), GeneradorRecomendaciones())


def test_clasifica_cada_parametro_y_aplica_la_regla(evaluador):
    diagnostico = evaluador.evaluar(sansevieria(), medicion(humedad=18, luz=1600, temperatura=22))

    assert [r.estado for r in diagnostico.resultados] == [
        EstadoParametro.BAJO,
        EstadoParametro.ALTO,
        EstadoParametro.OPTIMO,
    ]
    assert diagnostico.estado is EstadoGlobal.CRITICO


def test_solo_hay_recomendaciones_para_los_parametros_fuera_de_rango(evaluador):
    diagnostico = evaluador.evaluar(sansevieria(), medicion(humedad=18, luz=800, temperatura=22))

    assert diagnostico.estado is EstadoGlobal.EN_RIESGO
    assert len(diagnostico.recomendaciones) == 1
    assert "humedad" in diagnostico.recomendaciones[0]


def test_todo_optimo_es_saludable_y_sin_recomendaciones(evaluador):
    diagnostico = evaluador.evaluar(sansevieria(), medicion(humedad=30, luz=800, temperatura=22))

    assert diagnostico.estado is EstadoGlobal.SALUDABLE
    assert diagnostico.recomendaciones == ()


def test_agregar_un_parametro_nuevo_no_obliga_a_cambiar_el_evaluador(evaluador):
    ph = Parametro("ph", "", 0, 14)
    especie = Especie("helecho", {HUMEDAD: Rango(60, 85), ph: Rango(5, 6.5)})

    diagnostico = evaluador.evaluar(especie, Medicion((Lectura(HUMEDAD, 70), Lectura(ph, 7.5))))

    assert diagnostico.estado is EstadoGlobal.CRITICO  # pH 7.5: desviacion 0.67
    assert diagnostico.recomendaciones == ("El valor de ph está por encima del rango recomendado (5 a 6.5).",)


def test_una_lectura_sin_rango_en_la_especie_es_un_error(evaluador):
    especie = Especie("helecho", {HUMEDAD: Rango(60, 85)})

    with pytest.raises(ParametroSinRango):
        evaluador.evaluar(especie, Medicion((Lectura(LUZ, 500),)))


@pytest.mark.parametrize("nombre", ["potos", "  Potos ", "POTÓS", "potos\t"])
def test_normalizar_nombre_ignora_mayusculas_tildes_y_espacios(nombre):
    assert normalizar_nombre(nombre) == "potos"
