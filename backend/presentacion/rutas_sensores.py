"""La ruta vieja del sensor: el ESP32 manda una medicion con su clave en la cabecera X-Clave-Sensor.

Es una ruta de transicion: se quita cuando entre la ruta de dispositivos con
JWT (/api/v1/dispositivos). Mientras tanto traduce el pedido viejo a los casos
de uso nuevos: canjea la clave por un token, lo verifica y reporta la medicion
con la hora del servidor, porque el pedido viejo no la trae.
"""
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from dominio import puertos_entrada as entrada
from dominio.puertos_usuarios import VerificadorTokens
from dominio.reportes import ReporteDeDispositivo
from presentacion import esquemas, esquemas_usuarios
from presentacion.errores_usuarios import registrar_manejadores_usuarios

CABECERA_CLAVE = "X-Clave-Sensor"


def crear_blueprint_sensores(
    canjear: entrada.CanjearClaveDispositivo, verificador: VerificadorTokens, registrar: entrada.RegistrarLectura
) -> Blueprint:
    bp = Blueprint("api_v1_sensores", __name__, url_prefix="/api/v1/sensores")

    @bp.post("/<codigo>/mediciones")
    def medicion_del_sensor(codigo: str):
        medicion = esquemas.medicion_desde_json(request.get_json(silent=True))
        # Sin cabecera, la clave vacia no coincide con ninguna: el mismo 401 que una clave incorrecta.
        token = canjear.ejecutar(codigo, request.headers.get(CABECERA_CLAVE, "")).token
        identidad = verificador.verificar_dispositivo(token)
        reporte = ReporteDeDispositivo(identidad.codigo, datetime.now(timezone.utc), medicion)
        return jsonify(esquemas_usuarios.resultado_medicion_a_json(registrar.ejecutar(identidad, reporte))), 201

    registrar_manejadores_usuarios(bp)
    return bp
