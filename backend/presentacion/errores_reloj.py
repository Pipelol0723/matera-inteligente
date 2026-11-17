"""Traduce el error del reloj del juego a una respuesta HTTP, con el cuerpo uniforme {error, mensaje, detalle}."""
from flask import Blueprint

from dominio.reloj_juego import RelojDeJuegoInvalido
from presentacion.errores_http import respuesta_error


def registrar_manejadores_reloj(bp: Blueprint) -> None:
    """Como los demas manejadores, vale para toda la aplicacion."""

    @bp.app_errorhandler(RelojDeJuegoInvalido)
    def reloj_invalido(error: RelojDeJuegoInvalido):
        return respuesta_error(400, "RELOJ_INVALIDO", str(error), {"campo": "minutosPorDia"})
