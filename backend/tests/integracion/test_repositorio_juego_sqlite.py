"""Los puertos del juego en SQLite (corte 3).

Primero, que el adaptador da exactamente lo mismo que el doble en memoria con
que se probaron los casos de uso: los mismos movimientos pasan por los dos, con
varios relojes de juego. Despues, lo que el doble no imita: las restricciones
de la base, las cascadas y los filtros por dueno.
"""
import random
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest

from dominio.errores_juego import ApodoRepetido
from dominio.errores_usuarios import PlantaNoEncontrada
from dominio.estados import EstadoGlobal
from dominio.juego import ApodoJugador, MovimientoPuntaje, Participacion, ReglaDeCuidado
from dominio.mascota import CuidadoDeMascota, RelojDeJuego, ResumenCuidado, RitmoCrecimiento
from dominio.plantas import Planta
from dominio.sensores import CodigoSensor
from dominio.usuarios import Correo, Usuario
from infraestructura.sqlite import (
    BaseDatos,
    MovimientosPuntajeSqlite,
    RegistroJugadoresSqlite,
    RepositorioPlantasSqlite,
    RepositorioUsuariosSqlite,
    RitmosCrecimientoSqlite,
)
from tests.dobles_juego import MovimientosEnMemoria, RegistroJugadoresEnMemoria, ritmos_del_plan

AHORA = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
REGLA = ReglaDeCuidado()
# Minutos por dia de juego: el real, dos acelerados y uno cuya hora no es un numero entero de milisegundos (2,5 ms).
RELOJES = (1440, 6, 2, 0.001)


class Base:
    def __init__(self, ruta):
        self.bd = BaseDatos(ruta).preparar()
        self.usuarios = RepositorioUsuariosSqlite(self.bd)
        self.plantas = RepositorioPlantasSqlite(self.bd)
        self.movimientos = MovimientosPuntajeSqlite(self.bd)
        self.jugadores = RegistroJugadoresSqlite(self.bd)
        self.ritmos = RitmosCrecimientoSqlite(self.bd)
        self._codigos = 0

    def cuenta(self, correo: str, nombre: str = "Ana") -> Usuario:
        return self.usuarios.guardar(Usuario(None, Correo(correo), nombre, "pbkdf2_sha256$1$00$00"))

    def planta(self, usuario: Usuario, apodo: str, especie: str = "potos") -> Planta:
        self._codigos += 1
        codigo = CodigoSensor(f"MT-{self._codigos:04d}-ZZ")
        return self.plantas.guardar_con_sensor(Planta(None, usuario.id, apodo, especie), codigo, "huella")


@pytest.fixture
def base(tmp_path):
    return Base(tmp_path / "matera.sqlite")


def _movimiento(planta: Planta, momento: datetime, estado: EstadoGlobal) -> MovimientoPuntaje:
    return REGLA.movimiento(planta.usuario_id, planta.id, momento, estado)


# --- El adaptador y el doble dan lo mismo ---


def _momentos_de_prueba() -> list[datetime]:
    """Momentos que ponen a prueba la agrupacion: empates, bordes de hora, otra zona horaria y antes de 1970."""
    azar = random.Random(20261111)
    momentos = []
    for _ in range(90):
        # Unos muy juntos (comparten hora aun con la de 2,5 ms) y otros a dias de distancia, con microsegundos.
        escala = azar.choice((0.005, 2, 60, 3600, 4 * 86400))
        momentos.append(AHORA - timedelta(microseconds=azar.randrange(int(escala * 1_000_000))))
    for minutos_por_dia in RELOJES:
        hora = RelojDeJuego(minutos_por_dia).hora
        borde = RelojDeJuego(minutos_por_dia).numero_de_hora(AHORA) * hora + datetime(1970, 1, 1, tzinfo=timezone.utc)
        # Justo en el borde de una hora de juego, un microsegundo antes y uno despues.
        momentos += [borde, borde - timedelta(microseconds=1), borde + timedelta(microseconds=1)]
    momentos += [momentos[3], momentos[3], momentos[10]]  # el mismo momento repetido: desempata el orden de guardado
    momentos.append(datetime(2026, 11, 11, 9, 59, 59, 999_999, tzinfo=timezone(timedelta(hours=-5))))
    momentos.append(datetime(1969, 12, 31, 23, 59, 59, 500_000, tzinfo=timezone.utc))
    return momentos


def _comparar(doble, sqlite, plantas, usuarios, momentos):
    for usuario_id in [*usuarios, 999]:
        assert sqlite.total_de(usuario_id) == doble.total_de(usuario_id)
        assert sqlite.totales_por_planta(usuario_id) == doble.totales_por_planta(usuario_id)
        for limite in (1, 5, 1000):
            assert sqlite.recientes_de(usuario_id, limite) == doble.recientes_de(usuario_id, limite)
    assert sqlite.totales_de_usuarios([*usuarios, 999]) == doble.totales_de_usuarios([*usuarios, 999])
    assert sqlite.totales_de_usuarios([]) == doble.totales_de_usuarios([]) == {}
    for minutos_por_dia in RELOJES:
        reloj = RelojDeJuego(minutos_por_dia)
        desdes = [
            CuidadoDeMascota(reloj).inicio_ventana(AHORA),
            momentos[0],  # justo el momento de un movimiento: la ventana es estricta (>)
            AHORA - timedelta(days=30),
            AHORA + timedelta(days=1),
        ]
        for planta in plantas:
            for desde in desdes:
                esperado = doble.resumen_de(planta, reloj, desde)
                obtenido = sqlite.resumen_de(planta, reloj, desde)
                assert obtenido == esperado, (minutos_por_dia, planta, desde)


def test_el_adaptador_da_lo_mismo_que_el_doble_con_varios_relojes_de_juego(base):
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    base.cuenta("carla@correo.co", "Carla")  # sin movimientos
    sala, cocina, patio = base.planta(ana, "Sala"), base.planta(ana, "Cocina"), base.planta(beto, "Patio")
    doble = MovimientosEnMemoria()
    azar = random.Random(7)
    momentos = _momentos_de_prueba()
    for momento in momentos:
        movimiento = _movimiento(azar.choice((sala, sala, cocina, patio)), momento, azar.choice(list(EstadoGlobal)))
        doble.agregar(movimiento)
        base.movimientos.agregar(movimiento)
    # Una planta pedida con otro dueno no trae nada en ninguno de los dos.
    ajena = Planta(sala.id, beto.id, "Sala", "potos")
    plantas = [sala, cocina, patio, ajena]

    _comparar(doble, base.movimientos, plantas, [ana.id, beto.id], momentos)

    # Al borrar la cocina sus movimientos quedan sin planta, y una planta nueva con su id no los hereda.
    base.plantas.eliminar(cocina)
    doble.soltar_planta(cocina.id)
    nueva = base.planta(beto, "Terraza")
    _comparar(doble, base.movimientos, [*plantas, nueva], [ana.id, beto.id], momentos)


def test_el_resumen_agrupa_cada_hora_de_juego_como_numero_de_hora(base):
    """El caso a mano: con 2 minutos por dia, cada hora de juego dura 5 segundos."""
    ana = base.cuenta("ana@correo.co")
    sala = base.planta(ana, "Sala")
    reloj = RelojDeJuego(2)
    inicio = datetime(2026, 11, 11, 15, 0, 0, tzinfo=timezone.utc)  # un multiplo exacto de 5 s desde 1970
    for segundos, estado in ((0, EstadoGlobal.SALUDABLE), (4.999999, EstadoGlobal.CRITICO), (5, EstadoGlobal.EN_RIESGO)):
        base.movimientos.agregar(_movimiento(sala, inicio + timedelta(seconds=segundos), estado))

    resumen = base.movimientos.resumen_de(sala, reloj, inicio)

    primera = reloj.numero_de_hora(inicio)
    assert {hora: (t.cantidad, t.suma) for hora, t in resumen.horas.items()} == {primera: (2, 0), primera + 1: (1, -5)}
    assert (resumen.ventana.cantidad, resumen.ventana.suma) == (2, -15)  # el del momento exacto no entra
    assert (resumen.ultimo.estado, resumen.anterior.estado) == (EstadoGlobal.EN_RIESGO, EstadoGlobal.CRITICO)
    assert resumen.ultimo.momento == inicio + timedelta(seconds=5)


# --- Lo que asegura la base ---


def test_un_movimiento_solo_se_guarda_en_una_planta_que_sigue_siendo_de_su_dueno(base):
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    sala = base.planta(ana, "Sala")

    with pytest.raises(PlantaNoEncontrada):
        base.movimientos.agregar(REGLA.movimiento(beto.id, sala.id, AHORA, EstadoGlobal.SALUDABLE))
    base.plantas.eliminar(sala)
    with pytest.raises(PlantaNoEncontrada):
        base.movimientos.agregar(_movimiento(sala, AHORA, EstadoGlobal.SALUDABLE))

    assert base.movimientos.total_de(ana.id) == base.movimientos.total_de(beto.id) == 0


def test_cada_consulta_trae_solo_lo_del_dueno(base):
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    sala, patio = base.planta(ana, "Sala"), base.planta(beto, "Patio")
    base.movimientos.agregar(_movimiento(sala, AHORA, EstadoGlobal.SALUDABLE))
    base.movimientos.agregar(_movimiento(patio, AHORA + timedelta(seconds=1), EstadoGlobal.CRITICO))

    assert base.movimientos.total_de(ana.id) == 10
    assert base.movimientos.totales_por_planta(ana.id) == {sala.id: 10}
    assert [m.planta_id for m in base.movimientos.recientes_de(ana.id, 20)] == [sala.id]
    assert base.movimientos.totales_de_usuarios([ana.id, beto.id]) == {ana.id: 10, beto.id: -10}
    assert base.movimientos.totales_de_usuarios([ana.id]) == {ana.id: 10}
    # La planta de Beto pedida como si fuera de Ana: el resumen sale vacio.
    vacio = base.movimientos.resumen_de(Planta(patio.id, ana.id, "Patio", "potos"), RelojDeJuego(), AHORA - timedelta(days=1))
    assert vacio == ResumenCuidado.sin_lecturas()


def test_un_movimiento_con_otro_dueno_que_el_de_su_planta_no_cuenta_en_esa_planta(base):
    """Solo puede pasar editando la base a mano: agregar() no lo deja. Igual, cada consulta exige el dueno."""
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    patio = base.planta(beto, "Patio")
    with base.bd.conexion() as conexion:
        conexion.execute(
            "INSERT INTO movimiento_puntaje (usuario_id, planta_id, momento, momento_us, estado, puntos)"
            " VALUES (?, ?, '2026-11-11T15:00:00.000000+00:00', 1794409200000000, 'SALUDABLE', 10)",
            (ana.id, patio.id),
        )

    assert base.movimientos.total_de(ana.id) == 10  # es de Ana
    assert base.movimientos.totales_por_planta(ana.id) == {}  # pero la planta no es suya
    assert base.movimientos.totales_por_planta(beto.id) == {}
    assert base.movimientos.resumen_de(patio, RelojDeJuego(), AHORA - timedelta(days=1)) == ResumenCuidado.sin_lecturas()


def test_al_borrar_una_matera_sus_puntos_siguen_con_el_dueno_y_no_pasan_a_la_planta_que_toma_su_id(base):
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    sala = base.planta(ana, "Sala")
    base.movimientos.agregar(_movimiento(sala, AHORA, EstadoGlobal.SALUDABLE))
    base.movimientos.agregar(_movimiento(sala, AHORA + timedelta(seconds=1), EstadoGlobal.SALUDABLE))

    base.plantas.eliminar(sala)
    otra = base.planta(beto, "Patio")
    propia_nueva = base.planta(ana, "Sala nueva")

    assert otra.id == sala.id  # SQLite reutilizo el id de la planta borrada
    assert base.movimientos.total_de(ana.id) == 20
    assert base.movimientos.totales_por_planta(ana.id) == {}
    assert [m.planta_id for m in base.movimientos.recientes_de(ana.id, 20)] == [None, None]
    assert base.movimientos.total_de(beto.id) == 0
    assert base.movimientos.totales_por_planta(beto.id) == {}
    for planta in (otra, propia_nueva):
        assert base.movimientos.resumen_de(planta, RelojDeJuego(), AHORA - timedelta(days=1)) == ResumenCuidado.sin_lecturas()


def test_al_borrar_una_cuenta_se_borran_sus_movimientos_y_su_participacion(base):
    ana = base.cuenta("ana@correo.co")
    sala = base.planta(ana, "Sala")
    base.movimientos.agregar(_movimiento(sala, AHORA, EstadoGlobal.SALUDABLE))
    base.jugadores.guardar(Participacion.participa(ana.id, ApodoJugador("pipe_verde")))

    base.usuarios.eliminar(ana.id)

    with base.bd.conexion() as conexion:
        assert conexion.execute("SELECT COUNT(*) FROM movimiento_puntaje").fetchone()[0] == 0
        assert conexion.execute("SELECT COUNT(*) FROM jugador").fetchone()[0] == 0


def test_la_participacion_se_guarda_y_se_reemplaza(base):
    ana = base.cuenta("ana@correo.co")
    assert base.jugadores.participacion_de(ana.id) is None

    base.jugadores.guardar(Participacion.participa(ana.id, ApodoJugador("Pipe_Verde")))
    guardada = base.jugadores.participacion_de(ana.id)
    assert guardada == Participacion.participa(ana.id, ApodoJugador("Pipe_Verde"))
    assert guardada.apodo.valor == "Pipe_Verde"  # se guarda como lo escribio

    base.jugadores.guardar(Participacion.no_participa(ana.id))
    assert base.jugadores.participacion_de(ana.id) == Participacion.no_participa(ana.id)
    base.jugadores.guardar(Participacion.sin_decidir(ana.id))
    assert base.jugadores.participacion_de(ana.id) == Participacion.sin_decidir(ana.id)


def test_la_base_no_deja_repetir_un_apodo_sin_importar_mayusculas(base):
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    base.jugadores.guardar(Participacion.participa(ana.id, ApodoJugador("pipe_verde")))

    # Directo al puerto, sin pasar por apodo_en_uso: como si dos lo pidieran a la vez.
    with pytest.raises(ApodoRepetido):
        base.jugadores.guardar(Participacion.participa(beto.id, ApodoJugador("PIPE_VERDE")))

    assert base.jugadores.participacion_de(beto.id) is None
    assert base.jugadores.apodo_en_uso(ApodoJugador("Pipe_Verde"), excepto_usuario_id=beto.id)
    # El propio no cuenta: Ana puede cambiarle las mayusculas.
    assert not base.jugadores.apodo_en_uso(ApodoJugador("Pipe_Verde"), excepto_usuario_id=ana.id)
    base.jugadores.guardar(Participacion.participa(ana.id, ApodoJugador("Pipe_Verde")))
    # Al dejar de participar, el apodo queda libre.
    base.jugadores.guardar(Participacion.no_participa(ana.id))
    assert not base.jugadores.apodo_en_uso(ApodoJugador("pipe_verde"), excepto_usuario_id=beto.id)
    base.jugadores.guardar(Participacion.participa(beto.id, ApodoJugador("PIPE_VERDE")))


def test_la_tabla_solo_trae_a_quien_participa_con_la_cuenta_activa(base):
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    carla, dario = base.cuenta("carla@correo.co", "Carla"), base.cuenta("dario@correo.co", "Dario")
    base.jugadores.guardar(Participacion.participa(ana.id, ApodoJugador("ana_verde")))
    base.jugadores.guardar(Participacion.participa(beto.id, ApodoJugador("beto_zen")))
    base.jugadores.guardar(Participacion.no_participa(carla.id))
    base.usuarios.guardar(Usuario(beto.id, beto.correo, beto.nombre, beto.hash_contrasena, activo=False))

    assert base.jugadores.participantes_activos() == [Participacion.participa(ana.id, ApodoJugador("ana_verde"))]
    assert base.jugadores.participacion_de(dario.id) is None


def test_el_doble_de_jugadores_y_la_base_coinciden(base):
    """Los mismos pasos en los dos: participar, repetir, cambiar mayusculas y dejar de participar."""
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    doble = RegistroJugadoresEnMemoria(base.usuarios)
    pasos = [
        Participacion.participa(ana.id, ApodoJugador("pipe")),
        Participacion.participa(beto.id, ApodoJugador("PIPE")),
        Participacion.participa(ana.id, ApodoJugador("Pipe")),
        Participacion.no_participa(ana.id),
        Participacion.participa(beto.id, ApodoJugador("PIPE")),
    ]
    for paso in pasos:
        resultados = []
        for registro in (doble, base.jugadores):
            try:
                registro.guardar(paso)
                resultados.append("ok")
            except ApodoRepetido:
                resultados.append("repetido")
        assert resultados[0] == resultados[1], paso
        assert base.jugadores.participantes_activos() == sorted(doble.participantes_activos(), key=lambda p: p.usuario_id)
        for usuario in (ana, beto):
            assert base.jugadores.participacion_de(usuario.id) == doble.participacion_de(usuario.id)


def test_los_ritmos_de_las_cinco_especies_son_los_del_plan(base):
    del_plan = ritmos_del_plan()
    for especie in ("potos", "helecho", "lavanda", "sansevieria", "suculenta"):
        assert base.ritmos.de_especie(especie) == del_plan.de_especie(especie)
    # Una especie sin ritmo propio, como una que agrego el admin: el caso de uso usa 1/3/7.
    assert base.ritmos.de_especie("orquidea") is None
    assert RitmoCrecimiento() == RitmoCrecimiento(1, 3, 7)


def test_la_base_rechaza_un_ritmo_que_no_crece(base):
    with pytest.raises(sqlite3.IntegrityError):
        with base.bd.conexion() as conexion:
            conexion.execute("UPDATE ritmo_crecimiento SET dias_planta = 1 WHERE especie = 'potos'")
