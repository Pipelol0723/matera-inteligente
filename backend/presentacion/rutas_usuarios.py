"""Rutas de la cuenta: registro, inicio y cierre de sesion, y Mi cuenta. Solo traducen HTTP <-> caso de uso."""
from flask import Blueprint, jsonify, request

from dominio import puertos_entrada as entrada
from presentacion import esquemas_usuarios
from presentacion.autenticacion import Autenticacion
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_usuarios(
    registrar: entrada.RegistrarUsuario,
    iniciar: entrada.IniciarSesion,
    cerrar: entrada.CerrarSesion,
    consultar: entrada.ConsultarCuenta,
    autenticacion: Autenticacion,
) -> Blueprint:
    bp = Blueprint("api_v1_usuarios", __name__, url_prefix="/api/v1")

    @bp.post("/usuarios")
    def registrar_usuario():
        nombre, correo, contrasena = esquemas_usuarios.registro_desde_json(request.get_json(silent=True))
        usuario = registrar.ejecutar(nombre, correo, contrasena)
        return jsonify(esquemas_usuarios.usuario_a_json(usuario)), 201

    @bp.post("/sesiones")
    def iniciar_sesion():
        correo, contrasena = esquemas_usuarios.credenciales_desde_json(request.get_json(silent=True))
        return jsonify(esquemas_usuarios.sesion_a_json(iniciar.ejecutar(correo, contrasena))), 201

    @bp.delete("/sesiones/actual")
    @autenticacion.con_identidad
    def cerrar_sesion(identidad):
        cerrar.ejecutar(identidad)
        # 200 con un mensaje, no 204 sin cuerpo: toda respuesta es JSON (RA1).
        return jsonify({"mensaje": "Sesión cerrada."})

    @bp.get("/usuarios/yo")
    @autenticacion.con_usuario
    def mi_cuenta(usuario):
        return jsonify(esquemas_usuarios.cuenta_a_json(consultar.ejecutar(usuario)))

    registrar_manejadores_usuarios(bp)
    return bp
