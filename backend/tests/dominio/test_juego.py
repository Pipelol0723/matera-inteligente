"""Reglas del puntaje y de la participacion en la tabla (corte 3). Sin servidor ni archivos."""
from datetime import datetime, timezone

import pytest

from dominio.errores import ErrorDominio
from dominio.errores_juego import ApodoInvalido, ApodoRepetido, ParticipacionRequerida
from dominio.estados import EstadoGlobal
from dominio.juego import ApodoJugador, EstadoParticipacion, MovimientoPuntaje, Participacion, ReglaDeCuidado

AHORA = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)


# --- ReglaDeCuidado ---


@pytest.mark.parametrize(
    "estado, puntos",
    [(EstadoGlobal.SALUDABLE, 10), (EstadoGlobal.EN_RIESGO, -5), (EstadoGlobal.CRITICO, -10)],
)
def test_cada_estado_vale_sus_puntos(estado, puntos):
    assert ReglaDeCuidado().puntos(estado) == puntos


def test_cada_estado_global_tiene_puntos():
    assert set(ReglaDeCuidado.PUNTOS) == set(EstadoGlobal)


def test_el_movimiento_lleva_el_dueno_la_planta_el_momento_el_estado_y_sus_puntos():
    movimiento = ReglaDeCuidado().movimiento(1, 7, AHORA, EstadoGlobal.EN_RIESGO)

    assert movimiento == MovimientoPuntaje(1, 7, AHORA, EstadoGlobal.EN_RIESGO, -5)


def test_la_suma_de_los_movimientos_puede_quedar_negativa():
    regla = ReglaDeCuidado()
    estados = [EstadoGlobal.SALUDABLE, EstadoGlobal.CRITICO, EstadoGlobal.EN_RIESGO]

    assert sum(regla.puntos(estado) for estado in estados) == -5


# --- ApodoJugador ---


@pytest.mark.parametrize("texto", ["abc", "pipe_verde", "Helecho-Feliz", "x" * 20, "a_1", "  monstera99  "])
def test_apodos_validos(texto):
    assert ApodoJugador(texto).valor == texto.strip()


@pytest.mark.parametrize(
    "texto",
    ["", "ab", "x" * 21, "pipe verde", "camión", "pipe.verde", "pipe@verde", "ñandu", "ab\tc", None, 123],
)
def test_apodos_invalidos(texto):
    with pytest.raises(ApodoInvalido) as error:
        ApodoJugador(texto)

    assert (error.value.minimo, error.value.maximo) == (3, 20)


def test_el_apodo_se_compara_sin_importar_mayusculas_pero_se_guarda_como_se_escribio():
    apodo = ApodoJugador("Pipe_Verde")

    assert apodo.valor == "Pipe_Verde"
    assert apodo == ApodoJugador("pipe_verde")
    assert hash(apodo) == hash(ApodoJugador("PIPE_VERDE"))
    assert apodo != ApodoJugador("pipe_verde2")


# --- Participacion ---


def test_solo_quien_participa_pasa_a_la_tabla():
    Participacion.participa(1, ApodoJugador("pipe_verde")).exigir_participacion()


@pytest.mark.parametrize("participacion", [Participacion.sin_decidir(1), Participacion.no_participa(1)])
def test_quien_no_participa_o_no_decidio_no_ve_la_tabla(participacion):
    assert not participacion.en_tabla
    with pytest.raises(ParticipacionRequerida):
        participacion.exigir_participacion()


def test_solo_quien_participa_tiene_apodo():
    with pytest.raises(ValueError):
        Participacion(1, EstadoParticipacion.PARTICIPA)
    with pytest.raises(ValueError):
        Participacion(1, EstadoParticipacion.NO_PARTICIPA, ApodoJugador("pipe_verde"))


def test_los_errores_del_juego_son_errores_del_dominio_para_que_la_presentacion_los_traduzca():
    assert issubclass(ParticipacionRequerida, ErrorDominio)
    assert issubclass(ApodoInvalido, ErrorDominio)
    assert issubclass(ApodoRepetido, ErrorDominio)
    assert ApodoRepetido("pipe_verde").apodo == "pipe_verde"
