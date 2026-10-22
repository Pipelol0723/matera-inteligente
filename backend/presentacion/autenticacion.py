"""Borde de la sesion: saca el token de la cabecera Authorization.

Aqui el token deja de saber que existe HTTP: IdentificarUsuario recibe solo un
str y devuelve un Usuario del dominio. Las rutas no leen cabeceras.
"""
from flask import request

from dominio import puertos_entrada as entrada
from dominio.errores_usuarios import SesionInvalida
from dominio.usuarios import Usuario


class Autenticacion:
    def __init__(self, identificar: entrada.IdentificarUsuario):
        self._identificar = identificar

    def token(self) -> str:
        """El texto despues de 'Bearer '. Sin cabecera, o con otro esquema, es una sesion invalida."""
        esquema, _, token = request.headers.get("Authorization", "").partition(" ")
        if esquema.lower() != "bearer" or not token.strip():
            raise SesionInvalida()
        return token.strip()

    def usuario_actual(self) -> Usuario:
        return self._identificar.ejecutar(self.token())
