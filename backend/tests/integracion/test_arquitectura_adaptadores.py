"""Reglas de arquitectura que miran la carpeta infraestructura: cada libreria vive en un solo adaptador.

Estan aqui y no en tests/dominio porque necesitan que exista infraestructura/: las
pruebas de dominio y aplicacion tienen que seguir pasando aunque esa carpeta se borre.
"""
from tests.dominio.test_arquitectura import BACKEND, _modulos_importados


def test_solo_el_adaptador_de_tokens_importa_la_libreria_jwt():
    """Ni el dominio, ni los casos de uso, ni el decorador de las rutas conocen JWT: lo piden por los puertos."""
    archivos = [archivo for archivo in sorted(BACKEND.rglob("*.py")) if "tests" not in archivo.relative_to(BACKEND).parts]

    con_jwt = sorted(archivo.relative_to(BACKEND).as_posix() for archivo in archivos if "jwt" in _modulos_importados(archivo))

    assert con_jwt == ["infraestructura/tokens_jwt.py"]


def test_solo_el_adaptador_csv_sabe_que_existe_un_csv():
    archivos = [archivo for archivo in sorted(BACKEND.rglob("*.py")) if "tests" not in archivo.relative_to(BACKEND).parts]

    con_csv = sorted(archivo.relative_to(BACKEND).as_posix() for archivo in archivos if "csv" in _modulos_importados(archivo))

    assert con_csv == ["infraestructura/repositorio_especies_csv.py"]
