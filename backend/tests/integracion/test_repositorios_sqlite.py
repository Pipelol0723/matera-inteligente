"""Repositorios de cuentas, plantas, sensores e historial sobre un archivo SQLite temporal.

Aqui se prueba lo que los dobles en memoria no imitan: las restricciones de la
base y las cascadas.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import ApodoRepetido, CorreoYaRegistrado, PlantaConSensor, SensorYaVinculado
from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.historial import LecturaRegistrada, RegistroMedicion
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.plantas import Planta
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Correo, Rol, Sesion, Usuario
from infraestructura.sqlite import (
    BaseDatos,
    HistorialMedicionesSqlite,
    RepositorioPlantasSqlite,
    RepositorioSensoresSqlite,
    RepositorioSesionesSqlite,
    RepositorioUsuariosSqlite,
)

AHORA = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
CODIGO = CodigoSensor("MT-0001-AA")


class Repositorios:
    def __init__(self, ruta):
        self.bd = BaseDatos(ruta).preparar()
        self.usuarios = RepositorioUsuariosSqlite(self.bd)
        self.sesiones = RepositorioSesionesSqlite(self.bd)
        self.plantas = RepositorioPlantasSqlite(self.bd)
        self.sensores = RepositorioSensoresSqlite(self.bd)
        self.historial = HistorialMedicionesSqlite(self.bd)

    def registrar(self, correo="ana@correo.co", nombre="Ana"):
        return self.usuarios.guardar(Usuario(None, Correo(correo), nombre, "pbkdf2_sha256$1$00$00"))

    def registro(self, planta_id, momento=AHORA, humedad=18.0):
        lecturas = (
            LecturaRegistrada(HUMEDAD, humedad, EstadoParametro.BAJO),
            LecturaRegistrada(LUZ, 800.0, EstadoParametro.OPTIMO),
            LecturaRegistrada(TEMPERATURA, 22.0, EstadoParametro.OPTIMO),
        )
        return RegistroMedicion(planta_id, momento, EstadoGlobal.EN_RIESGO, lecturas, "MANUAL")

    def contar(self, tabla):
        with self.bd.conexion() as conexion:
            return conexion.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]


@pytest.fixture
def repos(tmp_path):
    return Repositorios(tmp_path / "matera.sqlite")


def test_un_usuario_se_guarda_con_id_y_se_encuentra_por_correo_y_por_id(repos):
    ana = repos.registrar()

    assert ana.id is not None
    assert repos.usuarios.por_correo(Correo("ANA@correo.co")) == ana
    assert repos.usuarios.por_id(ana.id) == ana
    assert repos.usuarios.por_id(999) is None


def test_actualizar_un_usuario_cambia_su_rol_y_su_estado(repos):
    ana = repos.registrar()

    repos.usuarios.guardar(ana.con_rol(Rol.ADMIN).con_estado(False))

    guardada = repos.usuarios.por_id(ana.id)
    assert (guardada.rol, guardada.activo) == (Rol.ADMIN, False)


def test_la_base_no_acepta_dos_cuentas_con_el_mismo_correo(repos):
    repos.registrar()

    with pytest.raises(CorreoYaRegistrado):
        repos.registrar(nombre="Otra Ana")


def test_los_resumenes_cuentan_las_plantas_de_cada_usuario(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    repos.plantas.guardar(Planta(None, beto.id, "Sala", "potos"))
    repos.plantas.guardar(Planta(None, beto.id, "Patio", "lavanda"))

    assert [(r.nombre, r.cantidad_plantas) for r in repos.usuarios.resumenes()] == [("Ana", 0), ("Beto", 2)]


def test_eliminar_un_usuario_borra_en_cascada_sesiones_plantas_sensores_e_historial(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    planta = repos.plantas.guardar(Planta(None, ana.id, "Sala", "potos"))
    repos.plantas.guardar(Planta(None, beto.id, "Sala", "potos"))
    repos.sesiones.guardar(Sesion("huella", ana.id, AHORA))
    repos.sensores.guardar(Sensor(CODIGO, planta.id, "huella-clave"))
    repos.historial.agregar(repos.registro(planta.id))

    repos.usuarios.eliminar(ana.id)

    assert [repos.contar(t) for t in ("usuario", "sesion", "planta", "sensor", "medicion", "lectura")] == [1, 0, 1, 0, 0, 0]


def test_una_sesion_conserva_su_vencimiento_con_zona_horaria(repos):
    ana = repos.registrar()
    repos.sesiones.guardar(Sesion("huella", ana.id, AHORA + timedelta(days=7)))

    assert repos.sesiones.por_huella("huella") == Sesion("huella", ana.id, AHORA + timedelta(days=7))

    repos.sesiones.eliminar_de_usuario(ana.id)
    assert repos.sesiones.por_huella("huella") is None


def test_una_planta_solo_se_encuentra_junto_con_su_dueno(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    planta = repos.plantas.guardar(Planta(None, ana.id, "Sala", "potos"))

    assert repos.plantas.por_id(ana.id, planta.id) == planta
    assert repos.plantas.por_id(beto.id, planta.id) is None
    repos.plantas.eliminar(beto.id, planta.id)
    assert repos.plantas.de_usuario(ana.id) == [planta]


def test_la_base_respalda_el_apodo_unico_sin_importar_mayusculas_y_la_especie_existente(repos):
    ana = repos.registrar()
    repos.plantas.guardar(Planta(None, ana.id, "Sala", "potos"))

    with pytest.raises(ApodoRepetido):
        repos.plantas.guardar(Planta(None, ana.id, "SALA", "lavanda"))
    with pytest.raises(EspecieNoSoportada):
        repos.plantas.guardar(Planta(None, ana.id, "Patio", "cactus"))


def test_no_se_puede_borrar_una_especie_que_una_planta_usa(repos):
    repos.plantas.guardar(Planta(None, repos.registrar().id, "Sala", "potos"))

    with pytest.raises(sqlite3.IntegrityError), repos.bd.conexion() as conexion:
        conexion.execute("DELETE FROM especie WHERE nombre = 'potos'")


def test_un_sensor_se_encuentra_por_codigo_y_por_planta_y_lleva_a_su_planta(repos):
    planta = repos.plantas.guardar(Planta(None, repos.registrar().id, "Sala", "potos"))
    sensor = Sensor(CODIGO, planta.id, "huella-clave")

    repos.sensores.guardar(sensor)

    assert repos.sensores.por_codigo(CODIGO) == sensor
    assert repos.sensores.de_planta(planta.id) == sensor
    assert repos.plantas.vinculada_a(CODIGO) == planta


def test_la_base_no_acepta_un_codigo_repetido_ni_dos_sensores_en_una_planta(repos):
    ana = repos.registrar()
    sala = repos.plantas.guardar(Planta(None, ana.id, "Sala", "potos"))
    patio = repos.plantas.guardar(Planta(None, ana.id, "Patio", "lavanda"))
    repos.sensores.guardar(Sensor(CODIGO, sala.id, "h"))

    with pytest.raises(SensorYaVinculado):
        repos.sensores.guardar(Sensor(CODIGO, patio.id, "h"))
    with pytest.raises(PlantaConSensor):
        repos.sensores.guardar(Sensor(CodigoSensor("MT-0002-BB"), sala.id, "h"))


def test_el_historial_se_lee_igual_mas_reciente_primero_y_con_limite(repos):
    planta = repos.plantas.guardar(Planta(None, repos.registrar().id, "Sala", "potos"))
    for horas in range(3):
        repos.historial.agregar(repos.registro(planta.id, AHORA + timedelta(hours=horas, microseconds=horas)))

    registros = repos.historial.de_planta(planta.id, limite=2)

    assert [r.momento for r in registros] == [AHORA + timedelta(hours=2, microseconds=2), AHORA + timedelta(hours=1, microseconds=1)]
    assert registros[0] == repos.registro(planta.id, AHORA + timedelta(hours=2, microseconds=2))
    assert repos.historial.ultimo_de(planta.id) == registros[0]


def test_borrar_una_planta_borra_su_sensor_y_su_historial(repos):
    ana = repos.registrar()
    planta = repos.plantas.guardar(Planta(None, ana.id, "Sala", "potos"))
    repos.sensores.guardar(Sensor(CODIGO, planta.id, "h"))
    repos.historial.agregar(repos.registro(planta.id))

    repos.plantas.eliminar(ana.id, planta.id)

    assert [repos.contar(t) for t in ("planta", "sensor", "medicion", "lectura")] == [0, 0, 0, 0]
    assert repos.historial.ultimo_de(planta.id) is None
