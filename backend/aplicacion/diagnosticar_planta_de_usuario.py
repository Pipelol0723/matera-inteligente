"""Caso de uso de la seccion 5.3: diagnosticar una planta de un usuario y guardar la medicion.

Busca la planta por su dueno, toma su especie, llama al ServicioDiagnostico
del corte 1 sin cambiarlo y guarda el resultado en el historial. Solo lo usa
el sensor, con el dueno de la planta a la que esta vinculado: el historial
guarda lo que se midio, no lo que alguien escribio a mano.
"""
from dataclasses import dataclass

from aplicacion.plantas import buscar_planta_propia
from dominio.diagnostico import Diagnostico
from dominio.historial import RegistroMedicion
from dominio.medicion import Medicion
from dominio.plantas import Planta
from dominio.puertos_usuarios import HistorialMediciones, Reloj, RepositorioPlantas
from dominio.servicio_diagnostico import ServicioDiagnostico


@dataclass(frozen=True)
class ResultadoMedicion:
    planta: Planta
    diagnostico: Diagnostico
    registro: RegistroMedicion


class DiagnosticarPlantaDeUsuario:
    def __init__(
        self,
        plantas: RepositorioPlantas,
        servicio: ServicioDiagnostico,
        historial: HistorialMediciones,
        reloj: Reloj,
    ):
        self._plantas = plantas
        self._servicio = servicio
        self._historial = historial
        self._reloj = reloj

    def ejecutar(self, usuario_id: int, planta_id: int, medicion: Medicion, origen: str) -> ResultadoMedicion:
        """El origen es el codigo del sensor que mando la medicion."""
        planta = buscar_planta_propia(self._plantas, usuario_id, planta_id)
        diagnostico = self._servicio.diagnosticar(planta.especie, medicion)
        registro = RegistroMedicion.desde(diagnostico, planta.id, self._reloj.ahora(), origen)
        self._historial.agregar(registro)
        return ResultadoMedicion(planta, diagnostico, registro)
