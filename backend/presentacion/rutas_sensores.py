"""La ruta del sensor: el ESP32 (o el simulador del front) manda una medicion con su clave.

El sensor no tiene sesion: se identifica con el codigo de la URL y la cabecera
X-Clave-Sensor. Aqui la clave deja de saber que existe HTTP.
"""
from flask import Blueprint, jsonify, request

from aplicacion.sensores import RecibirMedicionDeSensor
from presentacion import esquemas, esquemas_usuarios
from presentacion.errores_usuarios import registrar_manejadores_usuarios

CABECERA_CLAVE = "X-Clave-Sensor"


def crear_blueprint_sensores(recibir: RecibirMedicionDeSensor) -> Blueprint:
    bp = Blueprint("api_v1_sensores", __name__, url_prefix="/api/v1/sensores")

    @bp.post("/<codigo>/mediciones")
    def medicion_del_sensor(codigo: str):
        medicion = esquemas.medicion_desde_json(request.get_json(silent=True))
        # Sin cabecera, la clave vacia no coincide con ninguna: el mismo 401 que una clave incorrecta.
        clave = request.headers.get(CABECERA_CLAVE, "")
        return jsonify(esquemas_usuarios.resultado_medicion_a_json(recibir.ejecutar(codigo, clave, medicion))), 201

    registrar_manejadores_usuarios(bp)
    return bp
