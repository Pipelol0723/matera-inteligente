"""La ruta del WebSocket: el front abre una conexion y recibe en vivo las mediciones de sus plantas.

El navegador no deja poner la cabecera Authorization en un WebSocket, y un
token en la URL quedaria en registros e historiales. Por eso el token llega en
el primer mensaje: {"tipo": "autenticar", "token": "..."}. Si no llega a
tiempo o no sirve, el servidor responde un error y cierra.

Despues de eso solo habla el servidor: {"tipo": "listo"} y luego un mensaje
{"tipo": "medicion"} por cada medicion nueva de las plantas del usuario. Todo
mensaje es JSON (RA1), tambien los errores inesperados. CORS no aplica a los
WebSocket, asi que el Origin se revisa aqui, contra los mismos origenes del front.
"""
import json
import logging
import queue
import socket
import threading
import time
from collections.abc import Callable, Iterable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any, Protocol

from flask import Blueprint, request
from flask_sock import Sock
from simple_websocket import ConnectionClosed
from werkzeug.routing.exceptions import WebsocketMismatch
from wsproto.utilities import RemoteProtocolError

from dominio import puertos_entrada as entrada
from dominio.errores_usuarios import SesionInvalida
from presentacion.errores_http import respuesta_error

_log = logging.getLogger(__name__)

RUTA = "/api/v1/tiempo-real"
# Segundos que se espera el mensaje con el token.
ESPERA_AUTENTICACION = 5
# Cada cuantos segundos se revisa la sesion de una conexion que no recibe nada.
REVISION_SESION = 60
# Mensajes que pueden esperar en la cola de una pestana. Si se llena, la pestana no esta leyendo.
COLA_MAXIMA = 32
# Cuanto se espera a que salga el ultimo mensaje antes de cerrar.
ESPERA_CIERRE = 5
# Cada cuanto el hilo de la conexion mira si el canal se corto.
ESPERA_MAXIMA = 1
# Codigos de cierre de WebSocket (RFC 6455): violacion de politica y error del servidor.
CIERRE_POR_POLITICA = 1008
CIERRE_POR_ERROR = 1011


@dataclass(frozen=True)
class _Cierre:
    codigo: int
    motivo: str


class CanalWebSocket:
    """Una conexion abierta, con su propia cola de mensajes y su hilo emisor.

    El hilo que trae una medicion (el POST del sensor) nunca escribe en el
    socket: deja el mensaje en la cola y sigue. El emisor los manda en orden. Si
    la pestana deja de leer y la cola se llena, se corta la conexion: asi un
    cliente lento no traba el POST del sensor ni a las otras pestanas del usuario.
    """

    def __init__(self, ws: Any):
        self._ws = ws
        self._cola: queue.Queue = queue.Queue(maxsize=COLA_MAXIMA)
        self._revisar_sesion: Callable[[], object] | None = None
        self._cortado = threading.Event()
        self._emisor = threading.Thread(target=self._enviar_en_orden, name="tiempo-real", daemon=True)
        self._emisor.start()

    @property
    def cortado(self) -> bool:
        """La conexion se corto: el hilo de la conexion tiene que terminar para que se cierre el socket."""
        return self._cortado.is_set()

    def autenticado(self, revisar_sesion: Callable[[], object]) -> None:
        """Desde aqui, antes de cada medicion se revisa la sesion.

        Asi una cuenta borrada o desactivada no recibe nada mas, aunque falten
        segundos para la revision periodica, y aunque una cuenta nueva herede su id.
        """
        self._revisar_sesion = revisar_sesion

    def enviar(self, texto: str) -> None:
        """Lo llama CanalesTiempoReal desde el hilo de la medicion. Si el canal ya no sirve, lanza ConnectionError."""
        if self._revisar_sesion is not None:
            try:
                self._revisar_sesion()
            except SesionInvalida as error:
                self._encolar_cierre("SESION_INVALIDA", str(error), CIERRE_POR_POLITICA)
                raise ConnectionError("La sesion de esta conexion ya no es valida.") from None
            except Exception:
                # Por ejemplo, la base bloqueada. Sin cerrar, la pestana quedaria "en vivo" sin recibir
                # nada; cerrada con 1011, el front se reconecta y vuelve a pedir sus datos.
                _log.exception("No se pudo revisar la sesion antes de mandar una medicion en vivo.")
                self._encolar_cierre("ERROR_INTERNO", "Ocurrió un error inesperado en el servidor.", CIERRE_POR_ERROR)
                raise ConnectionError("No se pudo revisar la sesion de esta conexion.") from None
        self._encolar(texto)

    def enviar_json(self, mensaje: dict[str, Any]) -> None:
        self._encolar(json.dumps(mensaje, ensure_ascii=False))

    def recibir(self, espera: float) -> str | bytes | None:
        """None si no llega nada en `espera` segundos. Si el cliente cerro, lanza ConnectionClosed."""
        return self._ws.receive(timeout=espera)

    def cerrar_con_error(self, error: str, mensaje: str, codigo: int = CIERRE_POR_POLITICA) -> None:
        """Manda el error en JSON y cierra. Espera a que salga: despues flask-sock cierra el socket."""
        self._encolar_cierre(error, mensaje, codigo)
        self._emisor.join(timeout=ESPERA_CIERRE)
        if self._emisor.is_alive():
            # El emisor quedo trabado en una pestana que no lee: si no se corta, el cierre de
            # flask-sock tambien se trabaria escribiendo en ese socket.
            self._cortar()

    def terminar(self) -> None:
        """La conexion termino: se detiene el emisor y se apaga el socket.

        Hay que apagarlo antes de devolverle el control a flask-sock. Si no, el
        servidor de Werkzeug escribe una respuesta HTTP en el mismo socket (el
        close() de simple-websocket no lo cierra mientras Werkzeug lo tenga
        abierto), y el navegador la lee como una trama invalida.
        """
        try:
            self._cola.put_nowait(None)
        except queue.Full:
            self._cortar()
        self._emisor.join(timeout=ESPERA_CIERRE)
        hilo_lector = getattr(self._ws, "thread", None)  # el de simple-websocket: termina el cierre
        if hilo_lector is not None:
            hilo_lector.join(timeout=ESPERA_CIERRE)
        self._apagar_socket()

    def _encolar(self, elemento: str | _Cierre) -> None:
        try:
            self._cola.put_nowait(elemento)
        except queue.Full:
            self._cortar()
            raise ConnectionError("La pestana no esta leyendo los mensajes.") from None

    def _encolar_cierre(self, error: str, mensaje: str, codigo: int) -> None:
        try:
            self._encolar(json.dumps({"tipo": "error", "error": error, "mensaje": mensaje}, ensure_ascii=False))
            self._encolar(_Cierre(codigo, error))
        except ConnectionError:
            pass  # la cola estaba llena y la conexion ya se corto

    def _enviar_en_orden(self) -> None:
        while True:
            elemento = self._cola.get()
            if elemento is None:
                return
            try:
                if isinstance(elemento, _Cierre):
                    self._ws.close(reason=elemento.codigo, message=elemento.motivo)
                    return
                self._ws.send(elemento)
            except Exception:  # ConnectionClosed u OSError: la pestana ya no esta
                self._cortar()
                return

    def _cortar(self) -> None:
        # shutdown() hace fallar enseguida los envios que vengan despues. En Windows no destraba un
        # envio que ya esta esperando: por eso tambien se avisa al hilo de la conexion, que termina,
        # y al terminar Werkzeug cierra el socket de verdad.
        self._cortado.set()
        self._apagar_socket()

    def _apagar_socket(self) -> None:
        try:
            self._ws.sock.shutdown(socket.SHUT_RDWR)
        except (AttributeError, OSError):
            pass


class Suscripciones(Protocol):
    """Lo que esta ruta necesita de quien guarda las conexiones abiertas.

    Lo cumple infraestructura.tiempo_real.CanalesTiempoReal, y main.py se lo pasa:
    presentacion no importa infraestructura.
    """

    def conectado(self, usuario_id: int, canal: CanalWebSocket) -> AbstractContextManager[None]: ...


def crear_blueprint_tiempo_real(
    identificar: entrada.IdentificarUsuario, suscripciones: Suscripciones, origenes: Iterable[str]
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
        try:
            _atender(canal, identificar, suscripciones)
        except ConnectionClosed:
            raise  # el cliente cerro: flask-sock termina la conexion
        except Exception:
            # Ya no se puede responder un 500 por HTTP: el socket habla WebSocket. El error va en JSON.
            _log.exception("Error inesperado en la conexion en vivo.")
            canal.cerrar_con_error("ERROR_INTERNO", "Ocurrió un error inesperado en el servidor.", CIERRE_POR_ERROR)
        finally:
            canal.terminar()

    @bp.app_errorhandler(WebsocketMismatch)
    def websocket_equivocado(error: WebsocketMismatch):
        # Sin esto, un GET normal a la ruta del WebSocket recibiria el texto en ingles de Werkzeug.
        if request.path == RUTA:
            mensaje = f"{RUTA} es un WebSocket: ábralo con new WebSocket(...), no con fetch."
        else:
            mensaje = f"{request.path} no es un WebSocket: pídala por HTTP."
        return respuesta_error(400, "SOLICITUD_INVALIDA", mensaje, {"ruta": request.path})

    @bp.app_errorhandler(RemoteProtocolError)
    def apertura_invalida(error: RemoteProtocolError):
        # Un pedido de apertura sin Sec-WebSocket-Key o con otra version: es un error del cliente, no un 500.
        return respuesta_error(
            400,
            "SOLICITUD_INVALIDA",
            "El pedido para abrir el WebSocket no es válido: faltan Sec-WebSocket-Key o Sec-WebSocket-Version: 13.",
            {"ruta": request.path},
        )

    return bp


def _atender(canal: CanalWebSocket, identificar: entrada.IdentificarUsuario, suscripciones: Suscripciones) -> None:
    token = _token_del_primer_mensaje(canal)
    if token is None:
        return
    try:
        usuario = identificar.ejecutar(token)
    except SesionInvalida as error:
        canal.cerrar_con_error("SESION_INVALIDA", str(error))
        return

    canal.autenticado(lambda: identificar.ejecutar(token))
    # Primero se registra y despues se dice "listo": desde ese mensaje no se pierde ninguna medicion.
    with suscripciones.conectado(usuario.id, canal):
        canal.enviar_json({"tipo": "listo", "usuario": {"id": usuario.id, "nombre": usuario.nombre}})
        _esperar_hasta_que_cierre(canal, identificar, token)


def _token_del_primer_mensaje(canal: CanalWebSocket) -> str | None:
    texto = canal.recibir(ESPERA_AUTENTICACION)
    if texto is None:
        canal.cerrar_con_error("SESION_INVALIDA", f"No llegó el token en {ESPERA_AUTENTICACION} segundos.")
        return None
    try:
        mensaje = json.loads(texto)
    except (ValueError, RecursionError):  # RecursionError: un JSON anidado miles de veces
        mensaje = None
    token = mensaje.get("token") if isinstance(mensaje, dict) and mensaje.get("tipo") == "autenticar" else None
    if not isinstance(token, str) or not token.strip():
        canal.cerrar_con_error(
            "SOLICITUD_INVALIDA", 'El primer mensaje debe ser {"tipo": "autenticar", "token": "..."}.'
        )
        return None
    if not token.isascii():
        # Los tokens que entrega la API son ASCII; uno con otros caracteres no puede ser valido.
        canal.cerrar_con_error("SESION_INVALIDA", str(SesionInvalida()))
        return None
    return token.strip()


def _esperar_hasta_que_cierre(canal: CanalWebSocket, identificar: entrada.IdentificarUsuario, token: str) -> None:
    """El front no manda nada mas: cualquier otro mensaje se ignora.

    Cada REVISION_SESION segundos se revisa la sesion, aunque el cliente mande
    mensajes, para cerrar tambien las conexiones que no reciben mediciones. Cuando
    el cliente cierra, recibir() lanza ConnectionClosed y flask-sock termina la conexion.
    Se espera de a ESPERA_MAXIMA segundos para notar pronto un canal cortado.
    """
    revisada = time.monotonic()
    while True:
        if canal.cortado:
            return
        restante = revisada + REVISION_SESION - time.monotonic()
        canal.recibir(min(ESPERA_MAXIMA, max(0.0, restante)))
        if time.monotonic() - revisada < REVISION_SESION:
            continue
        try:
            identificar.ejecutar(token)
        except SesionInvalida as error:
            canal.cerrar_con_error("SESION_INVALIDA", str(error))
            return
        revisada = time.monotonic()
