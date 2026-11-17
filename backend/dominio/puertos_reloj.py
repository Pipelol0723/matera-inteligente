"""Puertos del reloj del juego ajustable (corte 3). Van aparte para no modificar ningun puerto existente."""
from abc import ABC, abstractmethod
from datetime import datetime

from dominio.mascota import RelojDeJuego
from dominio.usuarios import Usuario


# --- Entrada ---


class ConsultarRelojDeJuego(ABC):
    """Cuanto dura hoy un dia de juego. Lo puede ver cualquier usuario con sesion."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario) -> RelojDeJuego: ...


class CambiarRelojDeJuego(ABC):
    """Un admin cambia cuanto dura un dia de juego, en minutos reales. Vale para todos desde ese momento."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario, minutos_por_dia: float) -> RelojDeJuego: ...


# --- Salida ---


class RelojDeJuegoGuardado(ABC):
    """Donde queda el reloj que eligio un admin, para que siga despues de reiniciar el backend."""

    @abstractmethod
    def leer(self) -> RelojDeJuego | None:
        """El ultimo que eligio un admin, o None si nadie lo cambio (vale el de la configuracion)."""

    @abstractmethod
    def guardar(self, reloj: RelojDeJuego, usuario_id: int, momento: datetime) -> None: ...
