"""Puertos de entrada: lo que el nucleo ofrece a quien quiera usarlo.

Un adaptador de entrada (una ruta HTTP, el WebSocket, la consola o una prueba)
depende de estas clases y nunca del caso de uso concreto: main.py le entrega la
implementacion. Cada puerto tiene un solo metodo, ejecutar, y se llama igual
que el caso de uso de aplicacion/ que lo implementa y lo hereda.

Los puertos de salida, lo que el nucleo necesita de afuera, estan en
dominio.puertos y dominio.puertos_usuarios.
"""
from abc import ABC, abstractmethod

from dominio.diagnostico import Diagnostico
from dominio.especie import Especie
from dominio.identidad import IdentidadDispositivo, IdentidadUsuario
from dominio.parametros import Parametro
from dominio.reportes import ReporteDeDispositivo
from dominio.resultados import (
    CuentaUsuario,
    HistorialPlanta,
    PlantaConEstado,
    ResultadoMedicion,
    SensorVinculado,
    SesionIniciada,
    SolicitudDiagnostico,
    TokenDispositivo,
)
from dominio.usuarios import ResumenUsuario, Rol, Usuario

# Cuantos registros devuelve el historial si quien pregunta no dice cuantos.
LIMITE_HISTORIAL = 30


# --- Diagnostico publico (corte 1) ---


class DiagnosticarPlanta(ABC):
    """Diagnosticar una medicion contra los rangos de una especie, sin guardar nada."""

    @abstractmethod
    def ejecutar(self, solicitud: SolicitudDiagnostico) -> Diagnostico: ...


class ListarEspecies(ABC):
    @abstractmethod
    def ejecutar(self) -> list[Especie]: ...


class ListarParametros(ABC):
    @abstractmethod
    def ejecutar(self) -> tuple[Parametro, ...]: ...


# --- Cuenta ---


class RegistrarUsuario(ABC):
    @abstractmethod
    def ejecutar(self, nombre: str, correo: str, contrasena: str) -> Usuario: ...


class IniciarSesion(ABC):
    @abstractmethod
    def ejecutar(self, correo: str, contrasena: str) -> SesionIniciada: ...


class CerrarSesion(ABC):
    @abstractmethod
    def ejecutar(self, identidad: IdentidadUsuario) -> None: ...


class IdentificarUsuario(ABC):
    """De la identidad ya verificada al Usuario. Lo usan los adaptadores que exigen sesion.

    Recibe la identidad que saco el adaptador del token, nunca el token.
    """

    @abstractmethod
    def ejecutar(self, identidad: IdentidadUsuario) -> Usuario: ...


class ConsultarCuenta(ABC):
    @abstractmethod
    def ejecutar(self, usuario: Usuario) -> CuentaUsuario: ...


# --- Plantas, sensor e historial ---


class RegistrarPlanta(ABC):
    @abstractmethod
    def ejecutar(self, usuario: Usuario, apodo: str, especie: str, codigo: str) -> SensorVinculado: ...


class ListarPlantas(ABC):
    """El estado actual de cada planta del usuario: su ultima medicion."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario) -> list[PlantaConEstado]: ...


class EliminarPlanta(ABC):
    @abstractmethod
    def ejecutar(self, usuario: Usuario, planta_id: int) -> None: ...


class ReemplazarSensor(ABC):
    @abstractmethod
    def ejecutar(self, usuario: Usuario, planta_id: int, codigo: str) -> SensorVinculado: ...


class ConsultarHistorial(ABC):
    @abstractmethod
    def ejecutar(self, usuario: Usuario, planta_id: int, limite: int = LIMITE_HISTORIAL) -> HistorialPlanta: ...


# --- Dispositivos ---


class CanjearClaveDispositivo(ABC):
    """La placa cambia su clave por un token de alcance «lecturas»."""

    @abstractmethod
    def ejecutar(self, codigo: str, clave: str) -> TokenDispositivo: ...


class RegistrarLectura(ABC):
    """Un dispositivo, ya autenticado con su token, reporta una lectura de su planta (R2)."""

    @abstractmethod
    def ejecutar(self, identidad: IdentidadDispositivo, reporte: ReporteDeDispositivo) -> ResultadoMedicion: ...


# --- Administracion: cada caso de uso exige un actor ADMIN ---


class ListarUsuarios(ABC):
    @abstractmethod
    def ejecutar(self, actor: Usuario) -> list[ResumenUsuario]: ...


class CambiarEstadoUsuario(ABC):
    @abstractmethod
    def ejecutar(self, actor: Usuario, usuario_id: int, activo: bool) -> Usuario: ...


class CambiarRol(ABC):
    @abstractmethod
    def ejecutar(self, actor: Usuario, usuario_id: int, rol: Rol) -> Usuario: ...


class EliminarUsuario(ABC):
    @abstractmethod
    def ejecutar(self, actor: Usuario, usuario_id: int) -> None: ...


class AgregarEspecie(ABC):
    @abstractmethod
    def ejecutar(self, actor: Usuario, especie: Especie) -> Especie: ...


class ConvertirEnAdministrador(ABC):
    """Solo para la consola: es la forma de tener el primer admin."""

    @abstractmethod
    def ejecutar(self, correo: str) -> Usuario: ...
