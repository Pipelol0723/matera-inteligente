"""Raiz de composicion: el unico lugar que elige clases concretas y las conecta.

Uso, desde la carpeta backend/:
    python main.py
"""
from flask import Flask

from aplicacion.diagnosticar_planta import DiagnosticarPlanta
from aplicacion.listar_especies import ListarEspecies
from aplicacion.listar_parametros import ListarParametros
from dominio.evaluador import EvaluadorPlanta
from dominio.parametros import PARAMETROS
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from infraestructura.configuracion import Configuracion
from infraestructura.servidor_web import crear_app
from infraestructura.sqlite import BaseDatos, RepositorioEspeciesSqlite
from presentacion.rutas import crear_blueprint


def construir_app(config: Configuracion) -> Flask:
    # Escenario 5.2: las especies salen de SQLite. Cambiar de base es cambiar solo esta linea.
    especies = RepositorioEspeciesSqlite(BaseDatos(config.ruta_bd).preparar())

    # Cambiar la regla del estado global: cambiar solo esta linea.
    evaluador = EvaluadorPlanta(ReglaHibrida(umbral=0.5), GeneradorRecomendaciones())
    servicio = ServicioDiagnostico(especies, evaluador)

    api = crear_blueprint(
        diagnosticar=DiagnosticarPlanta(servicio),
        listar=ListarEspecies(especies),
        listar_parametros=ListarParametros(PARAMETROS),
    )
    return crear_app(api, config)


if __name__ == "__main__":
    configuracion = Configuracion.desde_entorno()
    construir_app(configuracion).run(host="127.0.0.1", port=configuracion.puerto, debug=False)
