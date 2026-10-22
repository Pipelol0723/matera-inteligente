"""Quien hace un pedido, ya verificado afuera del dominio.

El adaptador de entrada verifica el token (firma, vencimiento y alcance) con el
puerto VerificadorTokens y le entrega al nucleo solo esto. El dominio no sabe
que el token es un JWT ni que llego en una cabecera HTTP.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class IdentidadUsuario:
    """El dueno de una sesion. token_id es el id del token con que llego el pedido.

    El servidor guarda ese id mientras la sesion esta abierta: cerrar la sesion o
    desactivar la cuenta lo borra, y el token deja de servir aunque no haya vencido.
    """

    usuario_id: int
    token_id: str
