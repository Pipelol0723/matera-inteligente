"""Caso de uso: diagnosticar una planta a partir de una medicion."""
from dominio import puertos_entrada as entrada
from dominio.diagnostico import Diagnostico
from dominio.resultados import SolicitudDiagnostico
from dominio.servicio_diagnostico import ServicioDiagnostico


class DiagnosticarPlanta(entrada.DiagnosticarPlanta):
    """Hoy solo delega en el dominio.

    Es el lugar donde entrarian guardar el historico, resolver la planta de un
    usuario o avisar a la gamificacion, sin tocar las reglas de negocio.
    """

    def __init__(self, servicio: ServicioDiagnostico):
        self._servicio = servicio

    def ejecutar(self, solicitud: SolicitudDiagnostico) -> Diagnostico:
        return self._servicio.diagnosticar(solicitud.especie, solicitud.medicion)
