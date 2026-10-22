"""Casos de uso de administracion: cuentas y especies, solo para ADMIN.

Cada uno empieza con actor.exigir_admin(): la regla vive en el dominio y se
cumple igual si la orden llega por HTTP, por consola o por MQTT. La ruta no
decide nada, y esconder la pestana en el front es solo comodidad.
"""
from collections.abc import Sequence

from dominio import puertos_entrada as entrada
from dominio.errores import ParametroSinRango
from dominio.errores_usuarios import EspecieYaExiste, UsuarioNoEncontrado
from dominio.especie import Especie
from dominio.parametros import Parametro
from dominio.puertos import ConsultaRangos
from dominio.puertos_usuarios import RegistroEspecies, RepositorioSesiones, RepositorioUsuarios
from dominio.usuarios import Correo, ResumenUsuario, Rol, Usuario


def _buscar_usuario(usuarios: RepositorioUsuarios, usuario_id: int) -> Usuario:
    usuario = usuarios.por_id(usuario_id)
    if usuario is None:
        raise UsuarioNoEncontrado(usuario_id)
    return usuario


class ListarUsuarios(entrada.ListarUsuarios):
    """El admin ve cuantas plantas tiene cada usuario, pero no cuales."""

    def __init__(self, usuarios: RepositorioUsuarios):
        self._usuarios = usuarios

    def ejecutar(self, actor: Usuario) -> list[ResumenUsuario]:
        actor.exigir_admin()
        return sorted(self._usuarios.resumenes(), key=lambda resumen: resumen.id)


class CambiarEstadoUsuario(entrada.CambiarEstadoUsuario):
    """Desactivar cierra todas las sesiones de la cuenta en ese momento."""

    def __init__(self, usuarios: RepositorioUsuarios, sesiones: RepositorioSesiones):
        self._usuarios = usuarios
        self._sesiones = sesiones

    def ejecutar(self, actor: Usuario, usuario_id: int, activo: bool) -> Usuario:
        actor.exigir_admin()
        actor.exigir_otro_usuario(usuario_id)
        actualizado = self._usuarios.guardar(_buscar_usuario(self._usuarios, usuario_id).con_estado(activo))
        if not activo:
            self._sesiones.eliminar_de_usuario(usuario_id)
        return actualizado


class CambiarRol(entrada.CambiarRol):
    def __init__(self, usuarios: RepositorioUsuarios):
        self._usuarios = usuarios

    def ejecutar(self, actor: Usuario, usuario_id: int, rol: Rol) -> Usuario:
        actor.exigir_admin()
        actor.exigir_otro_usuario(usuario_id)
        return self._usuarios.guardar(_buscar_usuario(self._usuarios, usuario_id).con_rol(rol))


class EliminarUsuario(entrada.EliminarUsuario):
    """Borra la cuenta con sus sesiones, plantas, sensores e historial (lo hace el repositorio)."""

    def __init__(self, usuarios: RepositorioUsuarios):
        self._usuarios = usuarios

    def ejecutar(self, actor: Usuario, usuario_id: int) -> None:
        actor.exigir_admin()
        actor.exigir_otro_usuario(usuario_id)
        _buscar_usuario(self._usuarios, usuario_id)
        self._usuarios.eliminar(usuario_id)


class AgregarEspecie(entrada.AgregarEspecie):
    """Una especie nueva usa las mismas clases Especie y Rango del corte 1.

    Debe traer un rango por cada parametro que se mide: si no, sus plantas no
    se podrian diagnosticar.
    """

    def __init__(self, especies: ConsultaRangos, registro: RegistroEspecies, parametros: Sequence[Parametro]):
        self._especies = especies
        self._registro = registro
        self._parametros = tuple(parametros)

    def ejecutar(self, actor: Usuario, especie: Especie) -> Especie:
        actor.exigir_admin()
        for parametro in self._parametros:
            if parametro not in especie.rangos:
                raise ParametroSinRango(especie.nombre, parametro)
        if self._especies.rangos_de(especie.nombre) is not None:
            raise EspecieYaExiste(especie.nombre)
        self._registro.agregar(especie)
        return especie


class ConvertirEnAdministrador(entrada.ConvertirEnAdministrador):
    """Da el rol de admin a una cuenta ya registrada. Solo lo usa crear_admin.py, desde la consola.

    No pide actor: es la forma de tener el primer admin, y la API no lo expone.
    """

    def __init__(self, usuarios: RepositorioUsuarios):
        self._usuarios = usuarios

    def ejecutar(self, correo: str) -> Usuario:
        usuario = self._usuarios.por_correo(Correo(correo))
        if usuario is None:
            raise UsuarioNoEncontrado(correo)
        return self._usuarios.guardar(usuario.con_rol(Rol.ADMIN))
