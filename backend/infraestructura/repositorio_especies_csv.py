"""Tabla de referencia leida desde un CSV. Implementa los dos puertos del dominio (RA5).

Es el unico archivo del proyecto que sabe que existe un CSV. Pasar a una base
de datos es escribir otra clase con los mismos dos metodos y cambiar una linea
de main.py; el dominio no se toca.
"""
import csv
from pathlib import Path

from dominio.errores import RangoInvalido
from dominio.especie import Especie, normalizar_nombre
from dominio.parametros import PARAMETROS
from dominio.puertos import CatalogoEspecies, ConsultaRangos
from dominio.rango import Rango


class ErrorTablaReferencia(Exception):
    """El CSV no existe o no tiene el formato esperado. Se lanza al arrancar."""


class RepositorioEspeciesCsv(ConsultaRangos, CatalogoEspecies):
    def __init__(self, ruta: str | Path):
        self._ruta = Path(ruta)
        self._especies = self._cargar()

    def rangos_de(self, especie: str) -> Especie | None:
        return self._especies.get(normalizar_nombre(especie))

    def listar(self) -> list[Especie]:
        return list(self._especies.values())

    def _cargar(self) -> dict[str, Especie]:
        try:
            # utf-8-sig: Excel agrega BOM al guardar CSV en UTF-8.
            with self._ruta.open(encoding="utf-8-sig", newline="") as archivo:
                lector = csv.DictReader(archivo)
                filas = list(lector)
                columnas = lector.fieldnames or []
        except FileNotFoundError:
            raise ErrorTablaReferencia(f"No existe la tabla de referencia {self._ruta}") from None

        # Las columnas salen del catalogo de parametros: un parametro nuevo solo
        # exige agregar sus columnas al archivo, no cambiar este codigo.
        esperadas = ["especie"] + [f"{p.nombre}_{limite}" for p in PARAMETROS for limite in ("min", "max")]
        faltantes = [columna for columna in esperadas if columna not in columnas]
        if faltantes:
            raise ErrorTablaReferencia(f"A {self._ruta} le faltan las columnas: {', '.join(faltantes)}")

        especies: dict[str, Especie] = {}
        for numero_fila, fila in enumerate(filas, start=2):
            try:
                rangos = {
                    p: Rango(float(fila[f"{p.nombre}_min"]), float(fila[f"{p.nombre}_max"]))
                    for p in PARAMETROS
                }
            except (TypeError, ValueError, RangoInvalido) as error:
                raise ErrorTablaReferencia(f"Fila {numero_fila} de {self._ruta}: {error}") from error
            # nombre_cientifico es opcional: si la columna no esta, queda vacio.
            especie = Especie(fila["especie"], rangos, fila.get("nombre_cientifico") or "")
            if especie.nombre in especies:
                raise ErrorTablaReferencia(f"Fila {numero_fila} de {self._ruta}: la especie '{especie.nombre}' está repetida")
            especies[especie.nombre] = especie
        return especies
