"""Casos de uso del sensor: cambiarlo, canjear su clave por un token y registrar sus lecturas."""
from datetime import timedelta

from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.plantas import buscar_planta_propia
from dominio import puertos_entrada as entrada
from dominio.errores_usuarios import (
    ClaveSensorInvalida,
    CodigoSensorInvalido,
    CredencialDispositivoInvalida,
    DispositivoAjeno,
    SensorYaVinculado,
)
from dominio.identidad import IdentidadDispositivo
from dominio.puertos_usuarios import (
    ConsultaCuentas,
    ConsultaPlantas,
    CredencialesSensor,
    EmisorTokens,
    GeneradorSecretos,
    Reloj,
    SensoresVinculados,
)
from dominio.reportes import ReporteDeDispositivo
from dominio.resultados import ResultadoMedicion, SensorVinculado, TokenDispositivo
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Usuario


class ReemplazarSensor(entrada.ReemplazarSensor):
    """Cambia el sensor de una planta, o le da una clave nueva al mismo sensor si se perdio.

    La planta y su historial no cambian: el historial es de la planta, no del
    sensor. El codigo anterior queda libre, y su clave y su token dejan de servir.
    Tambien le da sensor a una matera creada antes de que fuera obligatorio.
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


class CanjearClaveDispositivo(entrada.CanjearClaveDispositivo):
    """Aqui se emite el token del dispositivo: la placa cambia su clave por un token de alcance «lecturas».

    La clave se muestra una sola vez, al crear la matera, y solo sirve para esto.
    Cada canje deja vigente solo el token nuevo, y cambiar el sensor de la planta
    deja sin efecto la clave y el token. Si el dueno de la planta esta desactivado,
    no hay canje.
    """

    def __init__(
        self,
        sensores: SensoresVinculados,
        credenciales: CredencialesSensor,
        plantas: ConsultaPlantas,
        cuentas: ConsultaCuentas,
        secretos: GeneradorSecretos,
        emisor: EmisorTokens,
        reloj: Reloj,
        duracion: timedelta,
    ):
        self._sensores = sensores
        self._credenciales = credenciales
        self._plantas = plantas
        self._cuentas = cuentas
        self._secretos = secretos
        self._emisor = emisor
        self._reloj = reloj
        self._duracion = duracion

    def ejecutar(self, codigo: str, clave: str) -> TokenDispositivo:
        # El mismo error si el codigo esta mal escrito, si no existe o si la clave no coincide.
        try:
            codigo_valido = CodigoSensor(codigo)
        except CodigoSensorInvalido:
            raise ClaveSensorInvalida() from None
        sensor = self._sensores.por_codigo(codigo_valido)
        if sensor is None or not self._secretos.coincide(clave, sensor.hash_clave):
            raise ClaveSensorInvalida()
        # Solo despues de verificar la clave se dice que la cuenta esta desactivada, como al iniciar sesion.
        planta = self._plantas.por_id(sensor.planta_id)
        dueno = self._cuentas.por_id(planta.usuario_id) if planta is not None else None
        if dueno is None:
            raise ClaveSensorInvalida()
        dueno.exigir_activo()
        token_id = self._secretos.nuevo()
        # Solo si el sensor sigue siendo el que se verifico: si mientras tanto se cambio, la clave ya no vale.
        if not self._credenciales.renovar(sensor, token_id):
            raise ClaveSensorInvalida()
        vence_en = self._reloj.ahora() + self._duracion
        return TokenDispositivo(self._emisor.emitir(IdentidadDispositivo(codigo_valido, token_id), vence_en), vence_en)


class RegistrarLectura(entrada.RegistrarLectura):
    """R2: un dispositivo reporta una lectura de su planta.

    Recibe la identidad que el adaptador saco del token ya verificado, nunca el
    token. No inventa un diagnostico propio: le pasa la medicion a
    DiagnosticarPlantaDeUsuario, con el dueno de la planta, la hora del reporte y
    el codigo del sensor como origen. Si el dueno de la planta esta desactivado,
    la lectura no se guarda, aunque el token siga vigente.
    """

    def __init__(
        self,
        credenciales: CredencialesSensor,
        cuentas: ConsultaCuentas,
        diagnosticar: DiagnosticarPlantaDeUsuario,
        reloj: Reloj,
    ):
        self._credenciales = credenciales
        self._cuentas = cuentas
        self._diagnosticar = diagnosticar
        self._reloj = reloj

    def ejecutar(self, identidad: IdentidadDispositivo, reporte: ReporteDeDispositivo) -> ResultadoMedicion:
        planta = self._credenciales.planta_con_token(identidad.codigo, identidad.token_id)
        if planta is None:
            raise CredencialDispositivoInvalida()  # otro canje o un cambio de sensor lo dejo sin efecto
        dueno = self._cuentas.por_id(planta.usuario_id)
        if dueno is None:
            raise CredencialDispositivoInvalida()
        dueno.exigir_activo()
        if reporte.dispositivo != identidad.codigo:
            raise DispositivoAjeno(identidad.codigo.valor, reporte.dispositivo.valor)
        reporte.exigir_que_no_sea_futuro(self._reloj.ahora())
        return self._diagnosticar.ejecutar(
            planta.usuario_id, planta.id, reporte.medicion, origen=identidad.codigo.valor, momento=reporte.momento
        )
