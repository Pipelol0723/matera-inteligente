"""Historial de mediciones en SQLite: una fila por medicion y una por cada lectura."""
import sqlite3
from datetime import datetime, timezone

from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.historial import LecturaRegistrada, RegistroMedicion
from dominio.parametros import PARAMETROS
from dominio.puertos_usuarios import HistorialMediciones
from infraestructura.sqlite.base_datos import BaseDatos

_PARAMETROS_POR_NOMBRE = {parametro.nombre: parametro for parametro in PARAMETROS}


class HistorialMedicionesSqlite(HistorialMediciones):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def agregar(self, registro: RegistroMedicion) -> None:
        with self._bd.conexion() as conexion:
            cursor = conexion.execute(
                "INSERT INTO medicion (planta_id, momento, estado, origen) VALUES (?, ?, ?, ?)",
                (registro.planta_id, _texto(registro.momento), registro.estado.value, registro.origen),
            )
            conexion.executemany(
                "INSERT INTO lectura (medicion_id, parametro, valor, estado) VALUES (?, ?, ?, ?)",
                [(cursor.lastrowid, l.parametro.nombre, l.valor, l.estado.value) for l in registro.lecturas],
            )

    def de_planta(self, planta_id: int, limite: int) -> list[RegistroMedicion]:
        with self._bd.conexion() as conexion:
            mediciones = conexion.execute(
                "SELECT id, planta_id, momento, estado, origen FROM medicion "
                "WHERE planta_id = ? ORDER BY momento DESC, id DESC LIMIT ?",
                (planta_id, limite),
            ).fetchall()
            ids = [m["id"] for m in mediciones]
            lecturas = conexion.execute(
                f"SELECT medicion_id, parametro, valor, estado FROM lectura "
                f"WHERE medicion_id IN ({', '.join('?' * len(ids))})",
                ids,
            ).fetchall() if ids else []
        por_medicion: dict[int, list[sqlite3.Row]] = {}
        for lectura in lecturas:
            por_medicion.setdefault(lectura["medicion_id"], []).append(lectura)
        return [_registro(m, por_medicion.get(m["id"], [])) for m in mediciones]

    def ultimo_de(self, planta_id: int) -> RegistroMedicion | None:
        recientes = self.de_planta(planta_id, 1)
        return recientes[0] if recientes else None


def _texto(momento: datetime) -> str:
    # Siempre en UTC y con microsegundos: asi el texto se ordena igual que la fecha, aunque el
    # dispositivo mande su hora con otra zona horaria.
    return momento.astimezone(timezone.utc).isoformat(timespec="microseconds")


def _registro(medicion: sqlite3.Row, lecturas: list[sqlite3.Row]) -> RegistroMedicion:
    # El orden de las lecturas es el del catalogo de parametros, no el de la base.
    orden = {nombre: i for i, nombre in enumerate(_PARAMETROS_POR_NOMBRE)}
    registradas = tuple(
        LecturaRegistrada(_PARAMETROS_POR_NOMBRE[l["parametro"]], l["valor"], EstadoParametro(l["estado"]))
        for l in sorted(lecturas, key=lambda l: orden.get(l["parametro"], len(orden)))
        if l["parametro"] in _PARAMETROS_POR_NOMBRE
    )
    return RegistroMedicion(
        medicion["planta_id"],
        datetime.fromisoformat(medicion["momento"]),
        EstadoGlobal(medicion["estado"]),
        registradas,
        medicion["origen"],
    )
