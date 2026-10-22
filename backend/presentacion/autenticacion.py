"""Borde de la sesion: el decorador que verifica el JWT de usuario de cada ruta que exige sesion.

Aqui se verifica el token: se saca de la cabecera Authorization y el puerto
VerificadorTokens revisa su firma, su vencimiento y su alcance. Desde aqui
hacia adentro nadie ve el token: IdentificarUsuario recibe la identidad ya
verificada, y la ruta recibe el Usuario. Las rutas no leen cabeceras.
"""
from collections.abc import Callable
from functools import wraps

from flask import request

from dominio import puertos_entrada as entrada
from dominio.errores_usuarios import SesionInvalida
from dominio.identidad import IdentidadUsuario
from dominio.puertos_usuarios import VerificadorTokens


def token_bearer(error: type[Exception] = SesionInvalida) -> str:
    """El texto despues de 'Bearer '. Sin cabecera, o con otro esquema, lanza error (por defecto, sesion invalida)."""
    esquema, _, token = request.headers.get("Authorization", "").partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        raise error()
    return token.strip()


class Autenticacion:
    def __init__(self, verificador: VerificadorTokens, identificar: entrada.IdentificarUsuario):
        self._verificador = verificador
        self._identificar = identificar

    def con_usuario(self, vista: Callable) -> Callable:
        """La ruta recibe el Usuario de la sesion como primer argumento."""

        @wraps(vista)
        def envuelta(*args, **kwargs):
            return vista(self._identificar.ejecutar(self._identidad()), *args, **kwargs)

        return envuelta

    def con_identidad(self, vista: Callable) -> Callable:
        """La ruta recibe la identidad, despues de revisar que la sesion siga abierta. Solo la usa cerrar sesion."""

        @wraps(vista)
        def envuelta(*args, **kwargs):
            identidad = self._identidad()
            self._identificar.ejecutar(identidad)  # 401 si la sesion ya se cerro
            return vista(identidad, *args, **kwargs)

        return envuelta

    def _identidad(self) -> IdentidadUsuario:
        return self._verificador.verificar_usuario(token_bearer())
