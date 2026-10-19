"""Un cliente de la API armado con main.construir_app sobre una base temporal, para las pruebas del corte 2.

Tambien levanta el servidor real, con hilos, para las pruebas que necesitan
hablarle por la red: el recorrido completo, el WebSocket y el script de desarrollo.
"""
import json
import threading
import urllib.error
import urllib.request

import pytest
from werkzeug.serving import make_server

from crear_admin import main as crear_admin
from infraestructura.configuracion import Configuracion
from main import construir_app

ORIGEN_FRONT = "http://localhost:5500"


class ClienteApi:
    """Atajos sobre el test_client de Flask: registrar, entrar, crear un admin y pedir rutas con token."""

    def __init__(self, config: Configuracion):
        self.config = config
        self.http = construir_app(config).test_client()

    def pedir(self, metodo, ruta, token=None, json=None, cabeceras=None):
        cabeceras = dict(cabeceras or {})
        if token:
            cabeceras["Authorization"] = f"Bearer {token}"
        return self.http.open(f"/api/v1{ruta}", method=metodo, json=json, headers=cabeceras)

    def registrar(self, nombre="Ana", correo="ana@correo.co", contrasena="clave-segura"):
        return self.pedir("POST", "/usuarios", json={"nombre": nombre, "correo": correo, "contrasena": contrasena})

    def entrar(self, correo="ana@correo.co", contrasena="clave-segura") -> str:
        respuesta = self.pedir("POST", "/sesiones", json={"correo": correo, "contrasena": contrasena})
        assert respuesta.status_code == 201, respuesta.get_json()
        return respuesta.get_json()["token"]

    def cuenta(self, nombre="Ana", correo="ana@correo.co") -> str:
        """Registra la cuenta y devuelve un token de sesion."""
        assert self.registrar(nombre, correo).status_code == 201
        return self.entrar(correo)

    def admin(self, nombre="Ada", correo="ada@correo.co") -> str:
        """Registra la cuenta, la vuelve admin con crear_admin.py y devuelve su token."""
        assert self.registrar(nombre, correo).status_code == 201
        assert crear_admin([correo], self.config) == 0
        return self.entrar(correo)


@pytest.fixture
def config(tmp_path):
    # Pocas iteraciones de PBKDF2: con las 600 000 reales cada registro tarda casi un segundo.
    return Configuracion(
        puerto=5000, ruta_bd=tmp_path / "matera.sqlite", origenes_cors=(ORIGEN_FRONT,), iteraciones_contrasena=1_000
    )


@pytest.fixture
def api(config):
    return ClienteApi(config)


@pytest.fixture
def base_url(config):
    """El servidor de verdad, con threaded=True como app.run(), en un puerto libre."""
    servidor = make_server("127.0.0.1", 0, construir_app(config), threaded=True)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    yield f"http://127.0.0.1:{servidor.server_port}/api/v1"
    servidor.shutdown()
    hilo.join()


def pedir_http(base_url, metodo, ruta, cuerpo=None, token=None, clave_sensor=None):
    """Una peticion de verdad por la red. Devuelve (estado, cuerpo JSON)."""
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    if clave_sensor:
        cabeceras["X-Clave-Sensor"] = clave_sensor
    datos = json.dumps(cuerpo).encode() if cuerpo is not None else None
    peticion = urllib.request.Request(f"{base_url}{ruta}", data=datos, headers=cabeceras, method=metodo)
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def es_error(respuesta, estado: int, codigo: str) -> bool:
    """Respuesta de error con el cuerpo uniforme del corte 1: {error, mensaje, detalle}."""
    cuerpo = respuesta.get_json(silent=True) or {}
    return (
        respuesta.status_code == estado
        and respuesta.mimetype == "application/json"
        and set(cuerpo) == {"error", "mensaje", "detalle"}
        and cuerpo["error"] == codigo
    )
