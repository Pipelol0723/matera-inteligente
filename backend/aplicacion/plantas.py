"""Casos de uso de las plantas de un usuario: registrar, listar y eliminar (seccion 5.3)."""
from dataclasses import dataclass

from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import ApodoRepetido, PlantaNoEncontrada
from dominio.historial import RegistroMedicion
from dominio.plantas import Planta
from dominio.puertos import ConsultaRangos
from dominio.puertos_usuarios import HistorialMediciones, RepositorioPlantas, RepositorioSensores
from dominio.sensores import Sensor
from dominio.usuarios import Usuario


def buscar_planta_propia(plantas: RepositorioPlantas, usuario_id: int, planta_id: int) -> Planta:
    """La planta solo se encuentra junto con su dueno. Una ajena da el mismo error que una inexistente."""
    planta = plantas.por_id(usuario_id, planta_id)
    if planta is None:
        raise PlantaNoEncontrada(planta_id)
    return planta


class RegistrarPlanta:
    """Usa el mismo puerto ConsultaRangos del corte 1 para saber si la especie existe."""

    def __init__(self, plantas: RepositorioPlantas, especies: ConsultaRangos):
        self._plantas = plantas
        self._especies = especies

    def ejecutar(self, usuario: Usuario, apodo: str, especie: str) -> Planta:
        nueva = Planta(None, usuario.id, apodo, especie)
        if self._especies.rangos_de(nueva.especie) is None:
            raise EspecieNoSoportada(especie)
        if any(propia.mismo_apodo(nueva.apodo) for propia in self._plantas.de_usuario(usuario.id)):
            raise ApodoRepetido(nueva.apodo)
        return self._plantas.guardar(nueva)


@dataclass(frozen=True)
class PlantaConEstado:
    """Una tarjeta de Mis materas: la planta, su sensor si tiene, y su ultima medicion si hay."""

    planta: Planta
    sensor: Sensor | None
    ultima_medicion: RegistroMedicion | None


class ListarPlantas:
    def __init__(self, plantas: RepositorioPlantas, sensores: RepositorioSensores, historial: HistorialMediciones):
        self._plantas = plantas
        self._sensores = sensores
        self._historial = historial

    def ejecutar(self, usuario: Usuario) -> list[PlantaConEstado]:
        return [
            PlantaConEstado(planta, self._sensores.de_planta(planta.id), self._historial.ultimo_de(planta.id))
            for planta in self._plantas.de_usuario(usuario.id)
        ]


class EliminarPlanta:
    """Borra la planta con su sensor y su historial."""

    def __init__(self, plantas: RepositorioPlantas):
        self._plantas = plantas

    def ejecutar(self, usuario: Usuario, planta_id: int) -> None:
        buscar_planta_propia(self._plantas, usuario.id, planta_id)
        self._plantas.eliminar(usuario.id, planta_id)
