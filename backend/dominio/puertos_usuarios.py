"""Puertos del corte 2: lo que cuentas, plantas, sensores, historial y el aviso en vivo necesitan de afuera.

Igual que dominio.puertos, se declaran aqui y se implementan en
infraestructura (RA5, DIP). En las pruebas, cada uno tiene un doble en memoria.
Los puertos del corte 1 no cambian: RegistroEspecies es una interfaz aparte,
asi que quien solo consulta especies sigue dependiendo solo de ConsultaRangos (ISP).
"""
from abc import ABC, abstractmethod
from datetime import datetime

from dominio.diagnostico import Diagnostico
from dominio.especie import Especie
from dominio.historial import RegistroMedicion
from dominio.plantas import Planta
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Correo, ResumenUsuario, Sesion, Usuario


class RegistroEspecies(ABC):
    """Agregar una especie a la tabla de referencia. Solo lo usa la administracion."""

    @abstractmethod
    def agregar(self, especie: Especie) -> None:
        """Lanza EspecieYaExiste si ya hay una con ese nombre."""


class RepositorioUsuarios(ABC):
    @abstractmethod
    def por_correo(self, correo: Correo) -> Usuario | None: ...

    @abstractmethod
    def por_id(self, usuario_id: int) -> Usuario | None: ...

    @abstractmethod
    def guardar(self, usuario: Usuario) -> Usuario:
        """Crea la cuenta si no tiene id y la devuelve con su id; si lo tiene, la actualiza.

        Lanza CorreoYaRegistrado si el correo ya es de otra cuenta.
        """

    @abstractmethod
    def resumenes(self) -> list[ResumenUsuario]: ...

    @abstractmethod
    def eliminar(self, usuario_id: int) -> None:
        """Borra la cuenta con sus sesiones, plantas, sensores e historial."""


class RepositorioSesiones(ABC):
    @abstractmethod
    def guardar(self, sesion: Sesion) -> None: ...

    @abstractmethod
    def por_huella(self, huella: str) -> Sesion | None: ...

    @abstractmethod
    def eliminar(self, huella: str) -> None: ...

    @abstractmethod
    def eliminar_de_usuario(self, usuario_id: int) -> None: ...


class RepositorioPlantas(ABC):
    """Aqui vive el aislamiento entre usuarios: no hay forma de pedir una planta sin decir de quien es."""

    @abstractmethod
    def guardar_con_sensor(self, planta: Planta, codigo: CodigoSensor, hash_clave: str) -> Planta:
        """Crea la planta junto con su sensor y la devuelve con su id.

        Una matera no existe sin sensor: es una sola operacion, y si una de las dos
        partes falla no se guarda ninguna. Lanza ApodoRepetido si el dueno ya usa ese
        apodo y SensorYaVinculado si el codigo es de otra planta.
        """

    @abstractmethod
    def de_usuario(self, usuario_id: int) -> list[Planta]: ...

    @abstractmethod
    def por_id(self, usuario_id: int, planta_id: int) -> Planta | None:
        """None si la planta no existe o si es de otro usuario."""

    @abstractmethod
    def vinculada_a(self, sensor: Sensor) -> Planta | None:
        """La planta de este sensor, que ya se autentico con su clave.

        None si el sensor cambio desde que se leyo (otra clave u otra planta): asi
        una clave recien revocada no puede escribir en la planta que tomo su codigo.
        """

    @abstractmethod
    def eliminar(self, usuario_id: int, planta_id: int) -> None:
        """Borra la planta con su sensor y su historial."""


class RepositorioSensores(ABC):
    @abstractmethod
    def por_codigo(self, codigo: CodigoSensor) -> Sensor | None: ...

    @abstractmethod
    def de_planta(self, planta_id: int) -> Sensor | None: ...

    @abstractmethod
    def reemplazar(self, usuario_id: int, sensor: Sensor) -> None:
        """Deja este sensor como el unico de su planta: quita el anterior, si habia, y guarda este.

        Es una sola operacion, y solo si la planta sigue siendo de ese usuario: si
        mientras tanto se borro, lanza PlantaNoEncontrada. Si algo falla, la planta
        conserva el sensor que tenia. El historial no se toca. Lanza
        SensorYaVinculado si el codigo es de otra planta.
        """


class HistorialMediciones(ABC):
    @abstractmethod
    def agregar(self, registro: RegistroMedicion) -> None: ...

    @abstractmethod
    def de_planta(self, planta_id: int, limite: int) -> list[RegistroMedicion]:
        """Los registros mas recientes primero, como maximo `limite`."""

    @abstractmethod
    def ultimo_de(self, planta_id: int) -> RegistroMedicion | None: ...


class NotificadorDiagnosticos(ABC):
    """Avisa al dueno de una planta que llego una medicion, para que su pantalla se actualice sola.

    Hoy lo implementa un WebSocket (infraestructura.tiempo_real); cambiarlo por
    MQTT o por un correo seria escribir otra implementacion, sin tocar el caso de uso.
    """

    @abstractmethod
    def publicar(self, usuario_id: int, planta: Planta, registro: RegistroMedicion, diagnostico: Diagnostico) -> None:
        """Se llama despues de guardar la medicion. Si el dueno no tiene la pantalla abierta, no hace nada."""


class Cifrador(ABC):
    """Huella lenta de una contrasena, con sal. Nunca se guarda la contrasena."""

    @abstractmethod
    def cifrar(self, texto: str) -> str: ...

    @abstractmethod
    def verificar(self, texto: str, cifrado: str) -> bool: ...


class GeneradorSecretos(ABC):
    """Tokens de sesion y claves de sensor: aleatorios, y guardados solo como huella."""

    @abstractmethod
    def nuevo(self) -> str: ...

    @abstractmethod
    def huella(self, secreto: str) -> str: ...

    @abstractmethod
    def coincide(self, secreto: str, huella: str) -> bool:
        """Compara en tiempo constante."""


class Reloj(ABC):
    """La hora actual, para que las pruebas puedan fijarla."""

    @abstractmethod
    def ahora(self) -> datetime: ...
