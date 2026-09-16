"""Especie de planta con su rango optimo para cada parametro."""
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from dominio.errores import ParametroSinRango
from dominio.parametros import Parametro
from dominio.rango import Rango


def normalizar_nombre(nombre: str) -> str:
    """'  Potós ' y 'potos' son la misma especie: minusculas, sin tildes ni espacios de mas."""
    sin_tildes = unicodedata.normalize("NFKD", nombre).encode("ascii", "ignore").decode("ascii")
    return " ".join(sin_tildes.lower().split())


@dataclass(frozen=True, eq=False)
class Especie:
    nombre: str
    rangos: Mapping[Parametro, Rango]
    # Dato descriptivo para mostrar; ninguna regla depende de el.
    nombre_cientifico: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "nombre", normalizar_nombre(self.nombre))
        object.__setattr__(self, "rangos", MappingProxyType(dict(self.rangos)))
        object.__setattr__(self, "nombre_cientifico", self.nombre_cientifico.strip())

    def rango_de(self, parametro: Parametro) -> Rango:
        try:
            return self.rangos[parametro]
        except KeyError:
            raise ParametroSinRango(self.nombre, parametro) from None
