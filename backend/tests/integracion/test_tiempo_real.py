"""Tiempo real: las conexiones abiertas de cada usuario y el mensaje de cada medicion nueva."""
import json
import threading
from datetime import datetime, timezone

from dominio.evaluador import EvaluadorPlanta
from dominio.historial import RegistroMedicion
from dominio.plantas import Planta
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from infraestructura.tiempo_real import CanalesTiempoReal, NotificadorWebSocket
from presentacion.esquemas_usuarios import medicion_en_vivo_a_json
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


def test_los_canales_aguantan_hilos_que_se_conectan_y_envian_a_la_vez():
    canales = CanalesTiempoReal()
    pestanas = [CanalFalso() for _ in range(20)]
    listos, salir = threading.Barrier(len(pestanas) + 1), threading.Event()

    def pestana_abierta(canal):
        with canales.conectado(ANA, canal):
            listos.wait()
            salir.wait()

    hilos = [threading.Thread(target=pestana_abierta, args=(canal,)) for canal in pestanas]
    for hilo in hilos:
        hilo.start()
    listos.wait()
    envios = [threading.Thread(target=canales.enviar, args=(ANA, f"m{i}")) for i in range(10)]
    for hilo in envios:
        hilo.start()
    for hilo in envios:
        hilo.join()
    salir.set()
    for hilo in hilos:
        hilo.join()

    assert all(sorted(p.recibidos) == sorted(f"m{i}" for i in range(10)) for p in pestanas)
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
