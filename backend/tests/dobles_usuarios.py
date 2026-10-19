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
from dominio.errores_usuarios import ApodoRepetido, CorreoYaRegistrado, EspecieYaExiste, SensorYaVinculado
from dominio.especie import Especie
from dominio.historial import RegistroMedicion
from dominio.plantas import Planta
from dominio.puertos_usuarios import (
    Cifrador,
    GeneradorSecretos,
    HistorialMediciones,
    NotificadorDiagnosticos,
    RegistroEspecies,
    Reloj,
    RepositorioPlantas,
    RepositorioSensores,
    RepositorioSesiones,
    RepositorioUsuarios,
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


class RepositorioSensoresEnMemoria(RepositorioSensores):
    def __init__(self):
        self._sensores: dict[str, Sensor] = {}

    def por_codigo(self, codigo: CodigoSensor) -> Sensor | None:
        return self._sensores.get(codigo.valor)

    def de_planta(self, planta_id: int) -> Sensor | None:
        return next((s for s in self._sensores.values() if s.planta_id == planta_id), None)

    def reemplazar(self, sensor: Sensor) -> None:
        en_uso = self._sensores.get(sensor.codigo.valor)
        if en_uso is not None and en_uso.planta_id != sensor.planta_id:
            raise SensorYaVinculado(sensor.codigo.valor)
        self.quitar_de_planta(sensor.planta_id)
        self._sensores[sensor.codigo.valor] = sensor

    def quitar_de_planta(self, planta_id: int) -> None:
        """No es del puerto: imita la cascada de la base al borrar una planta."""
        self._sensores = {c: s for c, s in self._sensores.items() if s.planta_id != planta_id}


class RepositorioPlantasEnMemoria(RepositorioPlantas):
    def __init__(self, sensores: RepositorioSensoresEnMemoria | None = None):
        self._plantas: dict[int, Planta] = {}
        self._siguiente_id = 1
        self._sensores = sensores or RepositorioSensoresEnMemoria()

    def guardar_con_sensor(self, planta: Planta, codigo: CodigoSensor, hash_clave: str) -> Planta:
        # Revisa todo antes de guardar nada, como la transaccion de la base.
        if any(p.es_de(planta.usuario_id) and p.mismo_apodo(planta.apodo) for p in self._plantas.values()):
            raise ApodoRepetido(planta.apodo)
        if self._sensores.por_codigo(codigo) is not None:
            raise SensorYaVinculado(codigo.valor)
        guardada = replace(planta, id=self._siguiente_id)
        self._plantas[guardada.id] = guardada
        self._siguiente_id += 1
        self._sensores.reemplazar(Sensor(codigo, guardada.id, hash_clave))
        return guardada

    def de_usuario(self, usuario_id: int) -> list[Planta]:
        return [p for p in self._plantas.values() if p.es_de(usuario_id)]

    def por_id(self, usuario_id: int, planta_id: int) -> Planta | None:
        planta = self._plantas.get(planta_id)
        return planta if planta is not None and planta.es_de(usuario_id) else None

    def vinculada_a(self, codigo: CodigoSensor) -> Planta | None:
        sensor = self._sensores.por_codigo(codigo)
        return self._plantas.get(sensor.planta_id) if sensor else None

    def eliminar(self, usuario_id: int, planta_id: int) -> None:
        if self.por_id(usuario_id, planta_id) is not None:
            del self._plantas[planta_id]
            self._sensores.quitar_de_planta(planta_id)


def codigo(numero: int) -> CodigoSensor:
    """Un codigo de sensor distinto para cada planta de una prueba: MT-0001-AA, MT-0002-AA..."""
    return CodigoSensor(f"MT-{numero:04d}-AA")


class RepositorioUsuariosEnMemoria(RepositorioUsuarios):
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


class RepositorioSesionesEnMemoria(RepositorioSesiones):
    def __init__(self):
        self.sesiones: dict[str, Sesion] = {}

    def guardar(self, sesion: Sesion) -> None:
        self.sesiones[sesion.hash_token] = sesion

    def por_huella(self, huella: str) -> Sesion | None:
        return self.sesiones.get(huella)

    def eliminar(self, huella: str) -> None:
        self.sesiones.pop(huella, None)

    def eliminar_de_usuario(self, usuario_id: int) -> None:
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


class RelojFijo(Reloj):
    def __init__(self, ahora: datetime):
        self._ahora = ahora

    def ahora(self) -> datetime:
        return self._ahora

    def avanzar(self, tiempo: timedelta) -> None:
        self._ahora += tiempo
