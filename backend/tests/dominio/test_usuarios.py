"""Reglas de las cuentas: correo, nombre, contrasena, permisos y sesion. Sin base de datos."""
from datetime import datetime, timedelta, timezone

import pytest

from dominio.errores_usuarios import (
    AccionSobreSiMismo,
    ContrasenaDebil,
    CorreoInvalido,
    NombreInvalido,
    PermisoDenegado,
)
from dominio.usuarios import Correo, PoliticaContrasena, Rol, Sesion, Usuario

AHORA = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)


def _usuario(rol=Rol.USUARIO, id=1, nombre="Ana"):
    return Usuario(id, Correo("ana@correo.co"), nombre, "huella", rol)


def test_el_correo_se_guarda_sin_espacios_y_en_minusculas():
    assert Correo("  Ana.Perez@Correo.CO ").valor == "ana.perez@correo.co"


@pytest.mark.parametrize("texto", ["", "ana", "ana@correo", "ana perez@correo.co", "ana@@correo.co"])
def test_un_texto_sin_forma_de_correo_se_rechaza(texto):
    with pytest.raises(CorreoInvalido):
        Correo(texto)


def test_el_nombre_se_guarda_sin_espacios_de_mas():
    assert _usuario(nombre="  Ana   María ").nombre == "Ana María"


@pytest.mark.parametrize("nombre", ["", "   ", "x" * 61])
def test_un_nombre_vacio_o_muy_largo_se_rechaza(nombre):
    with pytest.raises(NombreInvalido):
        _usuario(nombre=nombre)


def test_una_contrasena_de_menos_de_ocho_caracteres_es_debil():
    with pytest.raises(ContrasenaDebil):
        PoliticaContrasena.validar("1234567")

    PoliticaContrasena.validar("12345678")


def test_exigir_admin_deja_pasar_a_un_admin():
    _usuario(Rol.ADMIN).exigir_admin()


def test_exigir_admin_rechaza_a_un_usuario_comun():
    with pytest.raises(PermisoDenegado):
        _usuario(Rol.USUARIO).exigir_admin()


def test_un_admin_no_puede_actuar_sobre_su_propia_cuenta():
    admin = _usuario(Rol.ADMIN, id=7)

    with pytest.raises(AccionSobreSiMismo):
        admin.exigir_otro_usuario(7)
    admin.exigir_otro_usuario(8)


def test_cambiar_estado_o_rol_devuelve_otra_cuenta_y_no_modifica_la_original():
    original = _usuario()

    desactivada = original.con_estado(False)
    admin = original.con_rol(Rol.ADMIN)

    assert (original.activo, original.rol) == (True, Rol.USUARIO)
    assert desactivada.activo is False
    assert admin.es_admin()


def test_una_sesion_es_vigente_hasta_que_llega_su_vencimiento():
    sesion = Sesion.abrir("huella", 1, AHORA, timedelta(days=7))

    assert sesion.vence_en == AHORA + timedelta(days=7)
    assert sesion.vigente(AHORA + timedelta(days=6, hours=23))
    assert not sesion.vigente(AHORA + timedelta(days=7))
