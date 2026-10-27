"""R4: la tabla de referencia sale del CSV o de la base segun la configuracion, y el CSV es una copia de solo lectura."""
import dataclasses
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

from dominio.errores_usuarios import TablaDeSoloLectura
from dominio.especie import Especie
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.rango import Rango
from exportar_especies_csv import main as exportar
from infraestructura.configuracion import Configuracion
from infraestructura.repositorio_especies_csv import (
    ErrorTablaReferencia,
    EspeciesDeSoloLectura,
    RegistroEspeciesConCopiaCsv,
    RepositorioEspeciesCsv,
    escribir_csv,
)
from infraestructura.sqlite import BaseDatos, RepositorioEspeciesSqlite
from main import construir_app
from tests.integracion.conftest import ClienteApi, es_error
from tests.integracion.test_api_cuentas import ESPECIE_NUEVA

LAVANDA = Especie("lavanda", {HUMEDAD: Rango(25, 50), LUZ: Rango(10760, 107640), TEMPERATURA: Rango(13.5, 27)}, "Lavandula")
# No esta en carga.sql: sirve para que la base y la copia no tengan las mismas especies.
ORQUIDEA = Especie("orquidea", dict(LAVANDA.rangos), "Phalaenopsis")


def _diagnostico(api, token) -> dict:
    cuerpo = {"especie": "Potos", "humedad": 35, "luz": 800, "temperatura": 22}
    return api.pedir("POST", "/diagnosticos", token, json=cuerpo).get_json()


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


class TablaLenta:
    """Registro y catalogo en memoria. La primera vez que lista, se demora despues de leer:
    asi otro admin alcanza a agregar y escribir su copia mientras esta todavia no la escribe."""

    def __init__(self):
        self.especies = []
        self._primera = True

    def agregar(self, especie):
        self.especies.append(especie)

    def listar(self):
        vista = list(self.especies)
        if self._primera:
            self._primera = False
            time.sleep(0.3)
        return vista


def test_dos_admins_que_agregan_a_la_vez_dejan_la_copia_con_las_dos_especies(tmp_path):
    tabla = TablaLenta()
    ruta = tmp_path / "especies.csv"
    registro = RegistroEspeciesConCopiaCsv(tabla, tabla, ruta)
    primero = threading.Thread(target=registro.agregar, args=(LAVANDA,))
    primero.start()
    time.sleep(0.1)  # el primero ya leyo la tabla y se demora
    registro.agregar(ORQUIDEA)
    primero.join()

    assert sorted(especie.nombre for especie in RepositorioEspeciesCsv(ruta).listar()) == ["lavanda", "orquidea"]


def test_la_copia_escrita_desde_varios_hilos_nunca_queda_a_medias(tmp_path):
    ruta = tmp_path / "especies.csv"
    especies = [LAVANDA, ORQUIDEA]

    with ThreadPoolExecutor(max_workers=8) as hilos:
        list(hilos.map(lambda _: escribir_csv(especies, ruta), range(200)))

    assert [especie.nombre for especie in RepositorioEspeciesCsv(ruta).listar()] == ["lavanda", "orquidea"]
    assert [archivo.name for archivo in tmp_path.iterdir() if archivo.suffix == ".tmp"] == []


def test_el_comando_exporta_la_base_y_la_api_con_el_csv_diagnostica_igual(config, capsys):
    con_bd = ClienteApi(config)
    token = con_bd.cuenta()  # la misma base y el mismo secreto: el token sirve en las dos
    assert exportar([], config) == 0
    assert "especies escritas" in capsys.readouterr().out

    con_csv = ClienteApi(dataclasses.replace(config, tabla_referencia="csv"))

    assert _diagnostico(con_csv, token) == _diagnostico(con_bd, token)
    assert con_csv.pedir("GET", "/especies", token).get_json() == con_bd.pedir("GET", "/especies", token).get_json()


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


def test_con_una_copia_vieja_el_backend_no_arranca_y_pide_exportar(config):
    ClienteApi(config)
    assert exportar([], config) == 0
    # La especie entra a la base sin pasar por la API, asi que la copia no se entera.
    RepositorioEspeciesSqlite(BaseDatos(config.ruta_bd).preparar()).agregar(ORQUIDEA)

    with pytest.raises(ErrorTablaReferencia, match=r"faltan: orquidea.*exportar_especies_csv\.py"):
        construir_app(dataclasses.replace(config, tabla_referencia="csv"))

    assert exportar([], config) == 0
    assert construir_app(dataclasses.replace(config, tabla_referencia="csv"))


def test_con_una_copia_que_no_es_de_esta_base_el_backend_no_arranca(config):
    ClienteApi(config)
    especies = RepositorioEspeciesSqlite(BaseDatos(config.ruta_bd).preparar()).listar()
    [primera, *resto] = especies
    otra = Especie(primera.nombre, dict(LAVANDA.rangos), primera.nombre_cientifico)
    escribir_csv([otra, *resto, ORQUIDEA], config.ruta_tabla_csv)

    with pytest.raises(ErrorTablaReferencia, match=f"sobran: orquidea; con otros datos: {primera.nombre}"):
        construir_app(dataclasses.replace(config, tabla_referencia="csv"))


def test_una_tabla_de_referencia_desconocida_falla_al_arrancar_con_un_mensaje_claro(tmp_path, monkeypatch):
    monkeypatch.setenv("MATERA_RUTA_BD", str(tmp_path / "matera.sqlite"))
    monkeypatch.setenv("MATERA_TABLA_REFERENCIA", "excel")

    with pytest.raises(ValueError, match="bd o csv"):
        Configuracion.desde_entorno()


def test_por_defecto_la_tabla_es_la_base_y_la_copia_esta_en_el_repositorio(monkeypatch):
    for variable in ("MATERA_TABLA_REFERENCIA", "MATERA_RUTA_CSV", "MATERA_RUTA_BD"):
        monkeypatch.delenv(variable, raising=False)

    config = Configuracion.desde_entorno()

    assert (config.tabla_referencia, config.ruta_tabla_csv.parent.name, config.ruta_tabla_csv.name) == (
        "bd",
        "datos",
        "especies.csv",
    )


def test_con_una_base_fuera_del_repositorio_la_copia_va_junto_a_ella(tmp_path, monkeypatch):
    monkeypatch.delenv("MATERA_RUTA_CSV", raising=False)
    monkeypatch.setenv("MATERA_RUTA_BD", str(tmp_path / "matera.sqlite"))

    assert Configuracion.desde_entorno().ruta_tabla_csv == tmp_path / "especies.csv"
