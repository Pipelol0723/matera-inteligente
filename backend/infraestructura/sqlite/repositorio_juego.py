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


class MovimientosPuntajeSqlite(MovimientosPuntaje):
    """Los movimientos en movimiento_puntaje, y lo que se lee seguido ya sumado al guardarlos.

    - cuidado_por_hora: por matera y hora de juego, cuantas lecturas y cuanto
      sumaron. La hora la pone el reloj del juego vigente al llegar (el que pasa
      main.py): cambiar el reloj despues no reagrupa el pasado.
    - horas_por_tramo: por matera, cuantas horas terminaron con cada (cantidad,
      suma). Es ResumenCuidado.horas_por_tramo, ya contado.
    - puntaje_total: el total de cada usuario, con sus materas borradas.
    Asi el tamano, los puntos y la tabla no recorren los movimientos ni las horas;
    las ventanas de la condicion leen solo su tramo, con el indice movimiento_por_planta.
    Solo se cuenta: que hora fue bien cuidada lo sigue decidiendo el dominio.
    """

    def __init__(self, bd: BaseDatos, reloj: RelojDeJuego):
        self._bd = bd
        self._reloj = reloj

    def agregar(self, movimiento: MovimientoPuntaje) -> None:
        # Todo en una transaccion: el movimiento, su hora y los totales quedan juntos o no queda nada.
        # La primera escritura toma el candado de la base: dos lecturas a la vez no se pisan las cuentas.
        with self._bd.conexion() as conexion:
            # Solo si la planta sigue siendo la de ese dueno: si se borro mientras llegaba la lectura,
            # su id pudo pasar a la planta nueva de otro usuario.
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
            self._sumar_a_su_hora(conexion, movimiento)
            conexion.execute(
                "INSERT INTO puntaje_total (usuario_id, puntos) VALUES (?, ?)"
                " ON CONFLICT (usuario_id) DO UPDATE SET puntos = puntos + excluded.puntos",
                (movimiento.usuario_id, movimiento.puntos),
            )

    def _sumar_a_su_hora(self, conexion: sqlite3.Connection, movimiento: MovimientoPuntaje) -> None:
        """La hora de juego del movimiento suma una lectura, y en horas_por_tramo pasa de su forma de antes a la nueva."""
        planta, usuario = movimiento.planta_id, movimiento.usuario_id
        hora = self._reloj.numero_de_hora(movimiento.momento)
        antes = conexion.execute(
            "SELECT cantidad, suma FROM cuidado_por_hora WHERE planta_id = ? AND hora_juego = ?", (planta, hora)
        ).fetchone()
        cantidad, suma = (antes["cantidad"], antes["suma"]) if antes else (0, 0)
        conexion.execute(
            "INSERT INTO cuidado_por_hora (planta_id, usuario_id, hora_juego, cantidad, suma) VALUES (?, ?, ?, ?, ?)"
            " ON CONFLICT (planta_id, hora_juego) DO UPDATE SET cantidad = excluded.cantidad, suma = excluded.suma",
            (planta, usuario, hora, cantidad + 1, suma + movimiento.puntos),
        )
        if antes:
            forma_de_antes = (planta, cantidad, suma)
            borrada = conexion.execute(
                "DELETE FROM horas_por_tramo WHERE planta_id = ? AND cantidad = ? AND suma = ? AND horas = 1", forma_de_antes
            ).rowcount
            if not borrada:
                conexion.execute(
                    "UPDATE horas_por_tramo SET horas = horas - 1 WHERE planta_id = ? AND cantidad = ? AND suma = ?",
                    forma_de_antes,
                )
        conexion.execute(
            "INSERT INTO horas_por_tramo (planta_id, usuario_id, cantidad, suma, horas) VALUES (?, ?, ?, ?, 1)"
            " ON CONFLICT (planta_id, cantidad, suma) DO UPDATE SET horas = horas + 1",
            (planta, usuario, cantidad + 1, suma + movimiento.puntos),
        )

    def total_de(self, usuario_id: int) -> int:
        # Tambien los de sus materas borradas: borrar una planta no le resta a puntaje_total.
        with self._bd.conexion() as conexion:
            fila = conexion.execute("SELECT puntos FROM puntaje_total WHERE usuario_id = ?", (usuario_id,)).fetchone()
        return fila[0] if fila else 0

    def totales_por_planta(self, usuario_id: int) -> dict[int, int]:
        # Las horas de las plantas que siguen siendo suyas: las de una planta borrada se borraron con ella.
        with self._bd.conexion() as conexion:
            filas = conexion.execute(
                "SELECT t.planta_id, SUM(t.suma * t.horas) FROM planta p"
                " JOIN horas_por_tramo t ON t.planta_id = p.id AND t.usuario_id = p.usuario_id"
                " WHERE p.usuario_id = ? GROUP BY t.planta_id",
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
                    f"SELECT usuario_id, puntos FROM puntaje_total WHERE usuario_id IN ({', '.join('?' * len(grupo))})",
                    grupo,
                ).fetchall()
                totales.update({usuario_id: puntos for usuario_id, puntos in filas})
        return totales

    def resumen_de(self, planta: Planta, ventana: timedelta) -> ResumenCuidado:
        parametros = {"planta": planta.id, "usuario": planta.usuario_id}
        propios = "FROM movimiento_puntaje WHERE planta_id = :planta AND usuario_id = :usuario"
        with self._bd.conexion() as conexion:
            # Una transaccion de lectura: las consultas ven lo mismo aunque llegue una lectura en medio.
            conexion.execute("BEGIN")
            ultimos = conexion.execute(
                f"SELECT id, {_COLUMNAS_MOVIMIENTO} {propios} {_RECIENTES_PRIMERO} LIMIT 2", parametros
            ).fetchall()
            # Cuantas horas terminaron con cada (cantidad, suma): unas pocas filas aunque la matera tenga miles de horas.
            horas = conexion.execute(
                "SELECT cantidad, suma, horas FROM horas_por_tramo WHERE planta_id = :planta AND usuario_id = :usuario",
                parametros,
            ).fetchall()

            def al(fila: sqlite3.Row, sin_id: int | None = None) -> Tramo:
                """Los movimientos de la ventana que termina en el de esa fila, con el incluido. Solo lee ese tramo."""
                hasta = fila["momento_us"]
                cantidad, suma = conexion.execute(
                    f"SELECT COUNT(*), COALESCE(SUM(puntos), 0) {propios}"
                    " AND momento_us > :desde AND momento_us <= :hasta AND id IS NOT :sin",
                    {**parametros, "desde": hasta - ventana // _MICROSEGUNDO, "hasta": hasta, "sin": sin_id},
                ).fetchone()
                return Tramo(cantidad, suma)

            ultimo = ultimos[0] if ultimos else None
            anterior = ultimos[1] if len(ultimos) > 1 else None
            # La ventana de la anterior es sin la ultima: si las dos tienen el mismo momento, la ultima tambien cae ahi.
            al_ultimo = al(ultimo) if ultimo is not None else Tramo()
            al_anterior = al(anterior, sin_id=ultimo["id"]) if anterior is not None else Tramo()
        return ResumenCuidado(
            horas_por_tramo={Tramo(cantidad, suma): cuantas for cantidad, suma, cuantas in horas},
            ultimo=_movimiento(ultimo) if ultimo is not None else None,
            anterior=_movimiento(anterior) if anterior is not None else None,
            al_ultimo=al_ultimo,
            al_anterior=al_anterior,
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
