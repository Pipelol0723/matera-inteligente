"""GET /red, las direcciones de la red local y los origenes del front abiertos a la red."""
import pytest

from infraestructura import red_local
from infraestructura.configuracion import Configuracion
from infraestructura.red_local import AVISO_SIN_RED, RedLocal, direcciones_alcanzables
from main import construir_app
from tests.integracion.conftest import ClienteApi

IPS = ["192.168.1.20", "10.34.101.124"]


@pytest.fixture
def ips_falsas(monkeypatch):
    monkeypatch.setattr(red_local, "ips_ipv4", lambda: list(IPS))


def test_con_0_0_0_0_son_todas_las_ips_de_la_red(ips_falsas):
    assert direcciones_alcanzables("0.0.0.0") == IPS
    red = RedLocal("0.0.0.0", 5000)
    assert red.servidores() == ["http://192.168.1.20:5000/api/v1", "http://10.34.101.124:5000/api/v1"]
    assert red.aviso() is None


def test_con_una_ip_concreta_es_solo_esa(ips_falsas):
    assert RedLocal("192.168.1.20", 8080).servidores() == ["http://192.168.1.20:8080/api/v1"]


@pytest.mark.parametrize("host", ["127.0.0.1", "127.0.0.2", "localhost"])
def test_con_loopback_ninguna_placa_alcanza_el_servidor(ips_falsas, host):
    red = RedLocal(host, 5000)

    assert red.servidores() == []
    assert "MATERA_HOST=0.0.0.0" in red.aviso()


class SocketFalso:
    """La sonda UDP: dice por cual IP saldria el PC a internet, la de la ruta por defecto."""

    def __init__(self, ip: str | None):
        self._ip = ip

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def connect(self, destino):
        if self._ip is None:
            raise OSError("sin red")

    def getsockname(self):
        return (self._ip, 0)


def _red_falsa(monkeypatch, direcciones, de_la_ruta_por_defecto):
    monkeypatch.setattr(
        red_local.socket, "getaddrinfo", lambda *args, **kwargs: [(2, 1, 6, "", (ip, 0)) for ip in direcciones]
    )
    monkeypatch.setattr(red_local.socket, "socket", lambda *args, **kwargs: SocketFalso(de_la_ruta_por_defecto))


def test_ips_ipv4_sin_loopback_ni_link_local_y_sin_repetir(monkeypatch):
    _red_falsa(monkeypatch, ("127.0.0.1", "169.254.3.4", "10.0.0.5", "192.168.1.20"), "192.168.1.20")

    assert red_local.ips_ipv4() == ["192.168.1.20", "10.0.0.5"]


def test_primero_va_la_ip_de_la_ruta_por_defecto(monkeypatch):
    """El PC tiene VirtualBox y la conexion compartida: la placa prueba primero la de la red del hotspot."""
    _red_falsa(monkeypatch, ("192.168.56.1", "192.168.137.1", "10.34.101.124"), "10.34.101.124")

    assert red_local.ips_ipv4() == ["10.34.101.124", "192.168.56.1", "192.168.137.1"]


def test_sin_ruta_por_defecto_quedan_las_del_nombre_del_pc(monkeypatch):
    _red_falsa(monkeypatch, ("192.168.56.1", "10.34.101.124"), None)

    assert red_local.ips_ipv4() == ["192.168.56.1", "10.34.101.124"]


def test_get_red_sin_jwt_da_401_en_json(api):
    respuesta = api.pedir("GET", "/red")

    assert respuesta.status_code == 401
    assert respuesta.mimetype == "application/json"
    assert respuesta.get_json()["error"]


def test_get_red_con_loopback_trae_lista_vacia_y_aviso(api):
    cuerpo = api.pedir("GET", "/red", api.cuenta()).get_json()  # la config de prueba usa 127.0.0.1

    assert cuerpo == {"servidores": [], "aviso": AVISO_SIN_RED}


def test_get_red_con_jwt_trae_las_bases(tmp_path, ips_falsas):
    config = Configuracion(
        puerto=5000, ruta_bd=tmp_path / "m.sqlite", origenes_cors=(), iteraciones_contrasena=1_000, host="0.0.0.0"
    )
    api = ClienteApi(config)

    respuesta = api.pedir("GET", "/red", api.cuenta())

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {
        "servidores": ["http://192.168.1.20:5000/api/v1", "http://10.34.101.124:5000/api/v1"]
    }


def _configuracion(monkeypatch, tmp_path, **entorno):
    for nombre in ("MATERA_HOST", "MATERA_ORIGENES_CORS", "MATERA_PUERTO_FRONT", "MATERA_PUERTO"):
        monkeypatch.delenv(nombre, raising=False)
    monkeypatch.setenv("MATERA_RUTA_BD", str(tmp_path / "m.sqlite"))
    for nombre, valor in entorno.items():
        monkeypatch.setenv(nombre, valor)
    return Configuracion.desde_entorno()


def test_con_0_0_0_0_los_origenes_incluyen_la_red_y_conservan_los_de_antes(monkeypatch, tmp_path, ips_falsas):
    config = _configuracion(monkeypatch, tmp_path, MATERA_HOST="0.0.0.0")

    assert config.origenes_cors == (
        "http://localhost:5500",
        "http://127.0.0.1:5500",
        "http://192.168.1.20:5500",
        "http://10.34.101.124:5500",
    )


def test_el_puerto_del_front_sale_de_matera_puerto_front(monkeypatch, tmp_path, ips_falsas):
    config = _configuracion(monkeypatch, tmp_path, MATERA_HOST="0.0.0.0", MATERA_PUERTO_FRONT="8000")

    assert "http://192.168.1.20:8000" in config.origenes_cors
    assert "http://192.168.1.20:5500" not in config.origenes_cors


@pytest.mark.parametrize("host", ["127.0.0.1", "192.168.1.20"])
def test_sin_0_0_0_0_los_origenes_no_cambian(monkeypatch, tmp_path, ips_falsas, host):
    config = _configuracion(monkeypatch, tmp_path, MATERA_HOST=host)

    assert config.origenes_cors == ("http://localhost:5500", "http://127.0.0.1:5500")


def test_cors_acepta_el_origen_de_la_red_y_rechaza_uno_cualquiera(monkeypatch, tmp_path, ips_falsas):
    app = construir_app(_configuracion(monkeypatch, tmp_path, MATERA_HOST="0.0.0.0")).test_client()

    de_la_red = app.get("/api/v1/especies", headers={"Origin": "http://192.168.1.20:5500"})
    ajeno = app.get("/api/v1/especies", headers={"Origin": "http://evil.example:5500"})

    assert de_la_red.headers["Access-Control-Allow-Origin"] == "http://192.168.1.20:5500"
    assert "Access-Control-Allow-Origin" not in ajeno.headers
