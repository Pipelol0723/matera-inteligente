"""La lectura que reporta un dispositivo: la hora tiene zona horaria y no puede ser del futuro. Sin base de datos."""
from datetime import datetime, timedelta, timezone

import pytest

from dominio.errores_usuarios import MomentoInvalido
from dominio.reportes import ADELANTO_MAXIMO, ReporteDeDispositivo
from dominio.sensores import CodigoSensor
from tests.dobles import medicion

AHORA = datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)
SENSOR = CodigoSensor("MT-0001-AA")


@pytest.mark.parametrize(
    "momento",
    [AHORA - timedelta(hours=3), AHORA, AHORA + ADELANTO_MAXIMO],
    ids=["de hace un rato", "de ahora", "con el adelanto que se tolera"],
)
def test_una_lectura_de_ahora_o_del_pasado_se_acepta(momento):
    ReporteDeDispositivo(SENSOR, momento, medicion(30, 800, 22)).exigir_que_no_sea_futuro(AHORA)


def test_una_lectura_del_futuro_se_rechaza():
    reporte = ReporteDeDispositivo(SENSOR, AHORA + ADELANTO_MAXIMO + timedelta(seconds=1), medicion(30, 800, 22))

    with pytest.raises(MomentoInvalido):
        reporte.exigir_que_no_sea_futuro(AHORA)


def test_la_hora_de_otra_zona_horaria_se_compara_bien():
    # 10:05 en Bogota (UTC-5) son las 15:05 en UTC: cinco minutos en el futuro.
    bogota = timezone(timedelta(hours=-5))

    with pytest.raises(MomentoInvalido):
        ReporteDeDispositivo(SENSOR, datetime(2026, 10, 22, 10, 5, tzinfo=bogota), medicion(30, 800, 22)).exigir_que_no_sea_futuro(AHORA)


def test_una_hora_sin_zona_horaria_no_se_acepta():
    with pytest.raises(MomentoInvalido):
        ReporteDeDispositivo(SENSOR, datetime(2026, 10, 22, 15, 0), medicion(30, 800, 22))
