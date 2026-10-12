"""Sensor de una planta: un dispositivo con codigo y clave propios (corte 2).

El sensor no inicia sesion: se identifica con su codigo y su clave. La clave
se muestra una sola vez al vincularlo; aqui solo se guarda su huella.
"""
import re
from dataclasses import dataclass

from dominio.errores_usuarios import CodigoSensorInvalido

_FORMA_CODIGO = re.compile(r"MT-\d{4}-[A-Z]{2}")


@dataclass(frozen=True)
class CodigoSensor:
    """Codigo impreso en el dispositivo, con la forma MT-0000-XX. Se acepta en minusculas."""

    valor: str

    def __post_init__(self) -> None:
        normalizado = self.valor.strip().upper()
        if not _FORMA_CODIGO.fullmatch(normalizado):
            raise CodigoSensorInvalido(self.valor)
        object.__setattr__(self, "valor", normalizado)


@dataclass(frozen=True)
class Sensor:
    """Un sensor vinculado. Existe solo mientras esta vinculado a una planta."""

    codigo: CodigoSensor
    planta_id: int
    hash_clave: str
