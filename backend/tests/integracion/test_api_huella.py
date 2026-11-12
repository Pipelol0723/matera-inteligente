"""La huella (conexion): la placa crea su clave y la API solo guarda la huella SHA-256, como PKCE."""
import pytest

from tests.integracion.conftest import es_error

HUELLA_ABC = "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"  # SHA-256 de "abc"
HUELLA_OTRA = "3608bca1e44ea6c4d268eb6db02260269892c0b42b10d8f3ff8c4e0e4b3b2b13"  # otra huella valida
LECTURAS = {"humedad": 50, "luz": 800, "temperatura": 22}


@pytest.fixture
def ana(api):
    return api.cuenta()


def _crear(api, ana, huella=HUELLA_ABC, codigo="MT-0001-AA"):
    cuerpo = {"apodo": "Sala", "especie": "potos", "codigo": codigo}
    if huella is not None:
        cuerpo["huella"] = huella
    return api.pedir("POST", "/plantas", ana, json=cuerpo)


def test_crear_con_huella_no_devuelve_clave_y_la_placa_canjea_con_la_suya(api, ana):
    respuesta = _crear(api, ana)

    assert respuesta.status_code == 201
    assert set(respuesta.get_json()) == {"planta", "codigo"}  # la API nunca vio la clave
    canje = api.canjear("MT-0001-AA", "abc")
    assert canje.status_code == 200
    lectura = api.reportar("MT-0001-AA", canje.get_json()["token"], LECTURAS)
    assert lectura.status_code == 201


def test_con_huella_la_clave_equivocada_no_canjea(api, ana):
    _crear(api, ana)

    assert api.canjear("MT-0001-AA", "abd").status_code == 401


def test_sin_huella_sigue_dando_la_clave(api, ana):
    cuerpo = _crear(api, ana, huella=None).get_json()

    assert set(cuerpo) == {"planta", "codigo", "clave"}
    assert api.canjear("MT-0001-AA", cuerpo["clave"]).status_code == 200


HUELLAS_MALAS = [
    pytest.param(123, id="numero"),
    pytest.param(["a" * 64], id="lista"),
    pytest.param(True, id="booleano"),
    pytest.param(HUELLA_ABC.upper(), id="mayusculas"),
    pytest.param(HUELLA_ABC[:-1], id="63-caracteres"),
    pytest.param(HUELLA_ABC + "0", id="65-caracteres"),
    pytest.param("g" * 64, id="no-hexadecimal"),
    pytest.param("", id="vacia"),
    pytest.param(" " + HUELLA_ABC[1:], id="con-espacio"),
]


@pytest.mark.parametrize("huella", HUELLAS_MALAS)
def test_una_huella_mal_formada_al_crear_da_400_en_json(api, ana, huella):
    respuesta = _crear(api, ana, huella=huella)

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"]["campo"] == "huella"
    assert api.pedir("GET", "/plantas", ana).get_json() == []  # no se creo nada


@pytest.mark.parametrize("huella", HUELLAS_MALAS)
def test_una_huella_mal_formada_al_cambiar_el_sensor_da_400_en_json(api, ana, huella):
    planta = _crear(api, ana).get_json()["planta"]

    respuesta = api.pedir("PUT", f"/plantas/{planta['id']}/sensor", ana, json={"codigo": "MT-0002-AA", "huella": huella})

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")


def test_cambiar_el_sensor_con_huella_invalida_el_token_anterior_y_la_clave_anterior(api, ana):
    planta = _crear(api, ana).get_json()["planta"]
    token_viejo = api.canjear("MT-0001-AA", "abc").get_json()["token"]
    assert api.reportar("MT-0001-AA", token_viejo, LECTURAS).status_code == 201

    respuesta = api.pedir(
        "PUT", f"/plantas/{planta['id']}/sensor", ana, json={"codigo": "MT-0001-AA", "huella": HUELLA_OTRA}
    )

    assert respuesta.status_code == 200
    assert "clave" not in respuesta.get_json()
    assert api.reportar("MT-0001-AA", token_viejo, LECTURAS).status_code == 401  # el token anterior ya no sirve
    assert api.canjear("MT-0001-AA", "abc").status_code == 401  # ni la clave anterior


def test_cambiar_el_sensor_sin_huella_sigue_dando_clave(api, ana):
    planta = _crear(api, ana).get_json()["planta"]

    cuerpo = api.pedir("PUT", f"/plantas/{planta['id']}/sensor", ana, json={"codigo": "MT-0002-AA"}).get_json()

    assert set(cuerpo) == {"planta", "codigo", "clave"}
