"""Modo prueba de punta a punta: solo un admin pone un estado de mentira en una matera suya, y lo quita.

El estado de prueba se ve en GET /juego/materas y en la respuesta 201 a la
placa; los puntos y el diagnostico siguen siendo los reales.
"""
import pytest

from tests.integracion.conftest import es_error
from tests.integracion.test_api_juego import CRITICO, SALUDABLE, Matera

PRUEBA = {"etapa": "FLORECIDA", "condicion": "MARCHITA", "cara": "CRITICO", "dormida": False, "necesidad": "SED"}


def _mascota(api, token, planta_id):
    materas = api.pedir("GET", "/juego/materas", token).get_json()["materas"]
    return next(m for m in materas if m["plantaId"] == planta_id)


def test_un_admin_pone_y_quita_un_estado_de_prueba_en_su_matera(api):
    token = api.admin()
    matera = Matera(api, token)
    assert matera.leer(SALUDABLE).status_code == 201
    planta_id = matera.planta["id"]

    puesta = api.pedir("PUT", f"/juego/materas/{planta_id}/prueba", token, json=PRUEBA)
    assert puesta.status_code == 200, puesta.get_json()
    assert puesta.get_json() == {"plantaId": planta_id, "prueba": PRUEBA}

    mascota = _mascota(api, token, planta_id)
    assert (mascota["etapa"], mascota["condicion"], mascota["cara"]) == ("FLORECIDA", "MARCHITA", "CRITICO")
    assert mascota["necesidad"] == "SED" and mascota["dormida"] is False and mascota["aviso"] is None
    assert mascota["prueba"] == PRUEBA
    assert mascota["puntos"] == 10  # los puntos siguen siendo los reales

    # La placa recibe la prueba en la respuesta a su lectura, con el diagnostico real.
    lectura = matera.leer(SALUDABLE)
    assert lectura.status_code == 201
    assert lectura.get_json()["prueba"] == PRUEBA
    assert lectura.get_json()["diagnostico"]["estado"] == "SALUDABLE"
    assert _mascota(api, token, planta_id)["puntos"] == 20

    quitada = api.pedir("DELETE", f"/juego/materas/{planta_id}/prueba", token)
    assert quitada.status_code == 200 and quitada.get_json()["prueba"] is None
    mascota = _mascota(api, token, planta_id)
    assert mascota["prueba"] is None and mascota["cara"] == "SALUDABLE" and mascota["condicion"] == "SANA"
    assert matera.leer(SALUDABLE).get_json()["prueba"] is None


def test_dormida_no_tiene_globo(api):
    token = api.admin()
    matera = Matera(api, token)
    dormida = {**PRUEBA, "dormida": True}
    respuesta = api.pedir("PUT", f"/juego/materas/{matera.planta['id']}/prueba", token, json=dormida)
    assert respuesta.status_code == 200
    assert respuesta.get_json()["prueba"]["necesidad"] is None
    mascota = _mascota(api, token, matera.planta["id"])
    assert mascota["dormida"] is True and mascota["necesidad"] is None


def test_un_usuario_que_no_es_admin_recibe_403_en_json(api):
    token = api.cuenta()
    matera = Matera(api, token)
    for metodo, cuerpo in (("PUT", PRUEBA), ("DELETE", None)):
        respuesta = api.pedir(metodo, f"/juego/materas/{matera.planta['id']}/prueba", token, json=cuerpo)
        assert es_error(respuesta, 403, "PERMISO_DENEGADO"), respuesta.get_json()
    assert _mascota(api, token, matera.planta["id"])["prueba"] is None


def test_una_matera_ajena_da_el_mismo_404_que_una_inexistente(api):
    ajena = Matera(api, api.cuenta())
    token = api.admin()
    for planta_id in (ajena.planta["id"], 999999):
        respuesta = api.pedir("PUT", f"/juego/materas/{planta_id}/prueba", token, json=PRUEBA)
        assert es_error(respuesta, 404, "PLANTA_NO_ENCONTRADA"), respuesta.get_json()
    # Y la placa del otro usuario no recibe nada de prueba.
    assert ajena.leer(CRITICO).get_json()["prueba"] is None


def test_sin_token_da_401_en_json(api):
    respuesta = api.pedir("PUT", "/juego/materas/1/prueba", None, json=PRUEBA)
    assert respuesta.status_code == 401 and respuesta.is_json


@pytest.mark.parametrize(
    "cuerpo, campo",
    [
        ({**PRUEBA, "etapa": "ARBOL"}, "etapa"),
        ({**PRUEBA, "condicion": None}, "condicion"),
        ({**PRUEBA, "cara": 3}, "cara"),
        ({**PRUEBA, "dormida": "si"}, "dormida"),
        ({**PRUEBA, "necesidad": "HAMBRE"}, "necesidad"),
    ],
)
def test_un_estado_mal_formado_da_400_en_json(api, cuerpo, campo):
    token = api.admin()
    matera = Matera(api, token)
    respuesta = api.pedir("PUT", f"/juego/materas/{matera.planta['id']}/prueba", token, json=cuerpo)
    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO"), respuesta.get_json()
    assert respuesta.get_json()["detalle"]["campo"] == campo


def test_un_cuerpo_que_no_es_objeto_da_400(api):
    token = api.admin()
    matera = Matera(api, token)
    respuesta = api.pedir("PUT", f"/juego/materas/{matera.planta['id']}/prueba", token, json=[1, 2])
    assert es_error(respuesta, 400, "SOLICITUD_INVALIDA")
