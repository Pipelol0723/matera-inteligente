"""El WebSocket /api/v1/tiempo-real de punta a punta, con el servidor real y un cliente WebSocket de verdad.

El test_client de Flask no sabe abrir un WebSocket: estas pruebas usan el
fixture base_url de conftest.py, que levanta el servidor con hilos como app.run().
"""
import http.client
import json
import urllib.parse

import pytest
from simple_websocket import Client, ConnectionClosed
from simple_websocket import ConnectionError as ConexionRechazada

from crear_admin import main as crear_admin
from dominio.errores_usuarios import SesionInvalida
from presentacion import tiempo_real
from tests.integracion.conftest import ORIGEN_FRONT, es_error, medir_http, pedir_http

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
        except (ConnectionClosed, OSError):  # el servidor ya pudo haber cerrado el socket
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
    return medir_http(base_url, matera["codigo"], matera["clave"], lecturas)


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
    [
        "hola",
        json.dumps({"tipo": "autenticar"}),
        json.dumps({"tipo": "otro", "token": "x"}),
        json.dumps(["x"]),
        "[" * 3000,
    ],
    ids=["no es json", "sin token", "otro tipo", "no es un objeto", "json anidado 3000 veces"],
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


def test_un_token_con_caracteres_imposibles_recibe_sesion_invalida_en_json(base_url, abrir):
    pantalla = abrir()

    # Un surrogate suelto, como el que produce JSON.stringify: no se puede pasar a UTF-8.
    pantalla.ws.send('{"tipo": "autenticar", "token": "\\ud800"}')

    assert pantalla.mensaje()["error"] == "SESION_INVALIDA"


def test_una_sesion_valida_sigue_abierta_despues_de_varias_revisiones(base_url, abrir, monkeypatch):
    monkeypatch.setattr(tiempo_real, "REVISION_SESION", 0.2)
    token, matera = _cuenta_con_matera(base_url)
    pantalla = abrir()
    pantalla.autenticar(token)

    assert pantalla.mensaje(1.0) is None  # pasan unas cinco revisiones sin error
    _medir(base_url, matera)

    assert pantalla.mensaje()["tipo"] == "medicion"


def test_al_borrar_una_cuenta_su_pestana_no_recibe_nada_de_quien_hereda_su_id(base_url, abrir, config):
    # SQLite le da a la cuenta nueva el id de la ultima que se borro.
    pedir_http(base_url, "POST", "/usuarios", {"nombre": "Ada", "correo": "ada@correo.co", "contrasena": "clave-segura"})
    assert crear_admin(["ada@correo.co"], config) == 0
    admin = pedir_http(base_url, "POST", "/sesiones", {"correo": "ada@correo.co", "contrasena": "clave-segura"})[1]["token"]
    token_beto, _ = _cuenta_con_matera(base_url, "Beto", "MT-0002-BB")
    de_beto = abrir()
    de_beto.autenticar(token_beto)

    assert pedir_http(base_url, "DELETE", "/admin/usuarios/2", token=admin)[0] == 200
    token_carla, matera_carla = _cuenta_con_matera(base_url, "Carla", "MT-0003-CC")
    assert pedir_http(base_url, "GET", "/usuarios/yo", token=token_carla)[1]["id"] == 2
    de_carla = abrir()
    de_carla.autenticar(token_carla)
    _medir(base_url, matera_carla)

    assert de_carla.mensaje()["planta"]["apodo"] == "Sala"
    # En vez de la medicion de Carla, la pestana de Beto recibe el error y se cierra.
    assert de_beto.mensaje() == {"tipo": "error", "error": "SESION_INVALIDA", "mensaje": str(SesionInvalida())}
    with pytest.raises(ConnectionClosed):
        de_beto.ws.receive(timeout=5)


def test_una_pestana_que_falla_al_recibir_no_impide_guardar_la_medicion(base_url, abrir, monkeypatch):
    token, matera = _cuenta_con_matera(base_url)
    pantalla = abrir()
    pantalla.autenticar(token)

    def conexion_caida(self, texto):
        raise ConnectionError("la pestana ya no esta")

    monkeypatch.setattr(tiempo_real.CanalWebSocket, "enviar", conexion_caida)

    assert _medir(base_url, matera)[0] == 201
    registros = pedir_http(base_url, "GET", f"/plantas/{matera['planta']['id']}/historial", token=token)[1]["registros"]
    assert len(registros) == 1


def test_una_pestana_que_se_cerro_sale_de_los_canales_y_la_medicion_igual_se_guarda(base_url, abrir):
    token, matera = _cuenta_con_matera(base_url)
    pantalla = abrir()
    pantalla.autenticar(token)
    pantalla.cerrar()

    assert _medir(base_url, matera)[0] == 201

    registros = pedir_http(base_url, "GET", f"/plantas/{matera['planta']['id']}/historial", token=token)[1]["registros"]
    assert len(registros) == 1


def test_un_error_inesperado_en_la_conexion_llega_como_json_y_cierra_con_1011(base_url, abrir, monkeypatch):
    def falla(canal):
        raise RuntimeError("falla inventada para la prueba")

    monkeypatch.setattr(tiempo_real, "_token_del_primer_mensaje", falla)
    pantalla = abrir()

    assert pantalla.mensaje()["error"] == "ERROR_INTERNO"
    with pytest.raises(ConnectionClosed) as cierre:
        pantalla.ws.receive(timeout=5)
    assert cierre.value.reason == tiempo_real.CIERRE_POR_ERROR


def test_un_pedido_de_apertura_sin_sec_websocket_key_responde_400_en_json(base_url):
    direccion = urllib.parse.urlsplit(base_url)
    conexion = http.client.HTTPConnection(direccion.hostname, direccion.port, timeout=5)
    cabeceras = {"Upgrade": "websocket", "Connection": "Upgrade", "Origin": ORIGEN_FRONT}

    conexion.request("GET", f"{direccion.path}/tiempo-real", headers=cabeceras)
    respuesta = conexion.getresponse()

    assert respuesta.status == 400
    assert respuesta.getheader("Content-Type") == "application/json"
    assert json.loads(respuesta.read())["error"] == "SOLICITUD_INVALIDA"
    conexion.close()


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
