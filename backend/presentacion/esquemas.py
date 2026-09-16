"""Borde HTTP: JSON -> objetos del dominio, y diagnostico -> JSON.

Aqui se valida la forma de la peticion: que cada campo este y sea numerico.
Los limites fisicos no se revisan aqui; los revisa Lectura, en el dominio.
"""
from typing import Any

from aplicacion.diagnosticar_planta import SolicitudDiagnostico
from dominio.diagnostico import Diagnostico, ResultadoParametro
from dominio.especie import Especie
from dominio.medicion import Lectura, Medicion
from dominio.parametros import PARAMETROS


class EntradaInvalida(Exception):
    """La peticion no cumple el contrato de la API. errores_http.py la convierte en un 400."""

    def __init__(self, error: str, mensaje: str, detalle: dict[str, Any] | None = None):
        super().__init__(mensaje)
        self.error = error
        self.mensaje = mensaje
        self.detalle = detalle or {}


def solicitud_desde_json(cuerpo: Any) -> SolicitudDiagnostico:
    if not isinstance(cuerpo, dict):
        raise EntradaInvalida("SOLICITUD_INVALIDA", "El cuerpo de la petición debe ser un objeto JSON.")
    especie = _texto(cuerpo, "especie")
    # Desde esta linea el dato ya no sabe que llego por HTTP: son objetos del dominio.
    lecturas = tuple(Lectura(parametro, _numero(cuerpo, parametro.nombre)) for parametro in PARAMETROS)
    return SolicitudDiagnostico(especie=especie, medicion=Medicion(lecturas))


def diagnostico_a_json(diagnostico: Diagnostico) -> dict[str, Any]:
    return {
        "especie": diagnostico.especie,
        "estado": diagnostico.estado.value,
        "parametros": [_resultado_a_json(resultado) for resultado in diagnostico.resultados],
        "recomendaciones": list(diagnostico.recomendaciones),
    }


def especie_a_json(especie: Especie) -> dict[str, Any]:
    return {
        "nombre": especie.nombre,
        "rangos": {
            parametro.nombre: {"min": rango.minimo, "max": rango.maximo, "unidad": parametro.unidad}
            for parametro, rango in especie.rangos.items()
        },
    }


def _resultado_a_json(resultado: ResultadoParametro) -> dict[str, Any]:
    return {
        "nombre": resultado.parametro.nombre,
        "valor": resultado.valor,
        "unidad": resultado.parametro.unidad,
        "rangoOptimo": [resultado.rango.minimo, resultado.rango.maximo],
        "estado": resultado.estado.value,
        "desviacion": round(resultado.desviacion, 3),
    }


def _texto(cuerpo: dict, campo: str) -> str:
    valor = cuerpo.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise _parametro_invalido(campo, "ausente", f"Falta el campo {campo}.")
    if not isinstance(valor, str):
        raise _parametro_invalido(campo, "no_es_texto", f"El campo {campo} debe ser un texto.")
    return valor


def _numero(cuerpo: dict, campo: str) -> float:
    """Acepta un numero JSON o un texto numerico ("32.5" o "32,5"), como lo escribe una persona."""
    valor = cuerpo.get(campo)
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        raise _parametro_invalido(campo, "ausente", f"Falta el parámetro {campo}.")
    # En Python bool es subclase de int: true no es una medicion.
    if isinstance(valor, (int, float)) and not isinstance(valor, bool):
        return float(valor)
    if isinstance(valor, str):
        try:
            return float(valor.strip().replace(",", "."))
        except ValueError:
            pass
    raise _parametro_invalido(campo, "no_numerico", f"El parámetro {campo} debe ser un número.")


def _parametro_invalido(campo: str, motivo: str, mensaje: str) -> EntradaInvalida:
    return EntradaInvalida("PARAMETRO_INVALIDO", mensaje, {"campo": campo, "motivo": motivo})
