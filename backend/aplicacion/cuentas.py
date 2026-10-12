"""Casos de uso de la cuenta: registrarse, iniciar y cerrar sesion, e identificar por token.

Reciben textos ya sacados del borde (nunca un request) y trabajan solo con
puertos: no saben si la contrasena se cifra con PBKDF2 ni si la sesion se
guarda en SQLite.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from dominio.errores_usuarios import (
    CorreoInvalido,
    CorreoYaRegistrado,
    CredencialesInvalidas,
    CuentaDesactivada,
    SesionInvalida,
)
from dominio.puertos_usuarios import (
    Cifrador,
    GeneradorSecretos,
    Reloj,
    RepositorioPlantas,
    RepositorioSesiones,
    RepositorioUsuarios,
)
from dominio.usuarios import Correo, PoliticaContrasena, Sesion, Usuario


class RegistrarUsuario:
    """Crea siempre un USUARIO comun: ninguna ruta de la API da el rol de admin."""

    def __init__(self, usuarios: RepositorioUsuarios, cifrador: Cifrador):
        self._usuarios = usuarios
        self._cifrador = cifrador

    def ejecutar(self, nombre: str, correo: str, contrasena: str) -> Usuario:
        correo_valido = Correo(correo)
        PoliticaContrasena.validar(contrasena)
        if self._usuarios.por_correo(correo_valido) is not None:
            raise CorreoYaRegistrado(correo_valido.valor)
        return self._usuarios.guardar(Usuario(None, correo_valido, nombre, self._cifrador.cifrar(contrasena)))


@dataclass(frozen=True)
class SesionIniciada:
    """El token solo sale de aqui; la base guarda su huella."""

    token: str
    vence_en: datetime
    usuario: Usuario


class IniciarSesion:
    def __init__(
        self,
        usuarios: RepositorioUsuarios,
        sesiones: RepositorioSesiones,
        cifrador: Cifrador,
        secretos: GeneradorSecretos,
        reloj: Reloj,
        duracion: timedelta,
    ):
        self._usuarios = usuarios
        self._sesiones = sesiones
        self._cifrador = cifrador
        self._secretos = secretos
        self._reloj = reloj
        self._duracion = duracion

    def ejecutar(self, correo: str, contrasena: str) -> SesionIniciada:
        # El mismo error si el correo esta mal escrito, si no existe o si la contrasena
        # no coincide: el login no revela cuales correos tienen cuenta.
        try:
            correo_valido = Correo(correo)
        except CorreoInvalido:
            raise CredencialesInvalidas() from None
        usuario = self._usuarios.por_correo(correo_valido)
        if usuario is None or not self._cifrador.verificar(contrasena, usuario.hash_contrasena):
            raise CredencialesInvalidas()
        # Solo despues de verificar la contrasena se dice que la cuenta esta desactivada.
        if not usuario.activo:
            raise CuentaDesactivada()

        token = self._secretos.nuevo()
        sesion = Sesion.abrir(self._secretos.huella(token), usuario.id, self._reloj.ahora(), self._duracion)
        self._sesiones.guardar(sesion)
        return SesionIniciada(token, sesion.vence_en, usuario)


class CerrarSesion:
    def __init__(self, sesiones: RepositorioSesiones, secretos: GeneradorSecretos):
        self._sesiones = sesiones
        self._secretos = secretos

    def ejecutar(self, token: str) -> None:
        self._sesiones.eliminar(self._secretos.huella(token))


class IdentificarUsuario:
    """De un token a un Usuario. Aqui se rechaza una sesion vencida o de una cuenta desactivada."""

    def __init__(
        self,
        sesiones: RepositorioSesiones,
        usuarios: RepositorioUsuarios,
        secretos: GeneradorSecretos,
        reloj: Reloj,
    ):
        self._sesiones = sesiones
        self._usuarios = usuarios
        self._secretos = secretos
        self._reloj = reloj

    def ejecutar(self, token: str) -> Usuario:
        huella = self._secretos.huella(token)
        sesion = self._sesiones.por_huella(huella)
        if sesion is None:
            raise SesionInvalida()
        if not sesion.vigente(self._reloj.ahora()):
            self._sesiones.eliminar(huella)
            raise SesionInvalida()
        usuario = self._usuarios.por_id(sesion.usuario_id)
        if usuario is None or not usuario.activo:
            raise SesionInvalida()
        return usuario


@dataclass(frozen=True)
class CuentaUsuario:
    usuario: Usuario
    cantidad_plantas: int


class ConsultarCuenta:
    """Lo que muestra Mi cuenta: los datos del usuario y cuantas plantas tiene."""

    def __init__(self, plantas: RepositorioPlantas):
        self._plantas = plantas

    def ejecutar(self, usuario: Usuario) -> CuentaUsuario:
        return CuentaUsuario(usuario, len(self._plantas.de_usuario(usuario.id)))
