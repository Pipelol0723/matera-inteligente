"""Configuracion leida del entorno: en especial, en que direccion escucha la API y el reloj del juego."""
import os
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

import pytest

from infraestructura.configuracion import Configuracion

BACKEND = Path(__file__).resolve().parents[2]


def test_por_defecto_la_api_solo_escucha_en_este_pc(monkeypatch):
    for variable in ("MATERA_HOST", "MATERA_PUERTO", "MATERA_RUTA_BD"):
        monkeypatch.delenv(variable, raising=False)

    config = Configuracion.desde_entorno()

    assert (config.host, config.puerto, config.ruta_bd.name) == ("127.0.0.1", 5000, "matera.sqlite")


def test_matera_host_abre_la_api_a_la_red_para_el_esp32(monkeypatch, tmp_path):
    monkeypatch.setenv("MATERA_HOST", " 0.0.0.0 ")
    monkeypatch.setenv("MATERA_PUERTO", "5055")
    monkeypatch.setenv("MATERA_RUTA_BD", str(tmp_path / "otra.sqlite"))

    config = Configuracion.desde_entorno()

    assert (config.host, config.puerto, config.ruta_bd) == ("0.0.0.0", 5055, Path(tmp_path / "otra.sqlite"))


def test_por_defecto_el_reloj_del_juego_es_el_real_y_la_matera_duerme_a_los_30_minutos(monkeypatch):
    for variable in ("MATERA_MINUTOS_POR_DIA_JUEGO", "MATERA_MINUTOS_SIN_LECTURAS"):
        monkeypatch.delenv(variable, raising=False)

    config = Configuracion.desde_entorno()

    assert (config.minutos_por_dia_juego, config.minutos_sin_lecturas) == (1440, 30)
    assert config.reloj_de_juego.hora == timedelta(hours=1)


def test_el_reloj_del_juego_se_acelera_para_la_demo(monkeypatch):
    monkeypatch.setenv("MATERA_MINUTOS_POR_DIA_JUEGO", " 2 ")
    monkeypatch.setenv("MATERA_MINUTOS_SIN_LECTURAS", "0.5")

    config = Configuracion.desde_entorno()

    assert (config.minutos_por_dia_juego, config.minutos_sin_lecturas) == (2, 0.5)
    assert config.reloj_de_juego.hora == timedelta(seconds=5)


_INVALIDOS = ["0", "-2", "dos", "1,5", "nan", "inf", "1e300"]


@pytest.mark.parametrize(
    ("variable", "valor"),
    [("MATERA_MINUTOS_POR_DIA_JUEGO", valor) for valor in _INVALIDOS]
    # Una hora de juego de menos de un microsegundo: el reloj no sirve.
    + [("MATERA_MINUTOS_POR_DIA_JUEGO", "1e-12")]
    + [("MATERA_MINUTOS_SIN_LECTURAS", valor) for valor in _INVALIDOS],
)
def test_un_valor_invalido_no_deja_arrancar_y_dice_cual(monkeypatch, variable, valor):
    monkeypatch.setenv(variable, valor)

    with pytest.raises(ValueError, match=variable):
        Configuracion.desde_entorno()


def test_el_backend_no_arranca_con_un_reloj_invalido_y_lo_explica(tmp_path):
    entorno = {
        **os.environ,
        "MATERA_MINUTOS_POR_DIA_JUEGO": "0",
        "MATERA_RUTA_BD": str(tmp_path / "matera.sqlite"),
        "PYTHONIOENCODING": "utf-8",
    }

    resultado = subprocess.run(
        [sys.executable, "main.py"], cwd=BACKEND, env=entorno, capture_output=True, encoding="utf-8", timeout=60
    )

    assert resultado.returncode == 1
    assert "No se pudo arrancar: MATERA_MINUTOS_POR_DIA_JUEGO debe ser un número" in resultado.stderr
    assert "Traceback" not in resultado.stderr
    assert not (tmp_path / "matera.sqlite").exists()
