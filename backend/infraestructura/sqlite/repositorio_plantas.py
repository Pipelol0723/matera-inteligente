"""Plantas y sensores en SQLite.

Toda consulta de plantas filtra por usuario_id, salvo vinculada_a(), que solo
se usa despues de verificar la clave del sensor y exige que el sensor sea el mismo.

SQLite no dice que restriccion fallo en un error de llave foranea, y reutiliza
el id mas alto despues de borrarlo. Por eso las escrituras que dependen de otra
fila la revisan dentro de la misma operacion.
"""
import sqlite3
from dataclasses import replace

from dominio.errores import EspecieNoSoportada
from dominio.errores_usuarios import ApodoRepetido, PlantaNoEncontrada, SensorYaVinculado, SesionInvalida
from dominio.plantas import Planta
from dominio.puertos_usuarios import RepositorioPlantas, RepositorioSensores
from dominio.sensores import CodigoSensor, Sensor
from infraestructura.sqlite.base_datos import BaseDatos

_COLUMNAS_PLANTA = "p.id, p.usuario_id, p.apodo, p.especie"
_INSERTAR_SENSOR = "INSERT INTO sensor (codigo, planta_id, hash_clave) VALUES (?, ?, ?)"


def _planta(fila: sqlite3.Row) -> Planta:
    return Planta(fila["id"], fila["usuario_id"], fila["apodo"], fila["especie"])


class RepositorioPlantasSqlite(RepositorioPlantas):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def guardar_con_sensor(self, planta: Planta, codigo: CodigoSensor, hash_clave: str) -> Planta:
        try:
            # Una sola transaccion: si el sensor no se puede guardar, la planta tampoco queda.
            with self._bd.conexion() as conexion:
                cursor = conexion.execute(
                    "INSERT INTO planta (usuario_id, especie, apodo) VALUES (?, ?, ?)",
                    (planta.usuario_id, planta.especie, planta.apodo),
                )
                conexion.execute(_INSERTAR_SENSOR, (codigo.valor, cursor.lastrowid, hash_clave))
        except sqlite3.IntegrityError as error:
            # La base respalda las tres reglas que ya revisa RegistrarPlanta.
            mensaje = str(error)
            if "sensor.codigo" in mensaje:
                raise SensorYaVinculado(codigo.valor) from None
            if "planta.usuario_id, planta.apodo" in mensaje:
                raise ApodoRepetido(planta.apodo) from None
            if "FOREIGN KEY" in mensaje:
                # Fallo la especie o el usuario: si la especie existe, a la cuenta la borraron
                # mientras se atendia la peticion.
                if self._especie_existe(planta.especie):
                    raise SesionInvalida() from None
                raise EspecieNoSoportada(planta.especie) from None
            raise
        return replace(planta, id=cursor.lastrowid)

    def _especie_existe(self, nombre: str) -> bool:
        with self._bd.conexion() as conexion:
            return conexion.execute("SELECT 1 FROM especie WHERE nombre = ?", (nombre,)).fetchone() is not None

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

    def vinculada_a(self, sensor: Sensor) -> Planta | None:
        # Codigo, planta y huella: si entre tanto se cambio el sensor, la fila ya no coincide.
        with self._bd.conexion() as conexion:
            fila = conexion.execute(
                f"SELECT {_COLUMNAS_PLANTA} FROM planta p JOIN sensor s ON s.planta_id = p.id"
                " WHERE s.codigo = ? AND s.planta_id = ? AND s.hash_clave = ?",
                (sensor.codigo.valor, sensor.planta_id, sensor.hash_clave),
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

    def reemplazar(self, usuario_id: int, sensor: Sensor) -> None:
        # Una sola transaccion: si el codigo nuevo es de otra planta, esta conserva su sensor. Las dos
        # sentencias exigen que la planta siga siendo del usuario: otra pestana pudo borrarla, y su id
        # pudo pasar a la planta nueva de otro usuario.
        propia = "SELECT id FROM planta WHERE id = ? AND usuario_id = ?"
        try:
            with self._bd.conexion() as conexion:
                conexion.execute(f"DELETE FROM sensor WHERE planta_id IN ({propia})", (sensor.planta_id, usuario_id))
                insertado = conexion.execute(
                    f"INSERT INTO sensor (codigo, planta_id, hash_clave) SELECT ?, id, ? FROM ({propia})",
                    (sensor.codigo.valor, sensor.hash_clave, sensor.planta_id, usuario_id),
                )
                if insertado.rowcount == 0:
                    raise PlantaNoEncontrada(sensor.planta_id)  # deshace el DELETE
        except sqlite3.IntegrityError as error:
            if "sensor.codigo" in str(error):
                raise SensorYaVinculado(sensor.codigo.valor) from None
            raise

    def _uno(self, consulta: str, parametros: tuple) -> Sensor | None:
        with self._bd.conexion() as conexion:
            fila = conexion.execute(consulta, parametros).fetchone()
        if fila is None:
            return None
        return Sensor(CodigoSensor(fila["codigo"]), fila["planta_id"], fila["hash_clave"])
