"""Casos de uso del sensor: cambiar el de una planta y recibir sus mediciones."""
from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.plantas import buscar_planta_propia
from dominio import puertos_entrada as entrada
from dominio.errores_usuarios import ClaveSensorInvalida, CodigoSensorInvalido, SensorYaVinculado
from dominio.medicion import Medicion
from dominio.puertos_usuarios import ConsultaPlantas, GeneradorSecretos, SensoresVinculados
from dominio.resultados import ResultadoMedicion, SensorVinculado
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Usuario


class ReemplazarSensor(entrada.ReemplazarSensor):
    """Cambia el sensor de una planta, o le da una clave nueva al mismo sensor si se perdio.

    La planta y su historial no cambian: el historial es de la planta, no del
    sensor. El codigo anterior queda libre y su clave deja de servir. Tambien
    le da sensor a una matera creada antes de que fuera obligatorio.
    """

    def __init__(self, plantas: ConsultaPlantas, sensores: SensoresVinculados, secretos: GeneradorSecretos):
        self._plantas = plantas
        self._sensores = sensores
        self._secretos = secretos

    def ejecutar(self, usuario: Usuario, planta_id: int, codigo: str) -> SensorVinculado:
        planta = buscar_planta_propia(self._plantas, usuario.id, planta_id)
        codigo_valido = CodigoSensor(codigo)
        en_uso = self._sensores.por_codigo(codigo_valido)
        if en_uso is not None and en_uso.planta_id != planta.id:
            raise SensorYaVinculado(codigo_valido.valor)

        clave = self._secretos.nuevo()
        self._sensores.reemplazar(planta, Sensor(codigo_valido, planta.id, self._secretos.huella(clave)))
        return SensorVinculado(planta, codigo_valido, clave)


class RecibirMedicionDeSensor(entrada.RecibirMedicionDeSensor):
    """El sensor no tiene sesion: se identifica con su codigo y su clave.

    No inventa un diagnostico propio: verifica la clave y le pasa la medicion a
    DiagnosticarPlantaDeUsuario, con el dueno de la planta y su codigo como origen.
    """

    def __init__(
        self,
        sensores: SensoresVinculados,
        secretos: GeneradorSecretos,
        diagnosticar: DiagnosticarPlantaDeUsuario,
    ):
        self._sensores = sensores
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
        # La planta de ese mismo sensor: si cambio desde que se verifico la clave, no se acepta.
        planta = self._sensores.planta_de(sensor)
        if planta is None:
            raise ClaveSensorInvalida()
        return self._diagnosticar.ejecutar(planta.usuario_id, planta.id, medicion, origen=codigo_valido.valor)
