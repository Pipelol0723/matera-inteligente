"""Plantas y sensores en SQLite.

Toda consulta de plantas filtra por usuario_id, salvo vinculada_a(), que solo
se usa despues de verificar la clave del sensor.
"""
import sqlite3
from dataclasses import replace

from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import ApodoRepetido, PlantaConSensor, SensorYaVinculado
from dominio.plantas import Planta
from dominio.puertos_usuarios import RepositorioPlantas, RepositorioSensores
from dominio.sensores import CodigoSensor, Sensor
from infraestructura.sqlite.base_datos import BaseDatos

_COLUMNAS_PLANTA = "p.id, p.usuario_id, p.apodo, p.especie"


def _planta(fila: sqlite3.Row) -> Planta:
    return Planta(fila["id"], fila["usuario_id"], fila["apodo"], fila["especie"])


class RepositorioPlantasSqlite(RepositorioPlantas):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def guardar(self, planta: Planta) -> Planta:
        try:
            with self._bd.conexion() as conexion:
                cursor = conexion.execute(
                    "INSERT INTO planta (usuario_id, especie, apodo) VALUES (?, ?, ?)",
                    (planta.usuario_id, planta.especie, planta.apodo),
                )
        except sqlite3.IntegrityError as error:
            # La base respalda las dos reglas que ya revisa RegistrarPlanta.
            if "UNIQUE" in str(error):
                raise ApodoRepetido(planta.apodo) from None
            if "FOREIGN KEY" in str(error):
                raise EspecieNoSoportada(planta.especie) from None
            raise
        return replace(planta, id=cursor.lastrowid)

    def de_usuario(self, usuario_id: int) -> list[Planta]:
        with self._bd.conexion() as conexion:
            filas = conexion.execute(
                f"SELECT {_COLUMNAS_PLANTA} FROM planta p WHERE p.usuario_id = ? ORDER BY p.id", (usuario_id,)
            ).fetchall()
        return [_planta(fila) for fila in filas]

    def por_id(self, usuario_id: int, planta_id: int) -> Planta | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(
                f"SELECT {_COLUMNAS_PLANTA} FROM planta p WHERE p.id = ? AND p.usuario_id = ?", (planta_id, usuario_id)
            ).fetchone()
        return _planta(fila) if fila else None

    def vinculada_a(self, codigo: CodigoSensor) -> Planta | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(
                f"SELECT {_COLUMNAS_PLANTA} FROM planta p JOIN sensor s ON s.planta_id = p.id WHERE s.codigo = ?",
                (codigo.valor,),
            ).fetchone()
        return _planta(fila) if fila else None

    def eliminar(self, usuario_id: int, planta_id: int) -> None:
        # El sensor y el historial de la planta se borran en cascada.
        with self._bd.conexion() as conexion:
            conexion.execute("DELETE FROM planta WHERE id = ? AND usuario_id = ?", (planta_id, usuario_id))


class RepositorioSensoresSqlite(RepositorioSensores):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def por_codigo(self, codigo: CodigoSensor) -> Sensor | None:
        return self._uno("SELECT codigo, planta_id, hash_clave FROM sensor WHERE codigo = ?", (codigo.valor,))

    def de_planta(self, planta_id: int) -> Sensor | None:
        return self._uno("SELECT codigo, planta_id, hash_clave FROM sensor WHERE planta_id = ?", (planta_id,))

    def guardar(self, sensor: Sensor) -> None:
        try:
            with self._bd.conexion() as conexion:
                conexion.execute(
                    "INSERT INTO sensor (codigo, planta_id, hash_clave) VALUES (?, ?, ?)",
                    (sensor.codigo.valor, sensor.planta_id, sensor.hash_clave),
                )
        except sqlite3.IntegrityError as error:
            if "sensor.planta_id" in str(error):
                raise PlantaConSensor(sensor.planta_id) from None
            if "sensor.codigo" in str(error):
                raise SensorYaVinculado(sensor.codigo.valor) from None
            raise

    def eliminar(self, codigo: CodigoSensor) -> None:
        with self._bd.conexion() as conexion:
            conexion.execute("DELETE FROM sensor WHERE codigo = ?", (codigo.valor,))

    def _uno(self, consulta: str, parametros: tuple) -> Sensor | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(consulta, parametros).fetchone()
        if fila is None:
            return None
        return Sensor(CodigoSensor(fila["codigo"]), fila["planta_id"], fila["hash_clave"])
