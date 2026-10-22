"""Casos de uso de la cuenta: registrarse, iniciar y cerrar sesion, e identificar a quien pide algo.

Reciben textos ya sacados del borde (nunca un request) y trabajan solo con
puertos: no saben si la contrasena se cifra con PBKDF2, si el token es un JWT
ni si la sesion se guarda en SQLite. Fuera del inicio de sesion, que lo emite,
ninguno ve el token: reciben la identidad que el adaptador ya verifico.
"""
from datetime import timedelta

from dominio import puertos_entrada as entrada
from dominio.errores_usuarios import (
    CorreoInvalido,
    CorreoYaRegistrado,
    CredencialesInvalidas,
    CuentaDesactivada,
    SesionInvalida,
)
from dominio.identidad import IdentidadUsuario
from dominio.puertos_usuarios import (
    Cifrador,
    ConsultaCuentas,
    ConsultaPlantas,
    EmisorTokens,
    GeneradorSecretos,
    RegistroCuentas,
    Reloj,
    SesionesAbiertas,
)
from dominio.resultados import CuentaUsuario, SesionIniciada
from dominio.usuarios import Correo, PoliticaContrasena, Sesion, Usuario


class RegistrarUsuario(entrada.RegistrarUsuario):
    """Crea siempre un USUARIO comun: ninguna ruta de la API da el rol de admin."""

    def __init__(self, cuentas: ConsultaCuentas, registro: RegistroCuentas, cifrador: Cifrador):
        self._cuentas = cuentas
        self._registro = registro
        self._cifrador = cifrador

    def ejecutar(self, nombre: str, correo: str, contrasena: str) -> Usuario:
        correo_valido = Correo(correo)
        PoliticaContrasena.validar(contrasena)
        if self._cuentas.por_correo(correo_valido) is not None:
            raise CorreoYaRegistrado(correo_valido.valor)
        return self._registro.guardar(Usuario(None, correo_valido, nombre, self._cifrador.cifrar(contrasena)))


class IniciarSesion(entrada.IniciarSesion):
    """Aqui se emite el token de usuario: lo firma el puerto EmisorTokens con un id nuevo, y la sesion guarda ese id."""

    def __init__(
        self,
        cuentas: ConsultaCuentas,
        sesiones: SesionesAbiertas,
        cifrador: Cifrador,
        secretos: GeneradorSecretos,
        emisor: EmisorTokens,
        reloj: Reloj,
        duracion: timedelta,
    ):
        self._cuentas = cuentas
        self._sesiones = sesiones
        self._cifrador = cifrador
        self._secretos = secretos
        self._emisor = emisor
        self._reloj = reloj
        self._duracion = duracion

    def ejecutar(self, correo: str, contrasena: str) -> SesionIniciada:
        # El mismo error si el correo esta mal escrito, si no existe o si la contrasena
        # no coincide: el login no revela cuales correos tienen cuenta.
        try:
            correo_valido = Correo(correo)
        except CorreoInvalido:
            raise CredencialesInvalidas() from None
        usuario = self._cuentas.por_correo(correo_valido)
        if usuario is None or not self._cifrador.verificar(contrasena, usuario.hash_contrasena):
            raise CredencialesInvalidas()
        # Solo despues de verificar la contrasena se dice que la cuenta esta desactivada.
        if not usuario.activo:
            raise CuentaDesactivada()

        sesion = Sesion.abrir(self._secretos.nuevo(), usuario.id, self._reloj.ahora(), self._duracion)
        self._sesiones.abrir(sesion)
        token = self._emisor.emitir(IdentidadUsuario(usuario.id, sesion.token_id), sesion.vence_en)
        return SesionIniciada(token, sesion.vence_en, usuario)


class CerrarSesion(entrada.CerrarSesion):
    """El token ya firmado no se puede borrar, pero sin su sesion deja de servir."""

    def __init__(self, sesiones: SesionesAbiertas):
        self._sesiones = sesiones

    def ejecutar(self, identidad: IdentidadUsuario) -> None:
        self._sesiones.cerrar(identidad.token_id)


class IdentificarUsuario(entrada.IdentificarUsuario):
    """De la identidad verificada a un Usuario.

    El adaptador ya reviso la firma y el vencimiento del token. Aqui se rechaza una
    sesion cerrada, vencida o de una cuenta desactivada o borrada.
    """

    def __init__(self, sesiones: SesionesAbiertas, cuentas: ConsultaCuentas, reloj: Reloj):
        self._sesiones = sesiones
        self._cuentas = cuentas
        self._reloj = reloj

    def ejecutar(self, identidad: IdentidadUsuario) -> Usuario:
        sesion = self._sesiones.abierta(identidad.token_id)
        if sesion is None or sesion.usuario_id != identidad.usuario_id:
            raise SesionInvalida()
        if not sesion.vigente(self._reloj.ahora()):
            self._sesiones.cerrar(identidad.token_id)
            raise SesionInvalida()
        usuario = self._cuentas.por_id(sesion.usuario_id)
        if usuario is None or not usuario.activo:
            raise SesionInvalida()
        return usuario


class ConsultarCuenta(entrada.ConsultarCuenta):
    """Lo que muestra Mi cuenta: los datos del usuario y cuantas plantas tiene."""

    def __init__(self, plantas: ConsultaPlantas):
        self._plantas = plantas

    def ejecutar(self, usuario: Usuario) -> CuentaUsuario:
        return CuentaUsuario(usuario, len(self._plantas.de_usuario(usuario.id)))
