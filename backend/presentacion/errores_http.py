"""Traduce excepciones a respuestas HTTP con un cuerpo uniforme (RF6).

Toda respuesta de error tiene la forma {"error", "mensaje", "detalle"}. Tambien
reemplaza las paginas HTML que Flask devuelve por defecto en 404, 405 y 500:
este backend solo responde JSON (RA1).
"""
import math

from flask import Blueprint, current_app, jsonify, request
from werkzeug.exceptions import HTTPException

from dominio.errores import EspecieNoSoportada, ValorFisicamenteImposible
from presentacion.esquemas import EntradaInvalida

_CODIGOS_HTTP = {
    400: "SOLICITUD_INVALIDA",
    404: "RUTA_NO_ENCONTRADA",
    405: "METODO_NO_PERMITIDO",
    415: "TIPO_DE_CONTENIDO_NO_SOPORTADO",
}


def respuesta_error(estado_http: int, error: str, mensaje: str, detalle: dict | None = None):
    return jsonify({"error": error, "mensaje": mensaje, "detalle": detalle or {}}), estado_http


def registrar_manejadores(bp: Blueprint) -> None:
    """Registra los manejadores para toda la aplicacion, no solo para las rutas del blueprint."""

    @bp.app_errorhandler(EntradaInvalida)
    def entrada_invalida(error: EntradaInvalida):
        return respuesta_error(400, error.error, error.mensaje, error.detalle)

    @bp.app_errorhandler(ValorFisicamenteImposible)
    def valor_fisicamente_imposible(error: ValorFisicamenteImposible):
        p = error.parametro
        return respuesta_error(
            400,
            "PARAMETRO_INVALIDO",
            f"El valor de {p.nombre} no es físicamente posible: debe estar entre "
            f"{p.minimo_fisico:g} y {p.maximo_fisico:g} {p.unidad}.",
            {
                "campo": p.nombre,
                "motivo": "fuera_de_rango_fisico",
                # NaN e infinito no son JSON valido: se devuelven como texto.
                "valor": error.valor if math.isfinite(error.valor) else str(error.valor),
                "minimo": p.minimo_fisico,
                "maximo": p.maximo_fisico,
            },
        )

    @bp.app_errorhandler(EspecieNoSoportada)
    def especie_no_soportada(error: EspecieNoSoportada):
        return respuesta_error(
            404,
            "ESPECIE_NO_SOPORTADA",
            f"La especie '{error.especie}' no está soportada. Consulte GET /api/v1/especies.",
            {"especie": error.especie},
        )

    @bp.app_errorhandler(HTTPException)
    def error_http(error: HTTPException):
        mensajes = {
            404: f"No existe la ruta {request.path}.",
            405: f"El método {request.method} no está permitido en {request.path}.",
        }
        codigo = error.code or 500
        return respuesta_error(
            codigo,
            _CODIGOS_HTTP.get(codigo, "ERROR_HTTP"),
            mensajes.get(codigo, error.description or "Error HTTP."),
            {"ruta": request.path},
        )

    @bp.app_errorhandler(Exception)
    def error_inesperado(error: Exception):
        # La traza queda en el log del servidor; al cliente no se le muestra.
        current_app.logger.exception("Error inesperado en %s %s", request.method, request.path)
        return respuesta_error(500, "ERROR_INTERNO", "Ocurrió un error inesperado en el servidor.")
