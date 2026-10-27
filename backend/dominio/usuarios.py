"""Cuentas de usuario: correo, rol, contrasena y sesion (corte 2).

Aqui vive la regla de permisos de todo el sistema, Usuario.exigir_admin().
Los casos de uso de administracion la llaman antes de hacer nada, asi que se
cumple igual si la orden llega por HTTP, por consola o por MQTT.
"""
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from enum import Enum

from dominio.errores_usuarios import (
    AccionSobreSiMismo,
    ContrasenaDebil,
    CorreoInvalido,
    CuentaDesactivada,
    NombreInvalido,
    PermisoDenegado,
)

# Algo antes de una arroba y un dominio con punto. No pretende cubrir todo el RFC 5322.
_FORMA_CORREO = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")
_LARGO_MAXIMO_CORREO = 254
NOMBRE_MAXIMO = 60


class Rol(str, Enum):
    USUARIO = "USUARIO"
    ADMIN = "ADMIN"


@dataclass(frozen=True)
class Correo:
    """Correo sin espacios a los lados y en minusculas: 'Ana@X.co ' y 'ana@x.co' son la misma cuenta."""

    valor: str

    def __post_init__(self) -> None:
        normalizado = self.valor.strip().lower()
        if len(normalizado) > _LARGO_MAXIMO_CORREO or not _FORMA_CORREO.fullmatch(normalizado):
            raise CorreoInvalido(self.valor)
        object.__setattr__(self, "valor", normalizado)


class PoliticaContrasena:
    MINIMO = 8

    @classmethod
    def validar(cls, texto: str) -> None:
        if len(texto) < cls.MINIMO:
            raise ContrasenaDebil(cls.MINIMO)


@dataclass(frozen=True)
class Usuario:
    """Una cuenta. El id es None hasta que el repositorio la guarda.

    Guarda la huella de la contrasena, nunca la contrasena: la calcula el
    puerto Cifrador, que vive fuera del dominio.
    """

    id: int | None
    correo: Correo
    nombre: str
    hash_contrasena: str
    rol: Rol = Rol.USUARIO
    activo: bool = True

    def __post_init__(self) -> None:
        nombre = " ".join(self.nombre.split())
        if not nombre or len(nombre) > NOMBRE_MAXIMO:
            raise NombreInvalido(NOMBRE_MAXIMO)
        object.__setattr__(self, "nombre", nombre)

    def es_admin(self) -> bool:
        return self.rol is Rol.ADMIN

    def exigir_admin(self) -> None:
        """La regla de permisos: solo un ADMIN pasa de aqui."""
        if not self.es_admin():
            raise PermisoDenegado()

    def exigir_activo(self) -> None:
        """Una cuenta desactivada no entra ni deja que sus sensores reporten: queda en pausa entera."""
        if not self.activo:
            raise CuentaDesactivada()

    def exigir_otro_usuario(self, usuario_id: int) -> None:
        """Un admin no actua sobre su propia cuenta. Asi siempre queda al menos un admin activo."""
        if usuario_id == self.id:
            raise AccionSobreSiMismo()

    def con_estado(self, activo: bool) -> "Usuario":
        return replace(self, activo=activo)

    def con_rol(self, rol: Rol) -> "Usuario":
        return replace(self, rol=rol)


@dataclass(frozen=True)
class ResumenUsuario:
    """Lo que el admin ve de cada cuenta: cuantas plantas tiene, no cuales."""

    id: int
    correo: str
    nombre: str
    rol: Rol
    activo: bool
    cantidad_plantas: int


@dataclass(frozen=True)
class Sesion:
    """Sesion abierta. Se guarda el id del token que la abrio, nunca el token: con el id se puede cerrar antes de que venza."""

    token_id: str
    usuario_id: int
    vence_en: datetime

    @classmethod
    def abrir(cls, token_id: str, usuario_id: int, ahora: datetime, duracion: timedelta) -> "Sesion":
        return cls(token_id, usuario_id, ahora + duracion)

    def vigente(self, ahora: datetime) -> bool:
        return ahora < self.vence_en
