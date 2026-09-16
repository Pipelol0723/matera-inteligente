"""Controladores REST de la API v1. Solo traducen: HTTP -> caso de uso -> JSON."""
from flask import Blueprint, jsonify, request

from aplicacion.diagnosticar_planta import DiagnosticarPlanta
from aplicacion.listar_especies import ListarEspecies
from aplicacion.listar_parametros import ListarParametros
from presentacion import esquemas
from presentacion.errores_http import registrar_manejadores


def crear_blueprint(
    diagnosticar: DiagnosticarPlanta,
    listar: ListarEspecies,
    listar_parametros: ListarParametros,
) -> Blueprint:
    """Recibe los casos de uso ya armados: las rutas no crean dependencias (DIP)."""
    bp = Blueprint("api_v1", __name__, url_prefix="/api/v1")

    @bp.get("/especies")
    def especies():
        return jsonify([esquemas.especie_a_json(especie) for especie in listar.ejecutar()])

    @bp.get("/parametros")
    def parametros():
        return jsonify([esquemas.parametro_a_json(parametro) for parametro in listar_parametros.ejecutar()])

    @bp.post("/diagnosticos")
    def diagnosticos():
        solicitud = esquemas.solicitud_desde_json(request.get_json(silent=True))
        diagnostico = diagnosticar.ejecutar(solicitud)
        return jsonify(esquemas.diagnostico_a_json(diagnostico))

    registrar_manejadores(bp)
    return bp
