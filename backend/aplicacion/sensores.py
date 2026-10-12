"""Casos de uso del sensor: vincularlo a una planta, desvincularlo y recibir sus mediciones."""
from dataclasses import dataclass

from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario, ResultadoMedicion
from aplicacion.plantas import buscar_planta_propia
from dominio.errores_usuarios import (
    ClaveSensorInvalida,
    CodigoSensorInvalido,
    PlantaConSensor,
    PlantaSinSensor,
    SensorYaVinculado,
)
from dominio.medicion import Medicion
from dominio.plantas import Planta
from dominio.puertos_usuarios import GeneradorSecretos, RepositorioPlantas, RepositorioSensores
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Usuario


@dataclass(frozen=True)
class SensorVinculado:
    """La clave sale solo de aqui, una vez. La base guarda su huella."""

    planta: Planta
    codigo: CodigoSensor
    clave: str


class VincularSensor:
    def __init__(self, plantas: RepositorioPlantas, sensores: RepositorioSensores, secretos: GeneradorSecretos):
        self._plantas = plantas
        self._sensores = sensores
        self._secretos = secretos

    def ejecutar(self, usuario: Usuario, planta_id: int, codigo: str) -> SensorVinculado:
        planta = buscar_planta_propia(self._plantas, usuario.id, planta_id)
        codigo_valido = CodigoSensor(codigo)
        if self._sensores.de_planta(planta.id) is not None:
            raise PlantaConSensor(planta.id)
        if self._sensores.por_codigo(codigo_valido) is not None:
            raise SensorYaVinculado(codigo_valido.valor)

        clave = self._secretos.nuevo()
        self._sensores.guardar(Sensor(codigo_valido, planta.id, self._secretos.huella(clave)))
        return SensorVinculado(planta, codigo_valido, clave)


class DesvincularSensor:
    """Borra el sensor: su codigo queda libre para otra planta."""

    def __init__(self, plantas: RepositorioPlantas, sensores: RepositorioSensores):
        self._plantas = plantas
        self._sensores = sensores

    def ejecutar(self, usuario: Usuario, planta_id: int) -> None:
        planta = buscar_planta_propia(self._plantas, usuario.id, planta_id)
        sensor = self._sensores.de_planta(planta.id)
        if sensor is None:
            raise PlantaSinSensor(planta.id)
        self._sensores.eliminar(sensor.codigo)


class RecibirMedicionDeSensor:
    """El sensor no tiene sesion: se identifica con su codigo y su clave.

    No inventa un diagnostico propio: verifica la clave y le pasa la medicion a
    DiagnosticarPlantaDeUsuario, con el dueno de la planta y su codigo como origen.
    """

    def __init__(
        self,
        sensores: RepositorioSensores,
        plantas: RepositorioPlantas,
        secretos: GeneradorSecretos,
        diagnosticar: DiagnosticarPlantaDeUsuario,
    ):
        self._sensores = sensores
        self._plantas = plantas
        self._secretos = secretos
        self._diagnosticar = diagnosticar

    def ejecutar(self, codigo: str, clave: str, medicion: Medicion) -> ResultadoMedicion:
        # El mismo error si el codigo esta mal escrito, si no existe o si la clave no coincide.
        try:
            codigo_valido = CodigoSensor(codigo)
        except CodigoSensorInvalido:
            raise ClaveSensorInvalida() from None
        sensor = self._sensores.por_codigo(codigo_valido)
        if sensor is None or not self._secretos.coincide(clave, sensor.hash_clave):
            raise ClaveSensorInvalida()
        planta = self._plantas.vinculada_a(codigo_valido)
        if planta is None:
            raise ClaveSensorInvalida()
        return self._diagnosticar.ejecutar(planta.usuario_id, planta.id, medicion, origen=codigo_valido.valor)
