"""La ruta de los dispositivos de punta a punta (R2 y R7): canje de la clave por un JWT y lecturas con ese token."""
from datetime import datetime, timedelta, timezone

import pytest

from tests.integracion.conftest import es_error

LECTURAS = {"humedad": 50, "luz": 800, "temperatura": 22}


@pytest.fixture
def ana(api):
    return api.cuenta()


@pytest.fixture
def matera(api, ana):
    """La Sala de Ana (potos) con el sensor MT-0001-AA: {planta, codigo, clave}."""
    respuesta = api.pedir("POST", "/plantas", ana, json={"apodo": "Sala", "especie": "potos", "codigo": "MT-0001-AA"})
    assert respuesta.status_code == 201
    return respuesta.get_json()


@pytest.fixture
def token(api, matera):
    respuesta = api.canjear("MT-0001-AA", matera["clave"])
    assert respuesta.status_code == 200
    return respuesta.get_json()["token"]


def _historial(api, ana, matera):
    return api.pedir("GET", f"/plantas/{matera['planta']['id']}/historial", ana).get_json()["registros"]


def test_el_canje_entrega_el_token_y_cuando_vence(api, matera):
    respuesta = api.canjear("mt-0001-aa", matera["clave"])

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert set(cuerpo) == {"token", "venceEn"}
    assert cuerpo["token"].count(".") == 2  # cabecera.reclamos.firma
    vence = datetime.fromisoformat(cuerpo["venceEn"])
    assert timedelta(hours=23) < vence - datetime.now(timezone.utc) <= timedelta(hours=24)


def test_la_lectura_se_guarda_con_su_hora_y_su_sensor_y_se_ve_en_mis_materas(api, ana, matera, token):
    respuesta = api.reportar("MT-0001-AA", token, LECTURAS, momento="2026-10-22T10:30:00-05:00")

    assert respuesta.status_code == 201
    assert respuesta.get_json()["diagnostico"]["estado"] == "SALUDABLE"
    [registro] = _historial(api, ana, matera)
    assert (registro["origen"], registro["momento"]) == ("MT-0001-AA", "2026-10-22T15:30:00+00:00")
    assert api.pedir("GET", "/plantas", ana).get_json()[0]["ultimaMedicion"]["momento"] == "2026-10-22T15:30:00+00:00"


@pytest.mark.parametrize(
    ("cuerpo", "codigo_error", "campo"),
    [
        ({"dispositivo": "MT-0001-AA", "lecturas": LECTURAS}, "PARAMETRO_INVALIDO", "momento"),
        ({"dispositivo": "MT-0001-AA", "momento": "ayer", "lecturas": LECTURAS}, "PARAMETRO_INVALIDO", "momento"),
        ({"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:00:00Z"}, "PARAMETRO_INVALIDO", "lecturas"),
        ({"momento": "2026-10-22T15:00:00Z", "lecturas": LECTURAS}, "PARAMETRO_INVALIDO", "dispositivo"),
        ({"dispositivo": "sensor-1", "momento": "2026-10-22T15:00:00Z", "lecturas": LECTURAS}, "PARAMETRO_INVALIDO", "dispositivo"),
        ({"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:00:00Z", "lecturas": {**LECTURAS, "luz": "mucha"}}, "PARAMETRO_INVALIDO", "luz"),
        ({"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:00:00Z", "lecturas": {"humedad": 50, "luz": 800}}, "PARAMETRO_INVALIDO", "temperatura"),
        ({"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:00:00Z", "lecturas": {**LECTURAS, "humedad": 150}}, "PARAMETRO_INVALIDO", "humedad"),
        ({"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:00:00", "lecturas": LECTURAS}, "MOMENTO_INVALIDO", "momento"),
    ],
    ids=[
        "sin hora",
        "hora que no es ISO 8601",
        "sin lecturas",
        "sin dispositivo",
        "dispositivo mal escrito",
        "texto en vez de numero",
        "falta un parametro",
        "valor imposible",
        "hora sin zona horaria",
    ],
)
def test_un_cuerpo_invalido_responde_400_con_el_campo_y_no_se_guarda(api, ana, matera, token, cuerpo, codigo_error, campo):
    respuesta = api.pedir("POST", "/dispositivos/MT-0001-AA/lecturas", token, json=cuerpo)

    assert es_error(respuesta, 400, codigo_error)
    assert respuesta.get_json()["detalle"]["campo"] == campo
    assert _historial(api, ana, matera) == []


def test_un_json_mal_formado_responde_400(api, token):
    respuesta = api.http.post(
        "/api/v1/dispositivos/MT-0001-AA/lecturas",
        data=b'{"dispositivo": "MT-0001-AA", "momen',
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )

    assert es_error(respuesta, 400, "SOLICITUD_INVALIDA")


def test_una_lectura_del_futuro_responde_400_y_no_se_guarda(api, ana, matera, token):
    futuro = (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()

    assert es_error(api.reportar("MT-0001-AA", token, LECTURAS, momento=futuro), 400, "MOMENTO_INVALIDO")
    assert _historial(api, ana, matera) == []


@pytest.mark.parametrize(
    "cabeceras",
    [{}, {"Authorization": "token-suelto"}, {"Authorization": "Bearer "}, {"Authorization": "Bearer no.es.un-jwt"}],
)
def test_sin_un_token_valido_la_lectura_responde_401(api, matera, cabeceras):
    cuerpo = {"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:00:00Z", "lecturas": LECTURAS}

    respuesta = api.pedir("POST", "/dispositivos/MT-0001-AA/lecturas", json=cuerpo, cabeceras=cabeceras)

    assert es_error(respuesta, 401, "CREDENCIAL_DISPOSITIVO_INVALIDA")


def test_un_canje_nuevo_deja_sin_efecto_el_token_anterior(api, matera, token):
    nuevo = api.canjear("MT-0001-AA", matera["clave"]).get_json()["token"]

    assert es_error(api.reportar("MT-0001-AA", token, LECTURAS), 401, "CREDENCIAL_DISPOSITIVO_INVALIDA")
    assert api.reportar("MT-0001-AA", nuevo, LECTURAS).status_code == 201


def test_cambiar_el_sensor_deja_sin_efecto_la_clave_y_el_token(api, ana, matera, token):
    nuevo = api.pedir("PUT", f"/plantas/{matera['planta']['id']}/sensor", ana, json={"codigo": "MT-0001-AA"}).get_json()

    assert es_error(api.reportar("MT-0001-AA", token, LECTURAS), 401, "CREDENCIAL_DISPOSITIVO_INVALIDA")
    assert es_error(api.canjear("MT-0001-AA", matera["clave"]), 401, "CLAVE_SENSOR_INVALIDA")
    assert api.medir("MT-0001-AA", nuevo["clave"], LECTURAS).status_code == 201


@pytest.mark.parametrize(
    ("codigo", "cuerpo"),
    [("MT-0001-AA", {"clave": "otra-clave"}), ("MT-9999-ZZ", {"clave": "otra-clave"}), ("cualquiera", {"clave": "x"})],
)
def test_el_canje_responde_el_mismo_401_si_la_clave_o_el_codigo_no_sirven(api, matera, codigo, cuerpo):
    assert es_error(api.pedir("POST", f"/dispositivos/{codigo}/token", json=cuerpo), 401, "CLAVE_SENSOR_INVALIDA")


def test_un_canje_sin_clave_responde_400(api, matera):
    respuesta = api.pedir("POST", "/dispositivos/MT-0001-AA/token", json={})

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"] == {"campo": "clave", "motivo": "ausente"}


def test_el_token_de_un_usuario_no_sirve_para_reportar_lecturas(api, ana, matera):
    assert es_error(api.reportar("MT-0001-AA", ana, LECTURAS), 403, "ALCANCE_INVALIDO")


def test_el_token_de_un_sensor_no_sirve_en_las_rutas_de_usuario(api, token):
    assert es_error(api.pedir("GET", "/plantas", token), 403, "ALCANCE_INVALIDO")


def test_el_token_de_un_sensor_no_sirve_para_reportar_por_otro(api, matera, token):
    beto = api.cuenta("Beto", "beto@correo.co")
    api.pedir("POST", "/plantas", beto, json={"apodo": "Patio", "especie": "potos", "codigo": "MT-0002-BB"})

    por_la_url = api.reportar("MT-0002-BB", token, LECTURAS)
    por_el_cuerpo = api.reportar("MT-0001-AA", token, LECTURAS, dispositivo="MT-0002-BB")

    assert es_error(por_la_url, 403, "DISPOSITIVO_AJENO")
    assert es_error(por_el_cuerpo, 403, "DISPOSITIVO_AJENO")


def test_la_ruta_vieja_del_sensor_ya_no_existe_y_responde_404_en_json(api, matera):
    respuesta = api.pedir("POST", "/sensores/MT-0001-AA/mediciones", json=LECTURAS, cabeceras={"X-Clave-Sensor": matera["clave"]})

    assert es_error(respuesta, 404, "RUTA_NO_ENCONTRADA")


@pytest.mark.parametrize("ruta", ["/dispositivos/MT-0001-AA/token", "/dispositivos/MT-0001-AA/lecturas"])
def test_las_rutas_de_dispositivos_responden_405_en_json_a_otro_metodo(api, ruta):
    assert es_error(api.pedir("GET", ruta), 405, "METODO_NO_PERMITIDO")


@pytest.mark.parametrize("momento", ["0001-01-01T00:00:00+05:00", "9999-12-31T23:59:59-05:00"])
def test_una_hora_que_no_cabe_en_utc_responde_400_y_no_500(api, token, momento):
    respuesta = api.reportar("MT-0001-AA", token, LECTURAS, momento=momento)

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"] == {"campo": "momento", "motivo": "formato"}


def test_un_id_de_planta_que_no_cabe_en_sqlite_responde_404(api, ana):
    for metodo, ruta in (("GET", "/historial"), ("DELETE", ""), ("PUT", "/sensor")):
        respuesta = api.pedir(metodo, f"/plantas/{2**63}{ruta}", ana, json={"codigo": "MT-0009-ZZ"})
        assert es_error(respuesta, 404, "PLANTA_NO_ENCONTRADA"), (metodo, ruta)


def test_los_sensores_de_una_cuenta_desactivada_quedan_en_pausa(api, ana, matera, token):
    admin = api.admin()
    ana_id = api.pedir("GET", "/usuarios/yo", ana).get_json()["id"]
    assert api.pedir("PATCH", f"/admin/usuarios/{ana_id}", admin, json={"activo": False}).status_code == 200

    assert es_error(api.canjear("MT-0001-AA", matera["clave"]), 403, "CUENTA_DESACTIVADA")
    assert es_error(api.reportar("MT-0001-AA", token, LECTURAS), 403, "CUENTA_DESACTIVADA")

    assert api.pedir("PATCH", f"/admin/usuarios/{ana_id}", admin, json={"activo": True}).status_code == 200
    assert api.medir("MT-0001-AA", matera["clave"], LECTURAS).status_code == 201
