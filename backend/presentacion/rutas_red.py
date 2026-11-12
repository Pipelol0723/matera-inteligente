"""GET /red: por que direcciones puede una placa de la red local alcanzar este backend.

La app se abre en localhost, que para la placa no significa nada: le pregunta
aqui a que direccion mandar sus lecturas. La lista la da el punto de composicion.
"""
from collections.abc import Callable

from flask import Blueprint, jsonify

from presentacion.autenticacion import Autenticacion
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_red(
    servidores: Callable[[], list[str]],
    aviso: Callable[[], str | None],
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_red", __name__, url_prefix="/api/v1")

    @bp.get("/red")
    @autenticacion.con_usuario
    def red(_usuario):
        lista = servidores()
        respuesta: dict = {"servidores": lista}
        if not lista:
            respuesta["aviso"] = aviso()
        return jsonify(respuesta)

    registrar_manejadores_usuarios(bp)
    return bp
