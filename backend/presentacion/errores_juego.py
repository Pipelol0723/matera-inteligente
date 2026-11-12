"""Traduce los errores del juego (corte 3) a respuestas HTTP, con el cuerpo uniforme {error, mensaje, detalle}.

Los errores del apodo de jugador tienen codigos propios, distintos de los del
apodo de una planta (PARAMETRO_INVALIDO y APODO_REPETIDO): en dominio hay
clases con el mismo nombre, por eso se importa dominio.errores_juego como modulo.
"""
from flask import Blueprint

from dominio import errores_juego
from dominio.errores import ErrorDominio
from presentacion.errores_http import respuesta_error

# Error del dominio -> (estado HTTP, codigo de error).
_TABLA: dict[type[ErrorDominio], tuple[int, str]] = {
    errores_juego.ApodoInvalido: (400, "APODO_JUGADOR_INVALIDO"),
    # Quien no participa no ve la tabla: tiene sesion, pero no permiso para esto.
    errores_juego.ParticipacionRequerida: (403, "PARTICIPACION_REQUERIDA"),
    errores_juego.ApodoRepetido: (409, "APODO_JUGADOR_REPETIDO"),
}


def registrar_manejadores_juego(bp: Blueprint) -> None:
    """Como los demas manejadores, valen para toda la aplicacion."""
    for clase, (estado, codigo) in _TABLA.items():
        bp.app_errorhandler(clase)(_manejador(estado, codigo))


def _manejador(estado: int, codigo: str):
    def manejar(error: ErrorDominio):
        return respuesta_error(estado, codigo, str(error), _detalle(error))

    return manejar


def _detalle(error: ErrorDominio) -> dict:
    if isinstance(error, errores_juego.ApodoInvalido):
        return {"campo": "apodo", "motivo": "invalido", "minimo": error.minimo, "maximo": error.maximo}
    if isinstance(error, errores_juego.ApodoRepetido):
        return {"campo": "apodo", "apodo": error.apodo}
    return {}
