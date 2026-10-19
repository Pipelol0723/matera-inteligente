"""La herramienta de desarrollo manda una medicion como el ESP32, contra el servidor real."""
import pytest

from herramientas import enviar_medicion
from tests.integracion.conftest import pedir_http


@pytest.fixture
def matera(base_url):
    """La cuenta de Ana con una matera; devuelve (token, matera con su clave)."""
    pedir_http(base_url, "POST", "/usuarios", {"nombre": "Ana", "correo": "ana@correo.co", "contrasena": "clave-segura"})
    _, sesion = pedir_http(base_url, "POST", "/sesiones", {"correo": "ana@correo.co", "contrasena": "clave-segura"})
    cuerpo = {"apodo": "Sala", "especie": "potos", "codigo": "MT-0001-AA"}
    return sesion["token"], pedir_http(base_url, "POST", "/plantas", cuerpo, sesion["token"])[1]


def _registros(base_url, token, planta_id):
    return pedir_http(base_url, "GET", f"/plantas/{planta_id}/historial", token=token)[1]["registros"]


def test_la_medicion_de_la_herramienta_queda_en_el_historial_con_el_codigo_del_sensor(base_url, matera, capsys):
    token, nueva = matera

    estado = enviar_medicion.main(["mt-0001-aa", "--api", base_url, "--clave", nueva["clave"], "--humedad", "30"])

    assert estado == 0
    assert "201 · Sala (potos): EN_RIESGO" in capsys.readouterr().out
    [registro] = _registros(base_url, token, nueva["planta"]["id"])
    assert (registro["origen"], registro["lecturas"][0]["valor"]) == ("MT-0001-AA", 30.0)


def test_la_clave_puede_venir_de_la_variable_de_entorno_y_se_repite_las_veces_pedidas(base_url, matera, monkeypatch):
    token, nueva = matera
    monkeypatch.setenv("MATERA_CLAVE_SENSOR", nueva["clave"])

    assert enviar_medicion.main(["MT-0001-AA", "--api", base_url, "--cada", "0", "--veces", "3"]) == 0

    assert len(_registros(base_url, token, nueva["planta"]["id"])) == 3


def test_con_una_clave_mala_muestra_el_error_de_la_api_y_no_se_guarda_nada(base_url, matera, capsys):
    token, nueva = matera

    estado = enviar_medicion.main(["MT-0001-AA", "--api", base_url, "--clave", "inventada"])

    assert estado == 1
    assert "401 CLAVE_SENSOR_INVALIDA" in capsys.readouterr().err
    assert _registros(base_url, token, nueva["planta"]["id"]) == []


def test_sin_api_dice_que_no_la_encontro():
    assert enviar_medicion.main(["MT-0001-AA", "--api", "http://127.0.0.1:9/api/v1", "--clave", "x"]) == 2
