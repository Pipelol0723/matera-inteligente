"""Borde HTTP del corte 2: JSON -> textos y objetos del dominio, y resultados -> JSON.

Como en esquemas.py, aqui solo se valida la forma: que cada campo este y sea
del tipo correcto. Las reglas (correo valido, contrasena de 8 caracteres,
apodo, rango con minimo menor que maximo) las revisa el dominio.
"""
from dataclasses import dataclass
from typing import Any

from aplicacion.cuentas import CuentaUsuario, SesionIniciada
from dominio.errores import RangoInvalido
from dominio.especie import Especie
from dominio.parametros import PARAMETROS
from dominio.rango import Rango
from dominio.usuarios import ResumenUsuario, Rol, Usuario
from presentacion.esquemas import EntradaInvalida


@dataclass(frozen=True)
class CambioUsuario:
    """Lo que pide PATCH /admin/usuarios/{id}: cambiar el estado o el rol, uno a la vez."""

    activo: bool | None = None
    rol: Rol | None = None


def registro_desde_json(cuerpo: Any) -> tuple[str, str, str]:
    cuerpo = _objeto(cuerpo)
    return _texto(cuerpo, "nombre"), _texto(cuerpo, "correo"), _texto(cuerpo, "contrasena")


def credenciales_desde_json(cuerpo: Any) -> tuple[str, str]:
    cuerpo = _objeto(cuerpo)
    return _texto(cuerpo, "correo"), _texto(cuerpo, "contrasena")


def cambio_de_usuario_desde_json(cuerpo: Any) -> CambioUsuario:
    cuerpo = _objeto(cuerpo)
    pedidos = [campo for campo in ("activo", "rol") if campo in cuerpo]
    if len(pedidos) != 1:
        raise EntradaInvalida(
            "PARAMETRO_INVALIDO",
            "Envíe solo uno de estos campos: activo (true o false) o rol (USUARIO o ADMIN).",
            {"campo": "activo|rol", "motivo": "ausente" if not pedidos else "ambos"},
        )
    if pedidos == ["activo"]:
        if not isinstance(cuerpo["activo"], bool):
            raise _invalido("activo", "no_es_booleano", "El campo activo debe ser true o false.")
        return CambioUsuario(activo=cuerpo["activo"])
    try:
        return CambioUsuario(rol=Rol(cuerpo["rol"]))
    except ValueError:
        raise _invalido("rol", "valor_no_permitido", "El campo rol debe ser USUARIO o ADMIN.") from None


def especie_desde_json(cuerpo: Any) -> Especie:
    """Mismo formato de rangos que GET /especies: {"humedad": {"min": 20, "max": 45}, ...}."""
    cuerpo = _objeto(cuerpo)
    nombre = _texto(cuerpo, "nombre")
    cientifico = cuerpo.get("nombreCientifico") or ""
    if not isinstance(cientifico, str):
        raise _invalido("nombreCientifico", "no_es_texto", "El campo nombreCientifico debe ser un texto.")
    rangos_json = cuerpo.get("rangos")
    if not isinstance(rangos_json, dict):
        raise _invalido("rangos", "ausente", "Falta el objeto rangos, con un mínimo y un máximo por parámetro.")

    rangos = {}
    for parametro in PARAMETROS:
        rango = rangos_json.get(parametro.nombre)
        campo = f"rangos.{parametro.nombre}"
        if not isinstance(rango, dict):
            raise _invalido(campo, "ausente", f"Falta el rango de {parametro.nombre}.")
        minimo, maximo = _numero(rango, "min", campo), _numero(rango, "max", campo)
        try:
            rangos[parametro] = Rango(minimo, maximo)
        except RangoInvalido as error:
            raise _invalido(campo, "minimo_no_menor_que_maximo", str(error)) from None
    return Especie(nombre, rangos, cientifico)


def usuario_a_json(usuario: Usuario) -> dict[str, Any]:
    return {"id": usuario.id, "nombre": usuario.nombre, "correo": usuario.correo.valor, "rol": usuario.rol.value}


def usuario_admin_a_json(usuario: Usuario) -> dict[str, Any]:
    return {**usuario_a_json(usuario), "activo": usuario.activo}


def cuenta_a_json(cuenta: CuentaUsuario) -> dict[str, Any]:
    return {**usuario_a_json(cuenta.usuario), "plantas": cuenta.cantidad_plantas}


def sesion_a_json(sesion: SesionIniciada) -> dict[str, Any]:
    return {"token": sesion.token, "venceEn": sesion.vence_en.isoformat(), "usuario": usuario_a_json(sesion.usuario)}


def resumen_a_json(resumen: ResumenUsuario) -> dict[str, Any]:
    return {
        "id": resumen.id,
        "correo": resumen.correo,
        "nombre": resumen.nombre,
        "rol": resumen.rol.value,
        "activo": resumen.activo,
        "cantidadPlantas": resumen.cantidad_plantas,
    }


def _objeto(cuerpo: Any) -> dict:
    if not isinstance(cuerpo, dict):
        raise EntradaInvalida("SOLICITUD_INVALIDA", "El cuerpo de la petición debe ser un objeto JSON.")
    return cuerpo


def _texto(cuerpo: dict, campo: str) -> str:
    valor = cuerpo.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise _invalido(campo, "ausente", f"Falta el campo {campo}.")
    if not isinstance(valor, str):
        raise _invalido(campo, "no_es_texto", f"El campo {campo} debe ser un texto.")
    return valor


def _numero(rango: dict, limite: str, campo: str) -> float:
    valor = rango.get(limite)
    # En Python bool es subclase de int: true no es un limite.
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    raise _invalido(campo, "no_numerico", f"El {limite} de {campo} debe ser un número.")


def _invalido(campo: str, motivo: str, mensaje: str) -> EntradaInvalida:
    return EntradaInvalida("PARAMETRO_INVALIDO", mensaje, {"campo": campo, "motivo": motivo})
