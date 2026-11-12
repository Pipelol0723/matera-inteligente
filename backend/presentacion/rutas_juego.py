"""Rutas del juego (corte 3): la matera Tamagotchi, tus puntos y la tabla de posiciones.

  GET /api/v1/juego/materas        la matera Tamagotchi de cada planta propia
  GET /api/v1/juego/puntaje        tus puntos: el total, por matera y los ultimos movimientos
  GET /api/v1/juego/participacion  si participas en la tabla, y con que apodo
  PUT /api/v1/juego/participacion  {"participa": true, "apodo": "..."} o {"participa": false}
  GET /api/v1/juego/tabla          la tabla de posiciones, solo para quien participa

Todas exigen el JWT de usuario: el usuario sale del token, nunca del cuerpo ni
de la URL, asi que cada uno solo ve lo suyo. Las rutas solo traducen HTTP <->
puerto de entrada: las reglas del juego viven en el dominio.
"""
from flask import Blueprint, jsonify, request

from dominio import puertos_juego as juego
from presentacion import esquemas_juego
from presentacion.autenticacion import Autenticacion
from presentacion.errores_http import registrar_manejadores
from presentacion.errores_juego import registrar_manejadores_juego
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_juego(
    consultar_mascotas: juego.ConsultarMascotas,
    consultar_puntaje: juego.ConsultarPuntaje,
    consultar_participacion: juego.ConsultarParticipacion,
    elegir_participacion: juego.ElegirParticipacion,
    consultar_tabla: juego.ConsultarTablaPosiciones,
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_juego", __name__, url_prefix="/api/v1/juego")

    @bp.get("/materas")
    @autenticacion.con_usuario
    def materas(usuario):
        return jsonify(esquemas_juego.mascotas_a_json(consultar_mascotas.ejecutar(usuario)))

    @bp.get("/puntaje")
    @autenticacion.con_usuario
    def puntaje(usuario):
        return jsonify(esquemas_juego.puntaje_a_json(consultar_puntaje.ejecutar(usuario)))

    @bp.get("/participacion")
    @autenticacion.con_usuario
    def participacion(usuario):
        return jsonify(esquemas_juego.participacion_a_json(consultar_participacion.ejecutar(usuario)))

    @bp.put("/participacion")
    @autenticacion.con_usuario
    def elegir(usuario):
        participa, apodo = esquemas_juego.participacion_desde_json(request.get_json(silent=True))
        return jsonify(esquemas_juego.participacion_a_json(elegir_participacion.ejecutar(usuario, participa, apodo)))

    @bp.get("/tabla")
    @autenticacion.con_usuario
    def tabla(usuario):
        return jsonify(esquemas_juego.tabla_a_json(consultar_tabla.ejecutar(usuario)))

    registrar_manejadores(bp)
    registrar_manejadores_usuarios(bp)
    registrar_manejadores_juego(bp)
    return bp
