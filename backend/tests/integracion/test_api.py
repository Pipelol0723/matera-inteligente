"""Pruebas de la API con el cliente de pruebas de Flask. No cuentan como pruebas de dominio."""
from functools import wraps

import pytest

from aplicacion.listar_especies import ListarEspecies
from aplicacion.listar_parametros import ListarParametros
from dominio.especie import Especie
from dominio.parametros import HUMEDAD, LUZ, PARAMETROS, TEMPERATURA
from dominio.rango import Rango
from infraestructura.configuracion import Configuracion
from infraestructura.servidor_web import crear_app
from infraestructura.sqlite import BaseDatos, RepositorioEspeciesSqlite
from main import construir_app
from presentacion.rutas import crear_blueprint
from tests.dobles import RepositorioEspeciesEnMemoria

ORIGEN_FRONT = "http://localhost:5500"
# Rangos propios de estas pruebas, independientes de carga.sql.
ESPECIES = (
    Especie("sansevieria", {HUMEDAD: Rango(20, 45), LUZ: Rango(200, 1500), TEMPERATURA: Rango(15, 29)}, "Dracaena trifasciata"),
    Especie("potos", {HUMEDAD: Rango(40, 70), LUZ: Rango(270, 2150), TEMPERATURA: Rango(16, 29)}, "Epipremnum aureum"),
)


def _config(tmp_path):
    """Una base temporal con solo estas especies: como ya tiene especies, al arrancar no se ejecuta carga.sql."""
    ruta = tmp_path / "matera.sqlite"
    especies = RepositorioEspeciesSqlite(BaseDatos(ruta).preparar(carga=None))
    for especie in ESPECIES:
        especies.agregar(especie)
    # Pocas iteraciones de PBKDF2: cada prueba crea su cuenta para tener el token.
    return Configuracion(puerto=5000, ruta_bd=ruta, origenes_cors=(ORIGEN_FRONT,), iteraciones_contrasena=1_000)


def _con_sesion(cliente):
    """R7: estas rutas exigen el JWT de usuario. Crea una cuenta y deja su token en cada peticion del cliente."""
    cuenta = {"nombre": "Ana", "correo": "ana@correo.co", "contrasena": "clave-segura"}
    assert cliente.post("/api/v1/usuarios", json=cuenta).status_code == 201
    token = cliente.post("/api/v1/sesiones", json=cuenta).get_json()["token"]
    cliente.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return cliente


@pytest.fixture
def sin_sesion(tmp_path):
    return construir_app(_config(tmp_path)).test_client()


@pytest.fixture
def cliente(sin_sesion):
    return _con_sesion(sin_sesion)


def _pedir(cliente, sin=(), **cambios):
    cuerpo = {"especie": "sansevieria", "humedad": 18, "luz": 800, "temperatura": 22, **cambios}
    for campo in sin:
        cuerpo.pop(campo)
    return cliente.post("/api/v1/diagnosticos", json=cuerpo)


def _es_error_uniforme(respuesta):
    return respuesta.mimetype == "application/json" and set(respuesta.get_json()) == {"error", "mensaje", "detalle"}


@pytest.mark.parametrize(("metodo", "ruta"), [("GET", "/especies"), ("GET", "/parametros"), ("POST", "/diagnosticos")])
def test_las_rutas_del_corte_1_exigen_el_jwt_de_usuario(sin_sesion, metodo, ruta):
    sin_token = sin_sesion.open(f"/api/v1{ruta}", method=metodo, json={})
    token_falso = sin_sesion.open(f"/api/v1{ruta}", method=metodo, json={}, headers={"Authorization": "Bearer x.y.z"})

    for respuesta in (sin_token, token_falso):
        assert respuesta.status_code == 401
        assert _es_error_uniforme(respuesta)
        assert respuesta.get_json()["error"] == "SESION_INVALIDA"


def test_especies_devuelve_rangos_con_unidad_ordenadas_por_nombre(cliente):
    respuesta = cliente.get("/api/v1/especies")

    assert respuesta.status_code == 200
    especies = respuesta.get_json()
    assert [e["nombre"] for e in especies] == ["potos", "sansevieria"]
    assert especies[1]["nombreCientifico"] == "Dracaena trifasciata"
    assert especies[1]["rangos"]["humedad"] == {"min": 20.0, "max": 45.0, "unidad": "%"}


def test_parametros_devuelve_unidad_y_limites_fisicos_en_orden(cliente):
    respuesta = cliente.get("/api/v1/parametros")

    assert respuesta.status_code == 200
    assert respuesta.get_json() == [
        {"nombre": "humedad", "unidad": "%", "minimoFisico": 0.0, "maximoFisico": 100.0},
        {"nombre": "luz", "unidad": "lux", "minimoFisico": 0.0, "maximoFisico": 150000.0},
        {"nombre": "temperatura", "unidad": "C", "minimoFisico": -50.0, "maximoFisico": 60.0},
    ]


def test_diagnostico_cumple_el_contrato(cliente):
    respuesta = _pedir(cliente)

    assert respuesta.status_code == 200
    cuerpo = respuesta.get_json()
    assert cuerpo["especie"] == "sansevieria"
    assert cuerpo["estado"] == "EN_RIESGO"
    assert cuerpo["parametros"][0] == {
        "nombre": "humedad",
        "valor": 18.0,
        "unidad": "%",
        "rangoOptimo": [20.0, 45.0],
        "estado": "BAJO",
        "desviacion": 0.08,
    }
    assert len(cuerpo["recomendaciones"]) == 1


def test_acepta_numeros_escritos_como_texto(cliente):
    respuesta = _pedir(cliente, humedad="32,5", luz="800")

    assert respuesta.status_code == 200
    assert respuesta.get_json()["parametros"][0]["valor"] == 32.5


def test_especie_desconocida_responde_404(cliente):
    respuesta = _pedir(cliente, especie="cactus")

    assert respuesta.status_code == 404
    assert _es_error_uniforme(respuesta)
    assert respuesta.get_json()["error"] == "ESPECIE_NO_SOPORTADA"
    assert respuesta.get_json()["detalle"] == {"especie": "cactus"}


@pytest.mark.parametrize(
    ("sin", "cambios", "campo", "motivo"),
    [
        (("humedad",), {}, "humedad", "ausente"),
        ((), {"luz": ""}, "luz", "ausente"),
        ((), {"luz": "mucha"}, "luz", "no_numerico"),
        ((), {"temperatura": True}, "temperatura", "no_numerico"),
        ((), {"humedad": 150}, "humedad", "fuera_de_rango_fisico"),
        (("especie",), {}, "especie", "ausente"),
    ],
)
def test_parametro_invalido_responde_400_con_el_campo(cliente, sin, cambios, campo, motivo):
    respuesta = _pedir(cliente, sin=sin, **cambios)

    assert respuesta.status_code == 400
    assert _es_error_uniforme(respuesta)
    cuerpo = respuesta.get_json()
    assert cuerpo["error"] == "PARAMETRO_INVALIDO"
    assert (cuerpo["detalle"]["campo"], cuerpo["detalle"]["motivo"]) == (campo, motivo)


def test_un_cuerpo_que_no_es_json_responde_400(cliente):
    respuesta = cliente.post("/api/v1/diagnosticos", data="hola", content_type="text/plain")

    assert respuesta.status_code == 400
    assert respuesta.get_json()["error"] == "SOLICITUD_INVALIDA"


@pytest.mark.parametrize("ruta", ["/", "/api/v1/no-existe"])
def test_una_ruta_inexistente_responde_json_y_no_html(cliente, ruta):
    respuesta = cliente.get(ruta)

    assert respuesta.status_code == 404
    assert _es_error_uniforme(respuesta)
    assert b"<html" not in respuesta.data.lower()


def test_un_metodo_no_permitido_responde_json(cliente):
    respuesta = cliente.get("/api/v1/diagnosticos")

    assert respuesta.status_code == 405
    assert _es_error_uniforme(respuesta)
    assert respuesta.get_json()["error"] == "METODO_NO_PERMITIDO"


def test_un_error_inesperado_responde_json_sin_la_traza(tmp_path):
    class CasoDeUsoQueFalla:
        def ejecutar(self, solicitud):
            raise RuntimeError("detalle interno que no debe salir")

    class SinVerificarSesion:
        """Esta prueba es del manejo de errores, no de la sesion: deja pasar sin token."""

        def con_usuario(self, vista):
            return wraps(vista)(lambda *args, **kwargs: vista(None, *args, **kwargs))

    api = crear_blueprint(
        CasoDeUsoQueFalla(),
        ListarEspecies(RepositorioEspeciesEnMemoria()),
        ListarParametros(PARAMETROS),
        SinVerificarSesion(),
    )
    cliente = crear_app([api], _config(tmp_path)).test_client()

    respuesta = _pedir(cliente)

    assert respuesta.status_code == 500
    assert _es_error_uniforme(respuesta)
    assert b"detalle interno" not in respuesta.data


@pytest.mark.parametrize(
    "cuerpo",
    [
        "[" * 100_000 + "]" * 100_000,
        '{"especie": "potos", "humedad": NaN, "luz": 800, "temperatura": 22}',
        '{"especie": "potos", "humedad": 1e309, "luz": 800, "temperatura": 22}',
        '{"especie": "\\ud800", "humedad": 50, "luz": 800, "temperatura": 22}',
    ],
    ids=["anidado 100 000 veces", "NaN", "no cabe en un float", "medio caracter"],
)
def test_un_json_que_la_libreria_aceptaria_de_mas_responde_400_y_no_500(cliente, cuerpo):
    respuesta = cliente.post("/api/v1/diagnosticos", data=cuerpo, content_type="application/json")

    assert respuesta.status_code == 400
    assert _es_error_uniforme(respuesta)
    assert respuesta.get_json()["error"] == "SOLICITUD_INVALIDA"


def test_una_barra_doble_responde_404_en_json_y_no_una_redireccion_html(cliente):
    respuesta = cliente.get("/api/v1//especies")

    assert respuesta.status_code == 404
    assert _es_error_uniforme(respuesta)


def test_la_verificacion_previa_responde_json(sin_sesion):
    respuesta = sin_sesion.options("/api/v1/especies", headers={"Origin": ORIGEN_FRONT})

    assert respuesta.mimetype == "application/json"
    assert respuesta.get_json() == {}


def test_cors_permite_el_origen_del_front_incluso_en_errores(cliente):
    exito = cliente.get("/api/v1/especies", headers={"Origin": ORIGEN_FRONT})
    # Sin la cabecera en los errores, el front no podria leer el mensaje del 404.
    error = cliente.post(
        "/api/v1/diagnosticos",
        json={"especie": "cactus", "humedad": 30, "luz": 800, "temperatura": 22},
        headers={"Origin": ORIGEN_FRONT},
    )

    assert exito.headers["Access-Control-Allow-Origin"] == ORIGEN_FRONT
    assert error.status_code == 404
    assert error.headers["Access-Control-Allow-Origin"] == ORIGEN_FRONT


def test_cors_responde_la_verificacion_previa_del_post_sin_token(sin_sesion):
    # El navegador no manda el token en la verificacion previa: tiene que responderse sin sesion.
    respuesta = sin_sesion.options(
        "/api/v1/diagnosticos",
        headers={
            "Origin": ORIGEN_FRONT,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "Content-Type, Authorization",
        },
    )

    assert respuesta.status_code == 200
    assert respuesta.headers["Access-Control-Allow-Origin"] == ORIGEN_FRONT


def test_cors_no_autoriza_otros_origenes(cliente):
    respuesta = cliente.get("/api/v1/especies", headers={"Origin": "http://otro-sitio.example"})

    assert "Access-Control-Allow-Origin" not in respuesta.headers
