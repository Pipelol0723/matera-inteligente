"""Dobles en memoria de los puertos del corte 2.

Como tests/dobles.py, solo importa el dominio: las pruebas de dominio y de
aplicacion siguen pasando aunque se borre la carpeta infraestructura (RA4).
Las cascadas de la base de datos (borrar un usuario borra sus plantas) no se
imitan aqui: las prueban las pruebas de integracion con SQLite. La unica
excepcion es el sensor de una planta borrada, porque la planta y su sensor
nacen juntos.
"""
from dataclasses import replace
from datetime import datetime, timedelta

from dominio.diagnostico import Diagnostico
from dominio.errores_usuarios import (
    AlcanceInvalido,
    ApodoRepetido,
    CorreoYaRegistrado,
    CredencialDispositivoInvalida,
    EspecieYaExiste,
    PlantaNoEncontrada,
    SensorYaVinculado,
    SesionInvalida,
)
from dominio.especie import Especie
from dominio.historial import RegistroMedicion
from dominio.identidad import IdentidadDispositivo, IdentidadUsuario
from dominio.plantas import Planta
from dominio.puertos_usuarios import (
    Cifrador,
    ConsultaCuentas,
    ConsultaPlantas,
    CredencialesSensor,
    EmisorTokens,
    GeneradorSecretos,
    HistorialMediciones,
    ListadoCuentas,
    NotificadorDiagnosticos,
    RegistroCuentas,
    RegistroEspecies,
    RegistroPlantas,
    Reloj,
    SensoresVinculados,
    SesionesAbiertas,
    VerificadorTokens,
)
from dominio.sensores import CodigoSensor, Sensor
from dominio.usuarios import Correo, ResumenUsuario, Sesion, Usuario
from tests.dobles import RepositorioEspeciesEnMemoria


class EspeciesEditablesEnMemoria(RepositorioEspeciesEnMemoria, RegistroEspecies):
    """El doble de especies del corte 1, mas el puerto para agregar."""

    def agregar(self, especie: Especie) -> None:
        if especie.nombre in self._especies:
            raise EspecieYaExiste(especie.nombre)
        self._especies[especie.nombre] = especie


class RepositorioSensoresEnMemoria(SensoresVinculados, CredencialesSensor):
    """Los sensores y, como la columna token_id de la base, el id del token vigente de cada uno."""

    def __init__(self):
        self._sensores: dict[str, Sensor] = {}
        self._tokens: dict[str, str] = {}
        # Lo conecta RepositorioPlantasEnMemoria: la planta guardada con ese id, como el JOIN de la base.
        self.planta_con_id = lambda planta_id: None

    def por_codigo(self, codigo: CodigoSensor) -> Sensor | None:
        return self._sensores.get(codigo.valor)

    def de_planta(self, planta_id: int) -> Sensor | None:
        return next((s for s in self._sensores.values() if s.planta_id == planta_id), None)

    def reemplazar(self, planta: Planta, sensor: Sensor) -> None:
        # Como la base: la planta tiene que seguir siendo la que se leyo (mismo id y mismo dueno).
        guardada = self.planta_con_id(planta.id)
        if guardada is None or guardada.usuario_id != planta.usuario_id:
            raise PlantaNoEncontrada(planta.id)
        en_uso = self._sensores.get(sensor.codigo.valor)
        if en_uso is not None and en_uso.planta_id != sensor.planta_id:
            raise SensorYaVinculado(sensor.codigo.valor)
        self.quitar_de_planta(sensor.planta_id)
        self._sensores[sensor.codigo.valor] = sensor  # el sensor nuevo nace sin token vigente

    def renovar(self, sensor: Sensor, token_id: str) -> bool:
        # Solo si el sensor guardado sigue siendo ese mismo (codigo, planta y huella). Lee lo guardado
        # y no por_codigo(), que una prueba puede reemplazar para simular una lectura vieja.
        if self._sensores.get(sensor.codigo.valor) != sensor:
            return False
        self._tokens[sensor.codigo.valor] = token_id
        return True

    def planta_con_token(self, codigo: CodigoSensor, token_id: str) -> Planta | None:
        sensor = self._sensores.get(codigo.valor)
        if sensor is None or self._tokens.get(codigo.valor) != token_id:
            return None
        return self.planta_con_id(sensor.planta_id)

    def quitar_de_planta(self, planta_id: int) -> None:
        """No es del puerto: imita la cascada de la base al borrar una planta."""
        quitados = {c for c, s in self._sensores.items() if s.planta_id == planta_id}
        self._sensores = {c: s for c, s in self._sensores.items() if c not in quitados}
        self._tokens = {c: t for c, t in self._tokens.items() if c not in quitados}


class RepositorioPlantasEnMemoria(ConsultaPlantas, RegistroPlantas):
    """Como la base, no filtra por dueno: si una prueba pide la planta de otro, la regla del dominio la rechaza."""

    def __init__(self, sensores: RepositorioSensoresEnMemoria | None = None):
        self._plantas: dict[int, Planta] = {}
        self._siguiente_id = 1
        self._sensores = sensores or RepositorioSensoresEnMemoria()
        self._sensores.planta_con_id = self._plantas.get

    def guardar_con_sensor(self, planta: Planta, codigo: CodigoSensor, hash_clave: str) -> Planta:
        # Revisa todo antes de guardar nada, como la transaccion de la base.
        if any(p.es_de(planta.usuario_id) and p.mismo_apodo(planta.apodo) for p in self._plantas.values()):
            raise ApodoRepetido(planta.apodo)
        if self._sensores.por_codigo(codigo) is not None:
            raise SensorYaVinculado(codigo.valor)
        guardada = replace(planta, id=self._siguiente_id)
        self._plantas[guardada.id] = guardada
        self._siguiente_id += 1
        self._sensores.reemplazar(guardada, Sensor(codigo, guardada.id, hash_clave))
        return guardada

    def de_usuario(self, usuario_id: int) -> list[Planta]:
        return [p for p in self._plantas.values() if p.es_de(usuario_id)]

    def por_id(self, planta_id: int) -> Planta | None:
        return self._plantas.get(planta_id)

    def eliminar(self, planta: Planta) -> None:
        guardada = self._plantas.get(planta.id)
        if guardada is not None and guardada.usuario_id == planta.usuario_id:
            del self._plantas[planta.id]
            self._sensores.quitar_de_planta(planta.id)


def codigo(numero: int) -> CodigoSensor:
    """Un codigo de sensor distinto para cada planta de una prueba: MT-0001-AA, MT-0002-AA..."""
    return CodigoSensor(f"MT-{numero:04d}-AA")


class RepositorioUsuariosEnMemoria(ConsultaCuentas, RegistroCuentas, ListadoCuentas):
    def __init__(self, plantas: RepositorioPlantasEnMemoria | None = None):
        self._usuarios: dict[int, Usuario] = {}
        self._siguiente_id = 1
        self._plantas = plantas or RepositorioPlantasEnMemoria()

    def por_correo(self, correo: Correo) -> Usuario | None:
        return next((u for u in self._usuarios.values() if u.correo == correo), None)

    def por_id(self, usuario_id: int) -> Usuario | None:
        return self._usuarios.get(usuario_id)

    def guardar(self, usuario: Usuario) -> Usuario:
        otro = self.por_correo(usuario.correo)
        if otro is not None and otro.id != usuario.id:
            raise CorreoYaRegistrado(usuario.correo.valor)
        if usuario.id is None:
            usuario = replace(usuario, id=self._siguiente_id)
            self._siguiente_id += 1
        self._usuarios[usuario.id] = usuario
        return usuario

    def resumenes(self) -> list[ResumenUsuario]:
        return [
            ResumenUsuario(u.id, u.correo.valor, u.nombre, u.rol, u.activo, len(self._plantas.de_usuario(u.id)))
            for u in self._usuarios.values()
        ]

    def eliminar(self, usuario_id: int) -> None:
        self._usuarios.pop(usuario_id, None)


class RepositorioSesionesEnMemoria(SesionesAbiertas):
    def __init__(self):
        self.sesiones: dict[str, Sesion] = {}

    def abrir(self, sesion: Sesion) -> None:
        self.sesiones[sesion.token_id] = sesion

    def abierta(self, token_id: str) -> Sesion | None:
        return self.sesiones.get(token_id)

    def cerrar(self, token_id: str) -> None:
        self.sesiones.pop(token_id, None)

    def cerrar_de_usuario(self, usuario_id: int) -> None:
        self.sesiones = {h: s for h, s in self.sesiones.items() if s.usuario_id != usuario_id}


class HistorialEnMemoria(HistorialMediciones):
    def __init__(self):
        self.registros: list[RegistroMedicion] = []

    def agregar(self, registro: RegistroMedicion) -> None:
        self.registros.append(registro)

    def de_planta(self, planta_id: int, limite: int) -> list[RegistroMedicion]:
        propios = [r for r in self.registros if r.planta_id == planta_id]
        return sorted(propios, key=lambda r: r.momento, reverse=True)[:limite]

    def ultimo_de(self, planta_id: int) -> RegistroMedicion | None:
        recientes = self.de_planta(planta_id, 1)
        return recientes[0] if recientes else None


class NotificadorEnMemoria(NotificadorDiagnosticos):
    """Anota cada aviso, como si el dueno tuviera la pantalla abierta.

    Si recibe el historial, anota tambien si la medicion ya estaba guardada al avisar.
    """

    def __init__(self, historial: HistorialEnMemoria | None = None):
        self._historial = historial
        self.avisos: list[tuple[int, Planta, RegistroMedicion, Diagnostico]] = []
        self.guardada_al_avisar: list[bool] = []

    def publicar(self, usuario_id: int, planta: Planta, registro: RegistroMedicion, diagnostico: Diagnostico) -> None:
        self.avisos.append((usuario_id, planta, registro, diagnostico))
        if self._historial is not None:
            self.guardada_al_avisar.append(registro in self._historial.registros)


class NotificadorQueFalla(NotificadorDiagnosticos):
    """Como un WebSocket que se cae justo al avisar."""

    def publicar(self, usuario_id: int, planta: Planta, registro: RegistroMedicion, diagnostico: Diagnostico) -> None:
        raise ConnectionError("la conexion se cerro")


class CifradorFalso(Cifrador):
    """Reversible a proposito: las pruebas ven que no se guarda la contrasena en claro."""

    def cifrar(self, texto: str) -> str:
        return f"cifrado:{texto}"

    def verificar(self, texto: str, cifrado: str) -> bool:
        return cifrado == self.cifrar(texto)


class GeneradorSecretosFalso(GeneradorSecretos):
    """Secretos predecibles: secreto-1, secreto-2... y su huella es huella(secreto-1)."""

    def __init__(self):
        self._contador = 0

    def nuevo(self) -> str:
        self._contador += 1
        return f"secreto-{self._contador}"

    def huella(self, secreto: str) -> str:
        return f"huella({secreto})"

    def coincide(self, secreto: str, huella: str) -> bool:
        return self.huella(secreto) == huella


class TokensFalsos(EmisorTokens, VerificadorTokens):
    """Tokens legibles a proposito, sin firma: token(usuario 1, secreto-1) o token(dispositivo MT-0001-AA, secreto-2).

    Sirven para probar los casos de uso, que nunca ven un JWT. La firma y el
    vencimiento de los tokens de verdad los prueban las pruebas de
    infraestructura.tokens_jwt.
    """

    def emitir(self, identidad: IdentidadUsuario | IdentidadDispositivo, vence_en: datetime) -> str:
        if isinstance(identidad, IdentidadUsuario):
            return f"token(usuario {identidad.usuario_id}, {identidad.token_id})"
        return f"token(dispositivo {identidad.codigo.valor}, {identidad.token_id})"

    def verificar_usuario(self, token: str) -> IdentidadUsuario:
        alcance, sujeto, token_id = self._partes(token, SesionInvalida)
        if alcance != "usuario":
            raise AlcanceInvalido("usuario")
        return IdentidadUsuario(int(sujeto), token_id)

    def verificar_dispositivo(self, token: str) -> IdentidadDispositivo:
        alcance, sujeto, token_id = self._partes(token, CredencialDispositivoInvalida)
        if alcance != "dispositivo":
            raise AlcanceInvalido("dispositivo")
        return IdentidadDispositivo(CodigoSensor(sujeto), token_id)

    @staticmethod
    def _partes(token: str, error: type) -> tuple[str, str, str]:
        prefijo, _, resto = token.partition("token(")
        alcance, _, resto = resto.partition(" ")
        sujeto, _, token_id = resto.removesuffix(")").partition(", ")
        if prefijo or not sujeto or not token_id:
            raise error()
        return alcance, sujeto, token_id


class RelojFijo(Reloj):
    def __init__(self, ahora: datetime):
        self._ahora = ahora

    def ahora(self) -> datetime:
        return self._ahora

    def avanzar(self, tiempo: timedelta) -> None:
        self._ahora += tiempo
