"""Modo prueba con dobles, sin servidor ni base: solo un admin, solo sus materas, y solo cambia el dibujo."""
from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from aplicacion.modo_prueba import MascotasConPrueba, PonerEstadoDePrueba, QuitarEstadoDePrueba
from dominio.errores_usuarios import PermisoDenegado, PlantaNoEncontrada
from dominio.estados import EstadoGlobal
from dominio.mascota import Aviso, Condicion, EtapaCrecimiento, Mascota, Necesidad
from dominio.modo_prueba import EstadoDePrueba, MascotaEnPrueba
from dominio.plantas import Planta
from dominio.puertos_juego import ConsultarMascotas
from dominio.puertos_prueba import EstadosDePrueba
from dominio.usuarios import Correo, Rol, Usuario

PRUEBA = EstadoDePrueba(EtapaCrecimiento.SEMILLA, Condicion.MARCHITA, EstadoGlobal.CRITICO, False, Necesidad.SED)


class EstadosEnDiccionario(EstadosDePrueba):
    def __init__(self):
        self.estados = {}

    def de_planta(self, planta):
        dueno, estado = self.estados.get(planta.id, (None, None))
        return estado if dueno == planta.usuario_id else None

    def guardar(self, planta, estado):
        self.estados[planta.id] = (planta.usuario_id, estado)

    def quitar(self, planta_id):
        self.estados.pop(planta_id, None)


@dataclass
class PlantasFijas:
    plantas: dict

    def por_id(self, planta_id):
        return self.plantas.get(planta_id)


class MascotasFijas(ConsultarMascotas):
    def __init__(self, mascotas):
        self.mascotas = mascotas

    def ejecutar(self, usuario):
        return self.mascotas


def _usuario(usuario_id, rol):
    return Usuario(id=usuario_id, correo=Correo(f"u{usuario_id}@correo.co"), nombre="Ana", hash_contrasena="x", rol=rol)


def _planta(planta_id=1, dueno=1):
    return Planta(id=planta_id, usuario_id=dueno, apodo="Sala", especie="potos")


def _mascota(planta):
    return Mascota(
        planta=planta,
        etapa=EtapaCrecimiento.FLORECIDA,
        condicion=Condicion.SANA,
        cara=EstadoGlobal.SALUDABLE,
        dormida=False,
        necesidad=None,
        aviso=Aviso.PASO_A_CRITICO,
        puntos=120,
        horas_cuidada=40,
        ultima_lectura=datetime(2026, 11, 12, tzinfo=timezone.utc),
    )


def test_aplicar_cambia_solo_el_dibujo_y_quita_el_aviso():
    mascota = _mascota(_planta())
    en_prueba = PRUEBA.aplicar(mascota)
    assert isinstance(en_prueba, MascotaEnPrueba) and en_prueba.prueba is PRUEBA
    assert (en_prueba.etapa, en_prueba.condicion, en_prueba.cara) == (
        EtapaCrecimiento.SEMILLA,
        Condicion.MARCHITA,
        EstadoGlobal.CRITICO,
    )
    assert en_prueba.necesidad is Necesidad.SED and en_prueba.aviso is None
    assert (en_prueba.puntos, en_prueba.horas_cuidada, en_prueba.ultima_lectura) == (
        mascota.puntos,
        mascota.horas_cuidada,
        mascota.ultima_lectura,
    )


def test_una_matera_dormida_no_pide_nada():
    dormida = EstadoDePrueba(EtapaCrecimiento.BROTE, Condicion.SANA, EstadoGlobal.SALUDABLE, True, Necesidad.CALOR)
    assert dormida.necesidad is None


def test_el_estado_de_prueba_exige_tipos_del_dominio():
    with pytest.raises(TypeError):
        EstadoDePrueba("SEMILLA", Condicion.SANA, EstadoGlobal.SALUDABLE, False, None)


def test_solo_un_admin_pone_o_quita_un_estado_de_prueba():
    estados = EstadosEnDiccionario()
    plantas = PlantasFijas({1: _planta(dueno=7)})
    usuario = _usuario(7, Rol.USUARIO)
    with pytest.raises(PermisoDenegado):
        PonerEstadoDePrueba(plantas, estados).ejecutar(usuario, 1, PRUEBA)
    with pytest.raises(PermisoDenegado):
        QuitarEstadoDePrueba(plantas, estados).ejecutar(usuario, 1)
    assert estados.estados == {}


def test_un_admin_solo_toca_sus_materas():
    estados = EstadosEnDiccionario()
    plantas = PlantasFijas({1: _planta(dueno=8)})
    admin = _usuario(7, Rol.ADMIN)
    with pytest.raises(PlantaNoEncontrada):
        PonerEstadoDePrueba(plantas, estados).ejecutar(admin, 1, PRUEBA)
    with pytest.raises(PlantaNoEncontrada):
        PonerEstadoDePrueba(plantas, estados).ejecutar(admin, 2, PRUEBA)
    assert estados.estados == {}


def test_poner_y_quitar():
    estados = EstadosEnDiccionario()
    plantas = PlantasFijas({1: _planta(dueno=7)})
    admin = _usuario(7, Rol.ADMIN)
    PonerEstadoDePrueba(plantas, estados).ejecutar(admin, 1, PRUEBA)
    assert estados.de_planta(_planta(dueno=7)) is PRUEBA
    QuitarEstadoDePrueba(plantas, estados).ejecutar(admin, 1)
    assert estados.de_planta(_planta(dueno=7)) is None


def test_la_consulta_aplica_la_prueba_solo_si_quien_pregunta_es_admin():
    estados = EstadosEnDiccionario()
    estados.guardar(_planta(dueno=7), PRUEBA)
    mascota = _mascota(_planta(dueno=7))
    consulta = MascotasConPrueba(MascotasFijas([mascota]), estados)
    assert consulta.ejecutar(_usuario(7, Rol.ADMIN))[0].cara is EstadoGlobal.CRITICO
    assert consulta.ejecutar(_usuario(7, Rol.USUARIO)) == [mascota]


def test_borrar_la_matera_borra_su_prueba():
    from aplicacion.modo_prueba import EliminarPlantaYSuPrueba
    from dominio.puertos_entrada import EliminarPlanta

    class EliminarFijo(EliminarPlanta):
        def ejecutar(self, usuario, planta_id):
            self.borrada = planta_id

    estados = EstadosEnDiccionario()
    estados.guardar(_planta(dueno=7), PRUEBA)
    interno = EliminarFijo()
    EliminarPlantaYSuPrueba(interno, estados).ejecutar(_usuario(7, Rol.ADMIN), 1)
    assert interno.borrada == 1 and estados.estados == {}
