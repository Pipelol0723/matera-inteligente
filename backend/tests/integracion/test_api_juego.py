"""El juego de punta a punta (corte 3): cada lectura del sensor suma o resta, la matera Tamagotchi y la tabla.

Las lecturas llegan como las manda la placa: canje de la clave y POST con su
token. Para ver crecer y marchitarse una matera, la app usa el reloj del juego
de la demo (1 dia = 6 minutos: una hora de juego dura 15 segundos, lo que tarda
la placa entre lecturas) y un reloj que solo avanza cuando la prueba lo pide.
"""
from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

import main
from dominio.mascota import RelojDeJuego
from dominio.puertos_usuarios import Reloj
from infraestructura.sqlite import BaseDatos, MovimientosPuntajeSqlite
from infraestructura.tiempo_real import NotificadorWebSocket
from tests.integracion.conftest import ClienteApi, es_error

SALUDABLE = {"humedad": 50, "luz": 800, "temperatura": 22}
# Para el potos: 16 a 29 grados y 40 a 70 % de humedad.
EN_RIESGO = {"humedad": 50, "luz": 800, "temperatura": 33}  # solo calor, y poco
CRITICO = {"humedad": 10, "luz": 800, "temperatura": 33}  # sed y calor: el globo pide primero el agua

RUTAS = [
    ("GET", "/juego/materas", None),
    ("GET", "/juego/puntaje", None),
    ("GET", "/juego/participacion", None),
    ("PUT", "/juego/participacion", {"participa": True, "apodo": "pipe_verde"}),
    ("GET", "/juego/tabla", None),
]


class RelojDePrueba(Reloj):
    """Avanza solo cuando la prueba lo pide.

    Empieza dos horas atras: la libreria de JWT rechaza un token emitido en el futuro,
    y asi la prueba puede adelantarlo sin pasar la hora real.
    """

    def __init__(self):
        self.momento = datetime.now(timezone.utc) - timedelta(hours=2)

    def ahora(self) -> datetime:
        return self.momento

    def avanzar(self, **cuanto) -> None:
        self.momento += timedelta(**cuanto)


class Matera:
    """Una matera creada desde la app, con su placa ya canjeada: leer() manda una lectura con la hora del reloj."""

    def __init__(self, api: ClienteApi, token: str, apodo="Sala", codigo="MT-0001-AA", reloj=None):
        respuesta = api.pedir("POST", "/plantas", token, json={"apodo": apodo, "especie": "potos", "codigo": codigo})
        assert respuesta.status_code == 201, respuesta.get_json()
        self.api, self.codigo, self.reloj = api, codigo, reloj
        self.planta = respuesta.get_json()["planta"]
        canje = api.canjear(codigo, respuesta.get_json()["clave"])
        assert canje.status_code == 200
        self.token = canje.get_json()["token"]

    def leer(self, lecturas, momento=None):
        if momento is None and self.reloj is not None:
            momento = self.reloj.ahora().isoformat()
        return self.api.reportar(self.codigo, self.token, lecturas, momento=momento)


@pytest.fixture
def reloj():
    return RelojDePrueba()


@pytest.fixture
def juego(config, reloj):
    """La app con el reloj del juego de la demo (1 dia = 6 minutos), y el reloj de la prueba."""
    return ClienteApi(replace(config, minutos_por_dia_juego=6), reloj)


def _get(api, ruta, token):
    respuesta = api.pedir("GET", ruta, token)
    assert respuesta.status_code == 200, respuesta.get_json()
    return respuesta.get_json()


def _mascota(api, token):
    [mascota] = _get(api, "/juego/materas", token)["materas"]
    return mascota


def _participar(api, token, apodo):
    return api.pedir("PUT", "/juego/participacion", token, json={"participa": True, "apodo": apodo})


# --- Los puntos de cada lectura ---


def test_cada_lectura_aceptada_suma_o_resta_segun_su_estado_y_la_201_trae_la_necesidad(juego, reloj):
    ana = juego.cuenta()
    sala = Matera(juego, ana, reloj=reloj)
    momentos = []
    for lecturas, estado, necesidad in ((SALUDABLE, "SALUDABLE", None), (EN_RIESGO, "EN_RIESGO", "CALOR"), (CRITICO, "CRITICO", "SED")):
        reloj.avanzar(seconds=1)
        momentos.append(reloj.ahora().isoformat())
        respuesta = sala.leer(lecturas)

        assert respuesta.status_code == 201
        cuerpo = respuesta.get_json()
        assert set(cuerpo) == {"planta", "momento", "diagnostico", "necesidad", "prueba"}
        assert cuerpo["prueba"] is None  # sin modo prueba
        assert (cuerpo["diagnostico"]["estado"], cuerpo["necesidad"]) == (estado, necesidad)

    assert _get(juego, "/juego/puntaje", ana) == {
        "puntos": -5,
        "materas": [{"planta": sala.planta, "puntos": -5}],
        "movimientos": [
            {"momento": momentos[2], "planta": "Sala", "estado": "CRITICO", "puntos": -10},
            {"momento": momentos[1], "planta": "Sala", "estado": "EN_RIESGO", "puntos": -5},
            {"momento": momentos[0], "planta": "Sala", "estado": "SALUDABLE", "puntos": 10},
        ],
    }


def test_una_lectura_rechazada_no_cuenta(juego, reloj):
    ana = juego.cuenta()
    sala = Matera(juego, ana, reloj=reloj)

    assert sala.leer({**SALUDABLE, "humedad": 150}).status_code == 400  # fisicamente imposible
    futuro = sala.leer(SALUDABLE, momento=(reloj.ahora() + timedelta(minutes=10)).isoformat())
    assert es_error(futuro, 400, "MOMENTO_INVALIDO")
    assert juego.reportar("MT-0001-AA", "token-falso", SALUDABLE).status_code == 401

    assert _get(juego, "/juego/puntaje", ana) == {"puntos": 0, "materas": [{"planta": sala.planta, "puntos": 0}], "movimientos": []}
    mascota = _mascota(juego, ana)
    assert (mascota["puntos"], mascota["cara"], mascota["ultimaLectura"]) == (0, None, None)


# --- La matera Tamagotchi ---


def test_con_el_reloj_acelerado_la_matera_crece_de_semilla_a_brote_y_se_marchita(juego, reloj):
    ana = juego.cuenta()
    sala = Matera(juego, ana, reloj=reloj)
    assert _mascota(juego, ana) == {
        "plantaId": sala.planta["id"],
        "etapa": "SEMILLA",
        "condicion": "SANA",
        "cara": None,
        "dormida": True,
        "necesidad": None,
        "aviso": None,
        "puntos": 0,
        "horasCuidada": 0,
        "ultimaLectura": None,
        "prueba": None,
    }

    # El potos llega a brote con 1 dia de juego bien cuidada: 24 horas de juego. Con la placa mandando cada
    # 15 s, como en la demo, son 24 lecturas: 6 minutos.
    for _ in range(23):
        reloj.avanzar(seconds=15)
        assert sala.leer(SALUDABLE).status_code == 201
    assert (_mascota(juego, ana)["etapa"], _mascota(juego, ana)["horasCuidada"]) == ("SEMILLA", 23)
    reloj.avanzar(seconds=15)
    assert sala.leer(SALUDABLE).status_code == 201
    assert _mascota(juego, ana) == {
        "plantaId": sala.planta["id"],
        "etapa": "BROTE",
        "condicion": "SANA",
        "cara": "SALUDABLE",
        "dormida": False,
        "necesidad": None,
        "aviso": None,
        "puntos": 240,
        "horasCuidada": 24,
        "ultimaLectura": reloj.ahora().isoformat(),
        "prueba": None,
    }

    # Dos minutos despues (8 horas de juego: fuera de la ventana de 6), llega una lectura CRITICO.
    reloj.avanzar(minutes=2)
    assert sala.leer(CRITICO).status_code == 201
    marchita = _mascota(juego, ana)
    assert (marchita["condicion"], marchita["aviso"], marchita["cara"], marchita["necesidad"]) == (
        "MARCHITA", "SE_MARCHITO", "CRITICO", "SED"
    )
    # Marchita no crece, pero tampoco se achica.
    reloj.avanzar(seconds=15)
    assert sala.leer(CRITICO).status_code == 201
    sigue = _mascota(juego, ana)
    assert (sigue["etapa"], sigue["horasCuidada"], sigue["condicion"], sigue["aviso"], sigue["puntos"]) == (
        "BROTE", 24, "MARCHITA", None, 220
    )


def test_la_matera_se_duerme_con_los_minutos_sin_lecturas_de_la_configuracion(config, reloj):
    api = ClienteApi(replace(config, minutos_sin_lecturas=1), reloj)
    ana = api.cuenta()
    sala = Matera(api, ana, reloj=reloj)
    assert sala.leer(EN_RIESGO).status_code == 201
    assert _mascota(api, ana)["dormida"] is False

    reloj.avanzar(seconds=61)

    # Dormida conserva la cara, pero no muestra lo que pedia: esa lectura ya es vieja.
    dormida = _mascota(api, ana)
    assert (dormida["dormida"], dormida["cara"], dormida["necesidad"], dormida["aviso"]) == (True, "EN_RIESGO", None, None)


def test_con_la_ventana_llena_el_aviso_se_marchito_sale_una_vez(config, reloj):
    """El reloj de la demo (6 minutos por dia: una hora de juego dura 15 s) y una lectura cada 15 s, como la placa."""
    api = ClienteApi(replace(config, minutos_por_dia_juego=6), reloj)
    ana = api.cuenta()
    sala = Matera(api, ana, reloj=reloj)
    vistos = []
    for lecturas in [SALUDABLE] * 6 + [CRITICO] * 6:
        reloj.avanzar(seconds=15)
        assert sala.leer(lecturas).status_code == 201
        mascota = _mascota(api, ana)
        vistos.append((mascota["condicion"], mascota["aviso"]))

    assert [aviso for _, aviso in vistos] == [None] * 6 + ["PASO_A_CRITICO", None, None, None, "SE_MARCHITO", None]
    assert [condicion for condicion, _ in vistos][-2:] == ["MARCHITA", "MARCHITA"]

    # La placa se apaga: pasan los 90 s de la ventana y la matera sigue igual, hasta que se duerme.
    reloj.avanzar(minutes=2)
    quieta = _mascota(api, ana)
    assert (quieta["condicion"], quieta["cara"], quieta["dormida"], quieta["necesidad"]) == ("MARCHITA", "CRITICO", False, "SED")
    reloj.avanzar(minutes=29)
    dormida = _mascota(api, ana)
    assert (dormida["condicion"], dormida["dormida"], dormida["necesidad"], dormida["aviso"]) == ("MARCHITA", True, None, None)


def test_una_lectura_con_la_hora_del_dispositivo_atrasada_cambia_la_cara_y_avisa(juego, reloj):
    ana = juego.cuenta()
    sala = Matera(juego, ana, reloj=reloj)
    reloj.avanzar(seconds=15)
    assert sala.leer(SALUDABLE).status_code == 201
    reloj.avanzar(seconds=15)

    # La placa reinicio y manda su hora 31 minutos atrasada: la API la acepta.
    atrasada = sala.leer(CRITICO, momento=(reloj.ahora() - timedelta(minutes=31)).isoformat())

    assert atrasada.status_code == 201
    mascota = _mascota(juego, ana)
    assert (mascota["cara"], mascota["aviso"], mascota["dormida"], mascota["puntos"]) == ("CRITICO", "PASO_A_CRITICO", False, 0)
    assert mascota["ultimaLectura"] == reloj.ahora().isoformat()  # la hora del servidor


def test_cambiar_el_reloj_del_juego_no_hace_crecer_de_golpe_a_las_materas(config, reloj):
    """Con el reloj real, 24 lecturas cada 15 s caen en una o dos horas de juego.

    Al volver a arrancar con MATERA_MINUTOS_POR_DIA_JUEGO=6 (horas de 15 s), esas
    lecturas no se reagrupan en 24 horas: el potos no pasa a brote de golpe.
    """
    real = ClienteApi(config, reloj)
    ana = real.cuenta()
    sala = Matera(real, ana, reloj=reloj)
    for _ in range(24):
        reloj.avanzar(seconds=15)
        assert sala.leer(SALUDABLE).status_code == 201
    antes = _mascota(real, ana)

    demo = ClienteApi(replace(config, minutos_por_dia_juego=6), reloj)
    despues = _mascota(demo, ana)

    assert antes["horasCuidada"] in (1, 2)
    assert (despues["horasCuidada"], despues["etapa"], despues["puntos"]) == (antes["horasCuidada"], "SEMILLA", 240)


# --- Quien ve que ---


@pytest.mark.parametrize(("metodo", "ruta", "cuerpo"), RUTAS, ids=[f"{m} {r}" for m, r, _ in RUTAS])
def test_las_rutas_del_juego_exigen_el_jwt_de_usuario(api, metodo, ruta, cuerpo):
    token_usuario = api.cuenta()
    matera = api.pedir("POST", "/plantas", token_usuario, json={"apodo": "Sala", "especie": "potos", "codigo": "MT-0001-AA"})
    token_sensor = api.canjear("MT-0001-AA", matera.get_json()["clave"]).get_json()["token"]

    assert es_error(api.pedir(metodo, ruta, json=cuerpo), 401, "SESION_INVALIDA")
    assert es_error(api.pedir(metodo, ruta, "no-es-un-jwt", json=cuerpo), 401, "SESION_INVALIDA")
    assert es_error(api.pedir(metodo, ruta, token_sensor, json=cuerpo), 403, "ALCANCE_INVALIDO")


def test_cada_cuenta_solo_ve_sus_materas_y_sus_puntos(juego, reloj):
    ana, beto = juego.cuenta(), juego.cuenta("Beto", "beto@correo.co")
    sala = Matera(juego, ana, reloj=reloj)
    patio = Matera(juego, beto, "Patio", "MT-0002-BB", reloj=reloj)
    assert sala.leer(SALUDABLE).status_code == 201
    reloj.avanzar(seconds=1)
    assert patio.leer(CRITICO).status_code == 201

    assert [m["plantaId"] for m in _get(juego, "/juego/materas", ana)["materas"]] == [sala.planta["id"]]
    assert [m["plantaId"] for m in _get(juego, "/juego/materas", beto)["materas"]] == [patio.planta["id"]]
    puntaje_ana = _get(juego, "/juego/puntaje", ana)
    assert puntaje_ana["puntos"] == 10
    assert [m["planta"] for m in puntaje_ana["materas"]] == [sala.planta]
    assert [m["planta"] for m in puntaje_ana["movimientos"]] == ["Sala"]
    assert _get(juego, "/juego/puntaje", beto)["puntos"] == -10


def test_al_borrar_una_matera_sus_puntos_siguen_con_el_dueno_y_no_pasan_a_otra_planta(juego, reloj):
    ana, beto = juego.cuenta(), juego.cuenta("Beto", "beto@correo.co")
    sala = Matera(juego, ana, reloj=reloj)
    for _ in range(2):
        reloj.avanzar(seconds=5)
        assert sala.leer(SALUDABLE).status_code == 201

    assert juego.pedir("DELETE", f"/plantas/{sala.planta['id']}", ana).status_code == 200
    patio = Matera(juego, beto, "Patio", "MT-0002-BB", reloj=reloj)
    nueva = Matera(juego, ana, "Sala nueva", "MT-0003-CC", reloj=reloj)

    assert patio.planta["id"] == sala.planta["id"]  # SQLite le dio a Beto el id de la planta borrada
    puntaje_ana = _get(juego, "/juego/puntaje", ana)
    assert puntaje_ana["puntos"] == 20
    assert puntaje_ana["materas"] == [{"planta": nueva.planta, "puntos": 0}]
    assert [m["planta"] for m in puntaje_ana["movimientos"]] == [None, None]
    assert _get(juego, "/juego/puntaje", beto) == {"puntos": 0, "materas": [{"planta": patio.planta, "puntos": 0}], "movimientos": []}
    for token in (ana, beto):
        mascota = _mascota(juego, token)
        assert (mascota["puntos"], mascota["horasCuidada"], mascota["etapa"]) == (0, 0, "SEMILLA")


# --- Participar en la tabla ---


def test_la_participacion_empieza_sin_decidir_y_se_puede_cambiar(api):
    ana = api.cuenta()
    assert _get(api, "/juego/participacion", ana) == {"estado": "SIN_DECIDIR", "apodo": None}

    respuesta = _participar(api, ana, "Pipe_Verde")
    assert (respuesta.status_code, respuesta.get_json()) == (200, {"estado": "PARTICIPA", "apodo": "Pipe_Verde"})
    assert _get(api, "/juego/participacion", ana) == {"estado": "PARTICIPA", "apodo": "Pipe_Verde"}

    # Al no participar, el apodo se ignora y queda libre.
    respuesta = api.pedir("PUT", "/juego/participacion", ana, json={"participa": False, "apodo": "otro"})
    assert (respuesta.status_code, respuesta.get_json()) == (200, {"estado": "NO_PARTICIPA", "apodo": None})
    assert _get(api, "/juego/participacion", ana) == {"estado": "NO_PARTICIPA", "apodo": None}


def test_la_tabla_es_solo_para_quien_participa_y_solo_trae_a_quienes_participan(api):
    ana, beto = api.cuenta(), api.cuenta("Beto", "beto@correo.co")
    carla, dario = api.cuenta("Carla", "carla@correo.co"), api.cuenta("Dario", "dario@correo.co")
    for token, apodo, codigo, lecturas in (
        (ana, "Sala", "MT-0001-AA", [SALUDABLE, SALUDABLE]),
        (beto, "Patio", "MT-0002-BB", [CRITICO]),
        (carla, "Cocina", "MT-0003-CC", [SALUDABLE, SALUDABLE, SALUDABLE]),
    ):
        matera = Matera(api, token, apodo, codigo)
        for valores in lecturas:
            assert matera.leer(valores).status_code == 201
    assert _participar(api, ana, "ana_verde").status_code == 200
    assert _participar(api, beto, "beto_zen").status_code == 200
    assert api.pedir("PUT", "/juego/participacion", carla, json={"participa": False}).status_code == 200

    for quien in (carla, dario):  # no participa, o todavia no decidio
        assert es_error(api.pedir("GET", "/juego/tabla", quien), 403, "PARTICIPACION_REQUERIDA")
    assert _get(api, "/juego/tabla", ana) == {
        "posiciones": [
            {"posicion": 1, "apodo": "ana_verde", "puntos": 20, "soyYo": True},
            {"posicion": 2, "apodo": "beto_zen", "puntos": -10, "soyYo": False},
        ]
    }
    assert [fila["soyYo"] for fila in _get(api, "/juego/tabla", beto)["posiciones"]] == [False, True]


def test_el_apodo_de_jugador_repetido_da_409_sin_importar_mayusculas(api):
    ana, beto = api.cuenta(), api.cuenta("Beto", "beto@correo.co")
    assert _participar(api, ana, "pipe_verde").status_code == 200

    repetido = _participar(api, beto, "PIPE_Verde")

    assert es_error(repetido, 409, "APODO_JUGADOR_REPETIDO")
    assert repetido.get_json()["detalle"] == {"campo": "apodo", "apodo": "PIPE_Verde"}
    assert _get(api, "/juego/participacion", beto) == {"estado": "SIN_DECIDIR", "apodo": None}
    # El suyo no cuenta como repetido: Ana puede cambiarle las mayusculas.
    assert _participar(api, ana, "Pipe_Verde").get_json() == {"estado": "PARTICIPA", "apodo": "Pipe_Verde"}


@pytest.mark.parametrize("apodo", ["ab", "a" * 21, "con espacio", "ñandu", "", "   "])
def test_el_apodo_de_jugador_invalido_da_400_con_su_propio_codigo(api, apodo):
    ana = api.cuenta()

    respuesta = _participar(api, ana, apodo)

    assert es_error(respuesta, 400, "APODO_JUGADOR_INVALIDO")
    assert respuesta.get_json()["detalle"] == {"campo": "apodo", "motivo": "invalido", "minimo": 3, "maximo": 20}
    assert _get(api, "/juego/participacion", ana)["estado"] == "SIN_DECIDIR"


@pytest.mark.parametrize(
    ("cuerpo", "codigo", "campo"),
    [
        ([], "SOLICITUD_INVALIDA", None),
        ({}, "PARAMETRO_INVALIDO", "participa"),
        ({"participa": "si", "apodo": "pipe_verde"}, "PARAMETRO_INVALIDO", "participa"),
        ({"participa": 1, "apodo": "pipe_verde"}, "PARAMETRO_INVALIDO", "participa"),
        ({"participa": True}, "PARAMETRO_INVALIDO", "apodo"),
        ({"participa": True, "apodo": 12345}, "PARAMETRO_INVALIDO", "apodo"),
    ],
    ids=["no es objeto", "sin participa", "participa de texto", "participa numerico", "sin apodo", "apodo numerico"],
)
def test_un_cuerpo_invalido_da_400_en_json(api, cuerpo, codigo, campo):
    ana = api.cuenta()

    respuesta = api.pedir("PUT", "/juego/participacion", ana, json=cuerpo)

    assert es_error(respuesta, 400, codigo)
    assert respuesta.get_json()["detalle"].get("campo") == campo


def test_un_cuerpo_que_no_es_json_da_400_en_json(api):
    ana = api.cuenta()

    respuesta = api.pedir("PUT", "/juego/participacion", ana, cabeceras={"Content-Type": "application/json"})

    assert es_error(respuesta, 400, "SOLICITUD_INVALIDA")


# --- El orden de los avisos ---


def test_cuando_sale_el_aviso_en_vivo_los_puntos_ya_estan_guardados(config, monkeypatch):
    """main.py pone el puntaje antes que el WebSocket: el front pide /juego al recibir el mensaje y ya los ve.

    El WebSocket de esta app mira la base justo antes de avisar: con el orden al
    reves veria los puntos de la lectura anterior.
    """
    vistos = []

    class WebSocketQueMira(NotificadorWebSocket):
        def publicar(self, usuario_id, planta, registro, diagnostico):
            vistos.append(MovimientosPuntajeSqlite(BaseDatos(config.ruta_bd), RelojDeJuego()).total_de(usuario_id))
            super().publicar(usuario_id, planta, registro, diagnostico)

    monkeypatch.setattr(main, "NotificadorWebSocket", WebSocketQueMira)
    api = ClienteApi(config)
    sala = Matera(api, api.cuenta())

    for _ in range(3):
        assert sala.leer(SALUDABLE).status_code == 201

    assert vistos == [10, 20, 30]
