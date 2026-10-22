"""Caso de uso: consultar el historial de una planta propia."""
from aplicacion.plantas import buscar_planta_propia
from dominio import puertos_entrada as entrada
from dominio.puertos_usuarios import ConsultaPlantas, HistorialMediciones
from dominio.resultados import HistorialPlanta
from dominio.usuarios import Usuario


class ConsultarHistorial(entrada.ConsultarHistorial):
    def __init__(self, plantas: ConsultaPlantas, historial: HistorialMediciones):
        self._plantas = plantas
        self._historial = historial

    def ejecutar(self, usuario: Usuario, planta_id: int, limite: int = entrada.LIMITE_HISTORIAL) -> HistorialPlanta:
        planta = buscar_planta_propia(self._plantas, usuario.id, planta_id)
        return HistorialPlanta(planta, self._historial.de_planta(planta.id, limite))
