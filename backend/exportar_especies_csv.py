"""Escribe la copia en CSV de la tabla de especies a partir de la base de datos (R4).

La copia es de solo lectura: con MATERA_TABLA_REFERENCIA=csv la API la usa en
lugar de la base, y para cambiarla se cambia la base y se vuelve a exportar.
En modo BD se vuelve a escribir sola cada vez que el admin agrega una especie;
este comando sirve para dejarla al dia antes de cambiar de modo.

Uso, desde la carpeta backend/:
    python exportar_especies_csv.py
"""
import sys

from infraestructura.configuracion import Configuracion
from main import construir_consola


def main(argumentos: list[str], config: Configuracion | None = None) -> int:
    if argumentos:
        print("Uso: python exportar_especies_csv.py (la ruta sale de MATERA_RUTA_CSV)", file=sys.stderr)
        return 2
    config = config or Configuracion.desde_entorno()
    cantidad = construir_consola(config).exportar_especies()
    print(f"{cantidad} especies escritas en {config.ruta_tabla_csv}, desde {config.ruta_bd}.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
