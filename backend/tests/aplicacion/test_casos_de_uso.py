from aplicacion.diagnosticar_planta import DiagnosticarPlanta, SolicitudDiagnostico
from aplicacion.listar_especies import ListarEspecies
from dominio.especie import Especie
from dominio.estados import EstadoGlobal
from dominio.evaluador import EvaluadorPlanta
from dominio.parametros import HUMEDAD
from dominio.rango import Rango
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from tests.dobles import RepositorioEspeciesEnMemoria, medicion, sansevieria


def test_diagnosticar_planta_devuelve_el_diagnostico_del_dominio():
    repositorio = RepositorioEspeciesEnMemoria(sansevieria())
    evaluador = EvaluadorPlanta(ReglaHibrida(), GeneradorRecomendaciones())
    caso_de_uso = DiagnosticarPlanta(ServicioDiagnostico(repositorio, evaluador))

    diagnostico = caso_de_uso.ejecutar(SolicitudDiagnostico("sansevieria", medicion(18, 800, 22)))

    assert diagnostico.estado is EstadoGlobal.EN_RIESGO
    assert repositorio.consultas == ["sansevieria"]


def test_listar_especies_las_ordena_por_nombre():
    potos = Especie("potos", {HUMEDAD: Rango(40, 70)})
    helecho = Especie("helecho", {HUMEDAD: Rango(60, 85)})

    especies = ListarEspecies(RepositorioEspeciesEnMemoria(potos, sansevieria(), helecho)).ejecutar()

    assert [e.nombre for e in especies] == ["helecho", "potos", "sansevieria"]
