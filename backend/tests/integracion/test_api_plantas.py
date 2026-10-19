"""Materas, sensores, historial y medicion manual de punta a punta: HTTP, casos de uso y SQLite."""
import pytest

from tests.integracion.conftest import ORIGEN_FRONT, es_error

MEDICION = {"humedad": 18, "luz": 800, "temperatura": 25}


@pytest.fixture
def ana(api):
    return api.cuenta()


def _crear(api, token, apodo="Sala", especie="Sansevieria", codigo="MT-0001-AA"):
    return api.pedir("POST", "/plantas", token, json={"apodo": apodo, "especie": especie, "codigo": codigo})


@pytest.fixture
def matera(api, ana):
    """La Sala de Ana con el sensor MT-0001-AA: {planta, codigo, clave}."""
    respuesta = _crear(api, ana)
    assert respuesta.status_code == 201
    return respuesta.get_json()


@pytest.fixture
def planta(matera):
    return matera["planta"]


def _cambiar_sensor(api, token, planta_id, codigo):
    return api.pedir("PUT", f"/plantas/{planta_id}/sensor", token, json={"codigo": codigo})


def _desde_sensor(api, codigo, clave, cuerpo=MEDICION):
    cabeceras = {"X-Clave-Sensor": clave} if clave is not None else {}
    return api.pedir("POST", f"/sensores/{codigo}/mediciones", json=cuerpo, cabeceras=cabeceras)


def _historial(api, token, planta_id):
    return api.pedir("GET", f"/plantas/{planta_id}/historial", token).get_json()["registros"]


def test_crear_una_matera_devuelve_la_planta_y_la_clave_del_sensor_una_sola_vez(api, ana):
    respuesta = _crear(api, ana, especie="  SANSEVIERIA ", codigo="mt-0001-aa")

    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert cuerpo["planta"] == {"id": 1, "apodo": "Sala", "especie": "sansevieria"}
    assert cuerpo["codigo"] == "MT-0001-AA" and len(cuerpo["clave"]) >= 43
    [tarjeta] = api.pedir("GET", "/plantas", ana).get_json()
    assert tarjeta["sensor"] == {"codigo": "MT-0001-AA"}
    assert cuerpo["clave"] not in str(tarjeta)


@pytest.mark.parametrize(
    ("cambios", "estado", "codigo_error"),
    [
        ({"apodo": "Patio", "especie": "cactus"}, 404, "ESPECIE_NO_SOPORTADA"),
        ({"apodo": "sala", "especie": "potos"}, 409, "APODO_REPETIDO"),
        ({"apodo": "  ", "especie": "potos"}, 400, "PARAMETRO_INVALIDO"),
        ({"apodo": "x" * 41, "especie": "potos"}, 400, "PARAMETRO_INVALIDO"),
        ({"apodo": "Patio", "codigo": "MT-0001-AA"}, 409, "SENSOR_YA_VINCULADO"),
        ({"apodo": "Patio", "codigo": "sensor-1"}, 400, "CODIGO_SENSOR_INVALIDO"),
        ({"apodo": "Patio", "codigo": None}, 400, "PARAMETRO_INVALIDO"),
    ],
    ids=["especie", "apodo repetido", "apodo vacio", "apodo largo", "codigo en uso", "codigo mal escrito", "sin codigo"],
)
def test_una_matera_invalida_responde_con_su_error_y_no_se_crea(api, ana, planta, cambios, estado, codigo_error):
    cuerpo = {"apodo": "Patio", "especie": "lavanda", "codigo": "MT-0002-BB", **cambios}

    assert es_error(api.pedir("POST", "/plantas", ana, json=cuerpo), estado, codigo_error)
    assert [t["id"] for t in api.pedir("GET", "/plantas", ana).get_json()] == [planta["id"]]


def test_sin_codigo_el_error_dice_que_campo_falta(api, ana):
    respuesta = api.pedir("POST", "/plantas", ana, json={"apodo": "Sala", "especie": "potos"})

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"] == {"campo": "codigo", "motivo": "ausente"}


def test_las_rutas_de_plantas_exigen_sesion(api):
    assert es_error(api.pedir("GET", "/plantas"), 401, "SESION_INVALIDA")
    assert es_error(_crear(api, None), 401, "SESION_INVALIDA")


def test_mis_plantas_muestra_una_matera_nueva_con_su_sensor_y_sin_mediciones(api, ana, planta):
    tarjetas = api.pedir("GET", "/plantas", ana).get_json()

    assert tarjetas == [{**planta, "sensor": {"codigo": "MT-0001-AA"}, "ultimaMedicion": None}]


def test_la_medicion_manual_devuelve_el_diagnostico_completo_y_queda_en_el_historial(api, ana, planta):
    respuesta = api.pedir("POST", f"/plantas/{planta['id']}/mediciones", ana, json=MEDICION)

    assert respuesta.status_code == 201
    [tarjeta] = api.pedir("GET", "/plantas", ana).get_json()
    assert tarjeta["ultimaMedicion"]["origen"] == "MANUAL"


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("DELETE", "/plantas/{id}", None),
        ("PUT", "/plantas/{id}/sensor", {"codigo": "MT-0009-ZZ"}),
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


def test_el_sensor_con_su_clave_guarda_la_medicion_con_su_codigo(api, ana, matera):
    respuesta = _desde_sensor(api, "MT-0001-AA", matera["clave"])

    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert cuerpo["planta"] == matera["planta"]
    assert cuerpo["diagnostico"]["estado"] == "EN_RIESGO"
    assert len(cuerpo["diagnostico"]["recomendaciones"]) == 1
    [tarjeta] = api.pedir("GET", "/plantas", ana).get_json()
    assert tarjeta["ultimaMedicion"]["origen"] == "MT-0001-AA"
    assert tarjeta["ultimaMedicion"]["lecturas"][0] == {"nombre": "humedad", "valor": 18.0, "unidad": "%", "estado": "BAJO"}
    assert tarjeta["ultimaMedicion"]["momento"] == cuerpo["momento"]


def test_una_medicion_imposible_del_sensor_responde_400_y_no_se_guarda(api, ana, matera):
    respuesta = _desde_sensor(api, "MT-0001-AA", matera["clave"], {**MEDICION, "humedad": 150})

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"]["motivo"] == "fuera_de_rango_fisico"
    assert _historial(api, ana, matera["planta"]["id"]) == []


@pytest.mark.parametrize(
    ("codigo", "clave"),
    [("MT-0001-AA", None), ("MT-0001-AA", "clave-inventada"), ("MT-9999-ZZ", "clave-inventada"), ("cualquiera", "x")],
)
def test_el_sensor_recibe_el_mismo_401_sin_importar_que_fallo_y_no_se_guarda_nada(api, ana, planta, codigo, clave):
    assert es_error(_desde_sensor(api, codigo, clave), 401, "CLAVE_SENSOR_INVALIDA")
    assert _historial(api, ana, planta["id"]) == []


def test_cambiar_el_sensor_da_una_clave_nueva_y_conserva_el_historial(api, ana, matera):
    planta = matera["planta"]
    assert _desde_sensor(api, "MT-0001-AA", matera["clave"]).status_code == 201

    respuesta = _cambiar_sensor(api, ana, planta["id"], "mt-0002-bb")

    assert respuesta.status_code == 200
    nuevo = respuesta.get_json()
    assert (nuevo["planta"], nuevo["codigo"]) == (planta, "MT-0002-BB")
    assert es_error(_desde_sensor(api, "MT-0001-AA", matera["clave"]), 401, "CLAVE_SENSOR_INVALIDA")
    assert _desde_sensor(api, "MT-0002-BB", nuevo["clave"]).status_code == 201
    assert [r["origen"] for r in _historial(api, ana, planta["id"])] == ["MT-0002-BB", "MT-0001-AA"]
    assert api.pedir("GET", "/plantas", ana).get_json()[0]["sensor"] == {"codigo": "MT-0002-BB"}


def test_cambiar_al_mismo_codigo_reemplaza_una_clave_perdida(api, ana, matera):
    nuevo = _cambiar_sensor(api, ana, matera["planta"]["id"], "MT-0001-AA").get_json()

    assert nuevo["clave"] != matera["clave"]
    assert es_error(_desde_sensor(api, "MT-0001-AA", matera["clave"]), 401, "CLAVE_SENSOR_INVALIDA")
    assert _desde_sensor(api, "MT-0001-AA", nuevo["clave"]).status_code == 201


def test_errores_al_cambiar_el_sensor(api, ana, matera):
    planta_id = matera["planta"]["id"]
    _crear(api, ana, apodo="Patio", especie="lavanda", codigo="MT-0002-BB")

    assert es_error(_cambiar_sensor(api, ana, planta_id, "MT-0002-BB"), 409, "SENSOR_YA_VINCULADO")
    assert es_error(_cambiar_sensor(api, ana, planta_id, "sensor-1"), 400, "CODIGO_SENSOR_INVALIDO")
    assert es_error(api.pedir("PUT", f"/plantas/{planta_id}/sensor", ana), 400, "SOLICITUD_INVALIDA")
    assert _desde_sensor(api, "MT-0001-AA", matera["clave"]).status_code == 201


@pytest.mark.parametrize("metodo", ["POST", "DELETE"])
def test_vincular_y_desvincular_ya_no_existen_y_responden_405_en_json(api, ana, planta, metodo):
    respuesta = api.pedir(metodo, f"/plantas/{planta['id']}/sensor", ana, json={"codigo": "MT-0002-BB"})

    assert es_error(respuesta, 405, "METODO_NO_PERMITIDO")


def test_el_historial_trae_lo_mas_reciente_primero_y_respeta_el_limite(api, ana, matera):
    for humedad in (30, 31, 32):
        _desde_sensor(api, "MT-0001-AA", matera["clave"], {**MEDICION, "humedad": humedad})

    historial = api.pedir("GET", f"/plantas/{matera['planta']['id']}/historial?limite=2", ana).get_json()

    assert historial["planta"] == matera["planta"]
    assert [r["lecturas"][0]["valor"] for r in historial["registros"]] == [32.0, 31.0]


@pytest.mark.parametrize("limite", ["0", "201", "muchos"])
def test_un_limite_invalido_del_historial_responde_400(api, ana, planta, limite):
    respuesta = api.pedir("GET", f"/plantas/{planta['id']}/historial?limite={limite}", ana)

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"]["campo"] == "limite"


def test_eliminar_una_matera_la_quita_de_mis_plantas_y_de_mi_cuenta(api, ana, planta):
    assert api.pedir("DELETE", f"/plantas/{planta['id']}", ana).status_code == 200

    assert api.pedir("GET", "/plantas", ana).get_json() == []
    assert api.pedir("GET", "/usuarios/yo", ana).get_json()["plantas"] == 0
    assert _crear(api, ana, apodo="Cocina", especie="potos").status_code == 201


def test_eliminar_una_cuenta_libera_el_codigo_de_su_sensor(api, ana, planta):
    admin = api.admin()

    api.pedir("DELETE", "/admin/usuarios/1", admin)

    assert _crear(api, admin, apodo="Sala", especie="potos", codigo="MT-0001-AA").status_code == 201


def test_una_especie_que_agrega_el_admin_sirve_para_las_materas_de_todos(api, ana):
    admin = api.admin()
    rangos = {"humedad": {"min": 30, "max": 60}, "luz": {"min": 1080, "max": 5380}, "temperatura": {"min": 13, "max": 27}}
    api.pedir("POST", "/admin/especies", admin, json={"nombre": "Cinta", "rangos": rangos})

    matera = _crear(api, ana, apodo="Baño", especie="cinta", codigo="MT-0003-CC").get_json()
    respuesta = _desde_sensor(api, "MT-0003-CC", matera["clave"], {"humedad": 45, "luz": 2000, "temperatura": 20})

    assert respuesta.get_json()["diagnostico"]["estado"] == "SALUDABLE"


def test_cors_deja_al_front_cambiar_el_sensor_con_put(api):
    respuesta = api.http.options(
        "/api/v1/plantas/1/sensor",
        headers={
            "Origin": ORIGEN_FRONT,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        },
    )

    assert respuesta.headers["Access-Control-Allow-Origin"] == ORIGEN_FRONT
    assert "PUT" in respuesta.headers["Access-Control-Allow-Methods"]
