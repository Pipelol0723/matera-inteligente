"""El WebSocket /api/v1/tiempo-real de punta a punta, con el servidor real y un cliente WebSocket de verdad.

El test_client de Flask no sabe abrir un WebSocket: estas pruebas usan el
fixture base_url de conftest.py, que levanta el servidor con hilos como app.run().
"""
import json

import pytest
from simple_websocket import Client, ConnectionClosed
from simple_websocket import ConnectionError as ConexionRechazada

from presentacion import tiempo_real
from tests.integracion.conftest import ORIGEN_FRONT, es_error, pedir_http

LECTURAS = {"humedad": 18, "luz": 800, "temperatura": 25}
NADA = 0.5  # segundos que se espera para confirmar que no llega ningun mensaje


class Pantalla:
    """Una pestana del front con la conexion en vivo abierta."""

    def __init__(self, base_url, cabeceras):
        self.ws = Client.connect(base_url.replace("http://", "ws://") + "/tiempo-real", headers=cabeceras)

    def autenticar(self, token):
        self.ws.send(json.dumps({"tipo": "autenticar", "token": token}))
        return self.mensaje()

    def mensaje(self, espera=5):
        texto = self.ws.receive(timeout=espera)
        return json.loads(texto) if texto is not None else None

    def cerrar(self):
        try:
            self.ws.close()
        except ConnectionClosed:
            pass


@pytest.fixture
def abrir(base_url):
    """abrir() abre una pestana desde el origen del front; todas se cierran al terminar la prueba."""
    abiertas = []

    def abrir_pantalla(cabeceras=None):
        pantalla = Pantalla(base_url, {"Origin": ORIGEN_FRONT} if cabeceras is None else cabeceras)
        abiertas.append(pantalla)
        return pantalla

    yield abrir_pantalla
    for pantalla in abiertas:
        pantalla.cerrar()


def _cuenta_con_matera(base_url, nombre="Ana", codigo="MT-0001-AA"):
    correo = f"{nombre.lower()}@correo.co"
    pedir_http(base_url, "POST", "/usuarios", {"nombre": nombre, "correo": correo, "contrasena": "clave-segura"})
    _, sesion = pedir_http(base_url, "POST", "/sesiones", {"correo": correo, "contrasena": "clave-segura"})
    estado, matera = pedir_http(
        base_url, "POST", "/plantas", {"apodo": "Sala", "especie": "potos", "codigo": codigo}, sesion["token"]
    )
    assert estado == 201
    return sesion["token"], matera


def _medir(base_url, matera, lecturas=LECTURAS):
    ruta = f"/sensores/{matera['codigo']}/mediciones"
    return pedir_http(base_url, "POST", ruta, lecturas, clave_sensor=matera["clave"])


def test_el_dueno_recibe_en_vivo_cada_medicion_de_su_planta(base_url, abrir):
    token, matera = _cuenta_con_matera(base_url)
    pantalla = abrir()
    assert pantalla.autenticar(token) == {"tipo": "listo", "usuario": {"id": 1, "nombre": "Ana"}}

    estado, respuesta = _medir(base_url, matera)

    assert estado == 201
    mensaje = pantalla.mensaje()
    assert mensaje["tipo"] == "medicion"
    assert mensaje["planta"] == matera["planta"]
    assert mensaje["diagnostico"] == respuesta["diagnostico"]
    # La misma forma que la tarjeta de Mis materas: el front la reemplaza tal cual.
    assert mensaje["medicion"] == pedir_http(base_url, "GET", "/plantas", token=token)[1][0]["ultimaMedicion"]


def test_cada_pestana_de_ana_recibe_sus_mediciones_y_beto_no_las_ve(base_url, abrir):
    token_ana, matera_ana = _cuenta_con_matera(base_url)
    token_beto, matera_beto = _cuenta_con_matera(base_url, "Beto", "MT-0002-BB")
    sala, cocina, de_beto = abrir(), abrir(), abrir()
    sala.autenticar(token_ana)
    cocina.autenticar(token_ana)
    de_beto.autenticar(token_beto)

    _medir(base_url, matera_ana)

    assert sala.mensaje()["planta"]["id"] == cocina.mensaje()["planta"]["id"] == matera_ana["planta"]["id"]
    assert de_beto.mensaje(NADA) is None

    _medir(base_url, matera_beto)

    assert de_beto.mensaje()["planta"]["id"] == matera_beto["planta"]["id"]
    assert sala.mensaje(NADA) is None and cocina.mensaje(NADA) is None


def test_un_token_que_no_sirve_recibe_un_error_en_json_y_se_cierra(base_url, abrir):
    pantalla = abrir()

    mensaje = pantalla.autenticar("token-inventado")

    assert (mensaje["tipo"], mensaje["error"]) == ("error", "SESION_INVALIDA")
    with pytest.raises(ConnectionClosed) as cierre:
        pantalla.ws.receive(timeout=5)
    assert cierre.value.reason == 1008


@pytest.mark.parametrize(
    "primero",
    ["hola", json.dumps({"tipo": "autenticar"}), json.dumps({"tipo": "otro", "token": "x"}), json.dumps(["x"])],
    ids=["no es json", "sin token", "otro tipo", "no es un objeto"],
)
def test_si_el_primer_mensaje_no_es_autenticar_se_responde_un_error_y_se_cierra(base_url, abrir, primero):
    pantalla = abrir()

    pantalla.ws.send(primero)

    assert pantalla.mensaje()["error"] == "SOLICITUD_INVALIDA"
    with pytest.raises(ConnectionClosed):
        pantalla.ws.receive(timeout=5)


def test_si_el_token_no_llega_a_tiempo_se_cierra(base_url, abrir, monkeypatch):
    monkeypatch.setattr(tiempo_real, "ESPERA_AUTENTICACION", 0.3)

    pantalla = abrir()

    assert pantalla.mensaje()["error"] == "SESION_INVALIDA"


def test_al_cerrar_sesion_tambien_se_cierra_la_conexion_en_vivo(base_url, abrir, monkeypatch):
    monkeypatch.setattr(tiempo_real, "REVISION_SESION", 0.2)
    token, _ = _cuenta_con_matera(base_url)
    pantalla = abrir()
    pantalla.autenticar(token)

    assert pedir_http(base_url, "DELETE", "/sesiones/actual", token=token)[0] == 200

    assert pantalla.mensaje()["error"] == "SESION_INVALIDA"


def test_una_pestana_que_se_cerro_no_impide_guardar_la_medicion(base_url, abrir):
    token, matera = _cuenta_con_matera(base_url)
    pantalla = abrir()
    pantalla.autenticar(token)
    pantalla.cerrar()

    assert _medir(base_url, matera)[0] == 201

    registros = pedir_http(base_url, "GET", f"/plantas/{matera['planta']['id']}/historial", token=token)[1]["registros"]
    assert len(registros) == 1


def test_otro_origen_no_puede_abrir_la_conexion_en_vivo(base_url):
    with pytest.raises(ConexionRechazada) as rechazo:
        Client.connect(base_url.replace("http://", "ws://") + "/tiempo-real", headers={"Origin": "http://malo.example"})

    assert rechazo.value.status_code == 403


def test_el_rechazo_por_origen_tambien_es_json(api):
    cabeceras = {
        "Origin": "http://malo.example",
        "Connection": "Upgrade",
        "Upgrade": "websocket",
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Key": "dGhlIHNhbXBsZSBub25jZQ==",
    }

    respuesta = api.http.get("/api/v1/tiempo-real", headers=cabeceras)

    assert es_error(respuesta, 403, "ORIGEN_NO_PERMITIDO")


def test_un_script_sin_origin_igual_tiene_que_autenticarse(base_url, abrir):
    token, _ = _cuenta_con_matera(base_url)

    assert abrir(cabeceras={}).autenticar(token)["tipo"] == "listo"
    assert abrir(cabeceras={}).autenticar("token-inventado")["error"] == "SESION_INVALIDA"


def test_un_get_normal_a_la_ruta_del_websocket_responde_400_en_json(api):
    respuesta = api.pedir("GET", "/tiempo-real")

    assert es_error(respuesta, 400, "SOLICITUD_INVALIDA")
    assert "WebSocket" in respuesta.get_json()["mensaje"]
