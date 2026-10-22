"""Cada puerto de entrada del dominio tiene un caso de uso en aplicacion/ con su mismo nombre, que lo hereda."""
import importlib
import inspect
import pkgutil
from abc import ABC

import aplicacion
from dominio import puertos_entrada


def _puertos() -> dict[str, type]:
    return {
        nombre: clase
        for nombre, clase in inspect.getmembers(puertos_entrada, inspect.isclass)
        if clase.__module__ == puertos_entrada.__name__ and issubclass(clase, ABC)
    }


def _clases_de_aplicacion() -> dict[str, type]:
    clases = {}
    for info in pkgutil.iter_modules(aplicacion.__path__):
        modulo = importlib.import_module(f"aplicacion.{info.name}")
        clases.update(
            (nombre, clase)
            for nombre, clase in inspect.getmembers(modulo, inspect.isclass)
            if clase.__module__ == modulo.__name__
        )
    return clases


def test_cada_puerto_de_entrada_lo_implementa_el_caso_de_uso_de_su_mismo_nombre():
    puertos = _puertos()
    clases = _clases_de_aplicacion()
    assert puertos, "no se encontraron puertos de entrada"

    assert sorted(nombre for nombre in puertos if nombre not in clases) == []
    assert sorted(nombre for nombre, puerto in puertos.items() if not issubclass(clases[nombre], puerto)) == []


def test_ningun_caso_de_uso_deja_un_metodo_del_puerto_sin_implementar():
    assert sorted(nombre for nombre, clase in _clases_de_aplicacion().items() if inspect.isabstract(clase)) == []
