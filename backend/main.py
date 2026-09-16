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
from infraestructura.repositorio_especies_csv import RepositorioEspeciesCsv
from infraestructura.servidor_web import crear_app
from presentacion.rutas import crear_blueprint


def construir_app(config: Configuracion) -> Flask:
    # Pasar a una base de datos: cambiar solo esta linea por otra clase que implemente los puertos.
    especies = RepositorioEspeciesCsv(config.ruta_csv)

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
