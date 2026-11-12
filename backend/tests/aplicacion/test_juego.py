"""Casos de uso del juego (corte 3) con dobles en memoria, un reloj fijo y el diagnostico real del corte 1.

Las lecturas entran como en produccion: DiagnosticarPlantaDeUsuario guarda la
medicion y avisa por AvisarATodos, que reparte el aviso entre el aviso en vivo
y PuntuarLectura.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest

import aplicacion.juego
from aplicacion.avisos import AvisarATodos
from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.juego import (
    ConsultarMascotas,
    ConsultarParticipacion,
    ConsultarPuntaje,
    ConsultarTablaPosiciones,
    ElegirParticipacion,
    PuntuarLectura,
)
from dominio import puertos_juego
from dominio.errores import EspecieNoSoportada
from dominio.errores_juego import ApodoInvalido, ApodoRepetido, ParticipacionRequerida
from dominio.especie import Especie
from dominio.estados import EstadoGlobal
from dominio.evaluador import EvaluadorPlanta
from dominio.historial import RegistroMedicion
from dominio.juego import ApodoJugador, EstadoParticipacion, Participacion
from dominio.mascota import Aviso, Condicion, CuidadoDeMascota, EtapaCrecimiento, Necesidad, RelojDeJuego
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.plantas import Planta
from dominio.rango import Rango
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from dominio.usuarios import Correo, Usuario
from tests.dobles import medicion
from tests.dobles_juego import MovimientosEnMemoria, RegistroJugadoresEnMemoria, ritmos_del_plan
from tests.dominio.test_arquitectura import BACKEND, PROHIBIDOS_EN_DOMINIO, _violaciones
from tests.dobles_usuarios import (
    EspeciesEditablesEnMemoria,
    HistorialEnMemoria,
    NotificadorEnMemoria,
    NotificadorQueFalla,
    RelojFijo,
    RepositorioPlantasEnMemoria,
    RepositorioSensoresEnMemoria,
    RepositorioUsuariosEnMemoria,
    codigo,
)

# Una hora exacta: las horas de juego de 5 s y de 1 h empiezan justo aqui.
AHORA = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
ANA = Usuario(1, Correo("ana@correo.co"), "Ana", "h")
BETO = Usuario(2, Correo("beto@correo.co"), "Beto", "h")
CARO = Usuario(3, Correo("caro@correo.co"), "Caro", "h")
DANI = Usuario(4, Correo("dani@correo.co"), "Dani", "h")

S, R, C = EstadoGlobal.SALUDABLE, EstadoGlobal.EN_RIESGO, EstadoGlobal.CRITICO
RANGOS = {HUMEDAD: Rango(40, 70), LUZ: Rango(270, 2150), TEMPERATURA: Rango(16, 29)}
# Con esos rangos y la regla hibrida: todo bien; poca humedad, cerca del rango; poca humedad y calor.
LECTURAS = {S: medicion(55, 1000, 22), R: medicion(35, 1000, 22), C: medicion(35, 1000, 35)}
CADA_5_S = timedelta(seconds=5)


class Juego:
    """Los casos de uso del juego conectados a los mismos dobles, como los conectara main.py."""

    def __init__(self, minutos_por_dia: float = 1440, en_vivo=None):
        self.sensores = RepositorioSensoresEnMemoria()
        self.plantas = RepositorioPlantasEnMemoria(self.sensores)
        self.cuentas = RepositorioUsuariosEnMemoria(self.plantas)
        for usuario in (ANA, BETO, CARO, DANI):
            self.cuentas.guardar(usuario)
        self.historial = HistorialEnMemoria()
        self.reloj = RelojFijo(AHORA)
        self.movimientos = MovimientosEnMemoria(self.plantas)
        self.jugadores = RegistroJugadoresEnMemoria(self.cuentas)
        # Los mismos rangos con nombres distintos: asi solo cambia el ritmo de crecimiento.
        especies = EspeciesEditablesEnMemoria(*(Especie(n, RANGOS) for n in ("potos", "sansevieria", "orquidea")))
        servicio = ServicioDiagnostico(especies, EvaluadorPlanta(ReglaHibrida(), GeneradorRecomendaciones()))
        self.en_vivo = en_vivo or NotificadorEnMemoria(self.historial)
        self.puntuar = PuntuarLectura(self.movimientos, self.reloj)
        self.diagnosticar = DiagnosticarPlantaDeUsuario(
            self.plantas, servicio, self.historial, AvisarATodos([self.puntuar, self.en_vivo])
        )
        self.cuidado = CuidadoDeMascota(RelojDeJuego(minutos_por_dia))
        self.puntaje = ConsultarPuntaje(self.movimientos, self.plantas)
        self.tabla = ConsultarTablaPosiciones(self.jugadores, self.movimientos)
        self.participacion = ConsultarParticipacion(self.jugadores)
        self.elegir = ElegirParticipacion(self.jugadores)
        self.mascotas = ConsultarMascotas(
            self.plantas, self.historial, self.movimientos, ritmos_del_plan(), self.cuidado, self.reloj
        )
        self._sensores_creados = 0

    def matera(self, usuario: Usuario, apodo: str, especie: str = "potos") -> Planta:
        self._sensores_creados += 1
        nueva = Planta(None, usuario.id, apodo, especie)
        return self.plantas.guardar_con_sensor(nueva, codigo(self._sensores_creados), "huella")

    def leer(self, planta: Planta, *estados: EstadoGlobal, cada: timedelta = timedelta(0)) -> None:
        """Una lectura por estado, separadas por `cada`. El reloj queda en la hora de la ultima."""
        for indice, estado in enumerate(estados):
            if indice:
                self.reloj.avanzar(cada)
            self.diagnosticar.ejecutar(
                planta.usuario_id, planta.id, LECTURAS[estado], origen="MT-0001-AA", momento=self.reloj.ahora()
            )

    def mascota(self, usuario: Usuario, planta: Planta):
        return next(m for m in self.mascotas.ejecutar(usuario) if m.planta.id == planta.id)


# --- Puntaje: cada lectura aceptada suma o resta ---


def test_cada_lectura_aceptada_suma_o_resta_segun_su_estado():
    juego = Juego()
    sala = juego.matera(ANA, "sala")

    juego.leer(sala, S, R, C)

    assert [m.puntos for m in juego.movimientos.movimientos] == [10, -5, -10]
    assert [m.estado for m in juego.movimientos.movimientos] == [S, R, C]
    assert juego.puntaje.ejecutar(ANA).total == -5


def test_el_puntaje_puede_quedar_negativo():
    juego = Juego()
    juego.leer(juego.matera(ANA, "sala"), C, C, R)

    assert juego.puntaje.ejecutar(ANA).total == -25


def test_cada_matera_suma_por_su_lado():
    juego = Juego()
    sala, cocina = juego.matera(ANA, "sala"), juego.matera(ANA, "cocina")
    patio = juego.matera(BETO, "patio")

    juego.leer(sala, S, S, cada=CADA_5_S)
    juego.reloj.avanzar(CADA_5_S)
    juego.leer(cocina, C)
    juego.leer(patio, S)
    puntaje = juego.puntaje.ejecutar(ANA)

    assert puntaje.total == 10
    assert [(m.planta.apodo, m.puntos) for m in puntaje.materas] == [("sala", 20), ("cocina", -10)]
    assert [(m.planta.apodo, m.estado, m.puntos) for m in puntaje.movimientos] == [
        ("cocina", C, -10),
        ("sala", S, 10),
        ("sala", S, 10),
    ]


def test_los_puntos_se_guardan_con_la_hora_del_servidor_y_no_con_la_del_dispositivo():
    juego = Juego()
    sala = juego.matera(ANA, "sala")

    hace_tres_dias = AHORA - timedelta(days=3)
    juego.diagnosticar.ejecutar(ANA.id, sala.id, LECTURAS[S], origen="MT-0001-AA", momento=hace_tres_dias)

    assert juego.historial.registros[0].momento == hace_tres_dias
    assert juego.movimientos.movimientos[0].momento == AHORA
    assert juego.puntaje.ejecutar(ANA).movimientos[0].momento == AHORA


def test_puntuar_lectura_usa_el_estado_del_diagnostico_y_el_dueno_de_la_planta():
    juego = Juego()
    sala = juego.matera(ANA, "sala")
    juego.leer(sala, R)
    registro = juego.historial.registros[0]
    _, _, _, diagnostico = juego.en_vivo.avisos[0]

    juego.reloj.avanzar(timedelta(minutes=1))
    juego.puntuar.publicar(ANA.id, sala, registro, diagnostico)

    ultimo = juego.movimientos.movimientos[-1]
    assert (ultimo.usuario_id, ultimo.planta_id, ultimo.estado, ultimo.puntos) == (ANA.id, sala.id, R, -5)
    assert ultimo.momento == AHORA + timedelta(minutes=1)


def test_una_lectura_que_no_se_guarda_no_suma():
    juego = Juego()
    cactus = juego.matera(ANA, "cactus", especie="cactus")  # especie que no esta en la tabla

    with pytest.raises(EspecieNoSoportada):
        juego.leer(cactus, S)

    assert juego.movimientos.movimientos == []


def test_los_puntos_de_una_matera_borrada_siguen_siendo_del_dueno():
    juego = Juego()
    sala, cocina = juego.matera(ANA, "sala"), juego.matera(ANA, "cocina")
    juego.leer(sala, S)
    juego.leer(cocina, S, S)

    juego.plantas.eliminar(cocina)
    juego.movimientos.soltar_planta(cocina.id)
    puntaje = juego.puntaje.ejecutar(ANA)

    assert puntaje.total == 30
    assert [(m.planta.apodo, m.puntos) for m in puntaje.materas] == [("sala", 10)]
    assert [m.planta.apodo if m.planta else None for m in puntaje.movimientos] == [None, None, "sala"]


# --- AvisarATodos ---


def test_si_el_aviso_en_vivo_falla_la_lectura_igual_suma(caplog):
    juego = Juego(en_vivo=NotificadorQueFalla())

    with caplog.at_level(logging.ERROR, logger="aplicacion.avisos"):
        juego.leer(juego.matera(ANA, "sala"), S)

    assert juego.puntaje.ejecutar(ANA).total == 10
    assert "NotificadorQueFalla" in caplog.text


def test_avisar_a_todos_sigue_con_los_demas_si_uno_falla(caplog):
    juego = Juego()
    sala = juego.matera(ANA, "sala")
    juego.leer(sala, S)
    _, planta, registro, diagnostico = juego.en_vivo.avisos[0]
    primero, segundo = NotificadorEnMemoria(), NotificadorEnMemoria()

    with caplog.at_level(logging.ERROR, logger="aplicacion.avisos"):
        AvisarATodos([NotificadorQueFalla(), primero, NotificadorQueFalla(), segundo]).publicar(
            ANA.id, planta, registro, diagnostico
        )

    assert len(primero.avisos) == len(segundo.avisos) == 1
    assert len([r for r in caplog.records if r.levelno == logging.ERROR]) == 2


def test_si_puntuar_falla_el_aviso_en_vivo_igual_llega():
    juego = Juego()
    sala = juego.matera(ANA, "sala")
    juego.leer(sala, S)
    _, _, registro, diagnostico = juego.en_vivo.avisos[0]
    en_vivo = NotificadorEnMemoria()
    # La planta se borro mientras llegaba la lectura: guardar el movimiento falla.
    juego.plantas.eliminar(sala)

    AvisarATodos([juego.puntuar, en_vivo]).publicar(ANA.id, sala, registro, diagnostico)

    assert len(en_vivo.avisos) == 1
    assert len(juego.movimientos.movimientos) == 1


def test_avisar_a_todos_respeta_el_orden_de_los_suscriptores():
    orden = []

    class Anotador(NotificadorEnMemoria):
        def __init__(self, nombre):
            super().__init__()
            self.nombre = nombre

        def publicar(self, usuario_id, planta, registro, diagnostico):
            orden.append(self.nombre)

    registro = RegistroMedicion(1, AHORA, S, (), "MT-0001-AA")
    AvisarATodos([Anotador("puntaje"), Anotador("en vivo")]).publicar(1, Planta(1, 1, "sala", "potos"), registro, None)

    assert orden == ["puntaje", "en vivo"]


# --- Participacion ---


def test_quien_nunca_respondio_no_ha_decidido():
    assert Juego().participacion.ejecutar(ANA) == Participacion.sin_decidir(ANA.id)


def test_participar_con_un_apodo():
    juego = Juego()

    elegida = juego.elegir.ejecutar(ANA, True, " pipe_verde ")

    assert (elegida.estado, elegida.apodo.valor) == (EstadoParticipacion.PARTICIPA, "pipe_verde")
    assert juego.participacion.ejecutar(ANA) == elegida


@pytest.mark.parametrize("apodo", [None, "", "pi", "pipe verde", "x" * 21, "árbol"])
def test_participar_con_un_apodo_invalido_no_guarda_nada(apodo):
    juego = Juego()

    with pytest.raises(ApodoInvalido):
        juego.elegir.ejecutar(ANA, True, apodo)

    assert juego.participacion.ejecutar(ANA).estado is EstadoParticipacion.SIN_DECIDIR


def test_el_apodo_no_se_repite_sin_importar_mayusculas():
    juego = Juego()
    juego.elegir.ejecutar(ANA, True, "Pipe_Verde")

    with pytest.raises(ApodoRepetido):
        juego.elegir.ejecutar(BETO, True, "PIPE_VERDE")

    assert juego.participacion.ejecutar(BETO).estado is EstadoParticipacion.SIN_DECIDIR


def test_el_caso_de_uso_revisa_el_apodo_aunque_la_base_no_tuviera_indice():
    class JugadoresSinIndice(RegistroJugadoresEnMemoria):
        """Guarda sin revisar el apodo, como una base a la que le faltara el indice unico."""

        def guardar(self, participacion):
            self.participaciones[participacion.usuario_id] = participacion

    jugadores = JugadoresSinIndice()
    elegir = ElegirParticipacion(jugadores)
    elegir.ejecutar(ANA, True, "pipe_verde")

    with pytest.raises(ApodoRepetido):
        elegir.ejecutar(BETO, True, "Pipe_Verde")

    assert BETO.id not in jugadores.participaciones


def test_cada_uno_puede_cambiar_las_mayusculas_de_su_propio_apodo():
    juego = Juego()
    juego.elegir.ejecutar(ANA, True, "pipe_verde")

    assert juego.elegir.ejecutar(ANA, True, "Pipe_Verde").apodo.valor == "Pipe_Verde"


def test_dejar_de_participar_libera_el_apodo():
    juego = Juego()
    juego.elegir.ejecutar(ANA, True, "pipe_verde")

    # Al no participar, el apodo que llegue se ignora, aunque no sea valido.
    assert juego.elegir.ejecutar(ANA, False, "no importa!") == Participacion.no_participa(ANA.id)
    assert juego.elegir.ejecutar(BETO, True, "PIPE_verde").apodo == ApodoJugador("pipe_verde")


# --- Tabla de posiciones ---


@pytest.mark.parametrize("participa", [None, False])
def test_quien_no_participa_no_ve_la_tabla(participa):
    juego = Juego()
    juego.elegir.ejecutar(BETO, True, "beto_b")
    if participa is not None:
        juego.elegir.ejecutar(ANA, participa)

    with pytest.raises(ParticipacionRequerida):
        juego.tabla.ejecutar(ANA)


def test_la_tabla_trae_solo_participantes_activos_de_mayor_a_menor():
    juego = Juego()
    juego.leer(juego.matera(ANA, "sala"), S)
    juego.leer(juego.matera(BETO, "patio"), C)
    juego.leer(juego.matera(CARO, "balcon"), S, S)
    juego.leer(juego.matera(DANI, "terraza"), S, S, S)
    juego.elegir.ejecutar(ANA, True, "ana_a")
    juego.elegir.ejecutar(BETO, True, "beto_b")
    juego.elegir.ejecutar(CARO, False)  # no participa: no aparece aunque tenga mas puntos
    juego.elegir.ejecutar(DANI, True, "dani_d")
    juego.cuentas.guardar(DANI.con_estado(False))  # cuenta desactivada: no aparece

    tabla = juego.tabla.ejecutar(ANA)

    assert [(p.posicion, p.apodo.valor, p.puntos, p.soy_yo) for p in tabla] == [
        (1, "ana_a", 10, True),
        (2, "beto_b", -10, False),
    ]


def test_mismos_puntos_misma_posicion():
    juego = Juego()
    juego.leer(juego.matera(ANA, "sala"), S)
    juego.leer(juego.matera(BETO, "patio"), S)
    for usuario, apodo in ((ANA, "zeta"), (BETO, "alfa"), (CARO, "caro_c")):
        juego.elegir.ejecutar(usuario, True, apodo)

    tabla = juego.tabla.ejecutar(CARO)

    assert [(p.posicion, p.apodo.valor, p.puntos, p.soy_yo) for p in tabla] == [
        (1, "alfa", 10, False),
        (1, "zeta", 10, False),
        (3, "caro_c", 0, True),  # participa sin lecturas: aparece con 0
    ]


def test_la_tabla_aplica_la_regla_del_dominio_aunque_el_registro_traiga_de_mas():
    class JugadoresQueNoFiltran(RegistroJugadoresEnMemoria):
        """Un adaptador con un error: devuelve a todos, participen o no."""

        def participantes_activos(self):
            return list(self.participaciones.values())

    jugadores = JugadoresQueNoFiltran()
    jugadores.guardar(Participacion.participa(ANA.id, ApodoJugador("ana_a")))
    jugadores.guardar(Participacion.no_participa(BETO.id))

    tabla = ConsultarTablaPosiciones(jugadores, MovimientosEnMemoria()).ejecutar(ANA)

    assert [p.apodo.valor for p in tabla] == ["ana_a"]


# --- La matera Tamagotchi ---


def test_cada_uno_ve_solo_sus_materas():
    juego = Juego()
    sala = juego.matera(ANA, "sala")
    juego.matera(BETO, "patio")

    assert [m.planta for m in juego.mascotas.ejecutar(ANA)] == [sala]


def test_las_materas_ajenas_no_salen_aunque_el_puerto_las_devuelva():
    class PlantasQueNoFiltran(RepositorioPlantasEnMemoria):
        """Un adaptador con un error: devuelve las plantas de todos."""

        def de_usuario(self, usuario_id):
            return list(self._plantas.values())

    juego = Juego()
    plantas = PlantasQueNoFiltran()
    sala = plantas.guardar_con_sensor(Planta(None, ANA.id, "sala", "potos"), codigo(1), "h")
    plantas.guardar_con_sensor(Planta(None, BETO.id, "patio", "potos"), codigo(2), "h")
    mascotas = ConsultarMascotas(
        plantas, juego.historial, juego.movimientos, ritmos_del_plan(), juego.cuidado, juego.reloj
    )
    puntaje = ConsultarPuntaje(juego.movimientos, plantas)

    assert [m.planta for m in mascotas.ejecutar(ANA)] == [sala]
    assert [m.planta for m in puntaje.ejecutar(ANA).materas] == [sala]


def test_una_matera_sin_lecturas_es_una_semilla_dormida():
    juego = Juego()
    mascota = juego.mascota(ANA, juego.matera(ANA, "sala"))

    assert (mascota.etapa, mascota.condicion, mascota.cara, mascota.dormida) == (
        EtapaCrecimiento.SEMILLA,
        Condicion.SANA,
        None,
        True,
    )


@pytest.mark.parametrize(
    "especie, etapa",
    [
        ("potos", EtapaCrecimiento.BROTE),  # brote al dia
        ("sansevieria", EtapaCrecimiento.SEMILLA),  # brote a los 2 dias
        ("orquidea", EtapaCrecimiento.BROTE),  # sin ritmo propio: el de una especie nueva, brote al dia
    ],
)
def test_con_el_reloj_acelerado_la_matera_crece_al_ritmo_de_su_especie(especie, etapa):
    # 1 dia de juego = 2 minutos: una hora de juego dura 5 s y llega una lectura en cada una.
    juego = Juego(minutos_por_dia=2)
    sala = juego.matera(ANA, "sala", especie)

    juego.leer(sala, *[S] * 23, cada=CADA_5_S)
    assert juego.mascota(ANA, sala).etapa is EtapaCrecimiento.SEMILLA
    juego.reloj.avanzar(CADA_5_S)
    juego.leer(sala, S)
    mascota = juego.mascota(ANA, sala)

    assert (mascota.horas_cuidada, mascota.etapa) == (24, etapa)


def test_con_el_reloj_real_las_lecturas_de_una_misma_hora_cuentan_como_una():
    juego = Juego()
    sala = juego.matera(ANA, "sala")

    juego.leer(sala, *[S] * 24, cada=CADA_5_S)

    assert juego.mascota(ANA, sala).horas_cuidada == 1


def test_el_tiempo_marchita_no_hace_crecer():
    juego = Juego(minutos_por_dia=2)
    sala = juego.matera(ANA, "sala")

    juego.leer(sala, *[C] * 30, cada=CADA_5_S)
    mascota = juego.mascota(ANA, sala)

    assert (mascota.horas_cuidada, mascota.etapa, mascota.condicion) == (0, EtapaCrecimiento.SEMILLA, Condicion.MARCHITA)
    assert mascota.puntos == -300


def test_siempre_en_riesgo_queda_decaida_y_crece():
    juego = Juego(minutos_por_dia=2)
    sala = juego.matera(ANA, "sala")

    juego.leer(sala, *[R] * 30, cada=CADA_5_S)
    mascota = juego.mascota(ANA, sala)

    assert (mascota.horas_cuidada, mascota.etapa, mascota.condicion) == (30, EtapaCrecimiento.BROTE, Condicion.DECAIDA)
    assert mascota.puntos == -150


def test_la_mascota_trae_su_condicion_su_cara_y_lo_que_necesita():
    juego = Juego()
    sala = juego.matera(ANA, "sala")

    juego.leer(sala, S, S, R, cada=timedelta(minutes=10))
    mascota = juego.mascota(ANA, sala)

    assert mascota.condicion is Condicion.SANA  # promedio 5
    assert (mascota.cara, mascota.necesidad, mascota.dormida) == (R, Necesidad.SED, False)
    assert (mascota.puntos, mascota.ultima_lectura) == (15, juego.reloj.ahora())


def test_se_duerme_a_los_30_minutos_reales_aunque_el_reloj_del_juego_vaya_rapido():
    juego = Juego(minutos_por_dia=2)
    sala = juego.matera(ANA, "sala")
    juego.leer(sala, S)

    juego.reloj.avanzar(timedelta(minutes=30))
    assert juego.mascota(ANA, sala).dormida is False
    juego.reloj.avanzar(timedelta(seconds=1))
    assert juego.mascota(ANA, sala).dormida is True


def test_avisa_al_pasar_a_critico_y_al_marchitarse():
    juego = Juego()
    sala = juego.matera(ANA, "sala")
    avisos = []
    for estado in (S, S, C, C, C, C, C, C, C):
        juego.leer(sala, estado)
        avisos.append(juego.mascota(ANA, sala).aviso)
        juego.reloj.avanzar(timedelta(minutes=1))

    # Al octavo, el promedio de la ventana llega a -5 y sigue decaida; al noveno baja de -5: se marchita.
    assert avisos == [None, None, Aviso.PASO_A_CRITICO, None, None, None, None, None, Aviso.SE_MARCHITO]


CADA_15_S = timedelta(seconds=15)


def _avisos_al_leer(juego: Juego, planta: Planta, *estados: EstadoGlobal, cada: timedelta = CADA_15_S) -> list:
    """El aviso y la condicion que ve la app justo despues de cada lectura."""
    vistos = []
    for estado in estados:
        juego.reloj.avanzar(cada)
        juego.leer(planta, estado)
        mascota = juego.mascota(ANA, planta)
        vistos.append((mascota.condicion, mascota.aviso))
    return vistos


def test_con_la_ventana_llena_se_marchita_y_avisa_una_sola_vez():
    """El reloj de la demo (6 min por dia: hora de 15 s, ventana de 90 s) y la placa cada 15 s.

    En uso normal la ventana esta llena: con cada lectura que entra sale la mas
    vieja. El aviso compara la ventana de la ultima con la de la anterior.
    """
    juego = Juego(minutos_por_dia=6)
    sala = juego.matera(ANA, "sala")

    vistos = _avisos_al_leer(juego, sala, *[S] * 6, *[C] * 6)

    sana, decaida, marchita = Condicion.SANA, Condicion.DECAIDA, Condicion.MARCHITA
    assert vistos == [
        *[(sana, None)] * 6,
        (sana, Aviso.PASO_A_CRITICO),  # 5 S y 1 C
        (sana, None),  # 4 S y 2 C: 3,3
        (decaida, None),  # 3 S y 3 C: 0
        (decaida, None),  # 2 S y 4 C: -3,3
        (marchita, Aviso.SE_MARCHITO),  # 1 S y 5 C: -6,7. Sin la ultima seria 1 S y 4 C (-6): no avisaria
        (marchita, None),
    ]


def test_marchita_desde_la_primera_lectura_avisa_una_sola_vez():
    juego = Juego(minutos_por_dia=6)
    sala = juego.matera(ANA, "sala")

    vistos = _avisos_al_leer(juego, sala, C, R, R, R, R, R, C)

    assert {condicion for condicion, _ in vistos} == {Condicion.MARCHITA}
    # Al final vuelve a CRITICO desde EN_RIESGO: avisa eso, pero no que se marchito, porque ya lo estaba.
    assert [aviso for _, aviso in vistos] == [Aviso.SE_MARCHITO, *[None] * 5, Aviso.PASO_A_CRITICO]


def test_sin_lecturas_nuevas_la_matera_no_cambia_hasta_que_se_duerme():
    """La placa se apaga con el reloj de la demo: la ventana de 90 s pasa, pero no llega otra lectura."""
    juego = Juego(minutos_por_dia=6)
    sala = juego.matera(ANA, "sala")
    for segundos, estado in ((0, S), (30, C), (10, S), (10, C), (10, C), (10, C)):
        juego.reloj.avanzar(timedelta(seconds=segundos))
        juego.leer(sala, estado)
    recien = juego.mascota(ANA, sala)

    for despues in (timedelta(seconds=5), timedelta(seconds=25), timedelta(minutes=2), timedelta(minutes=30)):
        juego.reloj.avanzar(despues - (juego.reloj.ahora() - recien.ultima_lectura))
        igual = juego.mascota(ANA, sala)
        assert (igual.condicion, igual.cara, igual.necesidad, igual.aviso, igual.dormida) == (
            recien.condicion, C, Necesidad.SED, recien.aviso, False
        ), despues

    juego.reloj.avanzar(timedelta(seconds=1))  # 30 minutos y 1 segundo: se duerme
    dormida = juego.mascota(ANA, sala)
    assert (dormida.dormida, dormida.cara, dormida.necesidad, dormida.aviso) == (True, C, None, None)
    assert dormida.condicion is recien.condicion


def test_una_lectura_con_la_hora_del_dispositivo_atrasada_igual_cambia_la_cara_y_avisa():
    """La placa reinicio y manda su hora 31 minutos atrasada: la API la acepta y el historial la deja atras."""
    juego = Juego()
    sala = juego.matera(ANA, "sala")
    juego.leer(sala, S)
    juego.reloj.avanzar(CADA_15_S)

    atrasada = juego.reloj.ahora() - timedelta(minutes=31)
    juego.diagnosticar.ejecutar(ANA.id, sala.id, LECTURAS[C], origen="MT-0001-AA", momento=atrasada)
    mascota = juego.mascota(ANA, sala)

    assert juego.historial.ultimo_de(sala.id).estado is S  # por la hora del dispositivo, la ultima sigue siendo la S
    assert (mascota.cara, mascota.aviso, mascota.dormida, mascota.puntos) == (C, Aviso.PASO_A_CRITICO, False, 0)
    assert mascota.ultima_lectura == juego.reloj.ahora()


def test_la_primera_lectura_con_la_hora_atrasada_no_deja_dormida_a_la_matera():
    juego = Juego()
    sala = juego.matera(ANA, "sala")

    atrasada = juego.reloj.ahora() - timedelta(minutes=31)
    juego.diagnosticar.ejecutar(ANA.id, sala.id, LECTURAS[C], origen="MT-0001-AA", momento=atrasada)
    mascota = juego.mascota(ANA, sala)

    assert (mascota.cara, mascota.dormida, mascota.necesidad, mascota.aviso) == (C, False, Necesidad.SED, Aviso.SE_MARCHITO)


# --- Puertos de entrada del juego ---


@pytest.mark.parametrize(
    "nombre",
    ["ConsultarPuntaje", "ConsultarTablaPosiciones", "ConsultarParticipacion", "ElegirParticipacion", "ConsultarMascotas"],
)
def test_cada_puerto_de_entrada_del_juego_lo_implementa_el_caso_de_uso_de_su_mismo_nombre(nombre):
    puerto = getattr(puertos_juego, nombre)
    caso_de_uso = getattr(aplicacion.juego, nombre)

    assert caso_de_uso is not puerto
    assert issubclass(caso_de_uso, puerto)


def test_los_dobles_del_juego_solo_importan_el_dominio():
    """Como los otros dobles: si se borra la carpeta infraestructura, estas pruebas siguen pasando."""
    assert _violaciones([BACKEND / "tests" / "dobles_juego.py"], PROHIBIDOS_EN_DOMINIO) == {}
