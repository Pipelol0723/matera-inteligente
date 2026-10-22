"""Casos de uso de las plantas de un usuario: registrar, listar y eliminar (seccion 5.3)."""
from dominio import puertos_entrada as entrada
from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import ApodoRepetido, PlantaNoEncontrada, SensorYaVinculado
from dominio.plantas import Planta
from dominio.puertos import ConsultaRangos
from dominio.puertos_usuarios import GeneradorSecretos, HistorialMediciones, RepositorioPlantas, RepositorioSensores
from dominio.resultados import PlantaConEstado, SensorVinculado
from dominio.sensores import CodigoSensor
from dominio.usuarios import Usuario


def buscar_planta_propia(plantas: RepositorioPlantas, usuario_id: int, planta_id: int) -> Planta:
    """La planta solo se encuentra junto con su dueno. Una ajena da el mismo error que una inexistente."""
    planta = plantas.por_id(usuario_id, planta_id)
    if planta is None:
        raise PlantaNoEncontrada(planta_id)
    return planta


class RegistrarPlanta(entrada.RegistrarPlanta):
    """Una matera nace con su sensor: la planta y el sensor se guardan juntos.

    Usa el mismo puerto ConsultaRangos del corte 1 para saber si la especie existe.
    """

    def __init__(
        self,
        plantas: RepositorioPlantas,
        sensores: RepositorioSensores,
        especies: ConsultaRangos,
        secretos: GeneradorSecretos,
    ):
        self._plantas = plantas
        self._sensores = sensores
        self._especies = especies
        self._secretos = secretos

    def ejecutar(self, usuario: Usuario, apodo: str, especie: str, codigo: str) -> SensorVinculado:
        nueva = Planta(None, usuario.id, apodo, especie)
        codigo_valido = CodigoSensor(codigo)
        if self._especies.rangos_de(nueva.especie) is None:
            raise EspecieNoSoportada(especie)
        if any(propia.mismo_apodo(nueva.apodo) for propia in self._plantas.de_usuario(usuario.id)):
            raise ApodoRepetido(nueva.apodo)
        if self._sensores.por_codigo(codigo_valido) is not None:
            raise SensorYaVinculado(codigo_valido.valor)

        clave = self._secretos.nuevo()
        planta = self._plantas.guardar_con_sensor(nueva, codigo_valido, self._secretos.huella(clave))
        return SensorVinculado(planta, codigo_valido, clave)


class ListarPlantas(entrada.ListarPlantas):
    def __init__(self, plantas: RepositorioPlantas, sensores: RepositorioSensores, historial: HistorialMediciones):
        self._plantas = plantas
        self._sensores = sensores
        self._historial = historial

    def ejecutar(self, usuario: Usuario) -> list[PlantaConEstado]:
        return [
            PlantaConEstado(planta, self._sensores.de_planta(planta.id), self._historial.ultimo_de(planta.id))
            for planta in self._plantas.de_usuario(usuario.id)
        ]


class EliminarPlanta(entrada.EliminarPlanta):
    """Borra la planta con su sensor y su historial."""

    def __init__(self, plantas: RepositorioPlantas):
        self._plantas = plantas

    def ejecutar(self, usuario: Usuario, planta_id: int) -> None:
        buscar_planta_propia(self._plantas, usuario.id, planta_id)
        self._plantas.eliminar(usuario.id, planta_id)
