"""Rutas del reloj del juego (corte 3):

  GET /api/v1/juego/reloj   cuanto dura hoy un dia y una hora de juego (cualquier usuario con sesion)
  PUT /api/v1/juego/reloj   {"minutosPorDia": 24}  -> desde ya, 1 hora de juego = 1 minuto real (solo admins)

Exigen el JWT de usuario. Quien no es admin recibe 403 PERMISO_DENEGADO al
cambiarlo: lo decide Usuario.exigir_admin(), no esta ruta. Una duracion que no
sirve da 400 RELOJ_INVALIDO; un cuerpo mal formado, 400 PARAMETRO_INVALIDO.
"""
from typing import Any

from flask import Blueprint, jsonify, request

from dominio import puertos_reloj
from dominio.mascota import RelojDeJuego
from presentacion.autenticacion import Autenticacion
from presentacion.errores_http import registrar_manejadores
from presentacion.errores_reloj import registrar_manejadores_reloj
from presentacion.errores_usuarios import registrar_manejadores_usuarios
from presentacion.esquemas import EntradaInvalida


def crear_blueprint_reloj(
    consultar: puertos_reloj.ConsultarRelojDeJuego,
    cambiar: puertos_reloj.CambiarRelojDeJuego,
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_reloj_juego", __name__, url_prefix="/api/v1/juego")

    @bp.get("/reloj")
    @autenticacion.con_usuario
    def ver(usuario):
        return jsonify(reloj_a_json(consultar.ejecutar(usuario)))

    @bp.put("/reloj")
    @autenticacion.con_usuario
    def poner(usuario):
        minutos = minutos_desde_json(request.get_json(silent=True))
        return jsonify(reloj_a_json(cambiar.ejecutar(usuario, minutos)))

    registrar_manejadores(bp)
    registrar_manejadores_usuarios(bp)
    registrar_manejadores_reloj(bp)
    return bp


def reloj_a_json(reloj: RelojDeJuego) -> dict[str, Any]:
    """minutosPorDia es el dato; segundosPorHora es el mismo, ya convertido para mostrarlo."""
    return {"minutosPorDia": reloj.minutos_por_dia, "segundosPorHora": reloj.hora.total_seconds()}


def minutos_desde_json(cuerpo: Any) -> float:
    """Solo revisa la forma: un numero. Si sirve como duracion del dia lo decide el dominio."""
    if not isinstance(cuerpo, dict):
        raise EntradaInvalida("SOLICITUD_INVALIDA", "El cuerpo de la petición debe ser un objeto JSON.")
    minutos = cuerpo.get("minutosPorDia")
    if minutos is None:
        raise _invalido("ausente", "Falta el campo minutosPorDia: cuántos minutos reales dura un día de juego.")
    if isinstance(minutos, bool) or not isinstance(minutos, (int, float)):
        raise _invalido("no_es_numero", "El campo minutosPorDia debe ser un número.")
    return float(minutos)


def _invalido(motivo: str, mensaje: str) -> EntradaInvalida:
    return EntradaInvalida("PARAMETRO_INVALIDO", mensaje, {"campo": "minutosPorDia", "motivo": motivo})
