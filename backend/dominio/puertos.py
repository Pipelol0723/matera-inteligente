"""Puertos: lo que el dominio necesita de afuera, dicho en sus propios terminos.

Se declaran aqui y se implementan en infraestructura, asi que la dependencia
va de infraestructura hacia el dominio (RA5, DIP). Son dos interfaces de un
solo metodo para que cada cliente dependa solo de la operacion que usa (ISP).
"""
from abc import ABC, abstractmethod

from dominio.especie import Especie


class ConsultaRangos(ABC):
    """Dame los rangos de esta especie."""

    @abstractmethod
    def rangos_de(self, especie: str) -> Especie | None:
        """Devuelve la especie con sus rangos, o None si no existe.

        Recibe el nombre ya normalizado (ver dominio.especie.normalizar_nombre).
        """


class CatalogoEspecies(ABC):
    """Dame todas las especies soportadas."""

    @abstractmethod
    def listar(self) -> list[Especie]:
        """Devuelve todas las especies de la tabla de referencia."""
