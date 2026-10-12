"""Pruebas del repositorio de especies en SQLite. Usan un archivo temporal: no cuentan como pruebas de dominio."""
import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from dominio.errores_usuarios import EspecieYaExiste
from dominio.especie import Especie
from dominio.parametros import HUMEDAD, LUZ, PARAMETROS, TEMPERATURA
from dominio.rango import Rango
from infraestructura.sqlite import BaseDatos, RepositorioEspeciesSqlite

# Lo que tenia backend/datos/especies.csv antes de pasar a SQLite: carga.sql tiene que dar lo mismo.
CSV_ANTERIOR = {
    "sansevieria": ("Dracaena trifasciata", (20, 45), (270, 2150), (21, 32)),
    "potos": ("Epipremnum aureum", (40, 70), (270, 2150), (16, 29)),
    "suculenta": ("Crassula ovata", (10, 30), (10760, 107640), (10, 24)),
    "helecho": ("Nephrolepis exaltata", (60, 85), (1080, 5380), (10, 22)),
    "lavanda": ("Lavandula angustifolia", (25, 50), (10760, 107640), (13, 27)),
}


def _repositorio(tmp_path, carga=True):
    bd = BaseDatos(tmp_path / "matera.sqlite")
    return RepositorioEspeciesSqlite(bd.preparar() if carga else bd.preparar(carga=None))


def _lavanda_nueva():
    return Especie("Lavanda Dentata", {HUMEDAD: Rango(20, 40), LUZ: Rango(10760, 107640), TEMPERATURA: Rango(12, 28)})


def test_carga_sql_deja_las_mismas_especies_y_rangos_que_tenia_el_csv(tmp_path):
    especies = _repositorio(tmp_path).listar()

    assert {
        e.nombre: (e.nombre_cientifico, *((e.rangos[p].minimo, e.rangos[p].maximo) for p in PARAMETROS))
        for e in especies
    } == CSV_ANTERIOR


def test_busca_la_especie_sin_importar_mayusculas_ni_tildes(tmp_path):
    repositorio = _repositorio(tmp_path)

    especie = repositorio.rangos_de(" POTÓS ")

    assert especie is not None and especie.nombre == "potos"
    assert repositorio.rangos_de("cactus") is None


def test_una_especie_agregada_se_lee_igual_y_aparece_en_el_catalogo(tmp_path):
    repositorio = _repositorio(tmp_path, carga=False)

    repositorio.agregar(_lavanda_nueva())

    leida = repositorio.rangos_de("lavanda dentata")
    assert leida.rangos[TEMPERATURA] == Rango(12, 28)
    assert [e.nombre for e in repositorio.listar()] == ["lavanda dentata"]


def test_agregar_una_especie_repetida_es_un_error(tmp_path):
    repositorio = _repositorio(tmp_path)

    with pytest.raises(EspecieYaExiste):
        repositorio.agregar(Especie("Potos", {HUMEDAD: Rango(1, 2)}))


def test_preparar_otra_vez_no_duplica_ni_borra_las_especies_agregadas(tmp_path):
    _repositorio(tmp_path).agregar(_lavanda_nueva())

    especies = _repositorio(tmp_path).listar()

    assert len(especies) == len(CSV_ANTERIOR) + 1


def test_la_base_no_acepta_un_rango_con_el_minimo_mayor_que_el_maximo(tmp_path):
    bd = BaseDatos(tmp_path / "matera.sqlite").preparar()

    with pytest.raises(sqlite3.IntegrityError), bd.conexion() as conexion:
        conexion.execute("INSERT INTO rango_optimo VALUES ('potos', 'ph', 7, 5)")


def test_cada_conexion_activa_las_llaves_foraneas(tmp_path):
    bd = BaseDatos(tmp_path / "matera.sqlite").preparar()

    with bd.conexion() as conexion:
        assert conexion.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_se_puede_usar_desde_varios_hilos_como_lo_hace_flask(tmp_path):
    repositorio = _repositorio(tmp_path)

    with ThreadPoolExecutor(max_workers=4) as hilos:
        cantidades = list(hilos.map(lambda _: len(repositorio.listar()), range(8)))

    assert cantidades == [len(CSV_ANTERIOR)] * 8


def test_crea_la_carpeta_de_la_base_si_no_existe(tmp_path):
    ruta = tmp_path / "otra" / "carpeta" / "matera.sqlite"

    BaseDatos(ruta).preparar()

    assert ruta.exists()
