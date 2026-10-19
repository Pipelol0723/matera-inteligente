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
