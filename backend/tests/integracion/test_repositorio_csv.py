"""Pruebas del adaptador CSV. Leen archivos: no cuentan como pruebas de dominio."""
from pathlib import Path

import pytest

from dominio.parametros import PARAMETROS
from infraestructura.repositorio_especies_csv import ErrorTablaReferencia, RepositorioEspeciesCsv

CSV_REAL = Path(__file__).resolve().parents[2] / "datos" / "especies.csv"
ENCABEZADO = "especie,humedad_min,humedad_max,luz_min,luz_max,temperatura_min,temperatura_max\n"


def _csv(tmp_path, contenido):
    ruta = tmp_path / "especies.csv"
    ruta.write_text(contenido, encoding="utf-8")
    return ruta


def test_la_tabla_real_tiene_al_menos_cinco_especies_con_todos_los_parametros():
    especies = RepositorioEspeciesCsv(CSV_REAL).listar()

    assert len(especies) >= 5
    for especie in especies:
        assert set(especie.rangos) == set(PARAMETROS)
        assert especie.nombre_cientifico


def test_el_nombre_cientifico_es_opcional(tmp_path):
    especie = RepositorioEspeciesCsv(_csv(tmp_path, ENCABEZADO + "potos,40,70,270,2150,16,29\n")).rangos_de("potos")

    assert especie is not None and especie.nombre_cientifico == ""


def test_lee_el_nombre_cientifico_si_la_columna_existe(tmp_path):
    contenido = (
        "especie,nombre_cientifico,humedad_min,humedad_max,luz_min,luz_max,temperatura_min,temperatura_max\n"
        "potos, Epipremnum aureum ,40,70,270,2150,16,29\n"
    )

    especie = RepositorioEspeciesCsv(_csv(tmp_path, contenido)).rangos_de("potos")

    assert especie.nombre_cientifico == "Epipremnum aureum"


def test_busca_la_especie_sin_importar_mayusculas_ni_tildes(tmp_path):
    repositorio = RepositorioEspeciesCsv(_csv(tmp_path, ENCABEZADO + "Potós,40,70,270,2150,16,29\n"))

    especie = repositorio.rangos_de(" POTOS ")

    assert especie is not None and especie.nombre == "potos"
    assert repositorio.rangos_de("cactus") is None


def test_si_el_archivo_no_existe_falla_al_arrancar(tmp_path):
    with pytest.raises(ErrorTablaReferencia, match="No existe"):
        RepositorioEspeciesCsv(tmp_path / "no-existe.csv")


def test_si_falta_una_columna_dice_cual(tmp_path):
    ruta = _csv(tmp_path, "especie,humedad_min,humedad_max,luz_min,luz_max\npotos,40,70,270,2150\n")

    with pytest.raises(ErrorTablaReferencia, match="temperatura_min, temperatura_max"):
        RepositorioEspeciesCsv(ruta)


@pytest.mark.parametrize(
    "fila",
    [
        "potos,cuarenta,70,270,2150,16,29\n",  # no numerico
        "potos,70,40,270,2150,16,29\n",  # minimo mayor que maximo
        "potos,40,70,270,2150,16\n",  # fila incompleta
    ],
)
def test_una_fila_invalida_indica_el_numero_de_fila(tmp_path, fila):
    with pytest.raises(ErrorTablaReferencia, match="Fila 2"):
        RepositorioEspeciesCsv(_csv(tmp_path, ENCABEZADO + fila))


def test_una_especie_repetida_es_un_error(tmp_path):
    ruta = _csv(tmp_path, ENCABEZADO + "potos,40,70,270,2150,16,29\nPotos,40,70,270,2150,16,29\n")

    with pytest.raises(ErrorTablaReferencia, match="repetida"):
        RepositorioEspeciesCsv(ruta)
