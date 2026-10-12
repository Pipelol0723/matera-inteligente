"""Tabla de referencia en SQLite. Implementa los dos puertos del corte 1 y RegistroEspecies (RA5).

Es el escenario 5.2 del documento: reemplaza al repositorio CSV con una clase
nueva, y el dominio, la aplicacion y las rutas del corte 1 no cambian.
"""
import sqlite3
from collections import defaultdict
from collections.abc import Iterable

from dominio.errores_usuarios import EspecieYaExiste
from dominio.especie import Especie, normalizar_nombre
from dominio.parametros import PARAMETROS
from dominio.puertos import CatalogoEspecies, ConsultaRangos
from dominio.puertos_usuarios import RegistroEspecies
from dominio.rango import Rango
from infraestructura.sqlite.base_datos import BaseDatos

_PARAMETROS_POR_NOMBRE = {parametro.nombre: parametro for parametro in PARAMETROS}


class RepositorioEspeciesSqlite(ConsultaRangos, CatalogoEspecies, RegistroEspecies):
    def __init__(self, bd: BaseDatos):
        self._bd = bd

    def rangos_de(self, especie: str) -> Especie | None:
        nombre = normalizar_nombre(especie)
        with self._bd.conexion() as conexion:
            fila = conexion.execute(
                "SELECT nombre, nombre_cientifico FROM especie WHERE nombre = ?", (nombre,)
            ).fetchone()
            if fila is None:
                return None
            rangos = conexion.execute(
                "SELECT parametro, minimo, maximo FROM rango_optimo WHERE especie = ?", (nombre,)
            ).fetchall()
        return _especie(fila, rangos)

    def listar(self) -> list[Especie]:
        with self._bd.conexion() as conexion:
            especies = conexion.execute("SELECT nombre, nombre_cientifico FROM especie").fetchall()
            rangos = conexion.execute("SELECT especie, parametro, minimo, maximo FROM rango_optimo").fetchall()
        por_especie = defaultdict(list)
        for rango in rangos:
            por_especie[rango["especie"]].append(rango)
        return [_especie(fila, por_especie[fila["nombre"]]) for fila in especies]

    def agregar(self, especie: Especie) -> None:
        try:
            with self._bd.conexion() as conexion:
                conexion.execute(
                    "INSERT INTO especie (nombre, nombre_cientifico) VALUES (?, ?)",
                    (especie.nombre, especie.nombre_cientifico),
                )
                conexion.executemany(
                    "INSERT INTO rango_optimo (especie, parametro, minimo, maximo) VALUES (?, ?, ?, ?)",
                    [(especie.nombre, p.nombre, r.minimo, r.maximo) for p, r in especie.rangos.items()],
                )
        except sqlite3.IntegrityError as error:
            if "UNIQUE" in str(error):
                raise EspecieYaExiste(especie.nombre) from None
            raise


def _especie(fila: sqlite3.Row, rangos: Iterable[sqlite3.Row]) -> Especie:
    # Un rango de un parametro que el codigo aun no conoce (por ejemplo, el pH cargado
    # antes de agregarlo a parametros.py) se ignora en lugar de romper la consulta.
    return Especie(
        fila["nombre"],
        {
            _PARAMETROS_POR_NOMBRE[r["parametro"]]: Rango(r["minimo"], r["maximo"])
            for r in rangos
            if r["parametro"] in _PARAMETROS_POR_NOMBRE
        },
        fila["nombre_cientifico"],
    )
