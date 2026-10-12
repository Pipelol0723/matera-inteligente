"""Adaptadores de seguridad, del reloj y el script crear_admin.py."""
from datetime import timezone

from crear_admin import main as crear_admin
from dominio.usuarios import Correo, Rol, Usuario
from infraestructura.configuracion import Configuracion
from infraestructura.reloj import RelojSistema
from infraestructura.seguridad import CifradorPbkdf2, GeneradorSecretosSeguro
from infraestructura.sqlite import BaseDatos, RepositorioUsuariosSqlite

POCAS_ITERACIONES = 1_000


def test_la_contrasena_se_verifica_y_no_queda_en_claro():
    cifrador = CifradorPbkdf2(POCAS_ITERACIONES)

    cifrado = cifrador.cifrar("clave-segura")

    assert cifrado.startswith("pbkdf2_sha256$1000$")
    assert "clave-segura" not in cifrado
    assert cifrador.verificar("clave-segura", cifrado)
    assert not cifrador.verificar("clave-mala", cifrado)


def test_la_misma_contrasena_da_cifrados_distintos_por_la_sal():
    cifrador = CifradorPbkdf2(POCAS_ITERACIONES)

    assert cifrador.cifrar("clave-segura") != cifrador.cifrar("clave-segura")


def test_una_contrasena_cifrada_con_otras_iteraciones_se_sigue_verificando():
    cifrado = CifradorPbkdf2(POCAS_ITERACIONES).cifrar("clave-segura")

    assert CifradorPbkdf2(2_000).verificar("clave-segura", cifrado)


def test_un_cifrado_mal_formado_no_se_verifica():
    assert not CifradorPbkdf2(POCAS_ITERACIONES).verificar("clave", "texto-cualquiera")


def test_los_secretos_son_largos_distintos_y_se_guardan_como_sha256():
    generador = GeneradorSecretosSeguro()

    uno, otro = generador.nuevo(), generador.nuevo()

    assert uno != otro and len(uno) >= 43
    assert len(generador.huella(uno)) == 64
    assert generador.coincide(uno, generador.huella(uno))
    assert not generador.coincide(otro, generador.huella(uno))


def test_el_reloj_da_la_hora_en_utc():
    assert RelojSistema().ahora().tzinfo is timezone.utc


def _config(tmp_path):
    return Configuracion(puerto=5000, ruta_bd=tmp_path / "matera.sqlite", origenes_cors=())


def test_crear_admin_da_el_rol_a_una_cuenta_registrada(tmp_path, capsys):
    usuarios = RepositorioUsuariosSqlite(BaseDatos(tmp_path / "matera.sqlite").preparar())
    usuarios.guardar(Usuario(None, Correo("ada@correo.co"), "Ada", "h"))

    codigo = crear_admin([" ADA@correo.co "], _config(tmp_path))

    assert codigo == 0
    assert "Ada (ada@correo.co) ahora es administrador." in capsys.readouterr().out
    assert usuarios.por_correo(Correo("ada@correo.co")).rol is Rol.ADMIN


def test_crear_admin_con_un_correo_sin_cuenta_explica_que_hacer(tmp_path, capsys):
    assert crear_admin(["nadie@correo.co"], _config(tmp_path)) == 1
    assert "Primero cree la cuenta" in capsys.readouterr().err


def test_crear_admin_sin_correo_muestra_el_uso(tmp_path, capsys):
    assert crear_admin([], _config(tmp_path)) == 2
    assert "Uso:" in capsys.readouterr().err
