"""Quien hace un pedido, ya verificado afuera del dominio.

El adaptador de entrada verifica el token (firma, vencimiento y alcance) con el
puerto VerificadorTokens y le entrega al nucleo solo esto. El dominio no sabe
que el token es un JWT ni que llego en una cabecera HTTP.
"""
from dataclasses import dataclass

from dominio.sensores import CodigoSensor


@dataclass(frozen=True)
class IdentidadUsuario:
    """El dueno de una sesion. token_id es el id del token con que llego el pedido.

    El servidor guarda ese id mientras la sesion esta abierta: cerrar la sesion o
    desactivar la cuenta lo borra, y el token deja de servir aunque no haya vencido.
    """

    usuario_id: int
    token_id: str


@dataclass(frozen=True)
class IdentidadDispositivo:
    """Un sensor que se autentico con su token. Solo puede reportar lecturas de su planta.

    token_id es el id del ultimo token que se le entrego a cambio de su clave: un
    canje nuevo, o cambiar el sensor de la planta, deja sin efecto los anteriores.
    """

    codigo: CodigoSensor
    token_id: str
