"""Datos y dobles de prueba.

Solo importa el dominio: estas pruebas no leen el CSV ni levantan Flask, y
siguen pasando aunque se borre la carpeta infraestructura (RA4).
"""
from dominio.especie import Especie
from dominio.medicion import Lectura, Medicion
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.rango import Rango


def sansevieria() -> Especie:
    """Especie de ejemplo con rangos fijos, independientes del CSV real."""
    return Especie(
        "sansevieria",
        {HUMEDAD: Rango(20, 45), LUZ: Rango(200, 1500), TEMPERATURA: Rango(15, 29)},
    )


def medicion(humedad: float, luz: float, temperatura: float) -> Medicion:
    return Medicion((Lectura(HUMEDAD, humedad), Lectura(LUZ, luz), Lectura(TEMPERATURA, temperatura)))
