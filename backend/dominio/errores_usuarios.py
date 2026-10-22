"""Errores de negocio de cuentas, plantas y sensores (corte 2).

Heredan de ErrorDominio, como los del corte 1: no saben nada de HTTP, y la
capa de presentacion decide con que codigo y con que mensaje se muestran.
"""
from dominio.errores import ErrorDominio


class CorreoInvalido(ErrorDominio):
    """El texto no tiene forma de correo."""

    def __init__(self, texto: str):
        super().__init__(f"'{texto}' no es un correo válido.")
        self.texto = texto


class NombreInvalido(ErrorDominio):
    """Nombre de usuario vacio o demasiado largo."""

    def __init__(self, maximo: int):
        super().__init__(f"El nombre no puede estar vacío ni tener más de {maximo} caracteres.")
        self.maximo = maximo


class ContrasenaDebil(ErrorDominio):
    """La contrasena no cumple la politica minima."""

    def __init__(self, minimo: int):
        super().__init__(f"La contraseña debe tener al menos {minimo} caracteres.")
        self.minimo = minimo


class CorreoYaRegistrado(ErrorDominio):
    def __init__(self, correo: str):
        super().__init__(f"Ya existe una cuenta con el correo {correo}.")
        self.correo = correo


class CredencialesInvalidas(ErrorDominio):
    """El mismo error si el correo no existe o si la contrasena no coincide: no revela cual fallo."""

    def __init__(self):
        super().__init__("El correo o la contraseña no son correctos.")


class CuentaDesactivada(ErrorDominio):
    def __init__(self):
        super().__init__("La cuenta está desactivada. Hable con un administrador.")


class SesionInvalida(ErrorDominio):
    """Falta el token, su firma no es valida, ya vencio, se cerro la sesion o la cuenta esta desactivada."""

    def __init__(self):
        super().__init__("La sesión no es válida o ya venció. Inicie sesión de nuevo.")


class AlcanceInvalido(ErrorDominio):
    """El token es valido, pero es para otra cosa: por ejemplo, el de un sensor en una ruta de usuario."""

    def __init__(self, esperado: str):
        super().__init__(f"Este token no sirve aquí: se necesita uno de {esperado}.")
        self.esperado = esperado


class PermisoDenegado(ErrorDominio):
    def __init__(self):
        super().__init__("Esta acción es solo para administradores.")


class AccionSobreSiMismo(ErrorDominio):
    def __init__(self):
        super().__init__("Un administrador no puede desactivarse, quitarse el rol ni eliminarse a sí mismo.")


class UsuarioNoEncontrado(ErrorDominio):
    def __init__(self, referencia: int | str):
        super().__init__(f"No existe el usuario {referencia}.")
        self.referencia = referencia


class EspecieYaExiste(ErrorDominio):
    def __init__(self, nombre: str):
        super().__init__(f"La especie '{nombre}' ya existe.")
        self.nombre = nombre


class TablaDeSoloLectura(ErrorDominio):
    """La tabla de referencia que se esta usando no admite cambios, como la copia en CSV."""

    def __init__(self):
        super().__init__("La tabla de especies que se está usando es de solo lectura: no se pueden agregar especies.")


class PlantaNoEncontrada(ErrorDominio):
    """Tambien cuando la planta existe pero es de otro usuario: no se confirma que exista."""

    def __init__(self, planta_id: int):
        super().__init__(f"No existe la planta {planta_id}.")
        self.planta_id = planta_id


class ApodoInvalido(ErrorDominio):
    def __init__(self, maximo: int):
        super().__init__(f"El apodo no puede estar vacío ni tener más de {maximo} caracteres.")
        self.maximo = maximo


class ApodoRepetido(ErrorDominio):
    def __init__(self, apodo: str):
        super().__init__(f"Ya tiene una planta llamada '{apodo}'.")
        self.apodo = apodo


class CodigoSensorInvalido(ErrorDominio):
    def __init__(self, texto: str):
        super().__init__(f"'{texto}' no es un código de sensor válido: debe tener la forma MT-0000-XX.")
        self.texto = texto


class SensorYaVinculado(ErrorDominio):
    def __init__(self, codigo: str):
        super().__init__(f"El sensor {codigo} ya está vinculado a otra planta.")
        self.codigo = codigo


class ClaveSensorInvalida(ErrorDominio):
    """El mismo error si el sensor no existe o si la clave no coincide."""

    def __init__(self):
        super().__init__("El código del sensor o su clave no son correctos.")


class CredencialDispositivoInvalida(ErrorDominio):
    """Falta el token del dispositivo, su firma no es valida, ya vencio o lo reemplazo un canje nuevo.

    La placa responde a este error canjeando su clave otra vez.
    """

    def __init__(self):
        super().__init__("El token del dispositivo no es válido o ya venció: canjee la clave por uno nuevo.")


class DispositivoAjeno(ErrorDominio):
    """El reporte dice venir de un dispositivo distinto del que se autentico."""

    def __init__(self, autenticado: str, reportado: str):
        super().__init__(f"El sensor {autenticado} solo puede reportar sus propias lecturas, no las de {reportado}.")
        self.autenticado = autenticado
        self.reportado = reportado


class MomentoInvalido(ErrorDominio):
    """La hora de una lectura no sirve: no tiene zona horaria o es del futuro."""
