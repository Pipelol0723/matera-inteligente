"""Tiempo real: las conexiones abiertas de cada usuario, la cola de cada pestana y el mensaje de cada medicion."""
import json
import sys
import threading
from datetime import datetime, timezone

import pytest

from dominio.errores_usuarios import SesionInvalida
from dominio.evaluador import EvaluadorPlanta
from dominio.historial import RegistroMedicion
from dominio.plantas import Planta
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from infraestructura.tiempo_real import CanalesTiempoReal, NotificadorWebSocket
from presentacion import tiempo_real
from presentacion.esquemas_usuarios import medicion_en_vivo_a_json
from presentacion.tiempo_real import CanalWebSocket
from tests.dobles import medicion, sansevieria

ANA, BETO = 1, 2
MOMENTO = datetime(2026, 10, 18, 15, 0, tzinfo=timezone.utc)


class CanalFalso:
    """Una pestana abierta: guarda lo que recibe. Si esta cerrada, enviar falla como el WebSocket real."""

    def __init__(self, cerrado=False):
        self.recibidos: list[str] = []
        self.cerrado = cerrado

    def enviar(self, texto: str) -> None:
        if self.cerrado:
            raise ConnectionError("la pestana se cerro")
        self.recibidos.append(texto)


def _medicion_de_ana():
    planta = Planta(7, ANA, "Sala", "sansevieria")
    diagnostico = EvaluadorPlanta(ReglaHibrida(), GeneradorRecomendaciones()).evaluar(sansevieria(), medicion(18, 800, 22))
    return planta, RegistroMedicion.desde(diagnostico, planta.id, MOMENTO, "MT-0001-AA"), diagnostico


def test_cada_canal_recibe_solo_lo_de_su_usuario_y_mientras_esta_conectado():
    canales = CanalesTiempoReal()
    pestana_ana, otra_pestana_ana, pestana_beto = CanalFalso(), CanalFalso(), CanalFalso()

    with canales.conectado(ANA, pestana_ana), canales.conectado(ANA, otra_pestana_ana), canales.conectado(BETO, pestana_beto):
        assert canales.enviar(ANA, "hola Ana") == 2
    assert canales.enviar(ANA, "ya nadie escucha") == 0

    assert pestana_ana.recibidos == otra_pestana_ana.recibidos == ["hola Ana"]
    assert pestana_beto.recibidos == []
    assert canales.conectados(ANA) == canales.conectados(BETO) == 0


def test_una_conexion_que_falla_se_quita_y_las_demas_igual_reciben():
    canales = CanalesTiempoReal()
    cerrada, abierta = CanalFalso(cerrado=True), CanalFalso()

    with canales.conectado(ANA, cerrada), canales.conectado(ANA, abierta):
        assert canales.enviar(ANA, "medicion") == 1
        assert canales.conectados(ANA) == 1

    assert abierta.recibidos == ["medicion"]


def test_los_canales_aguantan_hilos_que_se_conectan_desconectan_y_envian_a_la_vez():
    # Cada hilo abre y cierra pestanas sin parar, y manda mientras otras se van. Con el cambio de
    # hilo forzado a cada microsegundo, sin el candado se pierden pestanas o falla _quitar.
    canales = CanalesTiempoReal()
    fallas = []

    def pestana_que_va_y_viene():
        try:
            for _ in range(1000):
                propia = CanalFalso()
                with canales.conectado(ANA, propia):
                    assert canales.enviar(ANA, "m") >= 1
                    assert "m" in propia.recibidos
        except Exception as error:  # se junta y se revisa en el hilo de la prueba
            fallas.append(error)

    anterior = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        hilos = [threading.Thread(target=pestana_que_va_y_viene) for _ in range(8)]
        for hilo in hilos:
            hilo.start()
        for hilo in hilos:
            hilo.join(timeout=60)
    finally:
        sys.setswitchinterval(anterior)

    assert not any(hilo.is_alive() for hilo in hilos)
    assert fallas == []
    assert canales.conectados(ANA) == 0


def test_el_notificador_manda_al_dueno_un_json_con_la_tarjeta_el_registro_y_el_diagnostico():
    canales = CanalesTiempoReal()
    notificador = NotificadorWebSocket(canales, medicion_en_vivo_a_json)
    pestana = CanalFalso()
    planta, registro, diagnostico = _medicion_de_ana()

    with canales.conectado(ANA, pestana):
        notificador.publicar(ANA, planta, registro, diagnostico)

    [texto] = pestana.recibidos
    mensaje = json.loads(texto)
    assert mensaje["tipo"] == "medicion"
    assert mensaje["planta"] == {"id": 7, "apodo": "Sala", "especie": "sansevieria"}
    assert mensaje["medicion"]["origen"] == "MT-0001-AA"
    assert mensaje["medicion"]["momento"] == MOMENTO.isoformat()
    assert mensaje["medicion"]["lecturas"][0] == {"nombre": "humedad", "valor": 18, "unidad": "%", "estado": "BAJO"}
    assert mensaje["diagnostico"]["estado"] == "EN_RIESGO"
    assert len(mensaje["diagnostico"]["recomendaciones"]) == 1


def test_sin_pantallas_abiertas_el_notificador_no_hace_nada():
    canales = CanalesTiempoReal()

    def formato_que_no_deberia_usarse(*_):
        raise AssertionError("no hay a quien avisar")

    NotificadorWebSocket(canales, formato_que_no_deberia_usarse).publicar(ANA, *_medicion_de_ana())


# ---- CanalWebSocket: la cola y el hilo emisor de cada pestana (presentacion/tiempo_real.py) ----


class WebSocketFalso:
    """Lo que CanalWebSocket usa del WebSocket de flask-sock. `trabado` imita una pestana que no lee."""

    def __init__(self, trabado: threading.Event | None = None):
        self.enviados: list[str] = []
        self.cierre = None
        self.cortado = threading.Event()
        self._trabado = trabado
        self.sock = self  # CanalWebSocket corta el socket con ws.sock.shutdown()

    def send(self, texto):
        if self._trabado is not None:
            self._trabado.wait(10)
        if self.cortado.is_set():
            raise OSError("el socket se corto")
        self.enviados.append(texto)

    def close(self, reason=None, message=None):
        self.cierre = (reason, message)

    def shutdown(self, como):
        self.cortado.set()


def _terminar(canal):
    canal.terminar()
    canal._emisor.join(timeout=5)
    assert not canal._emisor.is_alive()


def test_el_canal_manda_los_mensajes_en_el_orden_en_que_llegaron():
    ws = WebSocketFalso()
    canal = CanalWebSocket(ws)

    for texto in ("a", "b", "c"):
        canal.enviar(texto)
    _terminar(canal)

    assert ws.enviados == ["a", "b", "c"]


def test_una_pestana_que_no_lee_no_traba_al_que_avisa_y_se_corta_cuando_se_llena_su_cola():
    trabado = threading.Event()
    ws = WebSocketFalso(trabado)
    canal = CanalWebSocket(ws)
    resultado = []

    def avisar_muchas_veces():
        try:
            for i in range(tiempo_real.COLA_MAXIMA + 2):
                canal.enviar(f"m{i}")
        except ConnectionError:
            resultado.append("se corto")

    avisos = threading.Thread(target=avisar_muchas_veces, daemon=True)
    avisos.start()
    avisos.join(timeout=2)
    quedo_esperando = avisos.is_alive()
    trabado.set()

    assert not quedo_esperando, "el hilo que avisa quedo esperando al socket"
    assert resultado == ["se corto"]
    assert ws.cortado.is_set()
    _terminar(canal)


def test_si_la_sesion_ya_no_sirve_el_canal_manda_el_error_cierra_y_avisa_que_no_sirve():
    ws = WebSocketFalso()
    canal = CanalWebSocket(ws)

    def sesion_borrada():
        raise SesionInvalida()

    canal.autenticado(sesion_borrada)
    with pytest.raises(ConnectionError):
        canal.enviar("medicion de otra cuenta")
    canal._emisor.join(timeout=5)

    [error] = [json.loads(texto) for texto in ws.enviados]
    assert (error["tipo"], error["error"]) == ("error", "SESION_INVALIDA")
    assert ws.cierre == (tiempo_real.CIERRE_POR_POLITICA, "SESION_INVALIDA")


def test_cerrar_con_error_espera_a_que_salga_el_mensaje_antes_de_volver():
    ws = WebSocketFalso()
    canal = CanalWebSocket(ws)

    canal.cerrar_con_error("ERROR_INTERNO", "algo fallo", tiempo_real.CIERRE_POR_ERROR)

    assert json.loads(ws.enviados[0])["error"] == "ERROR_INTERNO"
    assert ws.cierre == (tiempo_real.CIERRE_POR_ERROR, "ERROR_INTERNO")
