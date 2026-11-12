"""Adaptador del puerto EstadosDePrueba: en la memoria del servidor, no en la base.

El modo prueba es para mirar los dibujos en una demo, no un dato de la matera:
no se guarda en SQLite y se borra solo al reiniciar el backend. Las peticiones
llegan en varios hilos, por eso el candado.
"""
from threading import Lock

from dominio.modo_prueba import EstadoDePrueba
from dominio.puertos_prueba import EstadosDePrueba


class EstadosDePruebaEnMemoria(EstadosDePrueba):
    def __init__(self) -> None:
        self._estados: dict[int, EstadoDePrueba] = {}
        self._candado = Lock()

    def de_planta(self, planta_id: int) -> EstadoDePrueba | None:
        with self._candado:
            return self._estados.get(planta_id)

    def guardar(self, planta_id: int, estado: EstadoDePrueba) -> None:
        with self._candado:
            self._estados[planta_id] = estado

    def quitar(self, planta_id: int) -> None:
        with self._candado:
            self._estados.pop(planta_id, None)
