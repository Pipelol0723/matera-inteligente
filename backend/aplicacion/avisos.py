"""Un aviso, varios suscriptores: el WebSocket del front y el puntaje del juego (corte 3).

DiagnosticarPlantaDeUsuario avisa por un solo NotificadorDiagnosticos y no
cambia: main.py le entrega un AvisarATodos con todos los que quieren enterarse.
Agregar otro suscriptor, como Web Push, es sumarlo a la lista.
"""
import logging
from collections.abc import Iterable

from dominio.diagnostico import Diagnostico
from dominio.historial import RegistroMedicion
from dominio.plantas import Planta
from dominio.puertos_usuarios import NotificadorDiagnosticos

_log = logging.getLogger(__name__)


class AvisarATodos(NotificadorDiagnosticos):
    """Reparte el aviso en el orden en que recibio los suscriptores.

    Si uno falla, el error va al log y los demas igual reciben el aviso: si el
    WebSocket se cae, la lectura igual suma puntos, y al reves.
    """

    def __init__(self, suscriptores: Iterable[NotificadorDiagnosticos]):
        self._suscriptores = tuple(suscriptores)

    def publicar(self, usuario_id: int, planta: Planta, registro: RegistroMedicion, diagnostico: Diagnostico) -> None:
        for suscriptor in self._suscriptores:
            try:
                suscriptor.publicar(usuario_id, planta, registro, diagnostico)
            except Exception:
                _log.exception(
                    "%s no recibio el aviso de la medicion de la planta %s.", type(suscriptor).__name__, planta.id
                )
