"""Rutas de administracion, bajo /api/v1/admin.

No revisan el rol: lo revisa cada caso de uso con actor.exigir_admin(). Aqui
el decorador identifica al actor por su token, y la ruta traduce HTTP <-> caso de uso.
"""
from flask import Blueprint, jsonify, request

from dominio import puertos_entrada as entrada
from presentacion import esquemas, esquemas_usuarios
from presentacion.autenticacion import Autenticacion
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_admin(
    listar: entrada.ListarUsuarios,
    cambiar_estado: entrada.CambiarEstadoUsuario,
    cambiar_rol: entrada.CambiarRol,
    eliminar: entrada.EliminarUsuario,
    agregar_especie: entrada.AgregarEspecie,
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_admin", __name__, url_prefix="/api/v1/admin")

    @bp.get("/usuarios")
    @autenticacion.con_usuario
    def usuarios(actor):
        resumenes = listar.ejecutar(actor)
        return jsonify([esquemas_usuarios.resumen_a_json(resumen) for resumen in resumenes])

    @bp.patch("/usuarios/<int:usuario_id>")
    @autenticacion.con_usuario
    def cambiar_usuario(actor, usuario_id: int):
        cambio = esquemas_usuarios.cambio_de_usuario_desde_json(request.get_json(silent=True))
        if cambio.activo is not None:
            usuario = cambiar_estado.ejecutar(actor, usuario_id, cambio.activo)
        else:
            usuario = cambiar_rol.ejecutar(actor, usuario_id, cambio.rol)
        return jsonify(esquemas_usuarios.usuario_admin_a_json(usuario))

    @bp.delete("/usuarios/<int:usuario_id>")
    @autenticacion.con_usuario
    def eliminar_usuario(actor, usuario_id: int):
        eliminar.ejecutar(actor, usuario_id)
        return jsonify({"mensaje": "Cuenta eliminada, con sus plantas, sensores e historial."})

    @bp.post("/especies")
    @autenticacion.con_usuario
    def agregar(actor):
        especie = esquemas_usuarios.especie_desde_json(request.get_json(silent=True))
        # La misma forma que en GET /especies.
        return jsonify(esquemas.especie_a_json(agregar_especie.ejecutar(actor, especie))), 201

    registrar_manejadores_usuarios(bp)
    return bp
