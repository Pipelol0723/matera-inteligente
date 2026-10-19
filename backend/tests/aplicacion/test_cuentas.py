"""Casos de uso de la cuenta con dobles en memoria: sin base de datos, sin Flask y sin PBKDF2."""
from datetime import datetime, timedelta, timezone

import pytest

from aplicacion.cuentas import CerrarSesion, ConsultarCuenta, IdentificarUsuario, IniciarSesion, RegistrarUsuario
from dominio.errores_usuarios import (
    ContrasenaDebil,
    CorreoYaRegistrado,
    CredencialesInvalidas,
    CuentaDesactivada,
    SesionInvalida,
)
from dominio.plantas import Planta
from dominio.usuarios import Rol
from tests.dobles_usuarios import (
    CifradorFalso,
    GeneradorSecretosFalso,
    RelojFijo,
    RepositorioPlantasEnMemoria,
    RepositorioSesionesEnMemoria,
    RepositorioUsuariosEnMemoria,
    codigo,
)

AHORA = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)
SIETE_DIAS = timedelta(days=7)


class Cuentas:
    """Los casos de uso de la cuenta conectados a los mismos dobles."""

    def __init__(self):
        self.plantas = RepositorioPlantasEnMemoria()
        self.usuarios = RepositorioUsuariosEnMemoria(self.plantas)
        self.sesiones = RepositorioSesionesEnMemoria()
        self.reloj = RelojFijo(AHORA)
        secretos = GeneradorSecretosFalso()
        self.registrar = RegistrarUsuario(self.usuarios, CifradorFalso())
        self.iniciar = IniciarSesion(self.usuarios, self.sesiones, CifradorFalso(), secretos, self.reloj, SIETE_DIAS)
        self.cerrar = CerrarSesion(self.sesiones, secretos)
        self.identificar = IdentificarUsuario(self.sesiones, self.usuarios, secretos, self.reloj)
        self.consultar = ConsultarCuenta(self.plantas)


@pytest.fixture
def cuentas():
    sistema = Cuentas()
    sistema.registrar.ejecutar("Ana", "ana@correo.co", "clave-segura")
    return sistema


def test_registrar_crea_un_usuario_comun_activo_sin_guardar_la_contrasena_en_claro():
    cuentas = Cuentas()

    usuario = cuentas.registrar.ejecutar("Ana", " Ana@Correo.CO ", "clave-segura")

    assert usuario.id is not None
    assert (usuario.correo.valor, usuario.rol, usuario.activo) == ("ana@correo.co", Rol.USUARIO, True)
    assert usuario.hash_contrasena == "cifrado:clave-segura"


def test_no_se_registran_dos_cuentas_con_el_mismo_correo(cuentas):
    with pytest.raises(CorreoYaRegistrado):
        cuentas.registrar.ejecutar("Otra Ana", "ANA@correo.co", "otra-clave")


def test_una_contrasena_debil_no_crea_la_cuenta():
    cuentas = Cuentas()

    with pytest.raises(ContrasenaDebil):
        cuentas.registrar.ejecutar("Ana", "ana@correo.co", "corta")
    assert cuentas.usuarios.resumenes() == []


def test_iniciar_sesion_entrega_el_token_y_guarda_solo_su_huella(cuentas):
    iniciada = cuentas.iniciar.ejecutar("ana@correo.co", "clave-segura")

    assert iniciada.token == "secreto-1"
    assert iniciada.vence_en == AHORA + SIETE_DIAS
    assert list(cuentas.sesiones.sesiones) == ["huella(secreto-1)"]


@pytest.mark.parametrize(
    ("correo", "contrasena"),
    [("nadie@correo.co", "clave-segura"), ("ana@correo.co", "clave-mala"), ("no-es-correo", "clave-segura")],
)
def test_el_login_da_el_mismo_error_sin_importar_que_fallo(cuentas, correo, contrasena):
    with pytest.raises(CredencialesInvalidas):
        cuentas.iniciar.ejecutar(correo, contrasena)


def test_una_cuenta_desactivada_no_inicia_sesion(cuentas):
    ana = cuentas.usuarios.por_id(1)
    cuentas.usuarios.guardar(ana.con_estado(False))

    with pytest.raises(CuentaDesactivada):
        cuentas.iniciar.ejecutar("ana@correo.co", "clave-segura")


def test_identificar_devuelve_el_usuario_del_token(cuentas):
    token = cuentas.iniciar.ejecutar("ana@correo.co", "clave-segura").token

    assert cuentas.identificar.ejecutar(token).nombre == "Ana"


def test_un_token_vencido_no_sirve_y_su_sesion_se_borra(cuentas):
    token = cuentas.iniciar.ejecutar("ana@correo.co", "clave-segura").token
    cuentas.reloj.avanzar(SIETE_DIAS)

    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(token)
    assert cuentas.sesiones.sesiones == {}


def test_un_token_que_nunca_existio_no_sirve(cuentas):
    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar("inventado")


def test_cerrar_sesion_invalida_el_token(cuentas):
    token = cuentas.iniciar.ejecutar("ana@correo.co", "clave-segura").token

    cuentas.cerrar.ejecutar(token)

    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(token)


def test_el_token_de_una_cuenta_desactivada_deja_de_servir_aunque_no_haya_vencido(cuentas):
    token = cuentas.iniciar.ejecutar("ana@correo.co", "clave-segura").token
    cuentas.usuarios.guardar(cuentas.usuarios.por_id(1).con_estado(False))

    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(token)


def test_mi_cuenta_cuenta_solo_las_plantas_propias(cuentas):
    beto = cuentas.registrar.ejecutar("Beto", "beto@correo.co", "clave-segura")
    cuentas.plantas.guardar_con_sensor(Planta(None, 1, "Sala", "potos"), codigo(1), "h")
    cuentas.plantas.guardar_con_sensor(Planta(None, beto.id, "Patio", "lavanda"), codigo(2), "h")
    cuentas.plantas.guardar_con_sensor(Planta(None, beto.id, "Cocina", "helecho"), codigo(3), "h")

    assert cuentas.consultar.ejecutar(cuentas.usuarios.por_id(1)).cantidad_plantas == 1
