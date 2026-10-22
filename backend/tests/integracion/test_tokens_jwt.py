"""El adaptador de JWT con la libreria de verdad: firma, vencimiento, algoritmo, alcance y reclamos.

Importa jwt para fabricar tokens como los haria alguien de afuera.
"""
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from dominio.errores_usuarios import AlcanceInvalido, SesionInvalida
from dominio.identidad import IdentidadUsuario
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


def test_un_secreto_corto_no_se_acepta():
    with pytest.raises(ValueError):
        TokensJwt("corto", RelojSistema())


def test_el_secreto_se_crea_una_vez_y_despues_se_reutiliza(tmp_path):
    ruta = tmp_path / "matera.sqlite.secreto-jwt"

    primero = secreto_guardado(ruta)

    assert len(primero) >= 32
    assert ruta.read_text(encoding="utf-8") == primero
    assert secreto_guardado(ruta) == primero
