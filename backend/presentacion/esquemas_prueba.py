"""Borde HTTP del modo prueba: el JSON del estado de prueba -> EstadoDePrueba, y de vuelta.

    {"etapa": "SEMILLA|BROTE|PLANTA|FLORECIDA", "condicion": "SANA|DECAIDA|MARCHITA",
     "cara": "SALUDABLE|EN_RIESGO|CRITICO", "dormida": false,
     "necesidad": "SED|EXCESO_AGUA|FRIO|CALOR|POCA_LUZ|MUCHA_LUZ" o null}

Aqui solo se valida la forma. Quien puede poner un estado de prueba lo decide el dominio.
"""
from enum import Enum
from typing import Any

from dominio.estados import EstadoGlobal
from dominio.mascota import Condicion, EtapaCrecimiento, Necesidad
from dominio.modo_prueba import EstadoDePrueba
from presentacion.esquemas import EntradaInvalida


def estado_de_prueba_desde_json(cuerpo: Any) -> EstadoDePrueba:
    if not isinstance(cuerpo, dict):
        raise EntradaInvalida("SOLICITUD_INVALIDA", "El cuerpo de la petición debe ser un objeto JSON.")
    dormida = cuerpo.get("dormida", False)
    if not isinstance(dormida, bool):
        raise _invalido("dormida", "no_es_booleano", "El campo dormida debe ser true o false.")
    necesidad = cuerpo.get("necesidad")
    return EstadoDePrueba(
        etapa=_opcion(cuerpo, "etapa", EtapaCrecimiento),
        condicion=_opcion(cuerpo, "condicion", Condicion),
        cara=_opcion(cuerpo, "cara", EstadoGlobal),
        dormida=dormida,
        necesidad=None if necesidad is None else _opcion(cuerpo, "necesidad", Necesidad),
    )


def estado_de_prueba_a_json(estado: EstadoDePrueba | None) -> dict[str, Any] | None:
    if estado is None:
        return None
    return {
        "etapa": estado.etapa.value,
        "condicion": estado.condicion.value,
        "cara": estado.cara.value,
        "dormida": estado.dormida,
        "necesidad": estado.necesidad.value if estado.necesidad is not None else None,
    }


def _opcion(cuerpo: dict, campo: str, tipo: type[Enum]) -> Any:
    valor = cuerpo.get(campo)
    validos = [opcion.value for opcion in tipo]
    if valor is None:
        raise _invalido(campo, "ausente", f"Falta el campo {campo}: {', '.join(validos)}.")
    if not isinstance(valor, str) or valor not in validos:
        raise _invalido(campo, "no_valido", f"El campo {campo} debe ser uno de: {', '.join(validos)}.")
    return tipo(valor)


def _invalido(campo: str, motivo: str, mensaje: str) -> EntradaInvalida:
    return EntradaInvalida("PARAMETRO_INVALIDO", mensaje, {"campo": campo, "motivo": motivo})
