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
from dominio.identidad import IdentidadUsuario
from dominio.plantas import Planta
from dominio.usuarios import Rol
from tests.dobles_usuarios import (
    CifradorFalso,
    GeneradorSecretosFalso,
    RelojFijo,
    RepositorioPlantasEnMemoria,
    RepositorioSesionesEnMemoria,
    RepositorioUsuariosEnMemoria,
    TokensFalsos,
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
        self.tokens = TokensFalsos()
        self.registrar = RegistrarUsuario(self.usuarios, self.usuarios, CifradorFalso())
        self.iniciar = IniciarSesion(
            self.usuarios, self.sesiones, CifradorFalso(), GeneradorSecretosFalso(), self.tokens, self.reloj, SIETE_DIAS
        )
        self.cerrar = CerrarSesion(self.sesiones)
        self.identificar = IdentificarUsuario(self.sesiones, self.usuarios, self.reloj)
        self.consultar = ConsultarCuenta(self.plantas)

    def entrar(self) -> IdentidadUsuario:
        """Inicia sesion como Ana y devuelve la identidad que el adaptador sacaria de su token."""
        return self.tokens.verificar_usuario(self.iniciar.ejecutar("ana@correo.co", "clave-segura").token)


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


def test_iniciar_sesion_emite_el_token_con_un_id_nuevo_y_la_sesion_guarda_solo_ese_id(cuentas):
    iniciada = cuentas.iniciar.ejecutar("ana@correo.co", "clave-segura")

    assert iniciada.token == "token(usuario 1, secreto-1)"
    assert iniciada.vence_en == AHORA + SIETE_DIAS
    assert list(cuentas.sesiones.sesiones) == ["secreto-1"]
    assert cuentas.sesiones.sesiones["secreto-1"].usuario_id == 1


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


def test_identificar_recibe_la_identidad_y_devuelve_su_usuario(cuentas):
    assert cuentas.identificar.ejecutar(cuentas.entrar()).nombre == "Ana"


def test_una_sesion_vencida_no_sirve_y_se_borra(cuentas):
    identidad = cuentas.entrar()
    cuentas.reloj.avanzar(SIETE_DIAS)

    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(identidad)
    assert cuentas.sesiones.sesiones == {}


def test_un_token_sin_sesion_abierta_no_sirve_aunque_su_firma_sea_valida(cuentas):
    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(IdentidadUsuario(1, "nunca-se-abrio"))


def test_el_id_de_la_sesion_de_ana_no_sirve_para_otro_usuario(cuentas):
    identidad = cuentas.entrar()
    beto = cuentas.registrar.ejecutar("Beto", "beto@correo.co", "clave-segura")

    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(IdentidadUsuario(beto.id, identidad.token_id))


def test_cerrar_sesion_hace_que_el_token_deje_de_servir_aunque_no_haya_vencido(cuentas):
    identidad = cuentas.entrar()

    cuentas.cerrar.ejecutar(identidad)

    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(identidad)


def test_el_token_de_una_cuenta_desactivada_deja_de_servir_aunque_no_haya_vencido(cuentas):
    identidad = cuentas.entrar()
    cuentas.usuarios.guardar(cuentas.usuarios.por_id(1).con_estado(False))

    with pytest.raises(SesionInvalida):
        cuentas.identificar.ejecutar(identidad)


def test_mi_cuenta_cuenta_solo_las_plantas_propias(cuentas):
    beto = cuentas.registrar.ejecutar("Beto", "beto@correo.co", "clave-segura")
    cuentas.plantas.guardar_con_sensor(Planta(None, 1, "Sala", "potos"), codigo(1), "h")
    cuentas.plantas.guardar_con_sensor(Planta(None, beto.id, "Patio", "lavanda"), codigo(2), "h")
    cuentas.plantas.guardar_con_sensor(Planta(None, beto.id, "Cocina", "helecho"), codigo(3), "h")

    assert cuentas.consultar.ejecutar(cuentas.usuarios.por_id(1)).cantidad_plantas == 1
