"""El simulador del ESP32 (R3) contra el servidor de verdad: lecturas normales, fuera de rango e invalidas.

El simulador vive fuera del backend (simulador/ en la raiz del repositorio) y no importa
nada de el: se carga desde su archivo, como lo correria cualquiera.
"""
import importlib.util
import random
from pathlib import Path

import pytest

from tests.integracion.conftest import pedir_http

RAIZ = Path(__file__).resolve().parents[3]
_spec = importlib.util.spec_from_file_location("simulador_esp32", RAIZ / "simulador" / "simulador_esp32.py")
simulador = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(simulador)


@pytest.fixture
def matera(base_url):
    """La cuenta de Ana con su matera del simulador: (token de Ana, {planta, codigo, clave})."""
    pedir_http(base_url, "POST", "/usuarios", {"nombre": "Ana", "correo": "ana@correo.co", "contrasena": "clave-segura"})
    _, sesion = pedir_http(base_url, "POST", "/sesiones", {"correo": "ana@correo.co", "contrasena": "clave-segura"})
    estado, matera = pedir_http(
        base_url, "POST", "/plantas", {"apodo": "Simulada", "especie": "potos", "codigo": "MT-0002-AB"}, sesion["token"]
    )
    assert estado == 201
    return sesion["token"], matera


def _correr(base_url, matera, *opciones):
    lineas = []
    codigo = simulador.main(
        [matera["codigo"], f"--clave={matera['clave']}", f"--api={base_url}", "--intervalo", "0", "--semilla", "7", *opciones],
        salida=lineas.append,
    )
    return codigo, lineas


def _historial(base_url, token, matera):
    return pedir_http(base_url, "GET", f"/plantas/{matera['planta']['id']}/historial?limite=50", token=token)[1]["registros"]


def test_el_modo_continuo_manda_lecturas_que_quedan_en_el_historial_con_el_codigo_del_sensor(base_url, matera):
    token, datos = matera

    codigo, lineas = _correr(base_url, datos, "--veces", "3")

    assert codigo == 0
    assert lineas[-1] == "Se mandaron 3 lecturas: 3 normales, 0 fuera de rango y 0 invalidas."
    registros = _historial(base_url, token, datos)
    assert [r["origen"] for r in registros] == ["MT-0002-AB"] * 3


def test_las_lecturas_fuera_de_rango_se_guardan_con_su_diagnostico(base_url, matera):
    token, datos = matera

    codigo, lineas = _correr(base_url, datos, "--veces", "3", "--fuera-de-rango", "1")

    assert codigo == 0
    assert lineas[-1] == "Se mandaron 3 lecturas: 0 normales, 3 fuera de rango y 0 invalidas."
    assert all(r["estado"] != "SALUDABLE" for r in _historial(base_url, token, datos))


def test_los_datos_invalidos_se_rechazan_como_se_esperaba_y_no_se_guardan(base_url, matera):
    token, datos = matera

    codigo, lineas = _correr(base_url, datos, "--veces", "6", "--invalidas", "1")

    assert codigo == 0
    assert all("como se esperaba" in linea for linea in lineas[1:-1])
    assert _historial(base_url, token, datos) == []


def test_el_modo_casos_recorre_cada_error_y_la_api_responde_lo_esperado(base_url, matera):
    token, datos = matera

    codigo, lineas = _correr(base_url, datos, "--casos")

    assert codigo == 0
    assert lineas[-1] == f"{len(simulador.CASOS) + 1} de {len(simulador.CASOS) + 1} como se esperaba."
    assert _historial(base_url, token, datos) == []


def test_con_una_clave_equivocada_el_simulador_avisa_y_termina(base_url, matera):
    _, datos = matera

    codigo, lineas = _correr(base_url, {**datos, "clave": "una-clave-que-no-es"}, "--veces", "1")

    assert codigo == 1
    assert "CLAVE_SENSOR_INVALIDA" in lineas[-1]


def test_si_la_api_deja_de_responder_el_modo_continuo_lo_dice_y_sigue(base_url, matera, monkeypatch):
    token, datos = matera
    pedir = simulador._pedir
    lecturas_pedidas = []

    def con_un_corte(url, cuerpo, token=None):
        if url.endswith("/lecturas"):
            lecturas_pedidas.append(url)
            if len(lecturas_pedidas) == 2:
                raise simulador.SinConexion("el backend se esta reiniciando")
        return pedir(url, cuerpo, token)

    monkeypatch.setattr(simulador, "_pedir", con_un_corte)

    codigo, lineas = _correr(base_url, datos, "--veces", "3")

    assert codigo == 0
    assert any("sin conexion con la API (el backend se esta reiniciando)" in linea for linea in lineas)
    assert lineas[-2:] == [
        "Se mandaron 2 lecturas: 2 normales, 0 fuera de rango y 0 invalidas.",
        "1 no se pudieron mandar porque la API no respondio.",
    ]
    assert len(_historial(base_url, token, datos)) == 2


def test_un_caso_de_error_con_el_token_vencido_canjea_y_prueba_el_dato(base_url, matera):
    _, datos = matera
    sim = simulador.Simulador(base_url, datos["codigo"], datos["clave"], salida=lambda _: None)
    assert sim.canjear()[0] == 200
    # Otro canje del mismo sensor deja sin efecto el token de sim, como si hubiera vencido.
    assert simulador.Simulador(base_url, datos["codigo"], datos["clave"]).canjear()[0] == 200
    [humedad_imposible] = [caso for caso in simulador.CASOS if caso.nombre.startswith("humedad imposible")]

    estado, respuesta = sim.probar(humedad_imposible, {"humedad": 50, "luz": 800, "temperatura": 22})

    assert (estado, respuesta["error"]) == (400, "PARAMETRO_INVALIDO")


def test_si_la_api_no_responde_el_simulador_lo_dice():
    lineas = []

    codigo = simulador.main(["MT-0002-AB", "--clave=x", "--api=http://127.0.0.1:9/api/v1"], salida=lineas.append)

    assert codigo == 2
    assert "No se pudo contactar la API" in lineas[-1]


def test_los_valores_de_la_matera_simulada_cambian_poco_a_poco_y_no_pasan_los_limites_fisicos():
    matera = simulador.MateraSimulada(random.Random(1))
    lecturas = [matera.siguiente() for _ in range(300)]

    for anterior, actual in zip(lecturas, lecturas[1:]):
        regada = actual["humedad"] > anterior["humedad"]
        assert regada or anterior["humedad"] - actual["humedad"] <= 0.8 + 0.05
        assert abs(actual["temperatura"] - anterior["temperatura"]) < 1.5
    assert all(0 <= l["humedad"] <= 100 and 0 <= l["luz"] <= 150000 and -50 <= l["temperatura"] <= 60 for l in lecturas)
    assert any(actual["humedad"] > anterior["humedad"] for anterior, actual in zip(lecturas, lecturas[1:]))  # hubo riego
