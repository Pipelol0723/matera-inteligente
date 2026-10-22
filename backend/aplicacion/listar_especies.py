"""Caso de uso: listar las especies soportadas con sus rangos (RF5)."""
from dominio import puertos_entrada as entrada
from dominio.especie import Especie
from dominio.puertos import CatalogoEspecies


class ListarEspecies(entrada.ListarEspecies):
    def __init__(self, catalogo: CatalogoEspecies):
        self._catalogo = catalogo

    def ejecutar(self) -> list[Especie]:
        return sorted(self._catalogo.listar(), key=lambda especie: especie.nombre)
