"""Repositorios de cuentas, plantas, sensores e historial sobre un archivo SQLite temporal.

Aqui se prueba lo que los dobles en memoria no imitan: las restricciones de la
base, las cascadas y que la planta y su sensor se guarden en una sola transaccion.
"""
import sqlite3
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import ApodoRepetido, CorreoYaRegistrado, PlantaNoEncontrada, SensorYaVinculado, SesionInvalida
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
    repos.sesiones.abrir(Sesion("huella", ana.id, AHORA))
    repos.historial.agregar(planta, repos.registro(planta.id))

    repos.usuarios.eliminar(ana.id)

    tablas = ("usuario", "sesion", "planta", "sensor", "medicion", "lectura")
    assert [repos.contar(t) for t in tablas] == [1, 0, 1, 1, 0, 0]


def test_una_sesion_conserva_su_vencimiento_con_zona_horaria(repos):
    ana = repos.registrar()
    repos.sesiones.abrir(Sesion("huella", ana.id, AHORA + timedelta(days=7)))

    assert repos.sesiones.abierta("huella") == Sesion("huella", ana.id, AHORA + timedelta(days=7))

    repos.sesiones.cerrar_de_usuario(ana.id)
    assert repos.sesiones.abierta("huella") is None


def test_por_id_no_decide_de_quien_es_la_planta_y_eliminar_exige_la_misma_planta(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    planta = repos.planta(ana.id)

    # Quien puede verla lo decide Planta.exigir_dueno, en el dominio.
    assert repos.plantas.por_id(planta.id) == planta
    assert repos.plantas.por_id(999) is None
    # Una planta con ese id pero de otro dueno no es la que se leyo: no se borra.
    repos.plantas.eliminar(replace(planta, usuario_id=beto.id))
    assert repos.plantas.de_usuario(ana.id) == [planta]


def test_una_lectura_de_una_planta_borrada_no_cae_en_la_planta_nueva_que_toma_su_id(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    de_ana = repos.planta(ana.id)
    repos.plantas.eliminar(de_ana)
    de_beto = repos.planta(beto.id)
    assert de_beto.id == de_ana.id  # SQLite reutiliza el id mas alto

    with pytest.raises(PlantaNoEncontrada):
        repos.historial.agregar(de_ana, repos.registro(de_ana.id))

    assert repos.historial.de_planta(de_beto.id, 30) == []
    assert repos.contar("medicion") == 0


def test_un_id_que_no_cabe_en_sqlite_no_existe(repos):
    assert repos.plantas.por_id(2**63) is None
    assert repos.usuarios.por_id(-(2**63) - 1) is None


def test_la_planta_y_su_sensor_se_guardan_juntos(repos):
    planta = repos.planta(repos.registrar().id, codigo=CODIGO)

    assert repos.sensores.por_codigo(CODIGO) == Sensor(CODIGO, planta.id, "huella-clave")
    assert repos.sensores.de_planta(planta.id) == Sensor(CODIGO, planta.id, "huella-clave")


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
    repos.historial.agregar(planta, repos.registro(planta.id))

    repos.sensores.reemplazar(planta, Sensor(OTRO_CODIGO, planta.id, "huella-nueva"))

    assert repos.sensores.de_planta(planta.id) == Sensor(OTRO_CODIGO, planta.id, "huella-nueva")
    assert repos.sensores.por_codigo(CODIGO) is None
    assert (repos.contar("sensor"), repos.contar("medicion")) == (1, 1)


def test_reemplazar_por_el_mismo_codigo_cambia_la_huella_de_la_clave(repos):
    planta = repos.planta(repos.registrar().id, codigo=CODIGO)

    repos.sensores.reemplazar(planta, Sensor(CODIGO, planta.id, "huella-nueva"))

    assert repos.sensores.por_codigo(CODIGO).hash_clave == "huella-nueva"


def test_reemplazar_por_un_codigo_de_otra_planta_no_le_quita_el_sensor_a_ninguna(repos):
    ana = repos.registrar()
    sala = repos.planta(ana.id, "Sala", codigo=CODIGO)
    patio = repos.planta(ana.id, "Patio", codigo=OTRO_CODIGO)

    with pytest.raises(SensorYaVinculado):
        repos.sensores.reemplazar(sala, Sensor(OTRO_CODIGO, sala.id, "h"))

    assert repos.sensores.de_planta(sala.id).codigo == CODIGO
    assert repos.sensores.de_planta(patio.id).codigo == OTRO_CODIGO


def test_una_planta_vieja_sin_sensor_recibe_uno(repos):
    # Antes de que el sensor fuera obligatorio, una planta se podia crear sin el.
    ana = repos.registrar()
    with repos.bd.conexion() as conexion:
        planta_id = conexion.execute(
            "INSERT INTO planta (usuario_id, especie, apodo) VALUES (?, 'potos', 'Sala')", (ana.id,)
        ).lastrowid

    repos.sensores.reemplazar(Planta(planta_id, ana.id, "Sala", "potos"), Sensor(CODIGO, planta_id, "h"))

    assert repos.sensores.de_planta(planta_id) == Sensor(CODIGO, planta_id, "h")


def test_el_canje_deja_vigente_solo_el_ultimo_token_del_sensor(repos):
    sala = repos.planta(repos.registrar().id, codigo=CODIGO)
    sensor = repos.sensores.por_codigo(CODIGO)

    assert repos.sensores.planta_con_token(CODIGO, "jti-1") is None  # sin canje, ningun token sirve
    assert repos.sensores.renovar(sensor, "jti-1") is True
    assert repos.sensores.planta_con_token(CODIGO, "jti-1") == sala
    assert repos.sensores.renovar(sensor, "jti-2") is True
    assert repos.sensores.planta_con_token(CODIGO, "jti-1") is None
    assert repos.sensores.planta_con_token(CODIGO, "jti-2") == sala


def test_cambiar_el_sensor_deja_sin_efecto_su_token(repos):
    sala = repos.planta(repos.registrar().id, codigo=CODIGO)
    repos.sensores.renovar(repos.sensores.por_codigo(CODIGO), "jti-1")

    repos.sensores.reemplazar(sala, Sensor(CODIGO, sala.id, "huella-nueva"))

    assert repos.sensores.planta_con_token(CODIGO, "jti-1") is None


def test_renovar_no_da_token_si_el_sensor_cambio_despues_de_leerlo(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    sala = repos.planta(ana.id, codigo=CODIGO)
    leido = repos.sensores.por_codigo(CODIGO)  # el sensor con el que se verifico la clave

    # Mientras tanto Ana cambia de sensor y Beto crea una matera con el codigo que quedo libre.
    repos.sensores.reemplazar(sala, Sensor(OTRO_CODIGO, sala.id, "huella-nueva"))
    repos.planta(beto.id, "Patio", codigo=CODIGO)

    assert repos.sensores.renovar(leido, "jti-1") is False
    assert repos.sensores.planta_con_token(CODIGO, "jti-1") is None


def test_no_se_reemplaza_el_sensor_si_la_planta_ya_no_es_la_que_se_leyo_ni_si_ya_no_existe(repos):
    ana, beto = repos.registrar(), repos.registrar("beto@correo.co", "Beto")
    de_beto = repos.planta(beto.id, codigo=CODIGO)

    # Ana leyo la planta con ese id cuando era suya; otra pestana la borro y el id paso a Beto.
    with pytest.raises(PlantaNoEncontrada):
        repos.sensores.reemplazar(replace(de_beto, usuario_id=ana.id), Sensor(OTRO_CODIGO, de_beto.id, "h"))
    with pytest.raises(PlantaNoEncontrada):
        repos.sensores.reemplazar(Planta(999, ana.id, "Sala", "potos"), Sensor(OTRO_CODIGO, 999, "h"))

    assert repos.sensores.de_planta(de_beto.id) == Sensor(CODIGO, de_beto.id, "huella-clave")
    assert repos.contar("sensor") == 1


def test_una_planta_de_una_cuenta_que_ya_no_existe_no_se_guarda_y_no_culpa_a_la_especie(repos):
    # La cuenta se borro entre la autenticacion y el INSERT: la especie si existe.
    with pytest.raises(SesionInvalida):
        repos.plantas.guardar_con_sensor(Planta(None, 999, "Sala", "potos"), CODIGO, "h")

    assert (repos.contar("planta"), repos.contar("sensor")) == (0, 0)


def test_el_historial_se_lee_igual_mas_reciente_primero_y_con_limite(repos):
    planta = repos.planta(repos.registrar().id)
    for horas in range(3):
        repos.historial.agregar(planta, repos.registro(planta.id, AHORA + timedelta(hours=horas, microseconds=horas)))

    registros = repos.historial.de_planta(planta.id, limite=2)

    assert [r.momento for r in registros] == [AHORA + timedelta(hours=2, microseconds=2), AHORA + timedelta(hours=1, microseconds=1)]
    assert registros[0] == repos.registro(planta.id, AHORA + timedelta(hours=2, microseconds=2))
    assert repos.historial.ultimo_de(planta.id) == registros[0]


def test_el_historial_guarda_en_utc_y_ordena_bien_horas_de_otra_zona_horaria(repos):
    planta = repos.planta(repos.registrar().id)
    bogota = timezone(timedelta(hours=-5))
    # 10:30 en Bogota son las 15:30 en UTC: es posterior a las 15:00 UTC aunque el texto diga 10:30.
    repos.historial.agregar(planta, repos.registro(planta.id, datetime(2026, 10, 22, 10, 30, tzinfo=bogota)))
    repos.historial.agregar(planta, repos.registro(planta.id, datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)))

    registros = repos.historial.de_planta(planta.id, limite=2)

    assert [r.momento.isoformat() for r in registros] == ["2026-10-22T15:30:00+00:00", "2026-10-22T15:00:00+00:00"]


def test_borrar_una_planta_borra_su_sensor_y_su_historial(repos):
    ana = repos.registrar()
    planta = repos.planta(ana.id, codigo=CODIGO)
    repos.historial.agregar(planta, repos.registro(planta.id))

    repos.plantas.eliminar(planta)

    assert [repos.contar(t) for t in ("planta", "sensor", "medicion", "lectura")] == [0, 0, 0, 0]
    assert repos.historial.ultimo_de(planta.id) is None
