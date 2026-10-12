"""Rutas de las plantas del usuario: Mis materas, sensor, historial y medicion manual.

Todas exigen sesion. El usuario sale del token, nunca del cuerpo ni de la URL:
pedir la planta de otro da 404, igual que una que no existe.
"""
from flask import Blueprint, jsonify, request

from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.historial import ConsultarHistorial
from aplicacion.plantas import EliminarPlanta, ListarPlantas, RegistrarPlanta
from aplicacion.sensores import DesvincularSensor, VincularSensor
from presentacion import esquemas, esquemas_usuarios
from presentacion.autenticacion import Autenticacion
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_plantas(
    registrar: RegistrarPlanta,
    listar: ListarPlantas,
    eliminar: EliminarPlanta,
    vincular: VincularSensor,
    desvincular: DesvincularSensor,
    consultar_historial: ConsultarHistorial,
    diagnosticar: DiagnosticarPlantaDeUsuario,
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_plantas", __name__, url_prefix="/api/v1/plantas")

    @bp.get("")
    def mis_plantas():
        tarjetas = listar.ejecutar(autenticacion.usuario_actual())
        return jsonify([esquemas_usuarios.tarjeta_a_json(tarjeta) for tarjeta in tarjetas])

    @bp.post("")
    def registrar_planta():
        usuario = autenticacion.usuario_actual()
        apodo, especie = esquemas_usuarios.planta_desde_json(request.get_json(silent=True))
        return jsonify(esquemas_usuarios.planta_a_json(registrar.ejecutar(usuario, apodo, especie))), 201

    @bp.delete("/<int:planta_id>")
    def eliminar_planta(planta_id: int):
        eliminar.ejecutar(autenticacion.usuario_actual(), planta_id)
        return jsonify({"mensaje": "Planta eliminada, con su sensor y su historial."})

    @bp.post("/<int:planta_id>/sensor")
    def vincular_sensor(planta_id: int):
        usuario = autenticacion.usuario_actual()
        codigo = esquemas_usuarios.codigo_desde_json(request.get_json(silent=True))
        return jsonify(esquemas_usuarios.sensor_vinculado_a_json(vincular.ejecutar(usuario, planta_id, codigo))), 201

    @bp.delete("/<int:planta_id>/sensor")
    def desvincular_sensor(planta_id: int):
        desvincular.ejecutar(autenticacion.usuario_actual(), planta_id)
        return jsonify({"mensaje": "Sensor desvinculado. Su código quedó libre."})

    @bp.get("/<int:planta_id>/historial")
    def historial(planta_id: int):
        usuario = autenticacion.usuario_actual()
        limite = esquemas_usuarios.limite_desde_consulta(request.args.get("limite"))
        return jsonify(esquemas_usuarios.historial_a_json(consultar_historial.ejecutar(usuario, planta_id, limite)))

    @bp.post("/<int:planta_id>/mediciones")
    def medicion_manual(planta_id: int):
        usuario = autenticacion.usuario_actual()
        medicion = esquemas.medicion_desde_json(request.get_json(silent=True))
        resultado = diagnosticar.ejecutar(usuario.id, planta_id, medicion)
        return jsonify(esquemas_usuarios.resultado_medicion_a_json(resultado)), 201

    registrar_manejadores_usuarios(bp)
    return bp
