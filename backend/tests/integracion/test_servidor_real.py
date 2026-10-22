"""El servidor de verdad, con hilos, como lo levanta python main.py.

El test_client de Flask atiende todo en el mismo hilo, asi que no detecta un
error que solo aparece en el servidor real: usar una conexion de sqlite3
desde otro hilo. Esta prueba levanta el servidor con threaded=True (lo que
hace app.run() por defecto, con el fixture base_url de conftest.py) y le
habla por HTTP.
"""
from concurrent.futures import ThreadPoolExecutor

from tests.integracion.conftest import medir_http
from tests.integracion.conftest import pedir_http as _pedir


def test_el_servidor_real_atiende_un_recorrido_completo_con_la_misma_base(base_url):
    assert _pedir(base_url, "POST", "/usuarios", {"nombre": "Ana", "correo": "ana@correo.co", "contrasena": "clave-segura"})[0] == 201
    _, sesion = _pedir(base_url, "POST", "/sesiones", {"correo": "ana@correo.co", "contrasena": "clave-segura"})
    token = sesion["token"]
    estado, matera = _pedir(base_url, "POST", "/plantas", {"apodo": "Sala", "especie": "potos", "codigo": "MT-0001-AA"}, token)
    assert estado == 201

    lecturas = {"humedad": 50, "luz": 800, "temperatura": 20}
    estado, medicion = medir_http(base_url, "MT-0001-AA", matera["clave"], lecturas)

    assert estado == 201 and medicion["diagnostico"]["estado"] == "SALUDABLE"
    assert _pedir(base_url, "GET", "/plantas", token=token)[1][0]["ultimaMedicion"]["estado"] == "SALUDABLE"


def test_el_servidor_real_atiende_peticiones_simultaneas(base_url):
    with ThreadPoolExecutor(max_workers=6) as hilos:
        respuestas = list(hilos.map(lambda _: _pedir(base_url, "GET", "/especies"), range(12)))

    assert {estado for estado, _ in respuestas} == {200}
    assert {len(especies) for _, especies in respuestas} == {5}
