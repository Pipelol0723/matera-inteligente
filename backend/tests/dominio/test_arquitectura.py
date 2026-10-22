"""RA4 como prueba ejecutable: el dominio no conoce framework, persistencia, HTTP ni otras capas."""
import ast
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]

PROHIBIDOS_EN_DOMINIO = {
    # framework web, HTTP y WebSocket
    "flask", "flask_cors", "flask_sock", "simple_websocket", "werkzeug", "http", "urllib", "requests", "json",
    # persistencia
    "csv", "pandas", "sqlite3", "sqlalchemy", "psycopg2",
    # criptografia: el dominio la pide por los puertos Cifrador y GeneradorSecretos
    "hashlib", "secrets", "hmac",
    # otras capas
    "aplicacion", "presentacion", "infraestructura",
}

# La aplicacion puede importar el dominio, pero no el framework, la persistencia ni las capas de afuera.
PROHIBIDOS_EN_APLICACION = PROHIBIDOS_EN_DOMINIO - {"aplicacion"}


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


def test_la_aplicacion_no_importa_framework_persistencia_criptografia_ni_capas_de_afuera():
    archivos = sorted((BACKEND / "aplicacion").glob("*.py"))
    assert archivos, "no se encontraron archivos de la aplicacion"

    assert _violaciones(archivos, PROHIBIDOS_EN_APLICACION) == {}


def test_presentacion_no_importa_infraestructura():
    """El WebSocket recibe los canales de main.py: la ruta no conoce la clase que guarda las conexiones."""
    archivos = sorted((BACKEND / "presentacion").glob("*.py"))
    assert archivos, "no se encontraron archivos de presentacion"

    assert _violaciones(archivos, {"infraestructura", "main"}) == {}


def test_los_adaptadores_de_entrada_conocen_los_puertos_y_no_los_casos_de_uso():
    """Las rutas y el WebSocket dependen de dominio.puertos_entrada: main.py les entrega la implementacion."""
    archivos = sorted((BACKEND / "presentacion").glob("*.py"))

    assert _violaciones(archivos, {"aplicacion"}) == {}


def test_las_pruebas_de_dominio_y_aplicacion_no_dependen_de_infraestructura_ni_de_flask():
    """Si se borra la carpeta infraestructura, estas pruebas tienen que seguir pasando."""
    archivos = (
        sorted((BACKEND / "tests" / "dominio").glob("*.py"))
        + sorted((BACKEND / "tests" / "aplicacion").glob("*.py"))
        + [BACKEND / "tests" / "dobles.py", BACKEND / "tests" / "dobles_usuarios.py"]
    )

    assert _violaciones(archivos, {"flask", "flask_sock", "infraestructura", "presentacion", "main"}) == {}
