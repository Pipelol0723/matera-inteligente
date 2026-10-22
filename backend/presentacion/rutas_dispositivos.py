"""Adaptador de entrada de los dispositivos (R2): la ESP32 y el simulador le hablan a la API por aqui.

Dos rutas, sin sesion de usuario:
  POST /api/v1/dispositivos/{codigo}/token     {"clave": "..."}  ->  {"token", "venceEn"}
  POST /api/v1/dispositivos/{codigo}/lecturas  Authorization: Bearer <token>
       {"dispositivo": "MT-0001-AA", "momento": "2026-10-22T15:04:05Z", "lecturas": {...}}  ->  201 con el diagnostico

El decorador con_dispositivo verifica el token: firma, vencimiento, alcance
«lecturas» y que sea del sensor de la URL. A la ruta le entrega la identidad,
y desde ahi nadie ve el token. Las rutas solo traducen HTTP <-> puerto de
entrada: las reglas viven en el nucleo, que no cambio para recibir esta ruta.
"""
from collections.abc import Callable
from functools import wraps

from flask import Blueprint, jsonify, request

from dominio import puertos_entrada as entrada
from dominio.errores_usuarios import CredencialDispositivoInvalida, DispositivoAjeno
from dominio.puertos_usuarios import VerificadorTokens
from presentacion import esquemas_dispositivos, esquemas_usuarios
from presentacion.autenticacion import token_bearer
from presentacion.errores_http import registrar_manejadores
from presentacion.errores_usuarios import registrar_manejadores_usuarios


def crear_blueprint_dispositivos(
    canjear: entrada.CanjearClaveDispositivo,
    registrar: entrada.RegistrarLectura,
    verificador: VerificadorTokens,
) -> Blueprint:
    bp = Blueprint("api_v1_dispositivos", __name__, url_prefix="/api/v1/dispositivos")
    con_dispositivo = _con_dispositivo(verificador)

    @bp.post("/<codigo>/token")
    def canjear_clave(codigo: str):
        clave = esquemas_dispositivos.clave_desde_json(request.get_json(silent=True))
        return jsonify(esquemas_dispositivos.token_a_json(canjear.ejecutar(codigo, clave)))

    @bp.post("/<codigo>/lecturas")
    @con_dispositivo
    def registrar_lectura(identidad, codigo: str):
        reporte = esquemas_dispositivos.reporte_desde_json(request.get_json(silent=True))
        return jsonify(esquemas_usuarios.resultado_medicion_a_json(registrar.ejecutar(identidad, reporte))), 201

    registrar_manejadores(bp)
    registrar_manejadores_usuarios(bp)
    return bp


def _con_dispositivo(verificador: VerificadorTokens) -> Callable[[Callable], Callable]:
    """Aqui se verifica el token del dispositivo. La ruta recibe la IdentidadDispositivo como primer argumento."""

    def decorador(vista: Callable) -> Callable:
        @wraps(vista)
        def envuelta(codigo: str, **kwargs):
            identidad = verificador.verificar_dispositivo(token_bearer(CredencialDispositivoInvalida))
            # El token solo sirve para su propio sensor: la URL de otro es un 403, igual que un cuerpo de otro.
            if identidad.codigo.valor != codigo.strip().upper():
                raise DispositivoAjeno(identidad.codigo.valor, codigo)
            return vista(identidad, codigo, **kwargs)

        return envuelta

    return decorador
