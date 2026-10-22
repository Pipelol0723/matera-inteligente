"""Borde HTTP de los dispositivos: el JSON del canje y de la lectura -> objetos del dominio, y el token -> JSON.

Como en esquemas.py, aqui solo se valida la forma: que cada campo este y tenga
el tipo correcto. Las reglas (los limites fisicos, la hora sin zona horaria o
en el futuro, que el reporte sea del mismo sensor) las revisa el nucleo.
"""
from datetime import datetime, timezone
from typing import Any

from dominio.errores_usuarios import CodigoSensorInvalido
from dominio.reportes import ReporteDeDispositivo
from dominio.resultados import TokenDispositivo
from dominio.sensores import CodigoSensor
from presentacion.esquemas import EntradaInvalida, medicion_desde_json


def clave_desde_json(cuerpo: Any) -> str:
    """{"clave": "..."}"""
    return _texto(_objeto(cuerpo), "clave")


def reporte_desde_json(cuerpo: Any) -> ReporteDeDispositivo:
    """{"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:04:05Z", "lecturas": {"humedad": 53, ...}}"""
    cuerpo = _objeto(cuerpo)
    texto_dispositivo = _texto(cuerpo, "dispositivo")
    try:
        dispositivo = CodigoSensor(texto_dispositivo)
    except CodigoSensorInvalido:
        raise _invalido("dispositivo", "invalido", f"'{texto_dispositivo}' no es un código de sensor: MT-0000-XX.") from None
    momento = _momento(_texto(cuerpo, "momento"))
    lecturas = cuerpo.get("lecturas")
    if not isinstance(lecturas, dict):
        motivo = "ausente" if lecturas is None else "no_es_objeto"
        raise _invalido("lecturas", motivo, 'Falta el objeto lecturas: {"humedad": ..., "luz": ..., "temperatura": ...}.')
    return ReporteDeDispositivo(dispositivo, momento, medicion_desde_json(lecturas))


def token_a_json(token: TokenDispositivo) -> dict[str, Any]:
    return {"token": token.token, "venceEn": token.vence_en.isoformat()}


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


def _momento(texto: str) -> datetime:
    """ISO 8601, por ejemplo 2026-10-22T15:04:05Z, pasado a UTC. Si le falta la zona horaria, lo rechaza el dominio."""
    try:
        momento = datetime.fromisoformat(texto.strip())
    except ValueError:
        raise _invalido("momento", "formato", f"'{texto}' no es una fecha y hora ISO 8601, como 2026-10-22T15:04:05Z.") from None
    return momento.astimezone(timezone.utc) if momento.utcoffset() is not None else momento


def _invalido(campo: str, motivo: str, mensaje: str) -> EntradaInvalida:
    return EntradaInvalida("PARAMETRO_INVALIDO", mensaje, {"campo": campo, "motivo": motivo})
