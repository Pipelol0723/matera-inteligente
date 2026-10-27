"""Arma la aplicacion Flask: framework, formato JSON y CORS. No conoce rutas ni reglas."""
import math
from collections.abc import Iterable

from flask import Blueprint, Flask, Response, request
from flask.json.provider import DefaultJSONProvider
from flask_cors import CORS

from infraestructura.configuracion import Configuracion


class _JsonEstricto(DefaultJSONProvider):
    """El JSON de las peticiones, sin lo que la libreria estandar acepta de mas.

    Rechaza NaN, Infinity y los numeros que no caben en un float (1e309, o un entero de
    400 cifras), los textos
    con medio caracter (un sustituto UTF-16 suelto, como U+D800) y los cuerpos anidados
    miles de veces. Todo eso llega a las rutas como un cuerpo que no es JSON: 400, no 500.
    """

    ensure_ascii = False
    sort_keys = False

    def loads(self, s, **kwargs):
        try:
            valor = super().loads(
                s, parse_constant=_sin_constantes, parse_float=_float_finito, parse_int=_entero_finito, **kwargs
            )
        except RecursionError:
            raise ValueError("El JSON esta anidado demasiadas veces.") from None
        _exigir_textos_validos(valor)
        return valor


def _sin_constantes(nombre: str):
    raise ValueError(f"{nombre} no es un numero JSON.")


def _float_finito(texto: str) -> float:
    valor = float(texto)
    if not math.isfinite(valor):
        raise ValueError(f"{texto} no cabe en un numero.")
    return valor


def _entero_finito(texto: str) -> int:
    valor = int(texto)
    try:
        float(valor)
    except OverflowError:
        raise ValueError(f"El entero de {len(texto)} cifras no cabe en un numero.") from None
    return valor


def _exigir_textos_validos(valor) -> None:
    pendientes = [valor]
    while pendientes:
        actual = pendientes.pop()
        if isinstance(actual, dict):
            pendientes.extend(actual.keys())
            pendientes.extend(actual.values())
        elif isinstance(actual, list):
            pendientes.extend(actual)
        elif isinstance(actual, str):
            actual.encode("utf-8")  # UnicodeEncodeError es un ValueError


def crear_app(blueprints: Iterable[Blueprint], config: Configuracion) -> Flask:
    # static_folder=None: este servidor no entrega archivos ni paginas (RA1).
    app = Flask(__name__, static_folder=None)
    app.json = _JsonEstricto(app)
    # Sin esto, /api/v1//especies responde 308 con una pagina HTML; asi responde el 404 en JSON (RA1).
    app.url_map.merge_slashes = False
    # WebSocket (flask-sock): un ping cada 25 s mantiene viva la conexion en vivo y detecta
    # las pestanas que se fueron sin cerrarla. El unico mensaje que llega del front es el token.
    app.config["SOCK_SERVER_OPTIONS"] = {"ping_interval": 25, "max_message_size": 4096}

    # El front vive en otro origen (RA2); solo esos origenes pueden leer la API (RA7),
    # mandar el token de sesion y usar PUT, PATCH y DELETE. Las rutas de dispositivos las
    # usan la ESP32 y el simulador, que no son navegadores y no pasan por CORS.
    CORS(
        app,
        resources={r"/api/*": {"origins": list(config.origenes_cors)}},
        allow_headers=["Content-Type", "Authorization"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    @app.after_request
    def opciones_en_json(respuesta: Response) -> Response:
        # Flask responde solo los OPTIONS (la verificacion previa de CORS) con un cuerpo vacio en
        # text/html. Se responde un objeto JSON vacio, con las mismas cabeceras (RA1).
        if request.method == "OPTIONS" and respuesta.mimetype != "application/json":
            respuesta.set_data(b"{}")
            respuesta.mimetype = "application/json"
        return respuesta

    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    return app
