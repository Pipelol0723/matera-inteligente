"""Reglas de la matera Tamagotchi (corte 3): tamano, condicion, cara, necesidad y aviso.

Sin servidor ni archivos, con un momento fijo. Los resumenes se arman a mano,
como los entregaria el puerto MovimientosPuntaje.
"""
from datetime import datetime, timedelta, timezone

import pytest

from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.historial import LecturaRegistrada, RegistroMedicion
from dominio.juego import MovimientoPuntaje, ReglaDeCuidado
from dominio.mascota import (
    Aviso,
    Condicion,
    CuidadoDeMascota,
    EtapaCrecimiento,
    Necesidad,
    RelojDeJuego,
    ResumenCuidado,
    RitmoCrecimiento,
    Tramo,
    necesidad_principal,
)
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.plantas import Planta

AHORA = datetime(2026, 11, 11, 15, 0, tzinfo=timezone.utc)
SALA = Planta(3, 1, "sala", "potos")
POTOS = RitmoCrecimiento(1, 3, 6)
SANSEVIERIA = RitmoCrecimiento(2, 5, 10)
REAL = RelojDeJuego()
DEMO = RelojDeJuego(2)

S, R, C = EstadoGlobal.SALUDABLE, EstadoGlobal.EN_RIESGO, EstadoGlobal.CRITICO
BAJO, OPTIMO, ALTO = EstadoParametro.BAJO, EstadoParametro.OPTIMO, EstadoParametro.ALTO


def movimiento(estado: EstadoGlobal, momento: datetime = AHORA) -> MovimientoPuntaje:
    return MovimientoPuntaje(1, SALA.id, momento, estado, ReglaDeCuidado().puntos(estado))


def tramo(*estados: EstadoGlobal) -> Tramo:
    regla = ReglaDeCuidado()
    return Tramo(len(estados), sum(regla.puntos(e) for e in estados))


def registro(estado: EstadoGlobal, momento: datetime = AHORA, humedad=OPTIMO, temperatura=OPTIMO, luz=OPTIMO):
    lecturas = (
        LecturaRegistrada(HUMEDAD, 50.0, humedad),
        LecturaRegistrada(LUZ, 1000.0, luz),
        LecturaRegistrada(TEMPERATURA, 22.0, temperatura),
    )
    return RegistroMedicion(SALA.id, momento, estado, lecturas, "MT-0001-AA")


def horas_saludables(cantidad: int) -> dict[int, Tramo]:
    return {numero: tramo(S) for numero in range(cantidad)}


def armar(resumen=None, ultima=None, ritmo=POTOS, reloj=REAL, ahora=AHORA):
    return CuidadoDeMascota(reloj).armar(SALA, ritmo, resumen or ResumenCuidado.sin_lecturas(), ultima, ahora)


# --- Necesidad: el globo ---


@pytest.mark.parametrize(
    "parametro, estado, necesidad",
    [
        ("humedad", BAJO, Necesidad.SED),
        ("humedad", ALTO, Necesidad.EXCESO_AGUA),
        ("temperatura", BAJO, Necesidad.FRIO),
        ("temperatura", ALTO, Necesidad.CALOR),
        ("luz", BAJO, Necesidad.POCA_LUZ),
        ("luz", ALTO, Necesidad.MUCHA_LUZ),
    ],
)
def test_cada_parametro_fuera_de_rango_pide_lo_suyo(parametro, estado, necesidad):
    assert necesidad_principal([(parametro, estado)]) is necesidad


def test_primero_el_agua_despues_la_temperatura_y_despues_la_luz():
    # El orden en que llegan las lecturas no importa.
    assert necesidad_principal([("luz", BAJO), ("temperatura", ALTO), ("humedad", BAJO)]) is Necesidad.SED
    assert necesidad_principal([("luz", ALTO), ("temperatura", BAJO), ("humedad", OPTIMO)]) is Necesidad.FRIO
    assert necesidad_principal([("luz", BAJO), ("temperatura", OPTIMO), ("humedad", OPTIMO)]) is Necesidad.POCA_LUZ


def test_sin_parametros_fuera_de_rango_no_pide_nada():
    assert necesidad_principal([("humedad", OPTIMO), ("temperatura", OPTIMO), ("luz", OPTIMO)]) is None
    assert necesidad_principal([]) is None


def test_un_parametro_sin_globo_propio_no_pide_nada():
    assert necesidad_principal([("ph", BAJO), ("luz", OPTIMO)]) is None


def test_la_mascota_pide_lo_de_la_ultima_lectura_del_historial():
    mascota = armar(ultima=registro(C, temperatura=ALTO, luz=BAJO))

    assert mascota.necesidad is Necesidad.CALOR


# --- Reloj del juego ---


def test_con_el_reloj_real_una_hora_de_juego_es_una_hora():
    assert REAL.hora == timedelta(hours=1)
    assert REAL.dia == timedelta(days=1)


def test_el_reloj_acelerado_escala_horas_y_dias():
    assert DEMO.dia == timedelta(minutes=2)
    assert DEMO.hora == timedelta(seconds=5)
    assert DEMO.horas(6) == timedelta(seconds=30)
    assert DEMO.dias(3) == timedelta(minutes=6)


def test_las_horas_de_juego_se_numeran_por_intervalos_consecutivos():
    assert DEMO.numero_de_hora(AHORA) == DEMO.numero_de_hora(AHORA + timedelta(seconds=4.9))
    assert DEMO.numero_de_hora(AHORA + timedelta(seconds=5)) == DEMO.numero_de_hora(AHORA) + 1
    assert REAL.numero_de_hora(AHORA + timedelta(minutes=59)) == REAL.numero_de_hora(AHORA)
    assert REAL.numero_de_hora(AHORA + timedelta(hours=1)) == REAL.numero_de_hora(AHORA) + 1


@pytest.mark.parametrize("minutos", [0, -2, float("nan"), float("inf")])
def test_el_dia_de_juego_dura_algo(minutos):
    with pytest.raises(ValueError):
        RelojDeJuego(minutos)


def test_la_ventana_de_la_condicion_son_6_horas_de_juego():
    assert CuidadoDeMascota(REAL).inicio_ventana(AHORA) == AHORA - timedelta(hours=6)
    assert CuidadoDeMascota(DEMO).inicio_ventana(AHORA) == AHORA - timedelta(seconds=30)


# --- Tamano: horas bien cuidada y ritmo de la especie ---


def test_el_ritmo_por_defecto_es_el_de_una_especie_nueva():
    assert RitmoCrecimiento() == RitmoCrecimiento(1, 3, 7)


@pytest.mark.parametrize(
    "horas, etapa",
    [
        (0, EtapaCrecimiento.SEMILLA),
        (23, EtapaCrecimiento.SEMILLA),
        (24, EtapaCrecimiento.BROTE),
        (71, EtapaCrecimiento.BROTE),
        (72, EtapaCrecimiento.PLANTA),
        (143, EtapaCrecimiento.PLANTA),
        (144, EtapaCrecimiento.FLORECIDA),
    ],
)
def test_la_etapa_sale_de_los_dias_bien_cuidada_y_del_ritmo(horas, etapa):
    assert POTOS.etapa(horas) is etapa


def test_cada_especie_crece_a_su_ritmo():
    resumen = ResumenCuidado(horas_saludables(24), Tramo())

    assert armar(resumen, ritmo=POTOS).etapa is EtapaCrecimiento.BROTE
    assert armar(resumen, ritmo=SANSEVIERIA).etapa is EtapaCrecimiento.SEMILLA


@pytest.mark.parametrize("ritmo", [(0, 3, 7), (3, 3, 7), (1, 4, 3)])
def test_el_ritmo_tiene_que_ser_creciente(ritmo):
    with pytest.raises(ValueError):
        RitmoCrecimiento(*ritmo)


def test_solo_cuentan_las_horas_con_promedio_mayor_que_menos_5():
    horas = {
        0: tramo(S),  # 10
        1: tramo(S, R, R),  # 0: decaida, cuenta
        2: tramo(S, C, C),  # -3,3: decaida, cuenta
        3: tramo(R),  # -5: marchita, no cuenta
        4: tramo(C, S, C),  # -3,3: cuenta
        5: tramo(C),  # -10: no cuenta
        6: tramo(R, R, C, S),  # -2,5: cuenta
    }

    assert armar(ResumenCuidado(horas, Tramo())).horas_cuidada == 5


def test_el_tiempo_marchita_no_hace_crecer():
    marchitas = {numero: tramo(R) for numero in range(200)}

    mascota = armar(ResumenCuidado(marchitas, Tramo()))

    assert (mascota.horas_cuidada, mascota.etapa) == (0, EtapaCrecimiento.SEMILLA)


def test_sin_lecturas_es_una_semilla_dormida_sin_cara():
    mascota = armar()

    assert mascota.etapa is EtapaCrecimiento.SEMILLA
    assert mascota.condicion is Condicion.SANA
    assert (mascota.cara, mascota.dormida, mascota.necesidad, mascota.aviso) == (None, True, None, None)
    assert (mascota.puntos, mascota.horas_cuidada, mascota.ultima_lectura) == (0, 0, None)


# --- Condicion: promedio de las ultimas 6 horas de juego ---


@pytest.mark.parametrize(
    "lecturas, condicion",
    [
        ((), Condicion.SANA),  # sin evidencia de descuido
        ((S,), Condicion.SANA),
        ((S, R), Condicion.SANA),  # 2,5
        ((S, C), Condicion.DECAIDA),  # 0: no es mayor que 0
        ((S, C, C), Condicion.DECAIDA),  # -3,3
        ((S, C, C, R, R), Condicion.DECAIDA),  # -4
        ((R,), Condicion.MARCHITA),  # -5: igual a -5 ya es marchita
        ((S, C, C, C), Condicion.MARCHITA),  # -5
        ((C,), Condicion.MARCHITA),
    ],
)
def test_la_condicion_sigue_el_promedio_de_la_ventana(lecturas, condicion):
    assert armar(ResumenCuidado({}, tramo(*lecturas))).condicion is condicion


def test_la_condicion_no_depende_de_las_horas_fuera_de_la_ventana():
    # Muchas horas marchitas antes, pero en la ventana solo hay lecturas buenas.
    resumen = ResumenCuidado({numero: tramo(C) for numero in range(50)}, tramo(S, S))

    assert armar(resumen).condicion is Condicion.SANA


# --- Cara y dormida ---


@pytest.mark.parametrize("estado", list(EstadoGlobal))
def test_la_cara_es_el_estado_de_la_ultima_lectura(estado):
    mascota = armar(ultima=registro(estado))

    assert mascota.cara is estado
    assert mascota.ultima_lectura == AHORA


def test_se_duerme_despues_de_30_minutos_reales_sin_lecturas():
    assert armar(ultima=registro(S, AHORA - timedelta(minutes=30))).dormida is False
    assert armar(ultima=registro(S, AHORA - timedelta(minutes=30, seconds=1))).dormida is True


def test_los_minutos_para_dormirse_no_se_escalan_con_el_reloj_del_juego():
    # Con el reloj de la demo, 10 minutos reales son 5 dias de juego: igual sigue despierta.
    assert armar(ultima=registro(S, AHORA - timedelta(minutes=10)), reloj=DEMO).dormida is False
    assert armar(ultima=registro(S, AHORA - timedelta(minutes=31)), reloj=DEMO).dormida is True


def test_los_minutos_para_dormirse_se_pueden_configurar():
    cuidado = CuidadoDeMascota(REAL, minutos_para_dormir=5)

    assert cuidado.dormida(registro(S, AHORA - timedelta(minutes=6)), AHORA) is True
    with pytest.raises(ValueError):
        CuidadoDeMascota(REAL, minutos_para_dormir=0)


def test_dormida_conserva_la_cara_de_la_ultima_lectura():
    mascota = armar(ultima=registro(R, AHORA - timedelta(hours=2), humedad=BAJO))

    assert (mascota.dormida, mascota.cara, mascota.necesidad) == (True, R, Necesidad.SED)


# --- Avisos ---


def resumen_con(ventana: tuple[EstadoGlobal, ...], anterior: EstadoGlobal | None) -> ResumenCuidado:
    """La ultima lectura es la ultima de la ventana."""
    return ResumenCuidado(
        {},
        tramo(*ventana),
        ultimo=movimiento(ventana[-1]),
        anterior=movimiento(anterior, AHORA - timedelta(minutes=1)) if anterior else None,
    )


def test_avisa_al_pasar_a_critico():
    resumen = resumen_con((S, S, C), anterior=S)  # 3,3: sigue sana

    assert CuidadoDeMascota(REAL).aviso(resumen) is Aviso.PASO_A_CRITICO


def test_no_avisa_si_ya_estaba_en_critico():
    resumen = resumen_con((S, S, S, C, C), anterior=C)  # 2: sana

    assert CuidadoDeMascota(REAL).aviso(resumen) is None


def test_la_primera_lectura_critica_tambien_avisa():
    # Con el reloj de la demo, la lectura ya salio de la ventana de 30 s pero la planta sigue despierta.
    resumen = ResumenCuidado({}, Tramo(), ultimo=movimiento(C), anterior=None)

    assert CuidadoDeMascota(DEMO).aviso(resumen) is Aviso.PASO_A_CRITICO


def test_avisa_al_marchitarse():
    resumen = resumen_con((S, C, C, C), anterior=C)  # sin la ultima: -3,3; con ella: -5

    assert CuidadoDeMascota(REAL).aviso(resumen) is Aviso.SE_MARCHITO


def test_no_avisa_si_ya_estaba_marchita():
    resumen = resumen_con((C, C, C), anterior=C)

    assert CuidadoDeMascota(REAL).aviso(resumen) is None


def test_si_pasan_las_dos_cosas_gana_se_marchito():
    resumen = resumen_con((C, C, S, C), anterior=S)  # sin la ultima: -3,3; con ella: -5

    assert CuidadoDeMascota(REAL).aviso(resumen) is Aviso.SE_MARCHITO


@pytest.mark.parametrize("ultima, anterior", [(S, C), (R, S), (R, None), (S, None)])
def test_sin_critico_nuevo_ni_marchitarse_no_avisa(ultima, anterior):
    resumen = ResumenCuidado({}, Tramo(), ultimo=movimiento(ultima), anterior=movimiento(anterior) if anterior else None)

    assert CuidadoDeMascota(REAL).aviso(resumen) is None


def test_dormida_no_avisa_lo_de_una_lectura_vieja():
    hace_una_hora = AHORA - timedelta(hours=1)
    resumen = ResumenCuidado({}, tramo(S, C), ultimo=movimiento(C, hace_una_hora), anterior=movimiento(S, hace_una_hora))

    assert armar(resumen, ultima=registro(C, hace_una_hora)).aviso is None
    assert armar(resumen, ultima=registro(C, hace_una_hora), ahora=hace_una_hora).aviso is Aviso.PASO_A_CRITICO


# --- Todo junto ---


def test_la_mascota_reune_las_cinco_capas():
    horas = horas_saludables(80)
    horas[80] = tramo(S, R)
    resumen = ResumenCuidado(horas, tramo(S, S, R), ultimo=movimiento(R), anterior=movimiento(S))

    mascota = armar(resumen, ultima=registro(R, humedad=BAJO))

    assert mascota.planta == SALA
    assert mascota.etapa is EtapaCrecimiento.PLANTA  # 81 horas: mas de 3 dias, menos de 6
    assert mascota.condicion is Condicion.SANA
    assert mascota.cara is R
    assert mascota.dormida is False
    assert mascota.necesidad is Necesidad.SED
    assert mascota.aviso is None
    assert mascota.puntos == 80 * 10 + 5
    assert mascota.horas_cuidada == 81
