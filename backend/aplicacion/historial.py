"""Caso de uso: consultar el historial de una planta propia."""
from dataclasses import dataclass

from aplicacion.plantas import buscar_planta_propia
from dominio.historial import RegistroMedicion
from dominio.plantas import Planta
from dominio.puertos_usuarios import HistorialMediciones, RepositorioPlantas
from dominio.usuarios import Usuario

LIMITE_POR_DEFECTO = 30


@dataclass(frozen=True)
class HistorialPlanta:
    planta: Planta
    registros: list[RegistroMedicion]


class ConsultarHistorial:
    def __init__(self, plantas: RepositorioPlantas, historial: HistorialMediciones):
        self._plantas = plantas
        self._historial = historial

    def ejecutar(self, usuario: Usuario, planta_id: int, limite: int = LIMITE_POR_DEFECTO) -> HistorialPlanta:
        planta = buscar_planta_propia(self._plantas, usuario.id, planta_id)
        return HistorialPlanta(planta, self._historial.de_planta(planta.id, limite))
