"""Caso de uso de la seccion 5.3: diagnosticar una planta de un usuario y guardar la medicion.

Busca la planta por su dueno, toma su especie, llama al ServicioDiagnostico
del corte 1 sin cambiarlo y guarda el resultado en el historial, con la hora
en que se midio. Solo lo usa RegistrarLectura, con el dueno de la planta del
sensor: el historial guarda lo que se midio, no lo que alguien escribio a mano.

Despues de guardar, avisa al dueno por el puerto NotificadorDiagnosticos. El
caso de uso no sabe si el aviso viaja por un WebSocket o por otro medio.
"""
import logging
from datetime import datetime

from aplicacion.plantas import buscar_planta_propia
from dominio.diagnostico import Diagnostico
from dominio.historial import RegistroMedicion
from dominio.medicion import Medicion
from dominio.plantas import Planta
from dominio.puertos_usuarios import ConsultaPlantas, HistorialMediciones, NotificadorDiagnosticos
from dominio.resultados import ResultadoMedicion
from dominio.servicio_diagnostico import ServicioDiagnostico

_log = logging.getLogger(__name__)


class DiagnosticarPlantaDeUsuario:
    """Sin puerto de entrada: ningun adaptador lo llama, solo otros casos de uso."""

    def __init__(
        self,
        plantas: ConsultaPlantas,
        servicio: ServicioDiagnostico,
        historial: HistorialMediciones,
        notificador: NotificadorDiagnosticos,
    ):
        self._plantas = plantas
        self._servicio = servicio
        self._historial = historial
        self._notificador = notificador

    def ejecutar(
        self, usuario_id: int, planta_id: int, medicion: Medicion, origen: str, momento: datetime
    ) -> ResultadoMedicion:
        """El origen es el codigo del sensor que mando la medicion, y el momento, cuando la tomo."""
        planta = buscar_planta_propia(self._plantas, usuario_id, planta_id)
        diagnostico = self._servicio.diagnosticar(planta.especie, medicion)
        registro = RegistroMedicion.desde(diagnostico, planta.id, momento, origen)
        self._historial.agregar(planta, registro)
        self._avisar(planta, registro, diagnostico)
        return ResultadoMedicion(planta, diagnostico, registro)

    def _avisar(self, planta: Planta, registro: RegistroMedicion, diagnostico: Diagnostico) -> None:
        # La medicion importa mas que el aviso: si avisar falla, la medicion ya quedo
        # guardada y el sensor recibe su respuesta. El front la ve al volver a pedir sus plantas.
        try:
            self._notificador.publicar(planta.usuario_id, planta, registro, diagnostico)
        except Exception:
            _log.exception("No se pudo avisar en vivo la medicion de la planta %s.", planta.id)
