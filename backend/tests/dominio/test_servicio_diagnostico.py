"""Reglas de negocio de punta a punta, con un doble del puerto ConsultaRangos."""
import pytest

from dominio.errores import EspecieNoSoportada
from dominio.estados import EstadoGlobal
from dominio.evaluador import EvaluadorPlanta
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaConteo, ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from tests.dobles import RepositorioEspeciesEnMemoria, medicion, sansevieria


def _servicio(repositorio, regla=None):
    evaluador = EvaluadorPlanta(regla or ReglaHibrida(umbral=0.5), GeneradorRecomendaciones())
    return ServicioDiagnostico(repositorio, evaluador)


def test_una_especie_desconocida_lanza_especie_no_soportada():
    servicio = _servicio(RepositorioEspeciesEnMemoria(sansevieria()))

    with pytest.raises(EspecieNoSoportada) as error:
        servicio.diagnosticar("cactus", medicion(30, 800, 22))
    assert error.value.especie == "cactus"


def test_consulta_el_puerto_con_el_nombre_normalizado():
    repositorio = RepositorioEspeciesEnMemoria(sansevieria())

    diagnostico = _servicio(repositorio).diagnosticar("  Sansevieria ", medicion(30, 800, 22))

    assert repositorio.consultas == ["sansevieria"]
    assert diagnostico.especie == "sansevieria"


def test_una_humedad_muy_baja_es_critica_aunque_sea_el_unico_problema():
    diagnostico = _servicio(RepositorioEspeciesEnMemoria(sansevieria())).diagnosticar(
        "sansevieria", medicion(humedad=1, luz=800, temperatura=22)
    )

    assert diagnostico.estado is EstadoGlobal.CRITICO
    assert len(diagnostico.recomendaciones) == 1


def test_cambiar_la_regla_no_obliga_a_tocar_el_servicio_ni_el_evaluador():
    repositorio = RepositorioEspeciesEnMemoria(sansevieria())
    con_hibrida = _servicio(repositorio, ReglaHibrida(umbral=0.5))
    con_conteo = _servicio(repositorio, ReglaConteo())

    muy_seca = medicion(humedad=1, luz=800, temperatura=22)

    assert con_hibrida.diagnosticar("sansevieria", muy_seca).estado is EstadoGlobal.CRITICO
    assert con_conteo.diagnosticar("sansevieria", muy_seca).estado is EstadoGlobal.EN_RIESGO
