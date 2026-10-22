"""Lo que reporta un dispositivo: quien midio, cuando y que valores (R2).

Las reglas viven aqui y no en la ruta HTTP, para que cualquier entrada (HTTP
hoy, MQTT manana) las cumpla: la hora tiene zona horaria y no puede ser del
futuro. Los valores ya los revisa Medicion, con los limites fisicos de Lectura.
"""
from dataclasses import dataclass
from datetime import datetime, timedelta

from dominio.errores_usuarios import MomentoInvalido
from dominio.medicion import Medicion
from dominio.sensores import CodigoSensor

# El reloj de la placa y el del servidor nunca coinciden del todo: hasta 2 minutos de adelanto se aceptan.
ADELANTO_MAXIMO = timedelta(minutes=2)


@dataclass(frozen=True)
class ReporteDeDispositivo:
    dispositivo: CodigoSensor
    momento: datetime
    medicion: Medicion

    def __post_init__(self) -> None:
        if self.momento.utcoffset() is None:
            raise MomentoInvalido("La hora de la lectura no dice su zona horaria: use, por ejemplo, 2026-10-22T15:04:05Z.")

    def exigir_que_no_sea_futuro(self, ahora: datetime) -> None:
        if self.momento > ahora + ADELANTO_MAXIMO:
            raise MomentoInvalido(
                f"La hora de la lectura ({self.momento.isoformat()}) es posterior a la del servidor"
                f" ({ahora.isoformat()}): revise el reloj del dispositivo."
            )
