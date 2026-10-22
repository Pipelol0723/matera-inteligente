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
from aplicacion.sensores import CanjearClaveDispositivo, ReemplazarSensor, RegistrarLectura
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
from infraestructura.tiempo_real import CanalesTiempoReal, NotificadorWebSocket
from infraestructura.tokens_jwt import TokensJwt, secreto_guardado
from presentacion import esquemas_usuarios
from presentacion.autenticacion import Autenticacion
from presentacion.rutas import crear_blueprint
from presentacion.rutas_admin import crear_blueprint_admin
from presentacion.rutas_plantas import crear_blueprint_plantas
from presentacion.rutas_sensores import crear_blueprint_sensores
from presentacion.rutas_usuarios import crear_blueprint_usuarios
from presentacion.tiempo_real import crear_blueprint_tiempo_real


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

    # Corte 2: cuentas, plantas, sensores e historial, en la misma base. Cada adaptador SQLite
    # implementa varios puertos pequenos: se pasa una vez por cada puerto que pide el caso de uso.
    usuarios = RepositorioUsuariosSqlite(bd)
    sesiones = RepositorioSesionesSqlite(bd)
    plantas = RepositorioPlantasSqlite(bd)
    sensores = RepositorioSensoresSqlite(bd)
    historial = HistorialMedicionesSqlite(bd)
    cifrador = CifradorPbkdf2(config.iteraciones_contrasena)
    secretos = GeneradorSecretosSeguro()
    reloj = RelojSistema()
    # Los JWT: los emite IniciarSesion y los verifican el decorador de las rutas y el WebSocket.
    tokens = TokensJwt(config.secreto_jwt or secreto_guardado(config.ruta_secreto_jwt), reloj)
    identificar = IdentificarUsuario(sesiones, usuarios, reloj)
    autenticacion = Autenticacion(tokens, identificar)

    cuentas = crear_blueprint_usuarios(
        registrar=RegistrarUsuario(usuarios, usuarios, cifrador),
        iniciar=IniciarSesion(usuarios, sesiones, cifrador, secretos, tokens, reloj, config.duracion_sesion),
        cerrar=CerrarSesion(sesiones),
        consultar=ConsultarCuenta(plantas),
        autenticacion=autenticacion,
    )
    administracion = crear_blueprint_admin(
        listar=ListarUsuarios(usuarios),
        cambiar_estado=CambiarEstadoUsuario(usuarios, usuarios, sesiones),
        cambiar_rol=CambiarRol(usuarios, usuarios),
        eliminar=EliminarUsuario(usuarios, usuarios),
        agregar_especie=AgregarEspecie(especies, especies, PARAMETROS),
        autenticacion=autenticacion,
    )

    # El aviso en vivo de cada medicion. Cambiar el WebSocket por MQTT: cambiar solo esta linea.
    canales = CanalesTiempoReal()
    notificador = NotificadorWebSocket(canales, esquemas_usuarios.medicion_en_vivo_a_json)

    # Las mediciones solo llegan del sensor, por el caso de uso de la 5.3, que reutiliza el servicio del corte 1.
    diagnosticar_planta = DiagnosticarPlantaDeUsuario(plantas, servicio, historial, notificador)
    mis_plantas = crear_blueprint_plantas(
        registrar=RegistrarPlanta(plantas, plantas, sensores, especies, secretos),
        listar=ListarPlantas(plantas, sensores, historial),
        eliminar=EliminarPlanta(plantas, plantas),
        reemplazar_sensor=ReemplazarSensor(plantas, sensores, secretos),
        consultar_historial=ConsultarHistorial(plantas, historial),
        autenticacion=autenticacion,
    )
    # El dispositivo canjea su clave por un JWT de alcance «lecturas» y reporta con el.
    canjear = CanjearClaveDispositivo(sensores, sensores, secretos, tokens, reloj, config.duracion_token_dispositivo)
    registrar_lectura = RegistrarLectura(sensores, diagnosticar_planta, reloj)
    entrada_sensor = crear_blueprint_sensores(canjear, tokens, registrar_lectura)
    # El WebSocket del front registra sus conexiones en los mismos canales que usa el notificador.
    en_vivo = crear_blueprint_tiempo_real(tokens, identificar, canales, config.origenes_cors)

    return crear_app([api, cuentas, administracion, mis_plantas, entrada_sensor, en_vivo], config)


if __name__ == "__main__":
    configuracion = Configuracion.desde_entorno()
    construir_app(configuracion).run(host=configuracion.host, port=configuracion.puerto, debug=False)
