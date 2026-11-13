"""Adaptador del puerto EstadosDePrueba: en la memoria del servidor, no en la base.

El modo prueba es para mirar los dibujos en una demo, no un dato de la matera:
no se guarda en SQLite y se borra solo al reiniciar el backend. Cada estado se
guarda con el dueno de la planta: si SQLite reutiliza el id de una planta
borrada para otra cuenta, la nueva no hereda la prueba. Las peticiones llegan
en varios hilos, por eso el candado.
"""
from threading import Lock

from dominio.modo_prueba import EstadoDePrueba
from dominio.plantas import Planta
from dominio.puertos_prueba import EstadosDePrueba


class EstadosDePruebaEnMemoria(EstadosDePrueba):
    def __init__(self) -> None:
        self._estados: dict[int, tuple[int, EstadoDePrueba]] = {}
        self._candado = Lock()

    def de_planta(self, planta: Planta) -> EstadoDePrueba | None:
        with self._candado:
            guardado = self._estados.get(planta.id)
        if guardado is None:
            return None
        dueno, estado = guardado
        return estado if dueno == planta.usuario_id else None

    def guardar(self, planta: Planta, estado: EstadoDePrueba) -> None:
        with self._candado:
            self._estados[planta.id] = (planta.usuario_id, estado)

    def quitar(self, planta_id: int) -> None:
        with self._candado:
            self._estados.pop(planta_id, None)
