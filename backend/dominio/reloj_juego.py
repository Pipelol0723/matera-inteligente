"""El reloj del juego, ajustable mientras la app corre (corte 3).

Un admin puede cambiar cuanto dura una hora de juego (por ejemplo, 1 minuto real
= 1 hora de juego) sin reiniciar el backend. RelojDeJuego sigue siendo el valor
(cuanto dura un dia de juego); RelojDeJuegoAjustable es el reloj vigente que
comparten el puntaje y la matera Tamagotchi, con la misma forma que RelojDeJuego.

Cambiarlo no reagrupa el pasado: cada lectura ya quedo en su hora de juego al
llegar. Las que lleguen despues se agrupan con la escala nueva, y la ventana de
la condicion (6 horas de juego) se mide con ella. Los 30 minutos para dormirse
son reales y no cambian.
"""
from datetime import datetime, timedelta

from dominio.errores import ErrorDominio
from dominio.mascota import CuidadoDeMascota, RelojDeJuego


class RelojDeJuegoInvalido(ErrorDominio):
    """La duracion pedida para el dia de juego no sirve."""

    def __init__(self):
        super().__init__(
            "La duración del día de juego debe ser un número de minutos mayor que cero, y no tan grande "
            "que 6 horas de juego se salgan del calendario."
        )


class RelojDeJuegoAjustable:
    """El reloj del juego vigente. Tiene la forma de RelojDeJuego y se puede cambiar por otro.

    Cambiar el valor es reemplazar una referencia: quien lo lee en ese momento ve
    el reloj de antes o el nuevo, nunca uno a medias.
    """

    def __init__(self, inicial: RelojDeJuego):
        self._vigente = self.validar(inicial)

    @staticmethod
    def validar(reloj: RelojDeJuego) -> RelojDeJuego:
        """Que sea un RelojDeJuego y que la ventana de la condicion quepa en el calendario."""
        if not isinstance(reloj, RelojDeJuego):
            raise RelojDeJuegoInvalido()
        try:
            CuidadoDeMascota(reloj)
        except ValueError:
            raise RelojDeJuegoInvalido() from None
        return reloj

    @staticmethod
    def desde_minutos(minutos_por_dia: float) -> RelojDeJuego:
        """El RelojDeJuego de esa duracion del dia, o RelojDeJuegoInvalido."""
        try:
            reloj = RelojDeJuego(minutos_por_dia)
        except (ValueError, TypeError, OverflowError):
            raise RelojDeJuegoInvalido() from None
        return RelojDeJuegoAjustable.validar(reloj)

    @property
    def vigente(self) -> RelojDeJuego:
        return self._vigente

    def cambiar(self, nuevo: RelojDeJuego) -> None:
        self._vigente = self.validar(nuevo)

    # --- La misma forma que RelojDeJuego: quien lo usa no sabe que se puede cambiar ---

    @property
    def minutos_por_dia(self) -> float:
        return self._vigente.minutos_por_dia

    @property
    def dia(self) -> timedelta:
        return self._vigente.dia

    @property
    def hora(self) -> timedelta:
        return self._vigente.hora

    def horas(self, cantidad: float) -> timedelta:
        return self._vigente.horas(cantidad)

    def dias(self, cantidad: float) -> timedelta:
        return self._vigente.dias(cantidad)

    def numero_de_hora(self, momento: datetime) -> int:
        return self._vigente.numero_de_hora(momento)
