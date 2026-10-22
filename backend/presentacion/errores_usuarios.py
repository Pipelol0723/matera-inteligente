"""Traduce los errores del corte 2 a respuestas HTTP, con el mismo cuerpo uniforme del corte 1 (RF6).

El dominio no sabe de codigos HTTP: la tabla de abajo es la unica que los decide.
"""
from flask import Blueprint

from dominio import errores_usuarios as e
from dominio.errores import ErrorDominio, ParametroSinRango, RangoInvalido
from presentacion.errores_http import respuesta_error

# Error del dominio -> (estado HTTP, codigo de error).
_TABLA: dict[type[ErrorDominio], tuple[int, str]] = {
    e.CorreoInvalido: (400, "PARAMETRO_INVALIDO"),
    e.NombreInvalido: (400, "PARAMETRO_INVALIDO"),
    e.ContrasenaDebil: (400, "PARAMETRO_INVALIDO"),
    e.ApodoInvalido: (400, "PARAMETRO_INVALIDO"),
    e.CodigoSensorInvalido: (400, "CODIGO_SENSOR_INVALIDO"),
    # El corte 1 no los manejaba y terminaban en 500; con especies nuevas pueden venir del cliente.
    RangoInvalido: (400, "PARAMETRO_INVALIDO"),
    ParametroSinRango: (400, "PARAMETRO_INVALIDO"),
    e.CredencialesInvalidas: (401, "CREDENCIALES_INVALIDAS"),
    e.SesionInvalida: (401, "SESION_INVALIDA"),
    e.ClaveSensorInvalida: (401, "CLAVE_SENSOR_INVALIDA"),
    e.CuentaDesactivada: (403, "CUENTA_DESACTIVADA"),
    # Un token valido pero de otro alcance (el de un sensor en una ruta de usuario): 403, no 401.
    e.AlcanceInvalido: (403, "ALCANCE_INVALIDO"),
    e.PermisoDenegado: (403, "PERMISO_DENEGADO"),
    # Una planta ajena tambien da 404: un 403 confirmaria que existe.
    e.PlantaNoEncontrada: (404, "PLANTA_NO_ENCONTRADA"),
    e.UsuarioNoEncontrado: (404, "USUARIO_NO_ENCONTRADO"),
    e.CorreoYaRegistrado: (409, "CORREO_YA_REGISTRADO"),
    e.AccionSobreSiMismo: (409, "ACCION_SOBRE_SI_MISMO"),
    e.EspecieYaExiste: (409, "ESPECIE_YA_EXISTE"),
    e.TablaDeSoloLectura: (409, "TABLA_SOLO_LECTURA"),
    e.ApodoRepetido: (409, "APODO_REPETIDO"),
    e.SensorYaVinculado: (409, "SENSOR_YA_VINCULADO"),
}

# Para los 400, el campo del formulario que hay que corregir.
_CAMPOS = {
    e.CorreoInvalido: "correo",
    e.NombreInvalido: "nombre",
    e.ContrasenaDebil: "contrasena",
    e.ApodoInvalido: "apodo",
    e.CodigoSensorInvalido: "codigo",
}


def registrar_manejadores_usuarios(bp: Blueprint) -> None:
    """Como en errores_http.py, los manejadores valen para toda la aplicacion.

    Lo llama cada blueprint del corte 2; registrar dos veces el mismo manejador no cambia nada.
    """
    for clase, (estado, codigo) in _TABLA.items():
        bp.app_errorhandler(clase)(_manejador(estado, codigo))


def _manejador(estado: int, codigo: str):
    def manejar(error: ErrorDominio):
        return respuesta_error(estado, codigo, str(error), _detalle(error))

    return manejar


def _detalle(error: ErrorDominio) -> dict:
    # Los datos simples que el error ya trae (el codigo del sensor, el id de la planta, el minimo...).
    detalle = {nombre: valor for nombre, valor in vars(error).items() if isinstance(valor, (str, int, float))}
    if type(error) in _CAMPOS:
        detalle.update(campo=_CAMPOS[type(error)], motivo="invalido")
    if isinstance(error, ParametroSinRango):
        detalle.update(campo=f"rangos.{error.parametro.nombre}", motivo="ausente")
    return detalle
