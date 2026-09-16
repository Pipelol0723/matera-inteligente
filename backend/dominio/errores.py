"""Errores de negocio.

No saben nada de HTTP: la capa de presentacion decide con que codigo y con que
mensaje se muestran.
"""
from dominio.parametros import Parametro


class ErrorDominio(Exception):
    """Base de los errores del dominio."""


class EspecieNoSoportada(ErrorDominio):
    """La especie pedida no esta en la tabla de referencia."""

    def __init__(self, especie: str):
        super().__init__(f"La especie '{especie}' no está en la tabla de referencia.")
        self.especie = especie


class ValorFisicamenteImposible(ErrorDominio):
    """Una lectura fuera de lo que el parametro puede valer en el mundo real."""

    def __init__(self, parametro: Parametro, valor: float):
        super().__init__(
            f"{parametro.nombre} = {valor} no es físicamente posible "
            f"(debe estar entre {parametro.minimo_fisico:g} y {parametro.maximo_fisico:g} {parametro.unidad})."
        )
        self.parametro = parametro
        self.valor = valor


class MedicionInvalida(ErrorDominio):
    """Una medicion vacia o que repite un parametro."""


class ParametroSinRango(ErrorDominio):
    """Llego una lectura de un parametro para el que la especie no tiene rango."""

    def __init__(self, especie: str, parametro: Parametro):
        super().__init__(f"La especie '{especie}' no tiene rango óptimo para {parametro.nombre}.")
        self.especie = especie
        self.parametro = parametro


class RangoInvalido(ErrorDominio):
    """Un rango optimo cuyo minimo no es menor que su maximo."""

    def __init__(self, minimo: float, maximo: float):
        super().__init__(
            f"Rango inválido: el mínimo ({minimo}) debe ser menor que el máximo ({maximo})."
        )
        self.minimo = minimo
        self.maximo = maximo
