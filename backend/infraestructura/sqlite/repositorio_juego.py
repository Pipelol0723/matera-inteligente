"""El juego en SQLite (corte 3): los movimientos del puntaje, los jugadores de la tabla y los ritmos de crecimiento.

Como los demas repositorios, abre una conexion por operacion. Cada consulta
filtra por dueno: el total, las materas y los movimientos de un usuario solo
traen los suyos, y el resumen de una planta exige su id y su dueno. Aqui solo
se agrupa y se cuenta: que hora fue bien cuidada, la condicion y los avisos los
decide CuidadoDeMascota, en el dominio.
"""
import sqlite3
from collections.abc import Collection
from datetime import datetime, timedelta, timezone

from dominio.errores_juego import ApodoRepetido
from dominio.errores_usuarios import PlantaNoEncontrada, SesionInvalida
from dominio.estados import EstadoGlobal
from dominio.juego import ApodoJugador, EstadoParticipacion, MovimientoPuntaje, Participacion
from dominio.mascota import EPOCA, RelojDeJuego, ResumenCuidado, RitmoCrecimiento, Tramo
from dominio.plantas import Planta
from dominio.puertos_juego import MovimientosPuntaje, RegistroJugadores, RitmosCrecimiento
from infraestructura.sqlite.base_datos import LA_MISMA_PLANTA, BaseDatos

_MICROSEGUNDO = timedelta(microseconds=1)
_COLUMNAS_MOVIMIENTO = "usuario_id, planta_id, momento_us, estado, puntos"
# Los mas recientes primero y, si dos tienen el mismo momento, el ultimo guardado.
_RECIENTES_PRIMERO = "ORDER BY momento_us DESC, id DESC"
# Cuantos ids van en un IN (...): SQLite limita los parametros de una consulta.
_IDS_POR_CONSULTA = 500


def microsegundos(momento: datetime) -> int:
    """El momento en microsegundos desde EPOCA. Es exacto: un datetime no tiene mas precision."""
    return (momento - EPOCA) // _MICROSEGUNDO


def _hora_de_juego(columna: str) -> str:
    """floor(columna / :hora): la misma division entera que hace RelojDeJuego.numero_de_hora.

    En SQLite la division de enteros redondea hacia cero. Para un momento anterior a
    1970 se corrige, asi coincide tambien con el floor de Python.
    """
    return f"CASE WHEN {columna} >= 0 THEN {columna} / :hora ELSE -((-{columna} - 1) / :hora) - 1 END"


class MovimientosPuntajeSqlite(MovimientosPuntaje):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def agregar(self, movimiento: MovimientoPuntaje) -> None:
        # Solo si la planta sigue siendo la de ese dueno: si se borro mientras llegaba la lectura,
        # su id pudo pasar a la planta nueva de otro usuario.
        with self._bd.conexion() as conexion:
            cursor = conexion.execute(
                "INSERT INTO movimiento_puntaje (usuario_id, planta_id, momento, momento_us, estado, puntos) "
                f"SELECT ?, id, ?, ?, ?, ? FROM ({LA_MISMA_PLANTA})",
                (
                    movimiento.usuario_id,
                    _texto(movimiento.momento),
                    microsegundos(movimiento.momento),
                    movimiento.estado.value,
                    movimiento.puntos,
                    movimiento.planta_id,
                    movimiento.usuario_id,
                ),
            )
            if cursor.rowcount == 0:
                raise PlantaNoEncontrada(movimiento.planta_id)

    def total_de(self, usuario_id: int) -> int:
        # Tambien los de sus materas borradas (planta_id NULL).
        with self._bd.conexion() as conexion:
            return conexion.execute(
                "SELECT COALESCE(SUM(puntos), 0) FROM movimiento_puntaje WHERE usuario_id = ?", (usuario_id,)
            ).fetchone()[0]

    def totales_por_planta(self, usuario_id: int) -> dict[int, int]:
        with self._bd.conexion() as conexion:
            filas = conexion.execute(
                "SELECT m.planta_id, SUM(m.puntos) FROM movimiento_puntaje m"
                " JOIN planta p ON p.id = m.planta_id AND p.usuario_id = m.usuario_id"
                " WHERE m.usuario_id = ? GROUP BY m.planta_id",
                (usuario_id,),
            ).fetchall()
        return {planta_id: suma for planta_id, suma in filas}

    def recientes_de(self, usuario_id: int, limite: int) -> list[MovimientoPuntaje]:
        with self._bd.conexion() as conexion:
            filas = conexion.execute(
                f"SELECT {_COLUMNAS_MOVIMIENTO} FROM movimiento_puntaje WHERE usuario_id = ? {_RECIENTES_PRIMERO} LIMIT ?",
                (usuario_id, max(limite, 0)),
            ).fetchall()
        return [_movimiento(fila) for fila in filas]

    def totales_de_usuarios(self, usuario_ids: Collection[int]) -> dict[int, int]:
        ids = sorted(set(usuario_ids))
        totales: dict[int, int] = {}
        with self._bd.conexion() as conexion:
            for inicio in range(0, len(ids), _IDS_POR_CONSULTA):
                grupo = ids[inicio : inicio + _IDS_POR_CONSULTA]
                filas = conexion.execute(
                    "SELECT usuario_id, SUM(puntos) FROM movimiento_puntaje"
                    f" WHERE usuario_id IN ({', '.join('?' * len(grupo))}) GROUP BY usuario_id",
                    grupo,
                ).fetchall()
                totales.update({usuario_id: suma for usuario_id, suma in filas})
        return totales

    def resumen_de(self, planta: Planta, reloj: RelojDeJuego, desde: datetime) -> ResumenCuidado:
        parametros = {
            "planta": planta.id,
            "usuario": planta.usuario_id,
            "hora": reloj.hora // _MICROSEGUNDO,
            "desde": microsegundos(desde),
        }
        propios = "FROM movimiento_puntaje WHERE planta_id = :planta AND usuario_id = :usuario"
        with self._bd.conexion() as conexion:
            # Una transaccion de lectura: las tres consultas ven lo mismo aunque llegue una lectura en medio.
            conexion.execute("BEGIN")
            horas = conexion.execute(
                f"SELECT {_hora_de_juego('momento_us')} AS hora_juego, COUNT(*), SUM(puntos) {propios} GROUP BY hora_juego",
                parametros,
            ).fetchall()
            cantidad, suma = conexion.execute(
                f"SELECT COUNT(*), COALESCE(SUM(puntos), 0) {propios} AND momento_us > :desde", parametros
            ).fetchone()
            ultimos = conexion.execute(
                f"SELECT {_COLUMNAS_MOVIMIENTO} {propios} {_RECIENTES_PRIMERO} LIMIT 2", parametros
            ).fetchall()
        movimientos = [_movimiento(fila) for fila in ultimos]
        return ResumenCuidado(
            horas={hora: Tramo(cuantas, total) for hora, cuantas, total in horas},
            ventana=Tramo(cantidad, suma),
            ultimo=movimientos[0] if movimientos else None,
            anterior=movimientos[1] if len(movimientos) > 1 else None,
        )


class RegistroJugadoresSqlite(RegistroJugadores):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def participacion_de(self, usuario_id: int) -> Participacion | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(
                "SELECT usuario_id, estado, apodo FROM jugador WHERE usuario_id = ?", (usuario_id,)
            ).fetchone()
        return _participacion(fila) if fila else None

    def guardar(self, participacion: Participacion) -> None:
        apodo = participacion.apodo.valor if participacion.apodo is not None else None
        try:
            with self._bd.conexion() as conexion:
                conexion.execute(
                    "INSERT INTO jugador (usuario_id, estado, apodo) VALUES (?, ?, ?)"
                    " ON CONFLICT (usuario_id) DO UPDATE SET estado = excluded.estado, apodo = excluded.apodo",
                    (participacion.usuario_id, participacion.estado.value, apodo),
                )
        except sqlite3.IntegrityError as error:
            mensaje = str(error)
            # El indice unico de jugador.apodo no distingue mayusculas: si dos piden el mismo apodo
            # a la vez, la base deja pasar solo a uno.
            if "jugador.apodo" in mensaje:
                raise ApodoRepetido(apodo) from None
            if "FOREIGN KEY" in mensaje:
                raise SesionInvalida() from None  # borraron la cuenta mientras se atendia la peticion
            raise

    def apodo_en_uso(self, apodo: ApodoJugador, excepto_usuario_id: int) -> bool:
        # La columna es COLLATE NOCASE: la comparacion no distingue mayusculas.
        with self._bd.conexion() as conexion:
            return conexion.execute(
                "SELECT 1 FROM jugador WHERE estado = ? AND apodo = ? AND usuario_id <> ? LIMIT 1",
                (EstadoParticipacion.PARTICIPA.value, apodo.valor, excepto_usuario_id),
            ).fetchone() is not None

    def participantes_activos(self) -> list[Participacion]:
        with self._bd.conexion() as conexion:
            filas = conexion.execute(
                "SELECT j.usuario_id, j.estado, j.apodo FROM jugador j JOIN usuario u ON u.id = j.usuario_id"
                " WHERE j.estado = ? AND u.activo = 1 ORDER BY j.usuario_id",
                (EstadoParticipacion.PARTICIPA.value,),
            ).fetchall()
        return [_participacion(fila) for fila in filas]


class RitmosCrecimientoSqlite(RitmosCrecimiento):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def de_especie(self, especie: str) -> RitmoCrecimiento | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(
                "SELECT dias_brote, dias_planta, dias_florecida FROM ritmo_crecimiento WHERE especie = ?", (especie,)
            ).fetchone()
        return RitmoCrecimiento(*fila) if fila else None


def _texto(momento: datetime) -> str:
    # Como en el historial: en UTC y con microsegundos, aunque el reloj traiga otra zona horaria.
    return momento.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _movimiento(fila: sqlite3.Row) -> MovimientoPuntaje:
    return MovimientoPuntaje(
        fila["usuario_id"],
        fila["planta_id"],
        EPOCA + timedelta(microseconds=fila["momento_us"]),
        EstadoGlobal(fila["estado"]),
        fila["puntos"],
    )


def _participacion(fila: sqlite3.Row) -> Participacion:
    estado = EstadoParticipacion(fila["estado"])
    if estado is EstadoParticipacion.PARTICIPA:
        return Participacion.participa(fila["usuario_id"], ApodoJugador(fila["apodo"]))
    return Participacion(fila["usuario_id"], estado)
