"""El reloj del juego desde la API: lo ve cualquiera con sesion, lo cambia solo un admin y sigue despues de reiniciar.

Cambiarlo no reagrupa el pasado: las lecturas que ya llegaron conservan su hora
de juego, y las nuevas se agrupan con la escala nueva.
"""
from datetime import datetime, timedelta, timezone

import pytest

from tests.integracion.conftest import ClienteApi, es_error
from tests.integracion.test_api_juego import SALUDABLE, Matera, juego, reloj  # noqa: F401 (fixtures)


def _reloj(api, token):
    respuesta = api.pedir("GET", "/juego/reloj", token)
    assert respuesta.status_code == 200, respuesta.get_json()
    return respuesta.get_json()


def test_cualquiera_con_sesion_ve_el_reloj_de_la_configuracion(juego):
    assert _reloj(juego, juego.cuenta()) == {"minutosPorDia": 6, "segundosPorHora": 15}


def test_sin_token_da_401_en_json(juego):
    for metodo in ("GET", "PUT"):
        respuesta = juego.pedir(metodo, "/juego/reloj", None, json={"minutosPorDia": 24})
        assert respuesta.status_code == 401 and respuesta.is_json


def test_un_admin_lo_cambia_para_todos(juego):
    ana = juego.cuenta()
    ada = juego.admin()
    respuesta = juego.pedir("PUT", "/juego/reloj", ada, json={"minutosPorDia": 24})
    assert respuesta.status_code == 200, respuesta.get_json()
    assert respuesta.get_json() == {"minutosPorDia": 24, "segundosPorHora": 60}
    assert _reloj(juego, ana) == {"minutosPorDia": 24, "segundosPorHora": 60}


def test_quien_no_es_admin_recibe_403_y_nada_cambia(juego):
    ana = juego.cuenta()
    respuesta = juego.pedir("PUT", "/juego/reloj", ana, json={"minutosPorDia": 24})
    assert es_error(respuesta, 403, "PERMISO_DENEGADO"), respuesta.get_json()
    assert _reloj(juego, ana)["minutosPorDia"] == 6


@pytest.mark.parametrize(
    "cuerpo, estado, codigo",
    [
        ({"minutosPorDia": 0}, 400, "RELOJ_INVALIDO"),
        ({"minutosPorDia": -3}, 400, "RELOJ_INVALIDO"),
        ({"minutosPorDia": 1e300}, 400, "RELOJ_INVALIDO"),
        ({"minutosPorDia": "seis"}, 400, "PARAMETRO_INVALIDO"),
        ({"minutosPorDia": True}, 400, "PARAMETRO_INVALIDO"),
        ({}, 400, "PARAMETRO_INVALIDO"),
        ([24], 400, "SOLICITUD_INVALIDA"),
    ],
)
def test_una_duracion_que_no_sirve_da_400_en_json(juego, cuerpo, estado, codigo):
    ada = juego.admin()
    respuesta = juego.pedir("PUT", "/juego/reloj", ada, json=cuerpo)
    assert es_error(respuesta, estado, codigo), respuesta.get_json()
    assert _reloj(juego, ada)["minutosPorDia"] == 6


def test_el_reloj_elegido_sigue_despues_de_reiniciar(juego, reloj):
    ada = juego.admin()
    assert juego.pedir("PUT", "/juego/reloj", ada, json={"minutosPorDia": 24}).status_code == 200
    reiniciado = ClienteApi(juego.config, reloj)  # la misma base, con MATERA_MINUTOS_POR_DIA_JUEGO = 6
    assert _reloj(reiniciado, reiniciado.entrar("ada@correo.co"))["minutosPorDia"] == 24


def test_la_escala_nueva_vale_para_las_lecturas_que_llegan_despues(juego, reloj):
    # Empieza en una hora en punto: con el reloj real (1 hora de juego = 1 hora), las lecturas siguientes
    # caen en la misma hora.
    reloj.momento = (datetime.now(timezone.utc) - timedelta(hours=3)).replace(minute=0, second=0, microsecond=0)
    ada = juego.admin()
    sala = Matera(juego, ada, reloj=reloj)
    mascota = lambda: juego.pedir("GET", "/juego/materas", ada).get_json()["materas"][0]  # noqa: E731

    # Con 1 dia = 6 minutos, cada lectura cada 15 s es una hora de juego.
    for _ in range(4):
        reloj.avanzar(seconds=15)
        assert sala.leer(SALUDABLE).status_code == 201
    assert mascota()["horasCuidada"] == 4

    assert juego.pedir("PUT", "/juego/reloj", ada, json={"minutosPorDia": 1440}).status_code == 200
    # Con el reloj real, otras 4 lecturas en un minuto son una sola hora; las 4 de antes no se reagrupan.
    for _ in range(4):
        reloj.avanzar(seconds=15)
        assert sala.leer(SALUDABLE).status_code == 201
    assert mascota()["horasCuidada"] == 5
    assert mascota()["puntos"] == 80
