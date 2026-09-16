"""Caso de uso: listar los parametros que se miden, con su unidad y sus limites fisicos.

Con esto el front arma los campos de la medicion y sus escalas sin escribir
parametros ni limites a mano: agregar el pH al dominio no obliga a tocarlo.
"""
from collections.abc import Sequence

from dominio.parametros import Parametro


class ListarParametros:
    def __init__(self, parametros: Sequence[Parametro]):
        self._parametros = tuple(parametros)

    def ejecutar(self) -> tuple[Parametro, ...]:
        return self._parametros
