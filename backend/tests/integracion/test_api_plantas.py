"""Plantas, sensores, historial y medicion manual de punta a punta: HTTP, casos de uso y SQLite."""
import pytest

from tests.integracion.conftest import ORIGEN_FRONT, es_error

MEDICION = {"humedad": 18, "luz": 800, "temperatura": 25}


@pytest.fixture
def ana(api):
    return api.cuenta()


@pytest.fixture
def planta(api, ana):
    respuesta = api.pedir("POST", "/plantas", ana, json={"apodo": "Sala", "especie": "Sansevieria"})
    assert respuesta.status_code == 201
    return respuesta.get_json()


def _vincular(api, token, planta_id, codigo="MT-0001-AA"):
    return api.pedir("POST", f"/plantas/{planta_id}/sensor", token, json={"codigo": codigo})


def _desde_sensor(api, codigo, clave, cuerpo=MEDICION):
    cabeceras = {"X-Clave-Sensor": clave} if clave is not None else {}
    return api.pedir("POST", f"/sensores/{codigo}/mediciones", json=cuerpo, cabeceras=cabeceras)


def test_registrar_una_planta_devuelve_su_id_y_la_especie_normalizada(planta):
    assert planta == {"id": 1, "apodo": "Sala", "especie": "sansevieria"}


@pytest.mark.parametrize(
    ("cuerpo", "estado", "codigo"),
    [
        ({"apodo": "Patio", "especie": "cactus"}, 404, "ESPECIE_NO_SOPORTADA"),
        ({"apodo": "sala", "especie": "potos"}, 409, "APODO_REPETIDO"),
        ({"apodo": "  ", "especie": "potos"}, 400, "PARAMETRO_INVALIDO"),
        ({"apodo": "x" * 41, "especie": "potos"}, 400, "PARAMETRO_INVALIDO"),
    ],
)
def test_una_planta_invalida_responde_con_su_error(api, ana, planta, cuerpo, estado, codigo):
    assert es_error(api.pedir("POST", "/plantas", ana, json=cuerpo), estado, codigo)


def test_las_rutas_de_plantas_exigen_sesion(api):
    assert es_error(api.pedir("GET", "/plantas"), 401, "SESION_INVALIDA")


def test_mis_plantas_muestra_una_planta_nueva_sin_sensor_ni_mediciones(api, ana, planta):
    assert api.pedir("GET", "/plantas", ana).get_json() == [{**planta, "sensor": None, "ultimaMedicion": None}]


def test_la_medicion_manual_devuelve_el_diagnostico_completo_y_queda_en_el_historial(api, ana, planta):
    respuesta = api.pedir("POST", f"/plantas/{planta['id']}/mediciones", ana, json=MEDICION)

    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert cuerpo["diagnostico"]["estado"] == "EN_RIESGO"
    assert len(cuerpo["diagnostico"]["recomendaciones"]) == 1
    [tarjeta] = api.pedir("GET", "/plantas", ana).get_json()
    assert tarjeta["ultimaMedicion"]["estado"] == "EN_RIESGO"
    assert tarjeta["ultimaMedicion"]["origen"] == "MANUAL"
    assert tarjeta["ultimaMedicion"]["lecturas"][0] == {"nombre": "humedad", "valor": 18.0, "unidad": "%", "estado": "BAJO"}
    assert tarjeta["ultimaMedicion"]["momento"] == cuerpo["momento"]


def test_una_medicion_manual_imposible_responde_400_y_no_se_guarda(api, ana, planta):
    respuesta = api.pedir("POST", f"/plantas/{planta['id']}/mediciones", ana, json={**MEDICION, "humedad": 150})

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"]["motivo"] == "fuera_de_rango_fisico"
    assert api.pedir("GET", f"/plantas/{planta['id']}/historial", ana).get_json()["registros"] == []


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("DELETE", "/plantas/{id}", None),
        ("POST", "/plantas/{id}/sensor", {"codigo": "MT-0009-ZZ"}),
        ("DELETE", "/plantas/{id}/sensor", None),
        ("GET", "/plantas/{id}/historial", None),
        ("POST", "/plantas/{id}/mediciones", MEDICION),
    ],
)
def test_beto_recibe_404_con_la_planta_de_ana_igual_que_con_una_que_no_existe(api, planta, metodo, ruta, cuerpo):
    beto = api.cuenta("Beto", "beto@correo.co")

    ajena = api.pedir(metodo, ruta.format(id=planta["id"]), beto, json=cuerpo)
    inexistente = api.pedir(metodo, ruta.format(id=999), beto, json=cuerpo)

    assert es_error(ajena, 404, "PLANTA_NO_ENCONTRADA")
    assert ajena.get_json()["mensaje"] == inexistente.get_json()["mensaje"].replace("999", str(planta["id"]))
    assert api.pedir("GET", "/plantas", beto).get_json() == []


def test_vincular_un_sensor_entrega_su_clave_una_sola_vez(api, ana, planta):
    respuesta = _vincular(api, ana, planta["id"], "mt-0001-aa")

    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert cuerpo["codigo"] == "MT-0001-AA" and len(cuerpo["clave"]) >= 43
    [tarjeta] = api.pedir("GET", "/plantas", ana).get_json()
    assert tarjeta["sensor"] == {"codigo": "MT-0001-AA"}
    assert "clave" not in str(api.pedir("GET", "/plantas", ana).get_json())


def test_errores_al_vincular_un_sensor(api, ana, planta):
    otra = api.pedir("POST", "/plantas", ana, json={"apodo": "Patio", "especie": "lavanda"}).get_json()
    _vincular(api, ana, planta["id"])

    assert es_error(_vincular(api, ana, planta["id"], "MT-0002-BB"), 409, "PLANTA_CON_SENSOR")
    assert es_error(_vincular(api, ana, otra["id"], "MT-0001-AA"), 409, "SENSOR_YA_VINCULADO")
    assert es_error(_vincular(api, ana, otra["id"], "sensor-1"), 400, "CODIGO_SENSOR_INVALIDO")


def test_el_sensor_con_su_clave_guarda_la_medicion_con_su_codigo(api, ana, planta):
    clave = _vincular(api, ana, planta["id"]).get_json()["clave"]

    respuesta = _desde_sensor(api, "MT-0001-AA", clave)

    assert respuesta.status_code == 201
    assert respuesta.get_json()["planta"] == planta
    [registro] = api.pedir("GET", f"/plantas/{planta['id']}/historial", ana).get_json()["registros"]
    assert registro["origen"] == "MT-0001-AA"


@pytest.mark.parametrize(
    ("codigo", "clave"),
    [("MT-0001-AA", None), ("MT-0001-AA", "clave-inventada"), ("MT-9999-ZZ", "clave-inventada"), ("cualquiera", "x")],
)
def test_el_sensor_recibe_el_mismo_401_sin_importar_que_fallo_y_no_se_guarda_nada(api, ana, planta, codigo, clave):
    _vincular(api, ana, planta["id"])

    assert es_error(_desde_sensor(api, codigo, clave), 401, "CLAVE_SENSOR_INVALIDA")
    assert api.pedir("GET", f"/plantas/{planta['id']}/historial", ana).get_json()["registros"] == []


def test_desvincular_hace_que_la_clave_vieja_deje_de_servir(api, ana, planta):
    clave = _vincular(api, ana, planta["id"]).get_json()["clave"]

    assert api.pedir("DELETE", f"/plantas/{planta['id']}/sensor", ana).status_code == 200

    assert es_error(_desde_sensor(api, "MT-0001-AA", clave), 401, "CLAVE_SENSOR_INVALIDA")
    assert es_error(api.pedir("DELETE", f"/plantas/{planta['id']}/sensor", ana), 404, "PLANTA_SIN_SENSOR")


def test_el_historial_trae_lo_mas_reciente_primero_y_respeta_el_limite(api, ana, planta):
    for humedad in (30, 31, 32):
        api.pedir("POST", f"/plantas/{planta['id']}/mediciones", ana, json={**MEDICION, "humedad": humedad})

    historial = api.pedir("GET", f"/plantas/{planta['id']}/historial?limite=2", ana).get_json()

    assert historial["planta"] == planta
    assert [r["lecturas"][0]["valor"] for r in historial["registros"]] == [32.0, 31.0]


@pytest.mark.parametrize("limite", ["0", "201", "muchos"])
def test_un_limite_invalido_del_historial_responde_400(api, ana, planta, limite):
    respuesta = api.pedir("GET", f"/plantas/{planta['id']}/historial?limite={limite}", ana)

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"]["campo"] == "limite"


def test_eliminar_una_planta_la_quita_de_mis_plantas_y_de_mi_cuenta(api, ana, planta):
    assert api.pedir("DELETE", f"/plantas/{planta['id']}", ana).status_code == 200

    assert api.pedir("GET", "/plantas", ana).get_json() == []
    assert api.pedir("GET", "/usuarios/yo", ana).get_json()["plantas"] == 0


def test_eliminar_una_cuenta_libera_el_codigo_de_su_sensor(api, ana, planta):
    admin = api.admin()
    _vincular(api, ana, planta["id"])

    api.pedir("DELETE", "/admin/usuarios/1", admin)

    sala_de_ada = api.pedir("POST", "/plantas", admin, json={"apodo": "Sala", "especie": "potos"}).get_json()
    assert _vincular(api, admin, sala_de_ada["id"]).status_code == 201


def test_una_especie_que_agrega_el_admin_sirve_para_las_plantas_de_todos(api, ana):
    admin = api.admin()
    rangos = {"humedad": {"min": 30, "max": 60}, "luz": {"min": 1080, "max": 5380}, "temperatura": {"min": 13, "max": 27}}
    api.pedir("POST", "/admin/especies", admin, json={"nombre": "Cinta", "rangos": rangos})

    planta = api.pedir("POST", "/plantas", ana, json={"apodo": "Baño", "especie": "cinta"}).get_json()
    respuesta = api.pedir("POST", f"/plantas/{planta['id']}/mediciones", ana, json={"humedad": 45, "luz": 2000, "temperatura": 20})

    assert respuesta.get_json()["diagnostico"]["estado"] == "SALUDABLE"


def test_cors_deja_al_simulador_del_front_mandar_la_clave_del_sensor(api):
    respuesta = api.http.options(
        "/api/v1/sensores/MT-0001-AA/mediciones",
        headers={
            "Origin": ORIGEN_FRONT,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, X-Clave-Sensor",
        },
    )

    assert respuesta.headers["Access-Control-Allow-Origin"] == ORIGEN_FRONT
    assert "x-clave-sensor" in respuesta.headers["Access-Control-Allow-Headers"].lower()
