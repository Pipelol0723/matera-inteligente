"""Dobles en memoria de los puertos de salida del juego (corte 3).

Como tests/dobles.py y tests/dobles_usuarios.py, solo importan el dominio: las
pruebas del juego no abren la base de datos ni levantan Flask, y siguen pasando
aunque se borre la carpeta infraestructura (RA4). Imitan lo que la base va a
asegurar en la fase 2: que un movimiento solo se guarda en una planta que sigue
siendo de su dueno, que un apodo no se repite y que las cuentas desactivadas no
aparecen en la tabla.
"""
from collections.abc import Collection
from dataclasses import replace
from datetime import timedelta

from dominio.errores_juego import ApodoRepetido
from dominio.errores_usuarios import PlantaNoEncontrada
from dominio.juego import ApodoJugador, MovimientoPuntaje, Participacion
from dominio.mascota import RelojDeJuego, ResumenCuidado, RitmoCrecimiento, Tramo
from dominio.plantas import Planta
from dominio.puertos_juego import MovimientosPuntaje, RegistroJugadores, RitmosCrecimiento
from dominio.puertos_usuarios import ConsultaCuentas, ConsultaPlantas


class MovimientosEnMemoria(MovimientosPuntaje):
    """Guarda los movimientos en una lista, en el orden en que llegan.

    Si recibe las plantas, revisa como la base que la planta siga siendo de ese usuario.
    """

    def __init__(self, plantas: ConsultaPlantas | None = None):
        self.movimientos: list[MovimientoPuntaje] = []
        self._plantas = plantas

    def agregar(self, movimiento: MovimientoPuntaje) -> None:
        if self._plantas is not None:
            planta = self._plantas.por_id(movimiento.planta_id)
            if planta is None or planta.usuario_id != movimiento.usuario_id:
                raise PlantaNoEncontrada(movimiento.planta_id)
        self.movimientos.append(movimiento)

    def soltar_planta(self, planta_id: int) -> None:
        """No es del puerto: imita lo que hara la base al borrar una planta (sus movimientos quedan sin planta)."""
        self.movimientos = [replace(m, planta_id=None) if m.planta_id == planta_id else m for m in self.movimientos]

    def total_de(self, usuario_id: int) -> int:
        return sum(m.puntos for m in self.movimientos if m.usuario_id == usuario_id)

    def totales_por_planta(self, usuario_id: int) -> dict[int, int]:
        totales: dict[int, int] = {}
        for m in self.movimientos:
            if m.usuario_id == usuario_id and m.planta_id is not None:
                totales[m.planta_id] = totales.get(m.planta_id, 0) + m.puntos
        return totales

    def recientes_de(self, usuario_id: int, limite: int) -> list[MovimientoPuntaje]:
        return [m for m in self._mas_recientes_primero() if m.usuario_id == usuario_id][:limite]

    def totales_de_usuarios(self, usuario_ids: Collection[int]) -> dict[int, int]:
        con_movimientos = {m.usuario_id for m in self.movimientos}
        return {u: self.total_de(u) for u in usuario_ids if u in con_movimientos}

    def resumen_de(self, planta: Planta, reloj: RelojDeJuego, ventana: timedelta) -> ResumenCuidado:
        propios = [
            m for m in self._mas_recientes_primero() if m.planta_id == planta.id and m.usuario_id == planta.usuario_id
        ]
        horas: dict[int, Tramo] = {}
        for m in propios:
            numero = reloj.numero_de_hora(m.momento)
            tramo = horas.get(numero, Tramo())
            horas[numero] = Tramo(tramo.cantidad + 1, tramo.suma + m.puntos)

        def al(indice: int) -> Tramo:
            # La ventana que termina en propios[indice], sin los mas recientes que el (aunque empaten en momento).
            fin = propios[indice].momento
            dentro = [m for m in propios[indice:] if fin - ventana < m.momento <= fin]
            return Tramo(len(dentro), sum(m.puntos for m in dentro))

        return ResumenCuidado(
            horas=horas,
            ultimo=propios[0] if propios else None,
            anterior=propios[1] if len(propios) > 1 else None,
            al_ultimo=al(0) if propios else Tramo(),
            al_anterior=al(1) if len(propios) > 1 else Tramo(),
        )

    def _mas_recientes_primero(self) -> list[MovimientoPuntaje]:
        # Por momento y, si empatan, el ultimo guardado primero.
        orden = sorted(enumerate(self.movimientos), key=lambda par: (par[1].momento, par[0]), reverse=True)
        return [m for _, m in orden]


class RegistroJugadoresEnMemoria(RegistroJugadores):
    """Una participacion por usuario. Si recibe las cuentas, la tabla deja afuera las desactivadas."""

    def __init__(self, cuentas: ConsultaCuentas | None = None):
        self.participaciones: dict[int, Participacion] = {}
        self._cuentas = cuentas

    def participacion_de(self, usuario_id: int) -> Participacion | None:
        return self.participaciones.get(usuario_id)

    def guardar(self, participacion: Participacion) -> None:
        # Como el indice unico de la base: el apodo no se repite entre usuarios.
        if participacion.apodo is not None and self.apodo_en_uso(participacion.apodo, participacion.usuario_id):
            raise ApodoRepetido(participacion.apodo.valor)
        self.participaciones[participacion.usuario_id] = participacion

    def apodo_en_uso(self, apodo: ApodoJugador, excepto_usuario_id: int) -> bool:
        return any(
            p.apodo == apodo for u, p in self.participaciones.items() if u != excepto_usuario_id and p.apodo is not None
        )

    def participantes_activos(self) -> list[Participacion]:
        return [p for p in self.participaciones.values() if p.en_tabla and self._activa(p.usuario_id)]

    def _activa(self, usuario_id: int) -> bool:
        if self._cuentas is None:
            return True
        usuario = self._cuentas.por_id(usuario_id)
        return usuario is not None and usuario.activo


class RitmosEnMemoria(RitmosCrecimiento):
    def __init__(self, ritmos: dict[str, RitmoCrecimiento] | None = None):
        self._ritmos = dict(ritmos or {})

    def de_especie(self, especie: str) -> RitmoCrecimiento | None:
        return self._ritmos.get(especie)


def ritmos_del_plan() -> RitmosEnMemoria:
    """Los ritmos de las cinco especies del plan, en dias de juego bien cuidada (brote, planta, florecida)."""
    return RitmosEnMemoria({
        "potos": RitmoCrecimiento(1, 3, 6),
        "helecho": RitmoCrecimiento(1, 3, 7),
        "lavanda": RitmoCrecimiento(1, 4, 8),
        "sansevieria": RitmoCrecimiento(2, 5, 10),
        "suculenta": RitmoCrecimiento(2, 6, 12),
    })
