"""Tabla de referencia en un CSV: el adaptador del corte 1, que vuelve en la fase 2 (R4).

Es el unico archivo del proyecto que sabe que existe un CSV. MATERA_TABLA_REFERENCIA
elige en main.py si la tabla sale de aqui o de SQLite; el dominio no se entera.

El CSV es una copia de la base, de solo lectura:
- RepositorioEspeciesCsv lo lee e implementa los dos puertos de consulta del corte 1.
- EspeciesDeSoloLectura cumple RegistroEspecies cuando la tabla es el CSV: no agrega nada.
- escribir_csv y RegistroEspeciesConCopiaCsv lo mantienen igual a la base: el comando
  exportar_especies_csv.py lo escribe, y en modo BD se vuelve a escribir cada vez que el
  admin agrega una especie.
- exigir_copia_al_dia impide arrancar en modo CSV con una copia distinta de la base.
"""
import csv
import logging
import math
import os
from collections.abc import Iterable
from pathlib import Path

from dominio.errores import RangoInvalido
from dominio.errores_usuarios import TablaDeSoloLectura
from dominio.especie import Especie, normalizar_nombre
from dominio.parametros import PARAMETROS
from dominio.puertos import CatalogoEspecies, ConsultaRangos
from dominio.puertos_usuarios import RegistroEspecies
from dominio.rango import Rango

_log = logging.getLogger(__name__)
_COLUMNAS = ["especie", "nombre_cientifico"] + [f"{p.nombre}_{limite}" for p in PARAMETROS for limite in ("min", "max")]


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


def exigir_copia_al_dia(copia: CatalogoEspecies, base: CatalogoEspecies, ruta: Path) -> None:
    """En modo CSV, la copia tiene que tener las mismas especies y rangos que la base.

    Si le faltara una especie, una planta de esa especie dejaria de recibir lecturas; si
    sobrara una, se podria diagnosticar pero no crear una planta con ella (la llave foranea
    de la base la rechaza). Por eso el backend no arranca hasta que se regenere la copia.
    """
    en_copia = {especie.nombre: especie for especie in copia.listar()}
    en_base = {especie.nombre: especie for especie in base.listar()}
    diferencias = [
        f"{titulo}: {', '.join(nombres)}"
        for titulo, nombres in (
            ("faltan", sorted(en_base.keys() - en_copia.keys())),
            ("sobran", sorted(en_copia.keys() - en_base.keys())),
            ("con otros datos", sorted(n for n in en_base.keys() & en_copia.keys() if not _iguales(en_base[n], en_copia[n]))),
        )
        if nombres
    ]
    if diferencias:
        raise ErrorTablaReferencia(
            f"La copia {ruta} no es igual a la tabla de la base ({'; '.join(diferencias)}). "
            "Regenerela con: python exportar_especies_csv.py"
        )


def _iguales(una: Especie, otra: Especie) -> bool:
    # El CSV guarda los limites con 15 cifras significativas: se comparan con esa tolerancia.
    return una.nombre_cientifico == otra.nombre_cientifico and all(
        math.isclose(getattr(una.rango_de(p), limite), getattr(otra.rango_de(p), limite), rel_tol=1e-12, abs_tol=1e-12)
        for p in PARAMETROS
        for limite in ("minimo", "maximo")
    )


class EspeciesDeSoloLectura(RegistroEspecies):
    """RegistroEspecies cuando la tabla es el CSV: la copia no se edita, se regenera desde la base."""

    def agregar(self, especie: Especie) -> None:
        raise TablaDeSoloLectura()


def escribir_csv(especies: Iterable[Especie], ruta: Path) -> int:
    """Escribe la tabla en el CSV, ordenada por nombre, y devuelve cuantas especies escribio.

    Escribe primero un archivo temporal y despues lo pone en su lugar: quien lea el
    CSV nunca ve uno a medio escribir.
    """
    ordenadas = sorted(especies, key=lambda especie: especie.nombre)
    temporal = ruta.with_name(ruta.name + ".tmp")
    ruta.parent.mkdir(parents=True, exist_ok=True)
    with temporal.open("w", encoding="utf-8", newline="") as archivo:
        escritor = csv.writer(archivo, lineterminator="\n")
        escritor.writerow(_COLUMNAS)
        for especie in ordenadas:
            limites = [
                f"{valor:.15g}"
                for p in PARAMETROS
                for valor in (especie.rango_de(p).minimo, especie.rango_de(p).maximo)
            ]
            escritor.writerow([especie.nombre, especie.nombre_cientifico, *limites])
    os.replace(temporal, ruta)
    return len(ordenadas)


class RegistroEspeciesConCopiaCsv(RegistroEspecies):
    """Envuelve el RegistroEspecies de la base: despues de agregar, vuelve a escribir la copia en CSV.

    Asi el adaptador SQLite no sabe que el CSV existe. Si escribir la copia falla, la
    especie ya quedo en la base y la peticion no falla: el comando exportar_especies_csv.py
    la deja al dia.
    """

    def __init__(self, registro: RegistroEspecies, catalogo: CatalogoEspecies, ruta: Path):
        self._registro = registro
        self._catalogo = catalogo
        self._ruta = ruta

    def agregar(self, especie: Especie) -> None:
        self._registro.agregar(especie)
        try:
            escribir_csv(self._catalogo.listar(), self._ruta)
        except OSError:
            _log.exception("La especie %s quedo en la base, pero no se pudo escribir la copia %s.", especie.nombre, self._ruta)
