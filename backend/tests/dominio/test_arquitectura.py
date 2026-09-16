"""RA4 como prueba ejecutable: el dominio no conoce framework, persistencia, HTTP ni otras capas."""
import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

PROHIBIDOS_EN_DOMINIO = {
    # framework web y HTTP
    "flask", "flask_cors", "werkzeug", "http", "urllib", "requests", "json",
    # persistencia
    "csv", "pandas", "sqlite3", "sqlalchemy", "psycopg2",
    # otras capas
    "aplicacion", "presentacion", "infraestructura",
}


def _modulos_importados(archivo: Path) -> set[str]:
    # utf-8-sig: el Bloc de notas de Windows guarda con BOM y Python lo acepta.
    arbol = ast.parse(archivo.read_text(encoding="utf-8-sig"))
    modulos = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            modulos.update(alias.name.split(".")[0] for alias in nodo.names)
        elif isinstance(nodo, ast.ImportFrom) and nodo.module and nodo.level == 0:
            modulos.add(nodo.module.split(".")[0])
    return modulos


def _violaciones(archivos, prohibidos):
    encontradas = {archivo.name: sorted(_modulos_importados(archivo) & prohibidos) for archivo in archivos}
    return {nombre: modulos for nombre, modulos in encontradas.items() if modulos}


def test_el_dominio_no_importa_framework_persistencia_ni_otras_capas():
    archivos = sorted((BACKEND / "dominio").glob("*.py"))
    assert archivos, "no se encontraron archivos del dominio"

    assert _violaciones(archivos, PROHIBIDOS_EN_DOMINIO) == {}


def test_las_pruebas_de_dominio_no_dependen_de_infraestructura_ni_de_flask():
    """Si se borra la carpeta infraestructura, estas pruebas tienen que seguir pasando."""
    archivos = sorted((BACKEND / "tests" / "dominio").glob("*.py")) + [BACKEND / "tests" / "dobles.py"]

    assert _violaciones(archivos, {"flask", "infraestructura", "presentacion", "main"}) == {}
