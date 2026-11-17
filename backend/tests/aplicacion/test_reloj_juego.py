"""El reloj del juego ajustable, con dobles: solo un admin lo cambia, se guarda antes de usarse y valida la duracion."""
from datetime import datetime, timedelta, timezone

import pytest

from aplicacion.reloj_juego import CambiarRelojDeJuego, ConsultarRelojDeJuego
from dominio.errores_usuarios import PermisoDenegado
from dominio.mascota import RelojDeJuego
from dominio.puertos_reloj import RelojDeJuegoGuardado
from dominio.reloj_juego import RelojDeJuegoAjustable, RelojDeJuegoInvalido
from dominio.usuarios import Correo, Rol, Usuario
from tests.dobles_usuarios import RelojFijo

AHORA = datetime(2026, 11, 17, 12, 0, tzinfo=timezone.utc)


class GuardadoEnMemoria(RelojDeJuegoGuardado):
    def __init__(self, falla=False):
        self.guardados = []
        self.falla = falla

    def leer(self):
        return self.guardados[-1][0] if self.guardados else None

    def guardar(self, reloj, usuario_id, momento):
        if self.falla:
            raise RuntimeError("sin disco")
        self.guardados.append((reloj, usuario_id, momento))


def _usuario(rol):
    return Usuario(id=7, correo=Correo("ada@correo.co"), nombre="Ada", hash_contrasena="x", rol=rol)


def _cambiar(ajustable, guardado):
    return CambiarRelojDeJuego(ajustable, guardado, RelojFijo(AHORA))


def test_un_admin_cambia_el_reloj_y_queda_guardado():
    ajustable = RelojDeJuegoAjustable(RelojDeJuego(6))
    guardado = GuardadoEnMemoria()
    nuevo = _cambiar(ajustable, guardado).ejecutar(_usuario(Rol.ADMIN), 24)
    assert nuevo == RelojDeJuego(24)
    assert ajustable.vigente == RelojDeJuego(24) and ajustable.hora == timedelta(minutes=1)
    assert guardado.guardados == [(RelojDeJuego(24), 7, AHORA)]
    assert ConsultarRelojDeJuego(ajustable).ejecutar(_usuario(Rol.USUARIO)) == RelojDeJuego(24)


def test_quien_no_es_admin_no_lo_cambia():
    ajustable = RelojDeJuegoAjustable(RelojDeJuego(6))
    guardado = GuardadoEnMemoria()
    with pytest.raises(PermisoDenegado):
        _cambiar(ajustable, guardado).ejecutar(_usuario(Rol.USUARIO), 24)
    assert ajustable.vigente == RelojDeJuego(6) and guardado.guardados == []


@pytest.mark.parametrize("minutos", [0, -5, float("nan"), float("inf"), 1e300])
def test_una_duracion_que_no_sirve_no_cambia_nada(minutos):
    ajustable = RelojDeJuegoAjustable(RelojDeJuego(6))
    guardado = GuardadoEnMemoria()
    with pytest.raises(RelojDeJuegoInvalido):
        _cambiar(ajustable, guardado).ejecutar(_usuario(Rol.ADMIN), minutos)
    assert ajustable.vigente == RelojDeJuego(6) and guardado.guardados == []


def test_si_no_se_pudo_guardar_el_reloj_no_cambia():
    ajustable = RelojDeJuegoAjustable(RelojDeJuego(6))
    with pytest.raises(RuntimeError):
        _cambiar(ajustable, GuardadoEnMemoria(falla=True)).ejecutar(_usuario(Rol.ADMIN), 24)
    assert ajustable.vigente == RelojDeJuego(6)


def test_el_ajustable_tiene_la_forma_del_reloj_y_sigue_al_vigente():
    ajustable = RelojDeJuegoAjustable(RelojDeJuego(6))
    momento = AHORA
    assert ajustable.numero_de_hora(momento) == RelojDeJuego(6).numero_de_hora(momento)
    assert ajustable.horas(6) == RelojDeJuego(6).horas(6)
    ajustable.cambiar(RelojDeJuego(1440))
    assert ajustable.numero_de_hora(momento) == RelojDeJuego(1440).numero_de_hora(momento)
    assert ajustable.dia == timedelta(days=1) and ajustable.minutos_por_dia == 1440
