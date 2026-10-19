"""Repositorios de cuentas, plantas, sensores e historial sobre un archivo SQLite temporal.

Aqui se prueba lo que los dobles en memoria no imitan: las restricciones de la
base, las cascadas y que la planta y su sensor se guarden en una sola transaccion.
"""
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import ApodoRepetido, CorreoYaRegistrado, SensorYaVinculado
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
OTRO_CODIGO = CodigoSensor("MT-0002-BB")


class Repositorios:
    def __init__(self, ruta):
        self.bd = BaseDatos(ruta).preparar()
        self.usuarios = RepositorioUsuariosSqlite(self.bd)
        self.sesiones = RepositorioSesionesSqlite(self.bd)
        self.plantas = RepositorioPlantasSqlite(self.bd)
        self.sensores = RepositorioSensoresSqlite(self.bd)
        self.historial = HistorialMedicionesSqlite(self.bd)
        self._codigos = 0

    def registrar(self, correo="ana@correo.co", nombre="Ana"):
        return self.usuarios.guardar(Usuario(None, Correo(correo), nombre, "pbkdf2_sha256$1$00$00"))

    def planta(self, usuario_id, apodo="Sala", especie="potos", codigo=None):
        """Una matera con su sensor; si no se pide un codigo, uno distinto cada vez (MT-0901-ZZ...)."""
        self._codigos += 1
        codigo = codigo or CodigoSensor(f"MT-{900 + self._codigos:04d}-ZZ")
        return self.plantas.guardar_con_sensor(Planta(None, usuario_id, apodo, especie), codigo, "huella-clave")

    def registro(self, planta_id, momento=AHORA, humedad=18.0):
        lecturas = (
            LecturaRegistrada(HUMEDAD, humedad, EstadoParametro.BAJO),
            LecturaRegistrada(LUZ, 800.0, EstadoParametro.OPTIMO),
            LecturaRegistrada(TEMPERATURA, 22.0, EstadoParametro.OPTIMO),
        )
        return RegistroMedicion(planta_id, momento, EstadoGlobal.EN_RIESGO, lecturas, CODIGO.valor)

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
    repos.planta(beto.id, "Sala", "potos")
    repos.planta(beto.id, "Patio", "lavanda")

    assert [(r.nombre, r.cantidad_plantas) for r in repos.usuarios.resumenes()] == [("Ana", 0), ("Beto", 2)]


def test_eliminar_un_usuario_borra_en_cascada_sesiones_plantas_sensores_e_historial(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    planta = repos.planta(ana.id)
    repos.planta(beto.id)
    repos.sesiones.guardar(Sesion("huella", ana.id, AHORA))
    repos.historial.agregar(repos.registro(planta.id))

    repos.usuarios.eliminar(ana.id)

    tablas = ("usuario", "sesion", "planta", "sensor", "medicion", "lectura")
    assert [repos.contar(t) for t in tablas] == [1, 0, 1, 1, 0, 0]


def test_una_sesion_conserva_su_vencimiento_con_zona_horaria(repos):
    ana = repos.registrar()
    repos.sesiones.guardar(Sesion("huella", ana.id, AHORA + timedelta(days=7)))

    assert repos.sesiones.por_huella("huella") == Sesion("huella", ana.id, AHORA + timedelta(days=7))

    repos.sesiones.eliminar_de_usuario(ana.id)
    assert repos.sesiones.por_huella("huella") is None


def test_una_planta_solo_se_encuentra_junto_con_su_dueno(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    planta = repos.planta(ana.id)

    assert repos.plantas.por_id(ana.id, planta.id) == planta
    assert repos.plantas.por_id(beto.id, planta.id) is None
    repos.plantas.eliminar(beto.id, planta.id)
    assert repos.plantas.de_usuario(ana.id) == [planta]


def test_la_planta_y_su_sensor_se_guardan_juntos(repos):
    planta = repos.planta(repos.registrar().id, codigo=CODIGO)

    assert repos.sensores.por_codigo(CODIGO) == Sensor(CODIGO, planta.id, "huella-clave")
    assert repos.sensores.de_planta(planta.id) == Sensor(CODIGO, planta.id, "huella-clave")
    assert repos.plantas.vinculada_a(CODIGO) == planta


@pytest.mark.parametrize(
    ("apodo", "especie", "codigo", "error"),
    [
        ("SALA", "lavanda", OTRO_CODIGO, ApodoRepetido),
        ("Patio", "cactus", OTRO_CODIGO, EspecieNoSoportada),
        ("Patio", "lavanda", CODIGO, SensorYaVinculado),
    ],
    ids=["apodo repetido sin importar mayusculas", "especie que no existe", "codigo en uso"],
)
def test_si_la_base_rechaza_la_planta_o_el_sensor_no_queda_ninguno_de_los_dos(repos, apodo, especie, codigo, error):
    ana = repos.registrar()
    repos.planta(ana.id, "Sala", "potos", CODIGO)

    with pytest.raises(error):
        repos.plantas.guardar_con_sensor(Planta(None, ana.id, apodo, especie), codigo, "h")

    assert (repos.contar("planta"), repos.contar("sensor")) == (1, 1)
    assert repos.sensores.por_codigo(OTRO_CODIGO) is None


def test_no_se_puede_borrar_una_especie_que_una_planta_usa(repos):
    repos.planta(repos.registrar().id, "Sala", "potos")

    with pytest.raises(sqlite3.IntegrityError), repos.bd.conexion() as conexion:
        conexion.execute("DELETE FROM especie WHERE nombre = 'potos'")


def test_reemplazar_el_sensor_deja_uno_solo_libera_el_codigo_y_conserva_el_historial(repos):
    planta = repos.planta(repos.registrar().id, codigo=CODIGO)
    repos.historial.agregar(repos.registro(planta.id))

    repos.sensores.reemplazar(Sensor(OTRO_CODIGO, planta.id, "huella-nueva"))

    assert repos.sensores.de_planta(planta.id) == Sensor(OTRO_CODIGO, planta.id, "huella-nueva")
    assert repos.sensores.por_codigo(CODIGO) is None
    assert (repos.contar("sensor"), repos.contar("medicion")) == (1, 1)


def test_reemplazar_por_el_mismo_codigo_cambia_la_huella_de_la_clave(repos):
    planta = repos.planta(repos.registrar().id, codigo=CODIGO)

    repos.sensores.reemplazar(Sensor(CODIGO, planta.id, "huella-nueva"))

    assert repos.sensores.por_codigo(CODIGO).hash_clave == "huella-nueva"


def test_reemplazar_por_un_codigo_de_otra_planta_no_le_quita_el_sensor_a_ninguna(repos):
    ana = repos.registrar()
    sala = repos.planta(ana.id, "Sala", codigo=CODIGO)
    patio = repos.planta(ana.id, "Patio", codigo=OTRO_CODIGO)

    with pytest.raises(SensorYaVinculado):
        repos.sensores.reemplazar(Sensor(OTRO_CODIGO, sala.id, "h"))

    assert repos.sensores.de_planta(sala.id).codigo == CODIGO
    assert repos.sensores.de_planta(patio.id).codigo == OTRO_CODIGO


def test_una_planta_vieja_sin_sensor_recibe_uno(repos):
    # Antes de que el sensor fuera obligatorio, una planta se podia crear sin el.
    ana = repos.registrar()
    with repos.bd.conexion() as conexion:
        planta_id = conexion.execute(
            "INSERT INTO planta (usuario_id, especie, apodo) VALUES (?, 'potos', 'Sala')", (ana.id,)
        ).lastrowid

    repos.sensores.reemplazar(Sensor(CODIGO, planta_id, "h"))

    assert repos.plantas.vinculada_a(CODIGO).id == planta_id


def test_el_historial_se_lee_igual_mas_reciente_primero_y_con_limite(repos):
    planta = repos.planta(repos.registrar().id)
    for horas in range(3):
        repos.historial.agregar(repos.registro(planta.id, AHORA + timedelta(hours=horas, microseconds=horas)))

    registros = repos.historial.de_planta(planta.id, limite=2)

    assert [r.momento for r in registros] == [AHORA + timedelta(hours=2, microseconds=2), AHORA + timedelta(hours=1, microseconds=1)]
    assert registros[0] == repos.registro(planta.id, AHORA + timedelta(hours=2, microseconds=2))
    assert repos.historial.ultimo_de(planta.id) == registros[0]


def test_borrar_una_planta_borra_su_sensor_y_su_historial(repos):
    ana = repos.registrar()
    planta = repos.planta(ana.id, codigo=CODIGO)
    repos.historial.agregar(repos.registro(planta.id))

    repos.plantas.eliminar(ana.id, planta.id)

    assert [repos.contar(t) for t in ("planta", "sensor", "medicion", "lectura")] == [0, 0, 0, 0]
    assert repos.historial.ultimo_de(planta.id) is None
