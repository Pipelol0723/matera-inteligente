"""Lo que entra y sale de los puertos de entrada: datos sin logica, hechos con tipos del dominio.

Antes vivian junto a cada caso de uso, en aplicacion/. Pasaron aqui porque los
puertos de entrada (dominio.puertos_entrada) los nombran, y el dominio no
importa aplicacion/.
"""
from dataclasses import dataclass
from datetime import datetime

from dominio.diagnostico import Diagnostico
from dominio.historial import RegistroMedicion
from dominio.medicion import Medicion
from dominio.plantas import Planta
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Usuario


@dataclass(frozen=True)
class SolicitudDiagnostico:
    """Pedido ya validado. No importa si llego por HTTP, por MQTT o desde una prueba."""

    especie: str
    medicion: Medicion


@dataclass(frozen=True)
class SesionIniciada:
    """El token firmado solo sale de aqui; la base guarda solo su id, para poder cerrar la sesion."""

    token: str
    vence_en: datetime
    usuario: Usuario


@dataclass(frozen=True)
class CuentaUsuario:
    usuario: Usuario
    cantidad_plantas: int


@dataclass(frozen=True)
class SensorVinculado:
    """La planta con el codigo de su sensor. La clave sale solo de aqui, una vez: la base guarda su huella."""

    planta: Planta
    codigo: CodigoSensor
    clave: str


@dataclass(frozen=True)
class PlantaConEstado:
    """Una tarjeta de Mis materas: la planta, su sensor y su ultima medicion si hay.

    El sensor solo falta en las materas creadas antes de que fuera obligatorio.
    """

    planta: Planta
    sensor: Sensor | None
    ultima_medicion: RegistroMedicion | None


@dataclass(frozen=True)
class HistorialPlanta:
    planta: Planta
    registros: list[RegistroMedicion]


@dataclass(frozen=True)
class TokenDispositivo:
    """El token que recibe la placa a cambio de su clave, y cuando vence: antes de eso, canjea otra vez."""

    token: str
    vence_en: datetime


@dataclass(frozen=True)
class ResultadoMedicion:
    planta: Planta
    diagnostico: Diagnostico
    registro: RegistroMedicion
