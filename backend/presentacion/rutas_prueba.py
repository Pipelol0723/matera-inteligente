"""Rutas del modo prueba (corte 3), solo para admins:

  PUT    /api/v1/juego/materas/{id}/prueba   {"etapa", "condicion", "cara", "dormida", "necesidad"}
  DELETE /api/v1/juego/materas/{id}/prueba   la matera vuelve a verse como es (200, en JSON)

Exigen el JWT de usuario. Un usuario que no es admin recibe 403 PERMISO_DENEGADO
y una matera ajena da 404, como una inexistente: lo deciden Usuario.exigir_admin
y Planta.exigir_dueno, no estas rutas. El estado de prueba aparece despues en
GET /juego/materas y en la respuesta a la proxima lectura de la placa.
"""
from flask import Blueprint, jsonify, request

from dominio import puertos_prueba
from presentacion import esquemas_prueba
from presentacion.autenticacion import Autenticacion
from presentacion.errores_http import registrar_manejadores
from presentacion.errores_juego import registrar_manejadores_juego
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_prueba(
    poner: puertos_prueba.PonerEstadoDePrueba,
    quitar: puertos_prueba.QuitarEstadoDePrueba,
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_modo_prueba", __name__, url_prefix="/api/v1/juego/materas")

    @bp.put("/<int:planta_id>/prueba")
    @autenticacion.con_usuario
    def poner_prueba(usuario, planta_id: int):
        estado = esquemas_prueba.estado_de_prueba_desde_json(request.get_json(silent=True))
        puesto = poner.ejecutar(usuario, planta_id, estado)
        return jsonify({"plantaId": planta_id, "prueba": esquemas_prueba.estado_de_prueba_a_json(puesto)})

    @bp.delete("/<int:planta_id>/prueba")
    @autenticacion.con_usuario
    def quitar_prueba(usuario, planta_id: int):
        quitar.ejecutar(usuario, planta_id)
        # RA1: hasta esta respuesta es JSON (no un 204 vacío).
        return jsonify({"plantaId": planta_id, "prueba": None, "mensaje": "La matera volvió a su estado real."})

    registrar_manejadores(bp)
    registrar_manejadores_usuarios(bp)
    registrar_manejadores_juego(bp)
    return bp
