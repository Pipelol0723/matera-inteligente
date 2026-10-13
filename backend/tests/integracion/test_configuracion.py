"""Configuracion leida del entorno: en especial, en que direccion escucha la API."""
from pathlib import Path

from infraestructura.configuracion import Configuracion


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
