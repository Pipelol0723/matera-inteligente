"""Raiz de composicion: el unico lugar que elige clases concretas y las conecta.

Uso, desde la carpeta backend/:
    python main.py
"""
from flask import Flask

from aplicacion.administracion import (
    AgregarEspecie,
    CambiarEstadoUsuario,
    CambiarRol,
    EliminarUsuario,
    ListarUsuarios,
)
from aplicacion.cuentas import CerrarSesion, ConsultarCuenta, IdentificarUsuario, IniciarSesion, RegistrarUsuario
from aplicacion.diagnosticar_planta import DiagnosticarPlanta
from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.historial import ConsultarHistorial
from aplicacion.listar_especies import ListarEspecies
from aplicacion.listar_parametros import ListarParametros
from aplicacion.plantas import EliminarPlanta, ListarPlantas, RegistrarPlanta
from aplicacion.sensores import RecibirMedicionDeSensor, ReemplazarSensor
from dominio.evaluador import EvaluadorPlanta
from dominio.parametros import PARAMETROS
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from infraestructura.configuracion import Configuracion
from infraestructura.reloj import RelojSistema
from infraestructura.seguridad import CifradorPbkdf2, GeneradorSecretosSeguro
from infraestructura.servidor_web import crear_app
from infraestructura.sqlite import (
    BaseDatos,
    HistorialMedicionesSqlite,
    RepositorioEspeciesSqlite,
    RepositorioPlantasSqlite,
    RepositorioSensoresSqlite,
    RepositorioSesionesSqlite,
    RepositorioUsuariosSqlite,
)
from presentacion.autenticacion import Autenticacion
from presentacion.rutas import crear_blueprint
from presentacion.rutas_admin import crear_blueprint_admin
from presentacion.rutas_plantas import crear_blueprint_plantas
from presentacion.rutas_sensores import crear_blueprint_sensores
from presentacion.rutas_usuarios import crear_blueprint_usuarios


def construir_app(config: Configuracion) -> Flask:
    bd = BaseDatos(config.ruta_bd).preparar()
    # Escenario 5.2: las especies salen de SQLite. Cambiar de base es cambiar solo esta linea.
    especies = RepositorioEspeciesSqlite(bd)

    # Cambiar la regla del estado global: cambiar solo esta linea.
    evaluador = EvaluadorPlanta(ReglaHibrida(umbral=0.5), GeneradorRecomendaciones())
    servicio = ServicioDiagnostico(especies, evaluador)

    api = crear_blueprint(
        diagnosticar=DiagnosticarPlanta(servicio),
        listar=ListarEspecies(especies),
        listar_parametros=ListarParametros(PARAMETROS),
    )

    # Corte 2: cuentas, plantas, sensores e historial, en la misma base.
    usuarios = RepositorioUsuariosSqlite(bd)
    sesiones = RepositorioSesionesSqlite(bd)
    plantas = RepositorioPlantasSqlite(bd)
    sensores = RepositorioSensoresSqlite(bd)
    historial = HistorialMedicionesSqlite(bd)
    cifrador = CifradorPbkdf2(config.iteraciones_contrasena)
    secretos = GeneradorSecretosSeguro()
    reloj = RelojSistema()
    autenticacion = Autenticacion(IdentificarUsuario(sesiones, usuarios, secretos, reloj))

    cuentas = crear_blueprint_usuarios(
        registrar=RegistrarUsuario(usuarios, cifrador),
        iniciar=IniciarSesion(usuarios, sesiones, cifrador, secretos, reloj, config.duracion_sesion),
        cerrar=CerrarSesion(sesiones, secretos),
        consultar=ConsultarCuenta(plantas),
        autenticacion=autenticacion,
    )
    administracion = crear_blueprint_admin(
        listar=ListarUsuarios(usuarios),
        cambiar_estado=CambiarEstadoUsuario(usuarios, sesiones),
        cambiar_rol=CambiarRol(usuarios),
        eliminar=EliminarUsuario(usuarios),
        agregar_especie=AgregarEspecie(especies, especies, PARAMETROS),
        autenticacion=autenticacion,
    )

    # La medicion manual y la del sensor pasan por el mismo caso de uso, que reutiliza el servicio del corte 1.
    diagnosticar_planta = DiagnosticarPlantaDeUsuario(plantas, servicio, historial, reloj)
    mis_plantas = crear_blueprint_plantas(
        registrar=RegistrarPlanta(plantas, sensores, especies, secretos),
        listar=ListarPlantas(plantas, sensores, historial),
        eliminar=EliminarPlanta(plantas),
        reemplazar_sensor=ReemplazarSensor(plantas, sensores, secretos),
        consultar_historial=ConsultarHistorial(plantas, historial),
        diagnosticar=diagnosticar_planta,
        autenticacion=autenticacion,
    )
    entrada_sensor = crear_blueprint_sensores(RecibirMedicionDeSensor(sensores, plantas, secretos, diagnosticar_planta))

    return crear_app([api, cuentas, administracion, mis_plantas, entrada_sensor], config)


if __name__ == "__main__":
    configuracion = Configuracion.desde_entorno()
    construir_app(configuracion).run(host=configuracion.host, port=configuracion.puerto, debug=False)
