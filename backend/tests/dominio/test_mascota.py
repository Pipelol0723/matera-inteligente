"""Reglas de la matera Tamagotchi (corte 3): tamano, condicion, cara, necesidad y aviso.

Sin servidor ni archivos, con un momento fijo. Los resumenes se arman a mano,
como los entregaria el puerto MovimientosPuntaje: las ventanas de la condicion
ya vienen ancladas en la ultima lectura y en la anterior.
"""
from collections import Counter
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


def por_tramo(*horas: Tramo) -> dict[Tramo, int]:
    """Las horas de juego como las da el puerto: cuantas terminaron con cada Tramo."""
    return dict(Counter(horas))


def horas_saludables(cantidad: int) -> dict[Tramo, int]:
    return {tramo(S): cantidad}


def resumen_con(
    al_ultimo: tuple[EstadoGlobal, ...],
    al_anterior: tuple[EstadoGlobal, ...] = (),
    horas: dict[Tramo, int] | None = None,
    cuando: datetime = AHORA,
) -> ResumenCuidado:
    """La ultima lectura es la ultima de al_ultimo, y la anterior, la ultima de al_anterior (si hay)."""
    return ResumenCuidado(
        horas or {},
        ultimo=movimiento(al_ultimo[-1], cuando),
        anterior=movimiento(al_anterior[-1], cuando - timedelta(minutes=1)) if al_anterior else None,
        al_ultimo=tramo(*al_ultimo),
        al_anterior=tramo(*al_anterior),
    )


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
    mascota = armar(resumen_con((C,)), ultima=registro(C, temperatura=ALTO, luz=BAJO))

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
    assert CuidadoDeMascota(REAL).ventana == timedelta(hours=6)
    assert CuidadoDeMascota(DEMO).ventana == timedelta(seconds=30)


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
    resumen = ResumenCuidado(horas_saludables(24))

    assert armar(resumen, ritmo=POTOS).etapa is EtapaCrecimiento.BROTE
    assert armar(resumen, ritmo=SANSEVIERIA).etapa is EtapaCrecimiento.SEMILLA


@pytest.mark.parametrize("ritmo", [(0, 3, 7), (3, 3, 7), (1, 4, 3)])
def test_el_ritmo_tiene_que_ser_creciente(ritmo):
    with pytest.raises(ValueError):
        RitmoCrecimiento(*ritmo)


def test_solo_cuentan_las_horas_con_su_propio_promedio_de_menos_5_o_mas():
    horas = por_tramo(
        tramo(S),  # 10
        tramo(S, R, R),  # 0: decaida, cuenta
        tramo(S, C, C),  # -3,3: decaida, cuenta
        tramo(R),  # -5: decaida, cuenta
        tramo(C, S, C),  # -3,3: cuenta (el mismo Tramo que la de S, C, C: van juntas)
        tramo(C),  # -10: no cuenta
        tramo(R, R, C, S),  # -2,5: cuenta
        tramo(R, C),  # -7,5: marchita, no cuenta
    )

    assert armar(ResumenCuidado(horas)).horas_cuidada == 6


def test_los_puntos_de_la_matera_suman_todas_sus_horas():
    resumen = ResumenCuidado(por_tramo(tramo(S), tramo(S), tramo(S, C, C), tramo(R)))

    assert armar(resumen).puntos == 10 + 10 - 10 - 5


@pytest.mark.parametrize("horas", [{Tramo(): 1}, {tramo(S): 0}, {tramo(S): -2}])
def test_solo_se_cuentan_horas_con_lecturas(horas):
    with pytest.raises(ValueError):
        ResumenCuidado(horas)


def test_una_hora_con_su_promedio_de_menos_5_cuenta_aunque_la_ventana_este_marchita():
    """Cada hora se mira sola: la condicion de 6 horas no la cambia (decision del equipo)."""
    resumen = resumen_con((C, C, C, C, C, R), (C, C, C, C, C), horas=por_tramo(tramo(C), tramo(C), tramo(R)))

    mascota = armar(resumen)

    assert (mascota.condicion, mascota.horas_cuidada) == (Condicion.MARCHITA, 1)


def test_siempre_en_riesgo_queda_decaida_y_sigue_creciendo():
    en_riesgo = {tramo(R): 200}

    mascota = armar(ResumenCuidado(en_riesgo, ultimo=movimiento(R), al_ultimo=tramo(R)))

    assert mascota.condicion is Condicion.DECAIDA
    assert mascota.horas_cuidada == 200
    assert mascota.etapa is not EtapaCrecimiento.SEMILLA


def test_el_tiempo_marchita_no_hace_crecer():
    marchitas = {tramo(C): 200}

    mascota = armar(ResumenCuidado(marchitas))

    assert (mascota.horas_cuidada, mascota.etapa) == (0, EtapaCrecimiento.SEMILLA)


def test_sin_lecturas_es_una_semilla_dormida_sin_cara():
    mascota = armar()

    assert mascota.etapa is EtapaCrecimiento.SEMILLA
    assert mascota.condicion is Condicion.SANA
    assert (mascota.cara, mascota.dormida, mascota.necesidad, mascota.aviso) == (None, True, None, None)
    assert (mascota.puntos, mascota.horas_cuidada, mascota.ultima_lectura) == (0, 0, None)


# --- Condicion: promedio de las 6 horas de juego que terminan en la ultima lectura ---


@pytest.mark.parametrize(
    "lecturas, condicion",
    [
        ((), Condicion.SANA),  # sin evidencia de descuido
        ((S,), Condicion.SANA),
        ((S, R), Condicion.SANA),  # 2,5
        ((S, C), Condicion.DECAIDA),  # 0: no es mayor que 0
        ((S, C, C), Condicion.DECAIDA),  # -3,3
        ((S, C, C, R, R), Condicion.DECAIDA),  # -4
        ((R,), Condicion.DECAIDA),  # -5: siempre en riesgo queda decaida
        ((S, C, C, C), Condicion.DECAIDA),  # -5
        ((S, C, C, C, C), Condicion.MARCHITA),  # -6: menos de -5 ya es marchita
        ((R, C), Condicion.MARCHITA),  # -7,5
        ((C,), Condicion.MARCHITA),
    ],
)
def test_la_condicion_sigue_el_promedio_de_la_ventana(lecturas, condicion):
    resumen = resumen_con(lecturas) if lecturas else ResumenCuidado.sin_lecturas()

    assert armar(resumen).condicion is condicion


def test_la_condicion_no_depende_de_las_horas_fuera_de_la_ventana():
    # Muchas horas marchitas antes, pero en la ventana solo hay lecturas buenas.
    resumen = resumen_con((S, S), horas={tramo(C): 50})

    assert armar(resumen).condicion is Condicion.SANA


def test_la_condicion_es_la_de_la_ventana_de_la_ultima_lectura_y_no_cambia_sin_lecturas():
    # Con el reloj de la demo la ventana dura 30 s: 20 minutos despues ya paso, pero no llego otra lectura.
    resumen = resumen_con((C, C, C), (C, C))

    recien = armar(resumen, reloj=DEMO)
    despues = armar(resumen, reloj=DEMO, ahora=AHORA + timedelta(minutes=20))

    assert recien.condicion is despues.condicion is Condicion.MARCHITA
    assert (despues.cara, despues.dormida) == (C, False)


# --- Cara y dormida ---


@pytest.mark.parametrize("estado", list(EstadoGlobal))
def test_la_cara_es_el_estado_de_la_ultima_lectura(estado):
    mascota = armar(resumen_con((estado,)), ultima=registro(estado))

    assert mascota.cara is estado
    assert mascota.ultima_lectura == AHORA


def test_la_cara_y_el_sueno_salen_del_ultimo_movimiento_y_no_de_la_hora_del_dispositivo():
    """Una placa con la hora 31 minutos atrasada: en el historial su lectura queda detras de la anterior.

    El movimiento guarda el estado con la hora del servidor: la cara es la de la
    lectura que acaba de llegar, la matera esta despierta y el aviso sale.
    """
    resumen = resumen_con((S, C), (S,))
    historial_atrasado = registro(S, AHORA - timedelta(seconds=15))  # el historial ordena por la hora del dispositivo

    mascota = armar(resumen, ultima=historial_atrasado)

    assert (mascota.cara, mascota.dormida, mascota.aviso) == (C, False, Aviso.PASO_A_CRITICO)
    assert mascota.ultima_lectura == AHORA


def test_se_duerme_despues_de_30_minutos_reales_sin_lecturas():
    assert armar(resumen_con((S,), cuando=AHORA - timedelta(minutes=30))).dormida is False
    assert armar(resumen_con((S,), cuando=AHORA - timedelta(minutes=30, seconds=1))).dormida is True


def test_los_minutos_para_dormirse_no_se_escalan_con_el_reloj_del_juego():
    # Con el reloj de la demo, 10 minutos reales son 5 dias de juego: igual sigue despierta.
    assert armar(resumen_con((S,), cuando=AHORA - timedelta(minutes=10)), reloj=DEMO).dormida is False
    assert armar(resumen_con((S,), cuando=AHORA - timedelta(minutes=31)), reloj=DEMO).dormida is True


def test_los_minutos_para_dormirse_se_pueden_configurar():
    cuidado = CuidadoDeMascota(REAL, minutos_para_dormir=5)

    assert cuidado.dormida(movimiento(S, AHORA - timedelta(minutes=6)), AHORA) is True
    assert cuidado.dormida(None, AHORA) is True
    with pytest.raises(ValueError):
        CuidadoDeMascota(REAL, minutos_para_dormir=0)


def test_dormida_conserva_la_cara_pero_no_muestra_lo_que_pedia_ni_avisa():
    hace_dos_horas = AHORA - timedelta(hours=2)
    resumen = resumen_con((S, C), (S,), cuando=hace_dos_horas)

    mascota = armar(resumen, ultima=registro(C, hace_dos_horas, humedad=BAJO))

    assert (mascota.dormida, mascota.cara, mascota.necesidad, mascota.aviso) == (True, C, None, None)
    assert mascota.ultima_lectura == hace_dos_horas


def test_las_ventanas_tienen_que_traer_la_lectura_en_que_terminan():
    with pytest.raises(ValueError):
        ResumenCuidado({}, ultimo=movimiento(S))  # sin la ventana de la ultima
    with pytest.raises(ValueError):
        ResumenCuidado({}, al_ultimo=tramo(S))  # una ventana sin su lectura
    with pytest.raises(ValueError):
        ResumenCuidado({}, ultimo=movimiento(S), anterior=movimiento(S), al_ultimo=tramo(S, S))
    with pytest.raises(ValueError):
        ResumenCuidado({}, anterior=movimiento(S), al_anterior=tramo(S))  # anterior sin ultima


# --- Avisos ---


def test_avisa_al_pasar_a_critico():
    resumen = resumen_con((S, S, C), (S, S))  # 3,3: sigue sana

    assert CuidadoDeMascota(REAL).aviso(resumen) is Aviso.PASO_A_CRITICO


def test_no_avisa_si_ya_estaba_en_critico():
    resumen = resumen_con((S, S, S, C, C), (S, S, S, C))  # 2: sana

    assert CuidadoDeMascota(REAL).aviso(resumen) is None


def test_la_primera_lectura_critica_ya_esta_marchita_y_avisa_eso():
    # Su ventana solo la tiene a ella (-10): pasa a CRITICO y se marchita a la vez, y gana SE_MARCHITO.
    assert CuidadoDeMascota(REAL).aviso(resumen_con((C,))) is Aviso.SE_MARCHITO


def test_avisa_al_marchitarse():
    resumen = resumen_con((S, C, C, C, C), (S, C, C, C))  # antes: -5; con la ultima: -6

    assert CuidadoDeMascota(REAL).aviso(resumen) is Aviso.SE_MARCHITO


def test_con_la_ventana_llena_compara_con_la_ventana_de_la_anterior():
    """La lectura mas vieja sale de la ventana mientras entra la nueva.

    Antes (la ventana de la anterior) habia S, S y cuatro C: -3,3, decaida.
    Ahora (la de la ultima) ya no esta la primera S y entra otra C: -6,7, marchita.
    Quitar solo la ultima de la ventana de ahora daria S y cuatro C (-6): marchita, y no avisaria.
    """
    resumen = resumen_con((S, C, C, C, C, C), (S, S, C, C, C, C))

    assert CuidadoDeMascota(REAL).aviso(resumen) is Aviso.SE_MARCHITO


def test_no_avisa_si_ya_estaba_marchita():
    resumen = resumen_con((C, C, C), (C, C))

    assert CuidadoDeMascota(REAL).aviso(resumen) is None


def test_si_se_recupera_y_vuelve_a_marchitarse_avisa_otra_vez():
    cuidado = CuidadoDeMascota(REAL)

    assert cuidado.aviso(resumen_con((S, S, R), (S, S))) is None
    assert cuidado.aviso(resumen_con((S, C, C, C, C), (S, S, C, C, C))) is Aviso.SE_MARCHITO


def test_si_pasan_las_dos_cosas_gana_se_marchito():
    resumen = resumen_con((C, C, C, S, C), (C, C, C, S))  # antes: -5; con la ultima: -6

    assert CuidadoDeMascota(REAL).aviso(resumen) is Aviso.SE_MARCHITO


@pytest.mark.parametrize("ultima, anterior", [(S, C), (R, S), (R, None), (S, None)])
def test_sin_critico_nuevo_ni_marchitarse_no_avisa(ultima, anterior):
    resumen = resumen_con((anterior, ultima) if anterior else (ultima,), (anterior,) if anterior else ())

    assert CuidadoDeMascota(REAL).aviso(resumen) is None


def test_dormida_no_avisa_lo_de_una_lectura_vieja():
    hace_una_hora = AHORA - timedelta(hours=1)
    resumen = resumen_con((S, C), (S,), cuando=hace_una_hora)

    assert armar(resumen, ultima=registro(C, hace_una_hora)).aviso is None
    assert armar(resumen, ultima=registro(C, hace_una_hora), ahora=hace_una_hora).aviso is Aviso.PASO_A_CRITICO


# --- Todo junto ---


def test_la_mascota_reune_las_cinco_capas():
    resumen = resumen_con((S, S, R), (S, S), horas={tramo(S): 80, tramo(S, R): 1})

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
