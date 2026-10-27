"""Raiz de composicion: el unico lugar que elige clases concretas y las conecta.

Arma la app (construir_app) y las piezas de los comandos de consola
(construir_consola): crear_admin.py y exportar_especies_csv.py no arman nada
por su cuenta.

Uso, desde la carpeta backend/:
    python main.py
"""
from collections.abc import Callable
from dataclasses import dataclass

from flask import Flask

from aplicacion.administracion import (
    AgregarEspecie,
    CambiarEstadoUsuario,
    CambiarRol,
    ConvertirEnAdministrador,
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
from dominio import puertos_entrada as entrada
from dominio.evaluador import EvaluadorPlanta
from dominio.parametros import PARAMETROS
from dominio.puertos import ConsultaRangos
from dominio.puertos_usuarios import RegistroEspecies
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from infraestructura.configuracion import Configuracion
from infraestructura.reloj import RelojSistema
from infraestructura.repositorio_especies_csv import (
    ErrorTablaReferencia,
    EspeciesDeSoloLectura,
    RegistroEspeciesConCopiaCsv,
    RepositorioEspeciesCsv,
    escribir_csv,
    exigir_copia_al_dia,
)
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
from presentacion.rutas_dispositivos import crear_blueprint_dispositivos
from presentacion.rutas_plantas import crear_blueprint_plantas
from presentacion.rutas_usuarios import crear_blueprint_usuarios
from presentacion.tiempo_real import crear_blueprint_tiempo_real


def _tabla_de_referencia(config: Configuracion, bd: BaseDatos) -> tuple[ConsultaRangos, RegistroEspecies]:
    """R4: la tabla sale del CSV o de SQLite segun MATERA_TABLA_REFERENCIA. Elegir es solo esto.

    Las dos implementan los puertos ConsultaRangos y CatalogoEspecies del corte 1.
    El CSV es una copia de la base y no se edita. Con la base, agregar una especie
    tambien vuelve a escribir la copia.
    """
    sqlite = RepositorioEspeciesSqlite(bd)
    if config.tabla_referencia == "csv":
        copia = RepositorioEspeciesCsv(config.ruta_tabla_csv)
        exigir_copia_al_dia(copia, sqlite, config.ruta_tabla_csv)  # si no es igual a la base, no arranca
        return copia, EspeciesDeSoloLectura()
    return sqlite, RegistroEspeciesConCopiaCsv(sqlite, sqlite, config.ruta_tabla_csv)


def construir_app(config: Configuracion) -> Flask:
    bd = BaseDatos(config.ruta_bd).preparar()
    especies, registro_especies = _tabla_de_referencia(config, bd)

    # Cambiar la regla del estado global: cambiar solo esta linea.
    evaluador = EvaluadorPlanta(ReglaHibrida(umbral=0.5), GeneradorRecomendaciones())
    servicio = ServicioDiagnostico(especies, evaluador)

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

    # R7: las rutas del corte 1 tambien exigen el JWT de usuario, como todas las del front.
    api = crear_blueprint(
        diagnosticar=DiagnosticarPlanta(servicio),
        listar=ListarEspecies(especies),
        listar_parametros=ListarParametros(PARAMETROS),
        autenticacion=autenticacion,
    )

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
        agregar_especie=AgregarEspecie(especies, registro_especies, PARAMETROS),
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
    # R2: la ESP32 y el simulador canjean su clave por un JWT de alcance «lecturas» y reportan con el.
    canjear = CanjearClaveDispositivo(
        sensores, sensores, plantas, usuarios, secretos, tokens, reloj, config.duracion_token_dispositivo
    )
    registrar_lectura = RegistrarLectura(sensores, usuarios, diagnosticar_planta, reloj)
    dispositivos = crear_blueprint_dispositivos(canjear, registrar_lectura, tokens)
    # El WebSocket del front registra sus conexiones en los mismos canales que usa el notificador.
    en_vivo = crear_blueprint_tiempo_real(tokens, identificar, canales, config.origenes_cors)

    return crear_app([api, cuentas, administracion, mis_plantas, dispositivos, en_vivo], config)


@dataclass(frozen=True)
class Consola:
    """Las piezas de los comandos de consola, armadas aqui igual que las de la app."""

    convertir_en_admin: entrada.ConvertirEnAdministrador
    # Escribe la copia en CSV de la tabla de la base y devuelve cuantas especies escribio.
    exportar_especies: Callable[[], int]


def construir_consola(config: Configuracion) -> Consola:
    bd = BaseDatos(config.ruta_bd).preparar()
    usuarios = RepositorioUsuariosSqlite(bd)
    especies = RepositorioEspeciesSqlite(bd)
    return Consola(
        convertir_en_admin=ConvertirEnAdministrador(usuarios, usuarios),
        exportar_especies=lambda: escribir_csv(especies.listar(), config.ruta_tabla_csv),
    )


if __name__ == "__main__":
    configuracion = Configuracion.desde_entorno()
    if configuracion.tabla_referencia == "csv":
        print(f"Tabla de referencia: la copia en CSV, {configuracion.ruta_tabla_csv} (solo lectura)")
    else:
        print(f"Tabla de referencia: la base de datos, {configuracion.ruta_bd}")
    try:
        app = construir_app(configuracion)
    except ErrorTablaReferencia as error:
        raise SystemExit(f"No se pudo arrancar: {error}") from None
    app.run(host=configuracion.host, port=configuracion.puerto, debug=False)
