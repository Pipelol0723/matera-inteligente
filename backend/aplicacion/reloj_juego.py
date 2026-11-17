"""Casos de uso del reloj del juego ajustable (corte 3). Solo agregan archivos.

Consultarlo lo puede cualquier usuario con sesion (la pantalla Juego lo muestra);
cambiarlo, solo un ADMIN: lo decide Usuario.exigir_admin(). El reloj nuevo se
guarda primero y despues entra en uso: si no se pudo guardar, nada cambia.
"""
from dominio import puertos_reloj
from dominio.mascota import RelojDeJuego
from dominio.puertos_reloj import RelojDeJuegoGuardado
from dominio.puertos_usuarios import Reloj
from dominio.reloj_juego import RelojDeJuegoAjustable
from dominio.usuarios import Usuario


class ConsultarRelojDeJuego(puertos_reloj.ConsultarRelojDeJuego):
    def __init__(self, ajustable: RelojDeJuegoAjustable):
        self._ajustable = ajustable

    def ejecutar(self, usuario: Usuario) -> RelojDeJuego:
        return self._ajustable.vigente


class CambiarRelojDeJuego(puertos_reloj.CambiarRelojDeJuego):
    def __init__(self, ajustable: RelojDeJuegoAjustable, guardado: RelojDeJuegoGuardado, reloj: Reloj):
        self._ajustable = ajustable
        self._guardado = guardado
        self._reloj = reloj

    def ejecutar(self, usuario: Usuario, minutos_por_dia: float) -> RelojDeJuego:
        usuario.exigir_admin()
        nuevo = RelojDeJuegoAjustable.desde_minutos(minutos_por_dia)
        self._guardado.guardar(nuevo, usuario.id, self._reloj.ahora())
        self._ajustable.cambiar(nuevo)
        return nuevo
