"""Puertos del modo prueba (corte 3). Van aparte para que el modo entre sin modificar ningun puerto existente."""
from abc import ABC, abstractmethod

from dominio.modo_prueba import EstadoDePrueba
from dominio.plantas import Planta
from dominio.usuarios import Usuario


# --- Entrada: lo que la app le pide al modo prueba ---


class PonerEstadoDePrueba(ABC):
    """Un admin le pone un estado de prueba a una matera suya. Si ya tenia otro, lo reemplaza."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario, planta_id: int, estado: EstadoDePrueba) -> EstadoDePrueba: ...


class QuitarEstadoDePrueba(ABC):
    """Un admin devuelve una matera suya a su estado real. Si no estaba en prueba, no pasa nada."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario, planta_id: int) -> None: ...


# --- Salida: donde se guarda el estado de prueba ---


class EstadosDePrueba(ABC):
    """El estado de prueba de cada matera, guardado junto con su dueno.

    SQLite puede reutilizar el id de una planta borrada: por eso de_planta solo
    devuelve el estado si la planta sigue siendo del mismo dueno que lo puso.
    """

    @abstractmethod
    def de_planta(self, planta: Planta) -> EstadoDePrueba | None: ...

    @abstractmethod
    def guardar(self, planta: Planta, estado: EstadoDePrueba) -> None: ...

    @abstractmethod
    def quitar(self, planta_id: int) -> None: ...
