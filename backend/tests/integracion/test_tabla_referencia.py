"""R4: la tabla de referencia sale del CSV o de la base segun la configuracion, y el CSV es una copia de solo lectura."""
import dataclasses

import pytest

from dominio.errores_usuarios import TablaDeSoloLectura
from dominio.especie import Especie
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.rango import Rango
from exportar_especies_csv import main as exportar
from infraestructura.configuracion import Configuracion
from infraestructura.repositorio_especies_csv import (
    EspeciesDeSoloLectura,
    RegistroEspeciesConCopiaCsv,
    RepositorioEspeciesCsv,
    escribir_csv,
)
from infraestructura.sqlite import BaseDatos, RepositorioEspeciesSqlite
from tests.integracion.conftest import ClienteApi, es_error
from tests.integracion.test_api_cuentas import ESPECIE_NUEVA

LAVANDA = Especie("lavanda", {HUMEDAD: Rango(25, 50), LUZ: Rango(10760, 107640), TEMPERATURA: Rango(13.5, 27)}, "Lavandula")


def _diagnostico(api) -> dict:
    cuerpo = {"especie": "Potos", "humedad": 35, "luz": 800, "temperatura": 22}
    return api.pedir("POST", "/diagnosticos", json=cuerpo).get_json()


def test_lo_que_se_escribe_en_el_csv_se_lee_igual(tmp_path):
    ruta = tmp_path / "especies.csv"

    assert escribir_csv([LAVANDA], ruta) == 1

    [leida] = RepositorioEspeciesCsv(ruta).listar()
    assert (leida.nombre, leida.nombre_cientifico, dict(leida.rangos)) == ("lavanda", "Lavandula", dict(LAVANDA.rangos))


def test_la_copia_del_csv_de_solo_lectura_no_agrega_especies():
    with pytest.raises(TablaDeSoloLectura):
        EspeciesDeSoloLectura().agregar(LAVANDA)


def test_con_la_base_agregar_una_especie_vuelve_a_escribir_la_copia(tmp_path):
    sqlite = RepositorioEspeciesSqlite(BaseDatos(tmp_path / "matera.sqlite").preparar())
    ruta = tmp_path / "especies.csv"

    RegistroEspeciesConCopiaCsv(sqlite, sqlite, ruta).agregar(Especie("cinta", dict(LAVANDA.rangos)))

    assert "cinta" in [especie.nombre for especie in RepositorioEspeciesCsv(ruta).listar()]
    assert len(RepositorioEspeciesCsv(ruta).listar()) == len(sqlite.listar())


def test_el_comando_exporta_la_base_y_la_api_con_el_csv_diagnostica_igual(config, capsys):
    con_bd = ClienteApi(config)
    assert exportar([], config) == 0
    assert "especies escritas" in capsys.readouterr().out

    con_csv = ClienteApi(dataclasses.replace(config, tabla_referencia="csv"))

    assert _diagnostico(con_csv) == _diagnostico(con_bd)
    assert con_csv.pedir("GET", "/especies").get_json() == con_bd.pedir("GET", "/especies").get_json()


def test_con_el_csv_el_admin_no_puede_agregar_especies(config):
    ClienteApi(config)  # prepara la base, para poder exportarla
    assert exportar([], config) == 0
    api = ClienteApi(dataclasses.replace(config, tabla_referencia="csv"))
    admin = api.admin()

    assert es_error(api.pedir("POST", "/admin/especies", admin, json=ESPECIE_NUEVA), 409, "TABLA_SOLO_LECTURA")


def test_con_la_base_el_admin_agrega_una_especie_y_la_copia_en_csv_queda_al_dia(api, config):
    admin = api.admin()

    assert api.pedir("POST", "/admin/especies", admin, json=ESPECIE_NUEVA).status_code == 201

    assert "cinta" in [especie.nombre for especie in RepositorioEspeciesCsv(config.ruta_tabla_csv).listar()]


def test_con_el_csv_una_planta_se_registra_con_una_especie_de_la_copia(config):
    ClienteApi(config)
    exportar([], config)
    api = ClienteApi(dataclasses.replace(config, tabla_referencia="csv"))
    token = api.cuenta()

    respuesta = api.pedir("POST", "/plantas", token, json={"apodo": "Sala", "especie": "potos", "codigo": "MT-0001-AA"})

    assert respuesta.status_code == 201


def test_una_tabla_de_referencia_desconocida_falla_al_arrancar_con_un_mensaje_claro(tmp_path, monkeypatch):
    monkeypatch.setenv("MATERA_RUTA_BD", str(tmp_path / "matera.sqlite"))
    monkeypatch.setenv("MATERA_TABLA_REFERENCIA", "excel")

    with pytest.raises(ValueError, match="bd o csv"):
        Configuracion.desde_entorno()


def test_por_defecto_la_tabla_es_la_base_y_la_copia_esta_en_el_repositorio(monkeypatch):
    for variable in ("MATERA_TABLA_REFERENCIA", "MATERA_RUTA_CSV"):
        monkeypatch.delenv(variable, raising=False)

    config = Configuracion.desde_entorno()

    assert (config.tabla_referencia, config.ruta_tabla_csv.parent.name, config.ruta_tabla_csv.name) == (
        "bd",
        "datos",
        "especies.csv",
    )
