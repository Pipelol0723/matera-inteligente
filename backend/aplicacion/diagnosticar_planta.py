"""Caso de uso: diagnosticar una planta a partir de una medicion."""
from dataclasses import dataclass

from dominio.diagnostico import Diagnostico
from dominio.medicion import Medicion
from dominio.servicio_diagnostico import ServicioDiagnostico


@dataclass(frozen=True)
class SolicitudDiagnostico:
    """Pedido ya validado. No importa si llego por HTTP, por MQTT o desde una prueba."""

    especie: str
    medicion: Medicion


class DiagnosticarPlanta:
    """Hoy solo delega en el dominio.

    Es el lugar donde entrarian guardar el historico, resolver la planta de un
    usuario o avisar a la gamificacion, sin tocar las reglas de negocio.
    """

    def __init__(self, servicio: ServicioDiagnostico):
        self._servicio = servicio

    def ejecutar(self, solicitud: SolicitudDiagnostico) -> Diagnostico:
        return self._servicio.diagnosticar(solicitud.especie, solicitud.medicion)
