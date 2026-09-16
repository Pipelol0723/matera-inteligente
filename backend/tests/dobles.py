"""Datos y dobles de prueba.

Solo importa el dominio: estas pruebas no leen el CSV ni levantan Flask, y
siguen pasando aunque se borre la carpeta infraestructura (RA4).
"""
from dominio.especie import Especie
from dominio.medicion import Lectura, Medicion
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.puertos import CatalogoEspecies, ConsultaRangos
from dominio.rango import Rango


class RepositorioEspeciesEnMemoria(ConsultaRangos, CatalogoEspecies):
    """Doble de los dos puertos: guarda especies en un dict y anota cada consulta (espia).

    A proposito no normaliza nombres: asi las pruebas comprueban que el
    servicio los normaliza antes de preguntar.
    """

    def __init__(self, *especies: Especie):
        self._especies = {especie.nombre: especie for especie in especies}
        self.consultas: list[str] = []

    def rangos_de(self, especie: str) -> Especie | None:
        self.consultas.append(especie)
        return self._especies.get(especie)

    def listar(self) -> list[Especie]:
        return list(self._especies.values())


def sansevieria() -> Especie:
    """Especie de ejemplo con rangos fijos, independientes del CSV real."""
    return Especie(
        "sansevieria",
        {HUMEDAD: Rango(20, 45), LUZ: Rango(200, 1500), TEMPERATURA: Rango(15, 29)},
    )


def medicion(humedad: float, luz: float, temperatura: float) -> Medicion:
    return Medicion((Lectura(HUMEDAD, humedad), Lectura(LUZ, luz), Lectura(TEMPERATURA, temperatura)))
