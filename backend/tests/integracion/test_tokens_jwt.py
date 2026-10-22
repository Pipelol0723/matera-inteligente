"""El adaptador de JWT con la libreria de verdad: firma, vencimiento, algoritmo, alcance y reclamos.

Importa jwt para fabricar tokens como los haria alguien de afuera.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from dominio.errores_usuarios import AlcanceInvalido, CredencialDispositivoInvalida, SesionInvalida
from dominio.identidad import IdentidadDispositivo, IdentidadUsuario
from dominio.sensores import CodigoSensor
from infraestructura.reloj import RelojSistema
from infraestructura.tokens_jwt import ALGORITMO, EMISOR, TokensJwt, secreto_guardado

SECRETO = "s" * 40
ANA = IdentidadUsuario(7, "id-del-token")


@pytest.fixture
def tokens():
    return TokensJwt(SECRETO, RelojSistema())


def _en(horas: float) -> datetime:
    return datetime.now(timezone.utc) + timedelta(hours=horas)


def _reclamos(**cambios) -> dict:
    ahora = datetime.now(timezone.utc)
    reclamos = {"iss": EMISOR, "sub": "7", "alcance": "usuario", "jti": "id-del-token", "iat": ahora, "exp": _en(1)}
    reclamos.update(cambios)
    return {clave: valor for clave, valor in reclamos.items() if valor is not None}


def test_el_token_emitido_se_verifica_y_devuelve_la_misma_identidad(tokens):
    token = tokens.emitir(ANA, _en(1))

    assert tokens.verificar_usuario(token) == ANA


def test_el_token_trae_el_alcance_y_el_id_pero_ningun_dato_de_la_cuenta(tokens):
    reclamos = jwt.decode(tokens.emitir(ANA, _en(1)), SECRETO, algorithms=[ALGORITMO], issuer=EMISOR)

    assert {clave: reclamos[clave] for clave in ("iss", "sub", "alcance", "jti")} == {
        "iss": "matera-inteligente",
        "sub": "7",
        "alcance": "usuario",
        "jti": "id-del-token",
    }
    assert set(reclamos) == {"iss", "sub", "alcance", "jti", "iat", "exp"}


def test_un_token_con_la_firma_alterada_no_sirve(tokens):
    cabecera, cuerpo, firma = tokens.emitir(ANA, _en(1)).split(".")
    otra_firma = ("A" if firma[0] != "A" else "B") + firma[1:]

    with pytest.raises(SesionInvalida):
        tokens.verificar_usuario(f"{cabecera}.{cuerpo}.{otra_firma}")


@pytest.mark.parametrize(
    "token",
    [
        jwt.encode(_reclamos(), "otro-secreto-de-cuarenta-caracteres-xxxx", algorithm=ALGORITMO),
        jwt.encode(_reclamos(), SECRETO, algorithm="HS512"),
        jwt.encode(_reclamos(), None, algorithm="none"),
        jwt.encode(_reclamos(exp=_en(-1)), SECRETO, algorithm=ALGORITMO),
        jwt.encode(_reclamos(iss="otro-sistema"), SECRETO, algorithm=ALGORITMO),
        jwt.encode(_reclamos(jti=None), SECRETO, algorithm=ALGORITMO),
        jwt.encode(_reclamos(alcance=None), SECRETO, algorithm=ALGORITMO),
        jwt.encode(_reclamos(sub="ana"), SECRETO, algorithm=ALGORITMO),
        "no-es-un-jwt",
        "",
    ],
    ids=[
        "otro secreto",
        "otro algoritmo",
        "sin firma (alg none)",
        "vencido",
        "otro emisor",
        "sin jti",
        "sin alcance",
        "sub que no es un id",
        "mal formado",
        "vacio",
    ],
)
def test_un_token_que_no_es_valido_da_sesion_invalida(tokens, token):
    with pytest.raises(SesionInvalida):
        tokens.verificar_usuario(token)


def test_un_token_valido_de_otro_alcance_no_sirve_como_token_de_usuario(tokens):
    del_sensor = jwt.encode(_reclamos(alcance="lecturas", sub="MT-0001-AA"), SECRETO, algorithm=ALGORITMO)

    with pytest.raises(AlcanceInvalido):
        tokens.verificar_usuario(del_sensor)


SENSOR = IdentidadDispositivo(CodigoSensor("MT-0001-AA"), "id-del-canje")


def test_el_token_de_un_sensor_tiene_alcance_lecturas_y_su_codigo(tokens):
    token = tokens.emitir(SENSOR, _en(24))

    reclamos = jwt.decode(token, SECRETO, algorithms=[ALGORITMO], issuer=EMISOR)
    assert (reclamos["alcance"], reclamos["sub"], reclamos["jti"]) == ("lecturas", "MT-0001-AA", "id-del-canje")
    assert tokens.verificar_dispositivo(token) == SENSOR


def test_el_token_de_un_usuario_no_sirve_como_token_de_sensor(tokens):
    with pytest.raises(AlcanceInvalido):
        tokens.verificar_dispositivo(tokens.emitir(ANA, _en(1)))


@pytest.mark.parametrize(
    "token",
    [
        jwt.encode(_reclamos(alcance="lecturas", sub="MT-0001-AA", exp=_en(-1)), SECRETO, algorithm=ALGORITMO),
        jwt.encode(_reclamos(alcance="lecturas", sub="no-es-un-codigo"), SECRETO, algorithm=ALGORITMO),
        jwt.encode(_reclamos(alcance="lecturas", sub="MT-0001-AA"), "otro-secreto-de-cuarenta-caracteres-xxxx", algorithm=ALGORITMO),
        "no-es-un-jwt",
    ],
    ids=["vencido", "sub que no es un codigo", "otro secreto", "mal formado"],
)
def test_un_token_de_sensor_que_no_es_valido_da_credencial_invalida(tokens, token):
    with pytest.raises(CredencialDispositivoInvalida):
        tokens.verificar_dispositivo(token)


def test_un_secreto_corto_no_se_acepta():
    with pytest.raises(ValueError):
        TokensJwt("corto", RelojSistema())


def test_el_secreto_se_crea_una_vez_y_despues_se_reutiliza(tmp_path):
    ruta = tmp_path / "matera.sqlite.secreto-jwt"

    primero = secreto_guardado(ruta)

    assert len(primero) >= 32
    assert ruta.read_text(encoding="utf-8") == primero
    assert secreto_guardado(ruta) == primero
