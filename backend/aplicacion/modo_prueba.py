"""Casos de uso del modo prueba (corte 3). Solo agregan: envuelven ConsultarMascotas y RegistrarLectura.

Poner y quitar exigen un ADMIN (Usuario.exigir_admin) y una matera suya
(buscar_planta_propia, con Planta.exigir_dueno): una ajena da el mismo 404 que
una inexistente. Al consultar, la prueba solo se aplica si el dueno sigue
siendo admin: si pierde el rol, sus materas vuelven a verse como son.
"""
from aplicacion.plantas import buscar_planta_propia
from dominio import puertos_entrada, puertos_juego, puertos_prueba
from dominio.identidad import IdentidadDispositivo
from dominio.mascota import Mascota
from dominio.modo_prueba import EstadoDePrueba, ResultadoEnPrueba
from dominio.puertos_prueba import EstadosDePrueba
from dominio.puertos_usuarios import ConsultaCuentas, ConsultaPlantas
from dominio.reportes import ReporteDeDispositivo
from dominio.resultados import ResultadoMedicion
from dominio.usuarios import Usuario


class PonerEstadoDePrueba(puertos_prueba.PonerEstadoDePrueba):
    def __init__(self, plantas: ConsultaPlantas, estados: EstadosDePrueba):
        self._plantas = plantas
        self._estados = estados

    def ejecutar(self, usuario: Usuario, planta_id: int, estado: EstadoDePrueba) -> EstadoDePrueba:
        usuario.exigir_admin()
        planta = buscar_planta_propia(self._plantas, usuario.id, planta_id)
        self._estados.guardar(planta.id, estado)
        return estado


class QuitarEstadoDePrueba(puertos_prueba.QuitarEstadoDePrueba):
    def __init__(self, plantas: ConsultaPlantas, estados: EstadosDePrueba):
        self._plantas = plantas
        self._estados = estados

    def ejecutar(self, usuario: Usuario, planta_id: int) -> None:
        usuario.exigir_admin()
        planta = buscar_planta_propia(self._plantas, usuario.id, planta_id)
        self._estados.quitar(planta.id)


class MascotasConPrueba(puertos_juego.ConsultarMascotas):
    """Las materas Tamagotchi de siempre; las que un admin puso en prueba, con las capas de la prueba."""

    def __init__(self, interno: puertos_juego.ConsultarMascotas, estados: EstadosDePrueba):
        self._interno = interno
        self._estados = estados

    def ejecutar(self, usuario: Usuario) -> list[Mascota]:
        mascotas = self._interno.ejecutar(usuario)
        if not usuario.es_admin():
            return mascotas
        return [self._con_prueba(mascota) for mascota in mascotas]

    def _con_prueba(self, mascota: Mascota) -> Mascota:
        estado = self._estados.de_planta(mascota.planta.id)
        return estado.aplicar(mascota) if estado is not None else mascota


class LecturaConPrueba(puertos_entrada.RegistrarLectura):
    """La lectura se registra y se puntua igual; si la matera esta en prueba, la respuesta lo dice para la placa."""

    def __init__(self, interno: puertos_entrada.RegistrarLectura, estados: EstadosDePrueba, cuentas: ConsultaCuentas):
        self._interno = interno
        self._estados = estados
        self._cuentas = cuentas

    def ejecutar(self, identidad: IdentidadDispositivo, reporte: ReporteDeDispositivo) -> ResultadoMedicion:
        resultado = self._interno.ejecutar(identidad, reporte)
        estado = self._estados.de_planta(resultado.planta.id)
        if estado is None:
            return resultado
        dueno = self._cuentas.por_id(resultado.planta.usuario_id)
        if dueno is None or not dueno.es_admin():
            return resultado
        return ResultadoEnPrueba(
            planta=resultado.planta,
            diagnostico=resultado.diagnostico,
            registro=resultado.registro,
            prueba=estado,
        )
