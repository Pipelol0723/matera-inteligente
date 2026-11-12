"""Borde HTTP del corte 2: JSON -> textos y objetos del dominio, y resultados -> JSON.

Como en esquemas.py, aqui solo se valida la forma: que cada campo este y sea
del tipo correcto. Las reglas (correo valido, contrasena de 8 caracteres,
apodo, rango con minimo menor que maximo) las revisa el dominio.
"""
import math
from dataclasses import dataclass
from typing import Any

from dominio.diagnostico import Diagnostico
from dominio.errores import RangoInvalido
from dominio.especie import Especie
from dominio.historial import RegistroMedicion
from dominio.mascota import necesidad_principal
from dominio.modo_prueba import ResultadoEnPrueba
from dominio.parametros import PARAMETROS
from dominio.plantas import Planta
from dominio.puertos_entrada import LIMITE_HISTORIAL
from dominio.rango import Rango
from dominio.resultados import (
    CuentaUsuario,
    HistorialPlanta,
    PlantaConEstado,
    ResultadoMedicion,
    SensorVinculado,
    SesionIniciada,
)
from dominio.usuarios import ResumenUsuario, Rol, Usuario
from presentacion.esquemas import EntradaInvalida, diagnostico_a_json
from presentacion.esquemas_prueba import estado_de_prueba_a_json

LIMITE_MAXIMO = 200


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


def planta_desde_json(cuerpo: Any) -> tuple[str, str, str, str | None]:
    """Una matera nueva: su apodo, su especie, el codigo de su sensor y, si la placa creo su clave, la huella."""
    cuerpo = _objeto(cuerpo)
    return _texto(cuerpo, "apodo"), _texto(cuerpo, "especie"), _texto(cuerpo, "codigo"), _huella(cuerpo)


def codigo_desde_json(cuerpo: Any) -> tuple[str, str | None]:
    """El codigo del sensor y la huella opcional de su clave."""
    cuerpo = _objeto(cuerpo)
    return _texto(cuerpo, "codigo"), _huella(cuerpo)


def limite_desde_consulta(texto: str | None) -> int:
    """?limite= del historial: un entero entre 1 y LIMITE_MAXIMO, o el valor por defecto."""
    if texto is None:
        return LIMITE_HISTORIAL
    try:
        limite = int(texto)
    except ValueError:
        limite = 0
    if not 1 <= limite <= LIMITE_MAXIMO:
        raise _invalido("limite", "fuera_de_rango", f"El límite debe ser un entero entre 1 y {LIMITE_MAXIMO}.")
    return limite


def planta_a_json(planta: Planta) -> dict[str, Any]:
    return {"id": planta.id, "apodo": planta.apodo, "especie": planta.especie}


def tarjeta_a_json(tarjeta: PlantaConEstado) -> dict[str, Any]:
    return {
        **planta_a_json(tarjeta.planta),
        "sensor": {"codigo": tarjeta.sensor.codigo.valor} if tarjeta.sensor else None,
        "ultimaMedicion": registro_a_json(tarjeta.ultima_medicion) if tarjeta.ultima_medicion else None,
    }


def registro_a_json(registro: RegistroMedicion) -> dict[str, Any]:
    """Lo guardado en el historial: estados y valores. Las recomendaciones no se guardan."""
    return {
        "momento": registro.momento.isoformat(),
        "estado": registro.estado.value,
        "origen": registro.origen,
        "lecturas": [
            {"nombre": l.parametro.nombre, "valor": l.valor, "unidad": l.parametro.unidad, "estado": l.estado.value}
            for l in registro.lecturas
        ],
    }


def historial_a_json(historial: HistorialPlanta) -> dict[str, Any]:
    return {"planta": planta_a_json(historial.planta), "registros": [registro_a_json(r) for r in historial.registros]}


def sensor_vinculado_a_json(vinculado: SensorVinculado) -> dict[str, Any]:
    """Las unicas respuestas que traen la clave del sensor: crear la matera y cambiarle el sensor."""
    respuesta = {"planta": planta_a_json(vinculado.planta), "codigo": vinculado.codigo.valor}
    if vinculado.clave is not None:  # con huella, la clave la creo la placa y la API nunca la vio
        respuesta["clave"] = vinculado.clave
    return respuesta


def medicion_en_vivo_a_json(planta: Planta, registro: RegistroMedicion, diagnostico: Diagnostico) -> dict[str, Any]:
    """El mensaje del WebSocket cuando llega una medicion.

    'medicion' tiene la forma de ultimaMedicion en GET /plantas y de cada registro del
    historial, asi que el front actualiza la tarjeta y el historial sin pedir nada mas.
    """
    return {
        "tipo": "medicion",
        "planta": planta_a_json(planta),
        "medicion": registro_a_json(registro),
        "diagnostico": diagnostico_a_json(diagnostico),
    }


def resultado_medicion_a_json(resultado: ResultadoMedicion) -> dict[str, Any]:
    """La respuesta 201 a la placa. Con el apodo, el estado y la necesidad dibuja su carita y su globo."""
    necesidad = necesidad_principal((r.parametro.nombre, r.estado) for r in resultado.diagnostico.resultados)
    return {
        "planta": planta_a_json(resultado.planta),
        "momento": resultado.registro.momento.isoformat(),
        # El mismo formato de POST /diagnosticos, con sus recomendaciones.
        "diagnostico": diagnostico_a_json(resultado.diagnostico),
        # Lo que mas necesita la planta (SED, CALOR...), o null si nada esta fuera de rango. Lo decide el dominio.
        "necesidad": necesidad.value if necesidad is not None else None,
        # Modo prueba: si un admin puso esta matera en prueba, la placa dibuja esto en vez de lo real.
        "prueba": estado_de_prueba_a_json(resultado.prueba) if isinstance(resultado, ResultadoEnPrueba) else None,
    }


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


_HEXADECIMALES_MINUSCULA = frozenset("0123456789abcdef")


def _huella(cuerpo: dict) -> str | None:
    """La huella SHA-256 de la clave, opcional: 64 caracteres hexadecimales en minuscula."""
    valor = cuerpo.get("huella")
    if valor is None:
        return None
    if not isinstance(valor, str):
        raise _invalido("huella", "no_es_texto", "El campo huella debe ser un texto.")
    if len(valor) != 64 or not set(valor) <= _HEXADECIMALES_MINUSCULA:
        raise _invalido(
            "huella", "formato_invalido", "La huella debe tener 64 caracteres hexadecimales en minúscula (SHA-256)."
        )
    return valor


def _numero(rango: dict, limite: str, campo: str) -> float:
    valor = rango.get(limite)
    # En Python bool es subclase de int: true no es un limite.
    if isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor):
        return float(valor)
    raise _invalido(campo, "no_numerico", f"El {limite} de {campo} debe ser un número.")


def _invalido(campo: str, motivo: str, mensaje: str) -> EntradaInvalida:
    return EntradaInvalida("PARAMETRO_INVALIDO", mensaje, {"campo": campo, "motivo": motivo})
