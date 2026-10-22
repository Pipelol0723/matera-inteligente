"""Puertos del corte 2: lo que cuentas, plantas, sensores, historial y el aviso en vivo necesitan de afuera.

Igual que dominio.puertos, se declaran aqui y se implementan en
infraestructura (RA5, DIP). En las pruebas, cada uno tiene un doble en memoria.
Cada puerto dice una cosa que el nucleo necesita, con pocos metodos: quien solo
consulta cuentas no depende de como se borran (ISP). Un mismo adaptador puede
implementar varios, como RepositorioEspeciesSqlite implementa los de especies.
"""
from abc import ABC, abstractmethod
from datetime import datetime

from dominio.diagnostico import Diagnostico
from dominio.especie import Especie
from dominio.historial import RegistroMedicion
from dominio.identidad import IdentidadUsuario
from dominio.plantas import Planta
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Correo, ResumenUsuario, Sesion, Usuario


class RegistroEspecies(ABC):
    """Agregar una especie a la tabla de referencia. Solo lo usa la administracion."""

    @abstractmethod
    def agregar(self, especie: Especie) -> None:
        """Lanza EspecieYaExiste si ya hay una con ese nombre.

        Lanza TablaDeSoloLectura si la tabla de referencia no admite cambios,
        como la copia en CSV.
        """


# --- Cuentas y sesiones ---


class ConsultaCuentas(ABC):
    """Buscar una cuenta: para registrarse, iniciar sesion e identificar a quien pide algo."""

    @abstractmethod
    def por_correo(self, correo: Correo) -> Usuario | None: ...

    @abstractmethod
    def por_id(self, usuario_id: int) -> Usuario | None: ...


class RegistroCuentas(ABC):
    @abstractmethod
    def guardar(self, usuario: Usuario) -> Usuario:
        """Crea la cuenta si no tiene id y la devuelve con su id; si lo tiene, la actualiza.

        Lanza CorreoYaRegistrado si el correo ya es de otra cuenta.
        """

    @abstractmethod
    def eliminar(self, usuario_id: int) -> None:
        """Borra la cuenta con sus sesiones, plantas, sensores e historial."""


class ListadoCuentas(ABC):
    """Lo que ve el admin de todas las cuentas: cuantas plantas tiene cada una, no cuales."""

    @abstractmethod
    def resumenes(self) -> list[ResumenUsuario]: ...


class SesionesAbiertas(ABC):
    """Las sesiones que siguen abiertas, por el id del token que las abrio."""

    @abstractmethod
    def abrir(self, sesion: Sesion) -> None: ...

    @abstractmethod
    def abierta(self, token_id: str) -> Sesion | None:
        """La sesion de ese token, o None si nunca se abrio o ya se cerro."""

    @abstractmethod
    def cerrar(self, token_id: str) -> None: ...

    @abstractmethod
    def cerrar_de_usuario(self, usuario_id: int) -> None:
        """Cierra todas las sesiones de la cuenta, por ejemplo al desactivarla."""


# --- Plantas y sensores ---


class ConsultaPlantas(ABC):
    """Buscar plantas. No decide quien puede verlas: eso lo decide Planta.exigir_dueno, en el dominio."""

    @abstractmethod
    def por_id(self, planta_id: int) -> Planta | None:
        """La planta con ese id, sea de quien sea, o None si no existe."""

    @abstractmethod
    def de_usuario(self, usuario_id: int) -> list[Planta]: ...


class RegistroPlantas(ABC):
    @abstractmethod
    def guardar_con_sensor(self, planta: Planta, codigo: CodigoSensor, hash_clave: str) -> Planta:
        """Crea la planta junto con su sensor y la devuelve con su id.

        Una matera no existe sin sensor: es una sola operacion, y si una de las dos
        partes falla no se guarda ninguna. Lanza ApodoRepetido si el dueno ya usa ese
        apodo y SensorYaVinculado si el codigo es de otra planta.
        """

    @abstractmethod
    def eliminar(self, planta: Planta) -> None:
        """Borra la planta con su sensor y su historial.

        Recibe la planta que ya se leyo: si mientras tanto otra pestana la borro y su
        id paso a una planta nueva, esa otra no se toca.
        """


class SensoresVinculados(ABC):
    @abstractmethod
    def por_codigo(self, codigo: CodigoSensor) -> Sensor | None: ...

    @abstractmethod
    def de_planta(self, planta_id: int) -> Sensor | None: ...

    @abstractmethod
    def reemplazar(self, planta: Planta, sensor: Sensor) -> None:
        """Deja este sensor como el unico de la planta: quita el anterior, si habia, y guarda este.

        Es una sola operacion, y solo si la planta sigue siendo la que se leyo: si
        mientras tanto se borro, lanza PlantaNoEncontrada. Si algo falla, la planta
        conserva el sensor que tenia. El historial no se toca. Lanza
        SensorYaVinculado si el codigo es de otra planta.
        """

    @abstractmethod
    def planta_de(self, sensor: Sensor) -> Planta | None:
        """La planta de este sensor, que ya se autentico con su clave.

        None si el sensor cambio desde que se leyo (otra clave u otra planta): asi
        una clave recien revocada no puede escribir en la planta que tomo su codigo.
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


# --- Tokens: los implementa la libreria JWT, en infraestructura ---


class EmisorTokens(ABC):
    """Firma el token de una identidad. El caso de uso lo pide; no sabe que es un JWT."""

    @abstractmethod
    def emitir(self, identidad: IdentidadUsuario, vence_en: datetime) -> str: ...


class VerificadorTokens(ABC):
    """Revisa la firma, el vencimiento y el alcance de un token, y dice de quien es.

    Lo usan los adaptadores de entrada (el decorador de las rutas y el WebSocket):
    el caso de uso recibe la identidad, nunca el token.
    """

    @abstractmethod
    def verificar_usuario(self, token: str) -> IdentidadUsuario:
        """Lanza SesionInvalida si el token no sirve y AlcanceInvalido si no es de un usuario."""


# --- Criptografia y tiempo ---


class Cifrador(ABC):
    """Huella lenta de una contrasena, con sal. Nunca se guarda la contrasena."""

    @abstractmethod
    def cifrar(self, texto: str) -> str: ...

    @abstractmethod
    def verificar(self, texto: str, cifrado: str) -> bool: ...


class GeneradorSecretos(ABC):
    """Ids de token y claves de sensor, aleatorios. La clave del sensor se guarda solo como huella."""

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
