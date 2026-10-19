"""La ruta del WebSocket: el front abre una conexion y recibe en vivo las mediciones de sus plantas.

El navegador no deja poner la cabecera Authorization en un WebSocket, y un
token en la URL quedaria en registros e historiales. Por eso el token llega en
el primer mensaje: {"tipo": "autenticar", "token": "..."}. Si no llega a
tiempo o no sirve, el servidor responde un error y cierra.

Despues de eso solo habla el servidor: {"tipo": "listo"} y luego un mensaje
{"tipo": "medicion"} por cada medicion nueva de las plantas del usuario. Todo
mensaje es JSON (RA1). CORS no aplica a los WebSocket, asi que el Origin se
revisa aqui, contra los mismos origenes del front.
"""
import json
import threading
import time
from collections.abc import Iterable
from contextlib import AbstractContextManager
from typing import Any, Protocol

from flask import Blueprint, request
from flask_sock import Sock
from werkzeug.routing.exceptions import WebsocketMismatch

from aplicacion.cuentas import IdentificarUsuario
from dominio.errores_usuarios import SesionInvalida
from presentacion.errores_http import respuesta_error

RUTA = "/api/v1/tiempo-real"
# Segundos que se espera el mensaje con el token.
ESPERA_AUTENTICACION = 5
# Cada cuantos segundos se revisa que la sesion siga valida (cerrada, vencida o cuenta desactivada).
REVISION_SESION = 60
# Codigo de cierre de WebSocket para "violacion de politica" (RFC 6455).
_CIERRE_POR_POLITICA = 1008


class CanalWebSocket:
    """Una conexion abierta.

    Dos mediciones pueden llegar al mismo tiempo, cada una en su hilo: el candado
    evita que sus mensajes se mezclen en el socket.
    """

    def __init__(self, ws: Any):
        self._ws = ws
        self._candado = threading.Lock()

    def enviar(self, texto: str) -> None:
        with self._candado:
            self._ws.send(texto)

    def enviar_json(self, mensaje: dict[str, Any]) -> None:
        self.enviar(json.dumps(mensaje, ensure_ascii=False))

    def recibir(self, espera: float) -> str | bytes | None:
        """None si no llega nada en `espera` segundos. Si el cliente cerro, lanza ConnectionClosed."""
        return self._ws.receive(timeout=espera)

    def cerrar_con_error(self, error: str, mensaje: str) -> None:
        self.enviar_json({"tipo": "error", "error": error, "mensaje": mensaje})
        with self._candado:
            self._ws.close(reason=_CIERRE_POR_POLITICA, message=error)


class Suscripciones(Protocol):
    """Lo que esta ruta necesita de quien guarda las conexiones abiertas.

    Lo cumple infraestructura.tiempo_real.CanalesTiempoReal, y main.py se lo pasa:
    presentacion no importa infraestructura.
    """

    def conectado(self, usuario_id: int, canal: CanalWebSocket) -> AbstractContextManager[None]: ...


def crear_blueprint_tiempo_real(
    identificar: IdentificarUsuario, suscripciones: Suscripciones, origenes: Iterable[str]
) -> Blueprint:
    bp = Blueprint("api_v1_tiempo_real", __name__)
    permitidos = frozenset(origenes)

    @bp.before_request
    def revisar_origen():
        # Se revisa antes de aceptar la conexion. Un navegador siempre manda Origin; un
        # script puede no mandarlo, y aun asi necesita el token para recibir algo.
        origen = request.headers.get("Origin")
        if origen is not None and origen not in permitidos:
            return respuesta_error(
                403,
                "ORIGEN_NO_PERMITIDO",
                f"El origen {origen} no puede abrir la conexión en vivo.",
                {"origen": origen},
            )
        return None

    @Sock().route(RUTA, bp=bp)
    def tiempo_real(ws):
        canal = CanalWebSocket(ws)
        token = _token_del_primer_mensaje(canal)
        if token is None:
            return
        try:
            usuario = identificar.ejecutar(token)
        except SesionInvalida as error:
            canal.cerrar_con_error("SESION_INVALIDA", str(error))
            return

        canal.enviar_json({"tipo": "listo", "usuario": {"id": usuario.id, "nombre": usuario.nombre}})
        with suscripciones.conectado(usuario.id, canal):
            _esperar_hasta_que_cierre(canal, identificar, token)

    @bp.app_errorhandler(WebsocketMismatch)
    def websocket_equivocado(error: WebsocketMismatch):
        # Sin esto, un GET normal a la ruta del WebSocket recibiria el texto en ingles de Werkzeug.
        if request.path == RUTA:
            mensaje = f"{RUTA} es un WebSocket: ábralo con new WebSocket(...), no con fetch."
        else:
            mensaje = f"{request.path} no es un WebSocket: pídala por HTTP."
        return respuesta_error(400, "SOLICITUD_INVALIDA", mensaje, {"ruta": request.path})

    return bp


def _token_del_primer_mensaje(canal: CanalWebSocket) -> str | None:
    texto = canal.recibir(ESPERA_AUTENTICACION)
    if texto is None:
        canal.cerrar_con_error("SESION_INVALIDA", f"No llegó el token en {ESPERA_AUTENTICACION} segundos.")
        return None
    try:
        mensaje = json.loads(texto)
    except ValueError:
        mensaje = None
    token = mensaje.get("token") if isinstance(mensaje, dict) and mensaje.get("tipo") == "autenticar" else None
    if not isinstance(token, str) or not token.strip():
        canal.cerrar_con_error(
            "SOLICITUD_INVALIDA", 'El primer mensaje debe ser {"tipo": "autenticar", "token": "..."}.'
        )
        return None
    return token.strip()


def _esperar_hasta_que_cierre(canal: CanalWebSocket, identificar: IdentificarUsuario, token: str) -> None:
    """El front no manda nada mas: cualquier otro mensaje se ignora.

    Cada REVISION_SESION segundos se revisa la sesion, aunque el cliente mande
    mensajes. Si se cerro, vencio o un admin desactivo la cuenta, el canal se
    cierra. Cuando el cliente cierra, recibir() lanza ConnectionClosed y
    flask-sock termina la conexion.
    """
    revisada = time.monotonic()
    while True:
        canal.recibir(max(0.0, revisada + REVISION_SESION - time.monotonic()))
        if time.monotonic() - revisada < REVISION_SESION:
            continue
        try:
            identificar.ejecutar(token)
        except SesionInvalida as error:
            canal.cerrar_con_error("SESION_INVALIDA", str(error))
            return
        revisada = time.monotonic()
