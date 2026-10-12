"""El servidor de verdad, con hilos, como lo levanta python main.py.

El test_client de Flask atiende todo en el mismo hilo, asi que no detecta un
error que solo aparece en el servidor real: usar una conexion de sqlite3
desde otro hilo. Esta prueba levanta el servidor con threaded=True (lo que
hace app.run() por defecto) y le habla por HTTP.
"""
import json
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

import pytest
from werkzeug.serving import make_server

from main import construir_app


@pytest.fixture
def base_url(config):
    servidor = make_server("127.0.0.1", 0, construir_app(config), threaded=True)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_port}/api/v1"
    servidor.shutdown()
    hilo.join()


def _pedir(base_url, metodo, ruta, cuerpo=None, token=None):
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(f"{base_url}{ruta}", data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def test_el_servidor_real_atiende_un_recorrido_completo_con_la_misma_base(base_url):
    assert _pedir(base_url, "POST", "/usuarios", {"nombre": "Ana", "correo": "ana@correo.co", "contrasena": "clave-segura"})[0] == 201
    _, sesion = _pedir(base_url, "POST", "/sesiones", {"correo": "ana@correo.co", "contrasena": "clave-segura"})
    token = sesion["token"]
    estado, planta = _pedir(base_url, "POST", "/plantas", {"apodo": "Sala", "especie": "potos"}, token)
    assert estado == 201

    estado, medicion = _pedir(base_url, "POST", f"/plantas/{planta['id']}/mediciones", {"humedad": 50, "luz": 800, "temperatura": 20}, token)

    assert estado == 201 and medicion["diagnostico"]["estado"] == "SALUDABLE"
    assert _pedir(base_url, "GET", "/plantas", token=token)[1][0]["ultimaMedicion"]["estado"] == "SALUDABLE"


def test_el_servidor_real_atiende_peticiones_simultaneas(base_url):
    with ThreadPoolExecutor(max_workers=6) as hilos:
        respuestas = list(hilos.map(lambda _: _pedir(base_url, "GET", "/especies"), range(12)))

    assert {estado for estado, _ in respuestas} == {200}
    assert {len(especies) for _, especies in respuestas} == {5}
