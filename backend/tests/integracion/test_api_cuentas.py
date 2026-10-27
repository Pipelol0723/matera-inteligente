"""Cuentas y administracion de punta a punta: HTTP, casos de uso y SQLite."""
import base64
import json
import sqlite3
from datetime import datetime, timedelta, timezone

import jwt
import pytest

from tests.integracion.conftest import ORIGEN_FRONT, ClienteApi, es_error

ESPECIE_NUEVA = {
    "nombre": "Cinta",
    "nombreCientifico": "Chlorophytum comosum",
    "rangos": {
        "humedad": {"min": 30, "max": 60},
        "luz": {"min": 1080, "max": 5380},
        "temperatura": {"min": 13, "max": 27},
    },
}


def test_registrarse_crea_un_usuario_comun_y_no_devuelve_la_contrasena(api):
    respuesta = api.registrar(correo=" Ana@Correo.CO ")

    assert respuesta.status_code == 201
    assert respuesta.get_json() == {"id": 1, "nombre": "Ana", "correo": "ana@correo.co", "rol": "USUARIO"}


def test_no_se_registran_dos_cuentas_con_el_mismo_correo(api):
    api.registrar()

    assert es_error(api.registrar(nombre="Otra"), 409, "CORREO_YA_REGISTRADO")


@pytest.mark.parametrize(
    ("cuerpo", "campo"),
    [
        ({"nombre": "Ana", "correo": "ana@correo.co", "contrasena": "corta"}, "contrasena"),
        ({"nombre": "Ana", "correo": "no-es-correo", "contrasena": "clave-segura"}, "correo"),
        ({"nombre": "   ", "correo": "ana@correo.co", "contrasena": "clave-segura"}, "nombre"),
        ({"correo": "ana@correo.co", "contrasena": "clave-segura"}, "nombre"),
    ],
)
def test_un_registro_invalido_responde_400_con_el_campo(api, cuerpo, campo):
    respuesta = api.pedir("POST", "/usuarios", json=cuerpo)

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert respuesta.get_json()["detalle"]["campo"] == campo


def test_iniciar_sesion_entrega_token_vencimiento_y_usuario(api):
    api.registrar()

    respuesta = api.pedir("POST", "/sesiones", json={"correo": "ana@correo.co", "contrasena": "clave-segura"})

    assert respuesta.status_code == 201
    cuerpo = respuesta.get_json()
    assert len(cuerpo["token"]) >= 43
    assert cuerpo["venceEn"].endswith("+00:00")
    assert cuerpo["usuario"]["rol"] == "USUARIO"


@pytest.mark.parametrize(("correo", "contrasena"), [("nadie@correo.co", "clave-segura"), ("ana@correo.co", "mala-clave")])
def test_el_login_responde_el_mismo_401_sin_decir_que_fallo(api, correo, contrasena):
    api.registrar()

    respuesta = api.pedir("POST", "/sesiones", json={"correo": correo, "contrasena": contrasena})

    assert es_error(respuesta, 401, "CREDENCIALES_INVALIDAS")


@pytest.mark.parametrize("cabeceras", [{}, {"Authorization": "token-suelto"}, {"Authorization": "Bearer "}, {"Authorization": "Bearer inventado"}])
def test_mi_cuenta_sin_un_token_valido_responde_401(api, cabeceras):
    assert es_error(api.pedir("GET", "/usuarios/yo", cabeceras=cabeceras), 401, "SESION_INVALIDA")


def test_mi_cuenta_muestra_los_datos_y_cuantas_plantas_tiene(api):
    token = api.cuenta()

    respuesta = api.pedir("GET", "/usuarios/yo", token)

    assert respuesta.status_code == 200
    assert respuesta.get_json() == {"id": 1, "nombre": "Ana", "correo": "ana@correo.co", "rol": "USUARIO", "plantas": 0}


def test_cerrar_sesion_invalida_el_token(api):
    token = api.cuenta()

    assert api.pedir("DELETE", "/sesiones/actual", token).status_code == 200
    assert es_error(api.pedir("GET", "/usuarios/yo", token), 401, "SESION_INVALIDA")


def _reclamos(token: str) -> dict:
    """Lo que trae un JWT, sin verificar la firma: cualquiera puede leerlo, por eso no lleva nada secreto."""
    cuerpo = token.split(".")[1]
    return json.loads(base64.urlsafe_b64decode(cuerpo + "=" * (-len(cuerpo) % 4)))


def test_el_token_es_un_jwt_de_usuario_y_la_base_guarda_solo_su_id(api, config):
    token = api.cuenta()

    reclamos = _reclamos(token)
    assert (reclamos["alcance"], reclamos["sub"]) == ("usuario", "1")
    with sqlite3.connect(config.ruta_bd) as conexion:
        assert conexion.execute("SELECT token_id, usuario_id FROM sesion").fetchall() == [(reclamos["jti"], 1)]


def test_un_token_valido_de_otro_alcance_responde_403_en_una_ruta_de_usuario(api, config):
    api.cuenta()
    secreto = config.ruta_secreto_jwt.read_text(encoding="utf-8")
    ahora = datetime.now(timezone.utc)
    reclamos = {"iss": "matera-inteligente", "alcance": "lecturas", "jti": "x", "iat": ahora, "exp": ahora + timedelta(hours=1)}
    del_sensor = jwt.encode({**reclamos, "sub": "MT-0001-AA"}, secreto, algorithm="HS256")

    assert es_error(api.pedir("GET", "/usuarios/yo", del_sensor), 403, "ALCANCE_INVALIDO")


def test_un_token_firmado_con_otro_secreto_responde_401(api):
    token = api.cuenta()
    reclamos = {**_reclamos(token), "iat": datetime.now(timezone.utc)}
    falso = jwt.encode(reclamos, "un-secreto-que-el-servidor-no-conoce-xxxx", algorithm="HS256")

    assert es_error(api.pedir("GET", "/usuarios/yo", falso), 401, "SESION_INVALIDA")


def test_reiniciar_el_backend_no_cierra_las_sesiones(api, config):
    token = api.cuenta()

    otra_vez = ClienteApi(config)  # otra app, con la misma base y el mismo archivo de secreto

    assert otra_vez.pedir("GET", "/usuarios/yo", token).status_code == 200


@pytest.mark.parametrize(
    ("metodo", "ruta", "cuerpo"),
    [
        ("GET", "/admin/usuarios", None),
        ("PATCH", "/admin/usuarios/1", {"activo": False}),
        ("DELETE", "/admin/usuarios/1", None),
        ("POST", "/admin/especies", ESPECIE_NUEVA),
    ],
)
def test_un_usuario_comun_recibe_403_en_cada_ruta_de_admin(api, metodo, ruta, cuerpo):
    api.admin()
    token = api.cuenta("Beto", "beto@correo.co")

    assert es_error(api.pedir(metodo, ruta, token, json=cuerpo), 403, "PERMISO_DENEGADO")
    assert es_error(api.pedir(metodo, ruta, json=cuerpo), 401, "SESION_INVALIDA")


def test_el_admin_lista_los_usuarios_con_su_cantidad_de_plantas(api):
    token = api.admin()
    api.registrar("Beto", "beto@correo.co")

    respuesta = api.pedir("GET", "/admin/usuarios", token)

    assert respuesta.status_code == 200
    assert [(u["nombre"], u["rol"], u["activo"], u["cantidadPlantas"]) for u in respuesta.get_json()] == [
        ("Ada", "ADMIN", True, 0),
        ("Beto", "USUARIO", True, 0),
    ]


def test_desactivar_una_cuenta_corta_su_sesion_y_bloquea_el_login(api):
    admin = api.admin()
    token_beto = api.cuenta("Beto", "beto@correo.co")

    respuesta = api.pedir("PATCH", "/admin/usuarios/2", admin, json={"activo": False})

    assert respuesta.status_code == 200 and respuesta.get_json()["activo"] is False
    assert es_error(api.pedir("GET", "/usuarios/yo", token_beto), 401, "SESION_INVALIDA")
    login = api.pedir("POST", "/sesiones", json={"correo": "beto@correo.co", "contrasena": "clave-segura"})
    assert es_error(login, 403, "CUENTA_DESACTIVADA")


def test_el_admin_da_el_rol_a_otro_pero_no_puede_actuar_sobre_si_mismo(api):
    admin = api.admin()
    api.registrar("Beto", "beto@correo.co")

    assert api.pedir("PATCH", "/admin/usuarios/2", admin, json={"rol": "ADMIN"}).get_json()["rol"] == "ADMIN"
    assert es_error(api.pedir("PATCH", "/admin/usuarios/1", admin, json={"rol": "USUARIO"}), 409, "ACCION_SOBRE_SI_MISMO")
    assert es_error(api.pedir("DELETE", "/admin/usuarios/1", admin), 409, "ACCION_SOBRE_SI_MISMO")


def test_un_id_de_usuario_que_no_cabe_en_sqlite_responde_404(api):
    admin = api.admin()

    assert es_error(api.pedir("DELETE", f"/admin/usuarios/{2**63}", admin), 404, "USUARIO_NO_ENCONTRADO")


def test_un_limite_infinito_de_una_especie_responde_400(api):
    admin = api.admin()
    rangos = {**ESPECIE_NUEVA["rangos"], "luz": {"min": 0, "max": 10**400}}

    respuesta = api.pedir("POST", "/admin/especies", admin, json={**ESPECIE_NUEVA, "rangos": rangos})

    assert es_error(respuesta, 400, "SOLICITUD_INVALIDA")


def test_medio_caracter_en_la_contrasena_responde_400_y_no_500(api):
    cuerpo = '{"nombre": "Ana", "correo": "ana@correo.co", "contrasena": "clave-\\ud800-segura"}'

    respuesta = api.http.post("/api/v1/usuarios", data=cuerpo, content_type="application/json")

    assert es_error(respuesta, 400, "SOLICITUD_INVALIDA")


@pytest.mark.parametrize("cuerpo", [{}, {"activo": False, "rol": "ADMIN"}, {"activo": "no"}, {"rol": "JEFE"}])
def test_un_cambio_de_usuario_mal_formado_responde_400(api, cuerpo):
    admin = api.admin()
    api.registrar("Beto", "beto@correo.co")

    assert es_error(api.pedir("PATCH", "/admin/usuarios/2", admin, json=cuerpo), 400, "PARAMETRO_INVALIDO")


def test_eliminar_una_cuenta_la_quita_de_la_lista(api):
    admin = api.admin()
    api.registrar("Beto", "beto@correo.co")

    assert api.pedir("DELETE", "/admin/usuarios/2", admin).status_code == 200
    assert [u["nombre"] for u in api.pedir("GET", "/admin/usuarios", admin).get_json()] == ["Ada"]
    assert es_error(api.pedir("DELETE", "/admin/usuarios/2", admin), 404, "USUARIO_NO_ENCONTRADO")


def test_el_admin_agrega_una_especie_y_aparece_en_el_catalogo(api):
    admin = api.admin()

    respuesta = api.pedir("POST", "/admin/especies", admin, json=ESPECIE_NUEVA)

    assert respuesta.status_code == 201
    assert respuesta.get_json()["rangos"]["luz"] == {"min": 1080.0, "max": 5380.0, "unidad": "lux"}
    assert "cinta" in [e["nombre"] for e in api.pedir("GET", "/especies", admin).get_json()]
    assert es_error(api.pedir("POST", "/admin/especies", admin, json=ESPECIE_NUEVA), 409, "ESPECIE_YA_EXISTE")


@pytest.mark.parametrize(
    ("rangos", "campo", "motivo"),
    [
        ({**ESPECIE_NUEVA["rangos"], "luz": {"min": 5380, "max": 1080}}, "rangos.luz", "minimo_no_menor_que_maximo"),
        ({"humedad": {"min": 30, "max": 60}, "luz": {"min": 1080, "max": 5380}}, "rangos.temperatura", "ausente"),
        ({**ESPECIE_NUEVA["rangos"], "humedad": {"min": "mucho", "max": 60}}, "rangos.humedad", "no_numerico"),
    ],
)
def test_una_especie_con_rangos_invalidos_responde_400_con_el_campo(api, rangos, campo, motivo):
    admin = api.admin()

    respuesta = api.pedir("POST", "/admin/especies", admin, json={**ESPECIE_NUEVA, "rangos": rangos})

    assert es_error(respuesta, 400, "PARAMETRO_INVALIDO")
    assert (respuesta.get_json()["detalle"]["campo"], respuesta.get_json()["detalle"]["motivo"]) == (campo, motivo)


def test_cors_deja_al_front_mandar_el_token_y_usar_patch(api):
    respuesta = api.http.options(
        "/api/v1/admin/usuarios/2",
        headers={
            "Origin": ORIGEN_FRONT,
            "Access-Control-Request-Method": "PATCH",
            "Access-Control-Request-Headers": "Authorization, Content-Type",
        },
    )

    assert respuesta.headers["Access-Control-Allow-Origin"] == ORIGEN_FRONT
    assert "PATCH" in respuesta.headers["Access-Control-Allow-Methods"]
    assert "authorization" in respuesta.headers["Access-Control-Allow-Headers"].lower()


def test_las_rutas_nuevas_tambien_responden_json_en_los_errores_http(api):
    assert es_error(api.pedir("GET", "/admin/especies"), 405, "METODO_NO_PERMITIDO")
    assert es_error(api.pedir("PATCH", "/admin/usuarios/abc"), 404, "RUTA_NO_ENCONTRADA")
