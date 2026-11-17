"""Adaptador del puerto RelojDeJuegoGuardado: el reloj que eligio un admin, en la tabla reloj_juego.

Es una sola fila (id = 1) con los minutos reales que dura un dia de juego,
cuando se cambio y quien lo cambio. Sin fila, main.py usa el de la
configuracion (MATERA_MINUTOS_POR_DIA_JUEGO).
"""
from datetime import datetime

from dominio.mascota import RelojDeJuego
from dominio.puertos_reloj import RelojDeJuegoGuardado
from infraestructura.sqlite.base_datos import BaseDatos


class RelojDeJuegoGuardadoSqlite(RelojDeJuegoGuardado):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def leer(self) -> RelojDeJuego | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute("SELECT minutos_por_dia FROM reloj_juego WHERE id = 1").fetchone()
        return RelojDeJuego(fila["minutos_por_dia"]) if fila is not None else None

    def guardar(self, reloj: RelojDeJuego, usuario_id: int, momento: datetime) -> None:
        with self._bd.conexion() as conexion:
            conexion.execute(
                "INSERT INTO reloj_juego (id, minutos_por_dia, cambiado_en, cambiado_por) VALUES (1, ?, ?, ?)"
                " ON CONFLICT (id) DO UPDATE SET minutos_por_dia = excluded.minutos_por_dia,"
                " cambiado_en = excluded.cambiado_en, cambiado_por = excluded.cambiado_por",
                (reloj.minutos_por_dia, momento.isoformat(), usuario_id),
            )
