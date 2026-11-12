"""Borde HTTP del juego (corte 3): el JSON de la participacion -> datos, y lo que devuelve el juego -> JSON.

Aqui solo se valida la forma y se traduce. El tamano, la condicion, la cara, el
globo, el aviso, los puntos y quien ve la tabla los decide el dominio: el front
solo dibuja lo que recibe. Los nombres van en camelCase, como el resto de la API.
"""
from datetime import datetime
from enum import Enum
from typing import Any

from dominio.juego import Participacion
from dominio.mascota import Mascota
from dominio.resultados_juego import PosicionTabla, PuntajeUsuario
from presentacion.esquemas import EntradaInvalida
from presentacion.esquemas_usuarios import planta_a_json


def participacion_desde_json(cuerpo: Any) -> tuple[bool, str | None]:
    """{"participa": true, "apodo": "pipe_verde"} o {"participa": false}.

    Solo revisa que participa sea true o false y que el apodo, si se participa,
    sea un texto. Si el apodo sirve (largo, caracteres, que no se repita) lo
    decide el dominio. Al no participar, el apodo se ignora.
    """
    if not isinstance(cuerpo, dict):
        raise EntradaInvalida("SOLICITUD_INVALIDA", "El cuerpo de la petición debe ser un objeto JSON.")
    participa = cuerpo.get("participa")
    if not isinstance(participa, bool):
        motivo = "ausente" if participa is None else "no_es_booleano"
        raise _invalido("participa", motivo, "El campo participa debe ser true o false.")
    if not participa:
        return False, None
    apodo = cuerpo.get("apodo")
    if apodo is None:
        raise _invalido("apodo", "ausente", "Para participar en la tabla de posiciones, envíe un apodo de jugador.")
    if not isinstance(apodo, str):
        raise _invalido("apodo", "no_es_texto", "El campo apodo debe ser un texto.")
    return True, apodo


def mascotas_a_json(mascotas: list[Mascota]) -> dict[str, Any]:
    return {"materas": [mascota_a_json(mascota) for mascota in mascotas]}


def mascota_a_json(mascota: Mascota) -> dict[str, Any]:
    """La matera Tamagotchi de una planta. cara, necesidad, aviso y ultimaLectura son null si no aplican."""
    return {
        "plantaId": mascota.planta.id,
        "etapa": mascota.etapa.value,
        "condicion": mascota.condicion.value,
        "cara": _valor(mascota.cara),
        "dormida": mascota.dormida,
        "necesidad": _valor(mascota.necesidad),
        "aviso": _valor(mascota.aviso),
        "puntos": mascota.puntos,
        "horasCuidada": mascota.horas_cuidada,
        "ultimaLectura": _momento(mascota.ultima_lectura),
    }


def puntaje_a_json(puntaje: PuntajeUsuario) -> dict[str, Any]:
    """Tus puntos. En los movimientos, planta es el apodo, o null si la matera se borro."""
    return {
        "puntos": puntaje.total,
        "materas": [{"planta": planta_a_json(matera.planta), "puntos": matera.puntos} for matera in puntaje.materas],
        "movimientos": [
            {
                "momento": movimiento.momento.isoformat(),
                "planta": movimiento.planta.apodo if movimiento.planta is not None else None,
                "estado": movimiento.estado.value,
                "puntos": movimiento.puntos,
            }
            for movimiento in puntaje.movimientos
        ],
    }


def participacion_a_json(participacion: Participacion) -> dict[str, Any]:
    """estado: SIN_DECIDIR, PARTICIPA o NO_PARTICIPA. Solo quien participa tiene apodo."""
    return {
        "estado": participacion.estado.value,
        "apodo": participacion.apodo.valor if participacion.apodo is not None else None,
    }


def tabla_a_json(posiciones: list[PosicionTabla]) -> dict[str, Any]:
    return {
        "posiciones": [
            {"posicion": fila.posicion, "apodo": fila.apodo.valor, "puntos": fila.puntos, "soyYo": fila.soy_yo}
            for fila in posiciones
        ]
    }


def _valor(enumerado: Enum | None) -> str | None:
    return enumerado.value if enumerado is not None else None


def _momento(momento: datetime | None) -> str | None:
    return momento.isoformat() if momento is not None else None


def _invalido(campo: str, motivo: str, mensaje: str) -> EntradaInvalida:
    return EntradaInvalida("PARAMETRO_INVALIDO", mensaje, {"campo": campo, "motivo": motivo})
