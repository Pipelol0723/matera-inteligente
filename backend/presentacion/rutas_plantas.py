"""Rutas de las plantas del usuario: Mis materas, el sensor de cada una y su historial.

Todas exigen sesion: el decorador con_usuario verifica el token y le entrega
el usuario a la ruta. El usuario sale del token, nunca del cuerpo ni de la URL:
pedir la planta de otro da 404, igual que una que no existe.
"""
from flask import Blueprint, jsonify, request

from dominio import puertos_entrada as entrada
from presentacion import esquemas_usuarios
from presentacion.autenticacion import Autenticacion
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_plantas(
    registrar: entrada.RegistrarPlanta,
    listar: entrada.ListarPlantas,
    eliminar: entrada.EliminarPlanta,
    reemplazar_sensor: entrada.ReemplazarSensor,
    consultar_historial: entrada.ConsultarHistorial,
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_plantas", __name__, url_prefix="/api/v1/plantas")

    @bp.get("")
    @autenticacion.con_usuario
    def mis_plantas(usuario):
        tarjetas = listar.ejecutar(usuario)
        return jsonify([esquemas_usuarios.tarjeta_a_json(tarjeta) for tarjeta in tarjetas])

    @bp.post("")
    @autenticacion.con_usuario
    def registrar_planta(usuario):
        apodo, especie, codigo = esquemas_usuarios.planta_desde_json(request.get_json(silent=True))
        vinculado = registrar.ejecutar(usuario, apodo, especie, codigo)
        return jsonify(esquemas_usuarios.sensor_vinculado_a_json(vinculado)), 201

    @bp.delete("/<int:planta_id>")
    @autenticacion.con_usuario
    def eliminar_planta(usuario, planta_id: int):
        eliminar.ejecutar(usuario, planta_id)
        return jsonify({"mensaje": "Planta eliminada, con su sensor y su historial."})

    @bp.put("/<int:planta_id>/sensor")
    @autenticacion.con_usuario
    def cambiar_sensor(usuario, planta_id: int):
        codigo = esquemas_usuarios.codigo_desde_json(request.get_json(silent=True))
        vinculado = reemplazar_sensor.ejecutar(usuario, planta_id, codigo)
        return jsonify(esquemas_usuarios.sensor_vinculado_a_json(vinculado))

    @bp.get("/<int:planta_id>/historial")
    @autenticacion.con_usuario
    def historial(usuario, planta_id: int):
        limite = esquemas_usuarios.limite_desde_consulta(request.args.get("limite"))
        return jsonify(esquemas_usuarios.historial_a_json(consultar_historial.ejecutar(usuario, planta_id, limite)))

    registrar_manejadores_usuarios(bp)
    return bp
