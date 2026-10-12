"""Plantas, sensores e historial con dobles en memoria. Incluye las pruebas de aislamiento entre usuarios."""
from datetime import datetime, timedelta, timezone

import pytest

from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.historial import ConsultarHistorial
from aplicacion.plantas import EliminarPlanta, ListarPlantas, RegistrarPlanta
from aplicacion.sensores import DesvincularSensor, RecibirMedicionDeSensor, VincularSensor
from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import (
    ApodoRepetido,
    ClaveSensorInvalida,
    PlantaConSensor,
    PlantaNoEncontrada,
    PlantaSinSensor,
    SensorYaVinculado,
)
from dominio.especie import Especie
from dominio.estados import EstadoGlobal
from dominio.evaluador import EvaluadorPlanta
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.rango import Rango
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from dominio.usuarios import Correo, Usuario
from tests.dobles import medicion, sansevieria
from tests.dobles_usuarios import (
    EspeciesEditablesEnMemoria,
    GeneradorSecretosFalso,
    HistorialEnMemoria,
    RelojFijo,
    RepositorioPlantasEnMemoria,
    RepositorioSensoresEnMemoria,
)

AHORA = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
ANA = Usuario(1, Correo("ana@correo.co"), "Ana", "h")
BETO = Usuario(2, Correo("beto@correo.co"), "Beto", "h")


def potos() -> Especie:
    return Especie("potos", {HUMEDAD: Rango(40, 70), LUZ: Rango(270, 2150), TEMPERATURA: Rango(16, 29)})


class Sistema:
    """Los casos de uso de plantas y sensores conectados a los mismos dobles y al ServicioDiagnostico real."""

    def __init__(self):
        self.sensores = RepositorioSensoresEnMemoria()
        self.plantas = RepositorioPlantasEnMemoria(self.sensores)
        self.historial = HistorialEnMemoria()
        self.reloj = RelojFijo(AHORA)
        especies = EspeciesEditablesEnMemoria(sansevieria(), potos())
        secretos = GeneradorSecretosFalso()
        servicio = ServicioDiagnostico(especies, EvaluadorPlanta(ReglaHibrida(), GeneradorRecomendaciones()))

        self.registrar = RegistrarPlanta(self.plantas, especies)
        self.listar = ListarPlantas(self.plantas, self.sensores, self.historial)
        self.eliminar = EliminarPlanta(self.plantas)
        self.vincular = VincularSensor(self.plantas, self.sensores, secretos)
        self.desvincular = DesvincularSensor(self.plantas, self.sensores)
        self.consultar_historial = ConsultarHistorial(self.plantas, self.historial)
        self.diagnosticar = DiagnosticarPlantaDeUsuario(self.plantas, servicio, self.historial, self.reloj)
        self.recibir = RecibirMedicionDeSensor(self.sensores, self.plantas, secretos, self.diagnosticar)


@pytest.fixture
def sistema():
    return Sistema()


@pytest.fixture
def planta_de_ana(sistema):
    return sistema.registrar.ejecutar(ANA, "Sala", "Sansevieria")


def test_registrar_una_planta_guarda_su_dueno_y_la_especie_normalizada(sistema):
    planta = sistema.registrar.ejecutar(ANA, "Sala", "  SANSEVIERIA ")

    assert (planta.id, planta.usuario_id, planta.especie) == (1, ANA.id, "sansevieria")


def test_no_se_registra_una_planta_de_una_especie_que_no_existe(sistema):
    with pytest.raises(EspecieNoSoportada):
        sistema.registrar.ejecutar(ANA, "Sala", "cactus")


def test_un_usuario_no_repite_apodos_pero_otro_usuario_si_puede_usarlo(sistema, planta_de_ana):
    with pytest.raises(ApodoRepetido):
        sistema.registrar.ejecutar(ANA, " sala ", "potos")

    assert sistema.registrar.ejecutar(BETO, "Sala", "potos").usuario_id == BETO.id


def test_listar_devuelve_solo_las_plantas_propias_con_su_sensor_y_su_ultima_medicion(sistema, planta_de_ana):
    sistema.registrar.ejecutar(BETO, "Patio", "potos")
    sistema.vincular.ejecutar(ANA, planta_de_ana.id, "MT-0001-AA")
    sistema.diagnosticar.ejecutar(ANA.id, planta_de_ana.id, medicion(18, 800, 22))

    [tarjeta] = sistema.listar.ejecutar(ANA)

    assert tarjeta.planta.apodo == "Sala"
    assert tarjeta.sensor.codigo.valor == "MT-0001-AA"
    assert tarjeta.ultima_medicion.estado is EstadoGlobal.EN_RIESGO


def test_una_planta_nueva_aparece_sin_sensor_y_sin_mediciones(sistema, planta_de_ana):
    [tarjeta] = sistema.listar.ejecutar(ANA)

    assert (tarjeta.sensor, tarjeta.ultima_medicion) == (None, None)


def test_eliminar_borra_la_planta_propia(sistema, planta_de_ana):
    sistema.eliminar.ejecutar(ANA, planta_de_ana.id)

    assert sistema.listar.ejecutar(ANA) == []


@pytest.mark.parametrize(
    "accion",
    [
        lambda s, p: s.eliminar.ejecutar(BETO, p.id),
        lambda s, p: s.vincular.ejecutar(BETO, p.id, "MT-0001-AA"),
        lambda s, p: s.desvincular.ejecutar(BETO, p.id),
        lambda s, p: s.consultar_historial.ejecutar(BETO, p.id),
        lambda s, p: s.diagnosticar.ejecutar(BETO.id, p.id, medicion(30, 800, 22)),
    ],
    ids=["eliminar", "vincular", "desvincular", "historial", "medicion manual"],
)
def test_beto_no_puede_tocar_la_planta_de_ana_y_recibe_el_mismo_error_que_si_no_existiera(
    sistema, planta_de_ana, accion
):
    with pytest.raises(PlantaNoEncontrada):
        accion(sistema, planta_de_ana)

    assert sistema.listar.ejecutar(ANA)[0].planta == planta_de_ana
    assert sistema.historial.registros == []
    assert sistema.sensores.de_planta(planta_de_ana.id) is None


def test_beto_no_ve_las_plantas_de_ana(sistema, planta_de_ana):
    assert sistema.listar.ejecutar(BETO) == []


def test_vincular_entrega_la_clave_una_vez_y_guarda_solo_su_huella(sistema, planta_de_ana):
    vinculado = sistema.vincular.ejecutar(ANA, planta_de_ana.id, "mt-0001-aa")

    assert (vinculado.codigo.valor, vinculado.clave) == ("MT-0001-AA", "secreto-1")
    assert sistema.sensores.de_planta(planta_de_ana.id).hash_clave == "huella(secreto-1)"


def test_un_codigo_en_uso_o_una_planta_con_sensor_no_se_vinculan(sistema, planta_de_ana):
    otra = sistema.registrar.ejecutar(ANA, "Cocina", "potos")
    sistema.vincular.ejecutar(ANA, planta_de_ana.id, "MT-0001-AA")

    with pytest.raises(SensorYaVinculado):
        sistema.vincular.ejecutar(ANA, otra.id, "MT-0001-AA")
    with pytest.raises(PlantaConSensor):
        sistema.vincular.ejecutar(ANA, planta_de_ana.id, "MT-0002-BB")


def test_desvincular_libera_el_codigo_para_otra_planta(sistema, planta_de_ana):
    otra = sistema.registrar.ejecutar(ANA, "Cocina", "potos")
    sistema.vincular.ejecutar(ANA, planta_de_ana.id, "MT-0001-AA")

    sistema.desvincular.ejecutar(ANA, planta_de_ana.id)

    assert sistema.vincular.ejecutar(ANA, otra.id, "MT-0001-AA").planta == otra
    with pytest.raises(PlantaSinSensor):
        sistema.desvincular.ejecutar(ANA, planta_de_ana.id)


def test_la_medicion_manual_usa_la_especie_de_la_planta_y_se_guarda_como_manual(sistema, planta_de_ana):
    resultado = sistema.diagnosticar.ejecutar(ANA.id, planta_de_ana.id, medicion(humedad=1, luz=800, temperatura=22))

    assert resultado.diagnostico.especie == "sansevieria"
    assert resultado.diagnostico.estado is EstadoGlobal.CRITICO
    [registro] = sistema.historial.registros
    assert (registro.planta_id, registro.momento, registro.origen) == (planta_de_ana.id, AHORA, "MANUAL")


def test_el_sensor_con_su_clave_guarda_la_medicion_en_su_planta_con_su_codigo(sistema, planta_de_ana):
    clave = sistema.vincular.ejecutar(ANA, planta_de_ana.id, "MT-0001-AA").clave

    resultado = sistema.recibir.ejecutar("mt-0001-aa", clave, medicion(30, 800, 22))

    assert resultado.planta == planta_de_ana
    assert resultado.diagnostico.estado is EstadoGlobal.SALUDABLE
    assert sistema.historial.registros[0].origen == "MT-0001-AA"


@pytest.mark.parametrize(
    ("codigo", "clave"),
    [("MT-0001-AA", "clave-mala"), ("MT-9999-ZZ", "secreto-1"), ("no-es-codigo", "secreto-1")],
)
def test_el_sensor_recibe_el_mismo_error_sin_importar_que_fallo_y_no_se_guarda_nada(
    sistema, planta_de_ana, codigo, clave
):
    sistema.vincular.ejecutar(ANA, planta_de_ana.id, "MT-0001-AA")

    with pytest.raises(ClaveSensorInvalida):
        sistema.recibir.ejecutar(codigo, clave, medicion(30, 800, 22))
    assert sistema.historial.registros == []


def test_el_historial_trae_lo_mas_reciente_primero_y_respeta_el_limite(sistema, planta_de_ana):
    for humedad in (30, 31, 32):
        sistema.diagnosticar.ejecutar(ANA.id, planta_de_ana.id, medicion(humedad, 800, 22))
        sistema.reloj.avanzar(timedelta(hours=1))

    historial = sistema.consultar_historial.ejecutar(ANA, planta_de_ana.id, limite=2)

    assert historial.planta == planta_de_ana
    assert [r.lecturas[0].valor for r in historial.registros] == [32, 31]
