"""Plantas, sensores e historial con dobles en memoria. Incluye las pruebas de aislamiento entre usuarios."""
from datetime import datetime, timedelta, timezone

import pytest

from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.historial import ConsultarHistorial
from aplicacion.plantas import EliminarPlanta, ListarPlantas, RegistrarPlanta
from aplicacion.sensores import RecibirMedicionDeSensor, ReemplazarSensor
from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import (
    ApodoRepetido,
    ClaveSensorInvalida,
    CodigoSensorInvalido,
    PlantaNoEncontrada,
    SensorYaVinculado,
)
from dominio.especie import Especie
from dominio.estados import EstadoGlobal
from dominio.evaluador import EvaluadorPlanta
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.rango import Rango
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.sensores import CodigoSensor
from dominio.servicio_diagnostico import ServicioDiagnostico
from dominio.usuarios import Correo, Usuario
from tests.dobles import medicion, sansevieria
from tests.dobles_usuarios import (
    EspeciesEditablesEnMemoria,
    GeneradorSecretosFalso,
    HistorialEnMemoria,
    NotificadorEnMemoria,
    NotificadorQueFalla,
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

    def __init__(self, notificador=None):
        self.sensores = RepositorioSensoresEnMemoria()
        self.plantas = RepositorioPlantasEnMemoria(self.sensores)
        self.historial = HistorialEnMemoria()
        self.reloj = RelojFijo(AHORA)
        especies = EspeciesEditablesEnMemoria(sansevieria(), potos())
        secretos = GeneradorSecretosFalso()
        servicio = ServicioDiagnostico(especies, EvaluadorPlanta(ReglaHibrida(), GeneradorRecomendaciones()))

        self.registrar = RegistrarPlanta(self.plantas, self.sensores, especies, secretos)
        self.listar = ListarPlantas(self.plantas, self.sensores, self.historial)
        self.eliminar = EliminarPlanta(self.plantas)
        self.reemplazar = ReemplazarSensor(self.plantas, self.sensores, secretos)
        self.consultar_historial = ConsultarHistorial(self.plantas, self.historial)
        self.notificador = notificador or NotificadorEnMemoria(self.historial)
        self.diagnosticar = DiagnosticarPlantaDeUsuario(
            self.plantas, servicio, self.historial, self.reloj, self.notificador
        )
        self.recibir = RecibirMedicionDeSensor(self.sensores, self.plantas, secretos, self.diagnosticar)

    def codigo_de(self, planta) -> str | None:
        sensor = self.sensores.de_planta(planta.id)
        return sensor.codigo.valor if sensor else None


@pytest.fixture
def sistema():
    return Sistema()


@pytest.fixture
def matera_de_ana(sistema):
    """La Sala de Ana con el sensor MT-0001-AA. Su clave es secreto-1."""
    return sistema.registrar.ejecutar(ANA, "Sala", "Sansevieria", "MT-0001-AA")


@pytest.fixture
def planta_de_ana(matera_de_ana):
    return matera_de_ana.planta


def test_la_matera_nace_con_su_sensor_y_la_clave_sale_una_sola_vez(sistema):
    matera = sistema.registrar.ejecutar(ANA, "Sala", "  SANSEVIERIA ", "mt-0001-aa")

    assert (matera.planta.id, matera.planta.usuario_id, matera.planta.especie) == (1, ANA.id, "sansevieria")
    assert (matera.codigo.valor, matera.clave) == ("MT-0001-AA", "secreto-1")
    assert sistema.sensores.de_planta(matera.planta.id).hash_clave == "huella(secreto-1)"


@pytest.mark.parametrize(
    ("apodo", "especie", "codigo", "error"),
    [
        ("Cocina", "cactus", "MT-0002-BB", EspecieNoSoportada),
        (" sala ", "potos", "MT-0002-BB", ApodoRepetido),
        ("Cocina", "potos", "MT-0001-AA", SensorYaVinculado),
        ("Cocina", "potos", "sensor-1", CodigoSensorInvalido),
    ],
    ids=["especie", "apodo repetido", "codigo en uso", "codigo mal escrito"],
)
def test_si_algo_falla_no_se_guarda_ni_la_planta_ni_el_sensor(sistema, planta_de_ana, apodo, especie, codigo, error):
    with pytest.raises(error):
        sistema.registrar.ejecutar(ANA, apodo, especie, codigo)

    assert sistema.plantas.de_usuario(ANA.id) == [planta_de_ana]
    assert sistema.sensores.por_codigo(CodigoSensor("MT-0002-BB")) is None


def test_otro_usuario_puede_repetir_el_apodo_pero_no_el_codigo_del_sensor(sistema, planta_de_ana):
    assert sistema.registrar.ejecutar(BETO, "Sala", "potos", "MT-0002-BB").planta.usuario_id == BETO.id

    with pytest.raises(SensorYaVinculado):
        sistema.registrar.ejecutar(BETO, "Patio", "potos", "MT-0001-AA")


def test_listar_devuelve_solo_las_plantas_propias_con_su_sensor_y_su_ultima_medicion(sistema, matera_de_ana):
    sistema.registrar.ejecutar(BETO, "Patio", "potos", "MT-0002-BB")
    sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(18, 800, 22))

    [tarjeta] = sistema.listar.ejecutar(ANA)

    assert tarjeta.planta.apodo == "Sala"
    assert tarjeta.sensor.codigo.valor == "MT-0001-AA"
    assert tarjeta.ultima_medicion.estado is EstadoGlobal.EN_RIESGO


def test_una_matera_nueva_aparece_con_su_sensor_y_sin_mediciones(sistema, planta_de_ana):
    [tarjeta] = sistema.listar.ejecutar(ANA)

    assert (tarjeta.sensor.codigo.valor, tarjeta.ultima_medicion) == ("MT-0001-AA", None)


def test_eliminar_borra_la_planta_propia_y_libera_el_codigo_de_su_sensor(sistema, planta_de_ana):
    sistema.eliminar.ejecutar(ANA, planta_de_ana.id)

    assert sistema.listar.ejecutar(ANA) == []
    assert sistema.registrar.ejecutar(ANA, "Cocina", "potos", "MT-0001-AA").codigo.valor == "MT-0001-AA"


@pytest.mark.parametrize(
    "accion",
    [
        lambda s, p: s.eliminar.ejecutar(BETO, p.id),
        lambda s, p: s.reemplazar.ejecutar(BETO, p.id, "MT-0009-ZZ"),
        lambda s, p: s.consultar_historial.ejecutar(BETO, p.id),
        lambda s, p: s.diagnosticar.ejecutar(BETO.id, p.id, medicion(30, 800, 22), "MT-0009-ZZ"),
    ],
    ids=["eliminar", "cambiar sensor", "historial", "medicion"],
)
def test_beto_no_puede_tocar_la_planta_de_ana_y_recibe_el_mismo_error_que_si_no_existiera(
    sistema, planta_de_ana, accion
):
    with pytest.raises(PlantaNoEncontrada):
        accion(sistema, planta_de_ana)

    assert sistema.listar.ejecutar(ANA)[0].planta == planta_de_ana
    assert sistema.historial.registros == []
    assert sistema.codigo_de(planta_de_ana) == "MT-0001-AA"


def test_beto_no_ve_las_plantas_de_ana(sistema, planta_de_ana):
    assert sistema.listar.ejecutar(BETO) == []


def test_cambiar_el_sensor_conserva_el_historial_y_la_clave_vieja_deja_de_servir(sistema, matera_de_ana):
    planta = matera_de_ana.planta
    sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(30, 800, 22))

    nuevo = sistema.reemplazar.ejecutar(ANA, planta.id, "mt-0002-bb")

    assert (nuevo.planta, nuevo.codigo.valor, nuevo.clave) == (planta, "MT-0002-BB", "secreto-2")
    with pytest.raises(ClaveSensorInvalida):
        sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(31, 800, 22))
    sistema.recibir.ejecutar("MT-0002-BB", nuevo.clave, medicion(32, 800, 22))
    assert [r.origen for r in sistema.historial.registros] == ["MT-0001-AA", "MT-0002-BB"]
    assert [t.sensor.codigo.valor for t in sistema.listar.ejecutar(ANA)] == ["MT-0002-BB"]


def test_el_codigo_que_se_deja_queda_libre_para_otra_matera(sistema, planta_de_ana):
    sistema.reemplazar.ejecutar(ANA, planta_de_ana.id, "MT-0002-BB")

    assert sistema.registrar.ejecutar(BETO, "Patio", "potos", "MT-0001-AA").codigo.valor == "MT-0001-AA"


def test_cambiar_al_mismo_codigo_da_una_clave_nueva_si_se_perdio_la_anterior(sistema, matera_de_ana):
    nuevo = sistema.reemplazar.ejecutar(ANA, matera_de_ana.planta.id, "MT-0001-AA")

    assert nuevo.clave == "secreto-2"
    with pytest.raises(ClaveSensorInvalida):
        sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(30, 800, 22))
    assert sistema.recibir.ejecutar("MT-0001-AA", nuevo.clave, medicion(30, 800, 22)).planta == matera_de_ana.planta


def test_no_se_cambia_a_un_codigo_de_otra_planta_y_el_sensor_actual_sigue_sirviendo(sistema, matera_de_ana):
    sistema.registrar.ejecutar(BETO, "Patio", "potos", "MT-0002-BB")

    with pytest.raises(SensorYaVinculado):
        sistema.reemplazar.ejecutar(ANA, matera_de_ana.planta.id, "MT-0002-BB")

    assert sistema.codigo_de(matera_de_ana.planta) == "MT-0001-AA"
    assert sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(30, 800, 22)).planta.apodo == "Sala"


def test_una_matera_vieja_sin_sensor_recibe_uno_con_el_mismo_caso_de_uso(sistema, planta_de_ana):
    # Las materas creadas antes de que el sensor fuera obligatorio no tienen ninguno.
    sistema.sensores.quitar_de_planta(planta_de_ana.id)
    assert sistema.listar.ejecutar(ANA)[0].sensor is None

    nuevo = sistema.reemplazar.ejecutar(ANA, planta_de_ana.id, "MT-0003-CC")

    assert sistema.listar.ejecutar(ANA)[0].sensor.codigo == nuevo.codigo


def test_el_sensor_con_su_clave_guarda_la_medicion_en_su_planta_con_su_codigo(sistema, matera_de_ana):
    resultado = sistema.recibir.ejecutar("mt-0001-aa", matera_de_ana.clave, medicion(30, 800, 22))

    assert resultado.planta == matera_de_ana.planta
    assert resultado.diagnostico.estado is EstadoGlobal.SALUDABLE
    assert sistema.historial.registros[0].origen == "MT-0001-AA"


@pytest.mark.parametrize(
    ("codigo", "clave"),
    [("MT-0001-AA", "clave-mala"), ("MT-9999-ZZ", "secreto-1"), ("no-es-codigo", "secreto-1")],
)
def test_el_sensor_recibe_el_mismo_error_sin_importar_que_fallo_y_no_se_guarda_nada(
    sistema, matera_de_ana, codigo, clave
):
    with pytest.raises(ClaveSensorInvalida):
        sistema.recibir.ejecutar(codigo, clave, medicion(30, 800, 22))
    assert sistema.historial.registros == []


def test_el_historial_trae_lo_mas_reciente_primero_y_respeta_el_limite(sistema, matera_de_ana):
    for humedad in (30, 31, 32):
        sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(humedad, 800, 22))
        sistema.reloj.avanzar(timedelta(hours=1))

    historial = sistema.consultar_historial.ejecutar(ANA, matera_de_ana.planta.id, limite=2)

    assert historial.planta == matera_de_ana.planta
    assert [r.lecturas[0].valor for r in historial.registros] == [32, 31]


def test_la_medicion_del_sensor_se_avisa_al_dueno_despues_de_guardarla(sistema, matera_de_ana):
    resultado = sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(18, 800, 22))

    assert sistema.notificador.avisos == [(ANA.id, resultado.planta, resultado.registro, resultado.diagnostico)]
    assert sistema.notificador.guardada_al_avisar == [True]


def test_cada_medicion_se_avisa_solo_al_dueno_de_su_planta(sistema, matera_de_ana):
    de_beto = sistema.registrar.ejecutar(BETO, "Patio", "potos", "MT-0002-BB")

    sistema.recibir.ejecutar("MT-0002-BB", de_beto.clave, medicion(50, 800, 22))
    sistema.recibir.ejecutar("MT-0001-AA", matera_de_ana.clave, medicion(30, 800, 22))

    assert [(usuario, planta.apodo) for usuario, planta, _, _ in sistema.notificador.avisos] == [
        (BETO.id, "Patio"),
        (ANA.id, "Sala"),
    ]


def test_si_el_aviso_falla_la_medicion_queda_guardada_y_el_sensor_recibe_su_diagnostico():
    sistema = Sistema(notificador=NotificadorQueFalla())
    matera = sistema.registrar.ejecutar(ANA, "Sala", "Sansevieria", "MT-0001-AA")

    resultado = sistema.recibir.ejecutar("MT-0001-AA", matera.clave, medicion(30, 800, 22))

    assert resultado.diagnostico.estado is EstadoGlobal.SALUDABLE
    assert sistema.historial.registros == [resultado.registro]


def test_una_medicion_rechazada_no_se_avisa(sistema, matera_de_ana):
    with pytest.raises(ClaveSensorInvalida):
        sistema.recibir.ejecutar("MT-0001-AA", "clave-mala", medicion(30, 800, 22))

    assert sistema.notificador.avisos == []
