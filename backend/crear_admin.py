"""Da el rol de administrador a una cuenta ya registrada. Es la forma de tener el primer admin.

La API no tiene ninguna ruta que de el rol sin otro admin: este script se
corre en el servidor, con acceso a la base de datos.

Uso, desde la carpeta backend/:
    python crear_admin.py correo@ejemplo.com
"""
import sys

from aplicacion.administracion import ConvertirEnAdministrador
from dominio.errores import ErrorDominio
from dominio.errores_usuarios import UsuarioNoEncontrado
from infraestructura.configuracion import Configuracion
from infraestructura.sqlite import BaseDatos, RepositorioUsuariosSqlite


def main(argumentos: list[str], config: Configuracion | None = None) -> int:
    if len(argumentos) != 1:
        print("Uso: python crear_admin.py correo", file=sys.stderr)
        return 2
    config = config or Configuracion.desde_entorno()
    usuarios = RepositorioUsuariosSqlite(BaseDatos(config.ruta_bd).preparar())
    try:
        admin = ConvertirEnAdministrador(usuarios, usuarios).ejecutar(argumentos[0])
    except UsuarioNoEncontrado as error:
        print(f"{error} Primero cree la cuenta desde el front o con POST /api/v1/usuarios.", file=sys.stderr)
        return 1
    except ErrorDominio as error:
        print(error, file=sys.stderr)
        return 1
    print(f"{admin.nombre} ({admin.correo.valor}) ahora es administrador.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
