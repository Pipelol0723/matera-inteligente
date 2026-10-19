"""Arma la aplicacion Flask: framework, formato JSON y CORS. No conoce rutas ni reglas."""
from collections.abc import Iterable

from flask import Blueprint, Flask
from flask_cors import CORS

from infraestructura.configuracion import Configuracion


def crear_app(blueprints: Iterable[Blueprint], config: Configuracion) -> Flask:
    # static_folder=None: este servidor no entrega archivos ni paginas (RA1).
    app = Flask(__name__, static_folder=None)
    app.json.ensure_ascii = False
    app.json.sort_keys = False
    # WebSocket (flask-sock): un ping cada 25 s mantiene viva la conexion en vivo y detecta
    # las pestanas que se fueron sin cerrarla. El unico mensaje que llega del front es el token.
    app.config["SOCK_SERVER_OPTIONS"] = {"ping_interval": 25, "max_message_size": 4096}

    # El front vive en otro origen (RA2); solo esos origenes pueden leer la API (RA7),
    # mandar el token de sesion o la clave de un sensor, y usar PUT, PATCH y DELETE.
    CORS(
        app,
        resources={r"/api/*": {"origins": list(config.origenes_cors)}},
        allow_headers=["Content-Type", "Authorization", "X-Clave-Sensor"],
        methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    )

    for blueprint in blueprints:
        app.register_blueprint(blueprint)
    return app
