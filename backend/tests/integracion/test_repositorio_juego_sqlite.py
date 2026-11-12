"""Los puertos del juego en SQLite (corte 3).

Primero, que el adaptador da exactamente lo mismo que el doble en memoria con
que se probaron los casos de uso: los mismos movimientos pasan por los dos, con
varios relojes de juego. Despues, lo que el doble no imita: las restricciones
de la base, las cascadas, los filtros por dueno y que las consultas no
recorran todo el historial.
"""
import random
import sqlite3
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import pytest

from dominio.errores_juego import ApodoRepetido
from dominio.errores_usuarios import PlantaNoEncontrada
from dominio.estados import EstadoGlobal
from dominio.juego import ApodoJugador, MovimientoPuntaje, Participacion, ReglaDeCuidado
from dominio.mascota import CuidadoDeMascota, RelojDeJuego, ResumenCuidado, RitmoCrecimiento, Tramo
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
SEIS_HORAS = timedelta(hours=6)


class BaseDatosDePrueba(BaseDatos):
    """La de produccion, con dos cambios para estas pruebas.

    No espera a que cada escritura llegue al disco (aqui se guardan miles de
    movimientos) y puede contar los pasos de la maquina virtual de SQLite: con
    eso se mide cuanto recorre una consulta, sin depender de la velocidad del PC.
    """

    def __init__(self, ruta):
        super().__init__(ruta)
        self._pasos: int | None = None

    @contextmanager
    def conexion(self) -> Iterator[sqlite3.Connection]:
        with super().conexion() as conexion:
            conexion.execute("PRAGMA synchronous = OFF")
            conexion.execute("PRAGMA journal_mode = MEMORY")
            if self._pasos is not None:
                conexion.set_progress_handler(self._un_paso, 1)
            yield conexion

    def _un_paso(self) -> int:
        self._pasos += 1
        return 0  # 0: que siga

    def pasos_de(self, consulta: Callable[[], object]) -> int:
        self._pasos = 0
        try:
            consulta()
            return self._pasos
        finally:
            self._pasos = None


class Base:
    def __init__(self, ruta, reloj: RelojDeJuego = RelojDeJuego()):
        self.bd = BaseDatosDePrueba(ruta).preparar()
        self.usuarios = RepositorioUsuariosSqlite(self.bd)
        self.plantas = RepositorioPlantasSqlite(self.bd)
        self.movimientos = MovimientosPuntajeSqlite(self.bd, reloj)
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
    ventanas = [
        CuidadoDeMascota(doble.reloj).ventana,
        timedelta(microseconds=1),  # solo los del mismo momento que la ultima: los empates
        timedelta(seconds=2),
        timedelta(days=30),
    ]
    for planta in plantas:
        for ventana in ventanas:
            assert sqlite.resumen_de(planta, ventana) == doble.resumen_de(planta, ventana), (doble.reloj, planta, ventana)


@pytest.mark.parametrize("minutos_por_dia", RELOJES)
def test_el_adaptador_da_lo_mismo_que_el_doble_con_varios_relojes_de_juego(tmp_path, minutos_por_dia):
    reloj = RelojDeJuego(minutos_por_dia)
    base = Base(tmp_path / "matera.sqlite", reloj)
    ana, beto = base.cuenta("ana@correo.co"), base.cuenta("beto@correo.co", "Beto")
    base.cuenta("carla@correo.co", "Carla")  # sin movimientos
    sala, cocina, patio = base.planta(ana, "Sala"), base.planta(ana, "Cocina"), base.planta(beto, "Patio")
    doble = MovimientosEnMemoria(reloj=reloj)
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


def _horas_guardadas(base: Base, planta: Planta) -> list[tuple[int, int, int]]:
    with base.bd.conexion() as conexion:
        return [
            tuple(fila)
            for fila in conexion.execute(
                "SELECT hora_juego, cantidad, suma FROM cuidado_por_hora WHERE planta_id = ? ORDER BY hora_juego",
                (planta.id,),
            )
        ]


def test_el_resumen_agrupa_cada_hora_de_juego_como_numero_de_hora(tmp_path):
    """El caso a mano: con 2 minutos por dia, cada hora de juego dura 5 segundos."""
    reloj = RelojDeJuego(2)
    base = Base(tmp_path / "matera.sqlite", reloj)
    ana = base.cuenta("ana@correo.co")
    sala = base.planta(ana, "Sala")
    inicio = datetime(2026, 11, 11, 15, 0, 0, tzinfo=timezone.utc)  # un multiplo exacto de 5 s desde 1970
    for segundos, estado in ((0, EstadoGlobal.SALUDABLE), (4.999999, EstadoGlobal.CRITICO), (5, EstadoGlobal.EN_RIESGO)):
        base.movimientos.agregar(_movimiento(sala, inicio + timedelta(seconds=segundos), estado))

    resumen = base.movimientos.resumen_de(sala, timedelta(seconds=5))

    primera = reloj.numero_de_hora(inicio)
    assert _horas_guardadas(base, sala) == [(primera, 2, 0), (primera + 1, 1, -5)]
    assert resumen.horas_por_tramo == {Tramo(2, 0): 1, Tramo(1, -5): 1}
    assert (resumen.ultimo.estado, resumen.anterior.estado) == (EstadoGlobal.EN_RIESGO, EstadoGlobal.CRITICO)
    assert resumen.ultimo.momento == inicio + timedelta(seconds=5)
    # La ventana de 5 s que termina en la ultima no incluye la del segundo 0: el inicio no entra.
    assert (resumen.al_ultimo.cantidad, resumen.al_ultimo.suma) == (2, -15)
    # La que termina en la anterior (segundo 4,999999) si la incluye, y no incluye la ultima.
    assert (resumen.al_anterior.cantidad, resumen.al_anterior.suma) == (2, 0)


def test_las_ventanas_se_anclan_en_las_lecturas_y_la_de_la_anterior_no_cuenta_la_ultima(base):
    """Con empates: dos movimientos con el mismo momento caen en las dos ventanas, salvo la ultima."""
    ana = base.cuenta("ana@correo.co")
    sala = base.planta(ana, "Sala")
    ventana = timedelta(seconds=90)
    doble = MovimientosEnMemoria()
    for segundos, estado in ((0, EstadoGlobal.SALUDABLE), (15, EstadoGlobal.SALUDABLE), (100, EstadoGlobal.CRITICO),
                             (100, EstadoGlobal.EN_RIESGO)):
        movimiento = _movimiento(sala, AHORA + timedelta(seconds=segundos), estado)
        base.movimientos.agregar(movimiento)
        doble.agregar(movimiento)

    resumen = base.movimientos.resumen_de(sala, ventana)

    # La ultima es la EN_RIESGO (guardada despues); su ventana (10 s, 100 s] tiene la S de 15 s, la C y ella.
    assert (resumen.ultimo.estado, resumen.anterior.estado) == (EstadoGlobal.EN_RIESGO, EstadoGlobal.CRITICO)
    assert (resumen.al_ultimo.cantidad, resumen.al_ultimo.suma) == (3, -5)
    # La de la anterior es la misma ventana sin la ultima.
    assert (resumen.al_anterior.cantidad, resumen.al_anterior.suma) == (2, 0)
    assert doble.resumen_de(sala, ventana) == resumen


def test_la_hora_de_juego_se_fija_al_llegar_y_cambiar_el_reloj_no_reagrupa_el_pasado(base):
    """Tres lecturas en el mismo minuto, con el reloj real: una hora de juego.

    Al volver a arrancar con el reloj de la demo (2 minutos por dia: horas de 5 s),
    esas tres siguen en su hora; solo las que lleguen despues usan el reloj nuevo.
    """
    ana = base.cuenta("ana@correo.co")
    sala = base.planta(ana, "Sala")
    for segundos in (0, 15, 30):
        base.movimientos.agregar(_movimiento(sala, AHORA + timedelta(seconds=segundos), EstadoGlobal.SALUDABLE))
    con_el_reloj_de_la_demo = MovimientosPuntajeSqlite(base.bd, RelojDeJuego(2))

    assert con_el_reloj_de_la_demo.resumen_de(sala, SEIS_HORAS).horas_por_tramo == {Tramo(3, 30): 1}
    con_el_reloj_de_la_demo.agregar(_movimiento(sala, AHORA + timedelta(seconds=45), EstadoGlobal.EN_RIESGO))
    assert con_el_reloj_de_la_demo.resumen_de(sala, SEIS_HORAS).horas_por_tramo == {Tramo(3, 30): 1, Tramo(1, -5): 1}
    assert [hora for hora, _, _ in _horas_guardadas(base, sala)] == [
        RelojDeJuego().numero_de_hora(AHORA),
        RelojDeJuego(2).numero_de_hora(AHORA + timedelta(seconds=45)),
    ]


def test_las_consultas_no_recorren_los_movimientos_viejos(tmp_path):
    """El juego no se pone lento con el tiempo.

    Dos bases con lo mismo en la ultima hora, pero una con 400 movimientos mas,
    uno por hora desde hace un mes (400 horas de juego). Las consultas hacen el mismo
    trabajo en las dos: el tamano y los totales salen de lo que ya se sumo al
    guardar, y las ventanas y los recientes solo leen su tramo del indice.
    """

    def pasos(viejos: int) -> dict[str, int]:
        base = Base(tmp_path / f"con-{viejos}.sqlite")
        ana = base.cuenta("ana@correo.co")
        sala = base.planta(ana, "Sala")
        hace_un_mes = AHORA - timedelta(days=30)
        for hora in range(viejos):
            base.movimientos.agregar(_movimiento(sala, hace_un_mes + timedelta(hours=hora), EstadoGlobal.SALUDABLE))
        for minuto in range(20):
            estado = list(EstadoGlobal)[minuto % 3]
            base.movimientos.agregar(_movimiento(sala, AHORA + timedelta(minutes=minuto), estado))
        consultas = {
            "resumen_de": lambda: base.movimientos.resumen_de(sala, SEIS_HORAS),
            "total_de": lambda: base.movimientos.total_de(ana.id),
            "totales_por_planta": lambda: base.movimientos.totales_por_planta(ana.id),
            "totales_de_usuarios": lambda: base.movimientos.totales_de_usuarios([ana.id]),
            "recientes_de": lambda: base.movimientos.recientes_de(ana.id, 20),
        }
        return {nombre: base.bd.pasos_de(consulta) for nombre, consulta in consultas.items()}

    pocos, muchos = pasos(10), pasos(400)

    assert {nombre: muchos[nombre] - pocos[nombre] for nombre in pocos} == {nombre: 0 for nombre in pocos}, (pocos, muchos)


def test_el_resumen_de_una_matera_no_recorre_los_movimientos_de_otra(tmp_path):
    """La placa de la sala se apago hace un mes y la de la cocina sigue mandando.

    El resumen de la sala hace el mismo trabajo con 10 o con 400 lecturas nuevas
    de la cocina: no las recorre para encontrar las dos ultimas de la sala.
    """

    def pasos(de_la_cocina: int) -> int:
        base = Base(tmp_path / f"cocina-{de_la_cocina}.sqlite")
        ana = base.cuenta("ana@correo.co")
        sala, cocina = base.planta(ana, "Sala"), base.planta(ana, "Cocina")
        hace_un_mes = AHORA - timedelta(days=30)
        for segundo in range(3):
            base.movimientos.agregar(_movimiento(sala, hace_un_mes + timedelta(seconds=segundo), EstadoGlobal.CRITICO))
        for segundo in range(de_la_cocina):
            base.movimientos.agregar(_movimiento(cocina, AHORA + timedelta(seconds=segundo), EstadoGlobal.SALUDABLE))
        return base.bd.pasos_de(lambda: base.movimientos.resumen_de(sala, SEIS_HORAS))

    assert pasos(400) == pasos(10)


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
    vacio = base.movimientos.resumen_de(Planta(patio.id, ana.id, "Patio", "potos"), SEIS_HORAS)
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
        # Y lo que habria sumado agregar(): su hora de juego, la forma de esa hora y el total de Ana.
        conexion.execute(
            "INSERT INTO cuidado_por_hora (planta_id, usuario_id, hora_juego, cantidad, suma) VALUES (?, ?, 498447, 1, 10)",
            (patio.id, ana.id),
        )
        conexion.execute(
            "INSERT INTO horas_por_tramo (planta_id, usuario_id, cantidad, suma, horas) VALUES (?, ?, 1, 10, 1)",
            (patio.id, ana.id),
        )
        conexion.execute("INSERT INTO puntaje_total (usuario_id, puntos) VALUES (?, 10)", (ana.id,))

    assert base.movimientos.total_de(ana.id) == 10  # es de Ana
    assert base.movimientos.totales_por_planta(ana.id) == {}  # pero la planta no es suya
    assert base.movimientos.totales_por_planta(beto.id) == {}
    assert base.movimientos.resumen_de(patio, SEIS_HORAS) == ResumenCuidado.sin_lecturas()


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
        assert base.movimientos.resumen_de(planta, SEIS_HORAS) == ResumenCuidado.sin_lecturas()


def test_al_borrar_una_cuenta_se_borran_sus_movimientos_y_su_participacion(base):
    ana = base.cuenta("ana@correo.co")
    sala = base.planta(ana, "Sala")
    base.movimientos.agregar(_movimiento(sala, AHORA, EstadoGlobal.SALUDABLE))
    base.jugadores.guardar(Participacion.participa(ana.id, ApodoJugador("pipe_verde")))

    base.usuarios.eliminar(ana.id)

    with base.bd.conexion() as conexion:
        for tabla in ("movimiento_puntaje", "cuidado_por_hora", "horas_por_tramo", "puntaje_total", "jugador"):
            assert conexion.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] == 0, tabla


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
