"""Errores de negocio.

No saben nada de HTTP: la capa de presentacion decide con que codigo y con que
mensaje se muestran.
"""


class ErrorDominio(Exception):
    """Base de los errores del dominio."""


class RangoInvalido(ErrorDominio):
    """Un rango optimo cuyo minimo no es menor que su maximo."""

    def __init__(self, minimo: float, maximo: float):
        super().__init__(
            f"Rango inválido: el mínimo ({minimo}) debe ser menor que el máximo ({maximo})."
        )
        self.minimo = minimo
        self.maximo = maximo
