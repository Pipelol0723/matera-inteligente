"""Controladores REST de la API v1. Solo traducen: HTTP -> caso de uso -> JSON."""
from flask import Blueprint, jsonify, request

from dominio import puertos_entrada as entrada
from presentacion import esquemas
from presentacion.autenticacion import Autenticacion
from presentacion.errores_http import registrar_manejadores


def crear_blueprint(
    diagnosticar: entrada.DiagnosticarPlanta,
    listar: entrada.ListarEspecies,
    listar_parametros: entrada.ListarParametros,
    autenticacion: Autenticacion,
) -> Blueprint:
    """Recibe los puertos de entrada ya armados: las rutas no crean dependencias ni conocen los casos de uso (DIP).

    R7: como todas las rutas del front, exigen el JWT de usuario. Los casos de uso del
    corte 1 no cambian: no necesitan saber quien pregunta, solo que hay una sesion.
    """
    bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

    @bp.get("/especies")
    @autenticacion.con_usuario
    def especies(_usuario):
        return jsonify([esquemas.especie_a_json(especie) for especie in listar.ejecutar()])

    @bp.get("/parametros")
    @autenticacion.con_usuario
    def parametros(_usuario):
        return jsonify([esquemas.parametro_a_json(parametro) for parametro in listar_parametros.ejecutar()])

    @bp.post("/diagnosticos")
    @autenticacion.con_usuario
    def diagnosticos(_usuario):
        solicitud = esquemas.solicitud_desde_json(request.get_json(silent=True))
        diagnostico = diagnosticar.ejecutar(solicitud)
        return jsonify(esquemas.diagnostico_a_json(diagnostico))

    registrar_manejadores(bp)
    return bp
