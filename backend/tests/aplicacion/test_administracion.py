"""Permisos y administracion con dobles en memoria: la regla se prueba sin HTTP y sin base de datos."""
from datetime import datetime, timedelta, timezone

import pytest

from aplicacion.administracion import (
    AgregarEspecie,
    CambiarEstadoUsuario,
    CambiarRol,
    ConvertirEnAdministrador,
    EliminarUsuario,
    ListarUsuarios,
)
from aplicacion.cuentas import IdentificarUsuario, IniciarSesion, RegistrarUsuario
from aplicacion.diagnosticar_planta_de_usuario import DiagnosticarPlantaDeUsuario
from aplicacion.plantas import RegistrarPlanta
from dominio.errores import ParametroSinRango
from dominio.errores_usuarios import (
    AccionSobreSiMismo,
    CuentaDesactivada,
    EspecieYaExiste,
    PermisoDenegado,
    SesionInvalida,
    UsuarioNoEncontrado,
)
from dominio.especie import Especie
from dominio.estados import EstadoGlobal
from dominio.evaluador import EvaluadorPlanta
from dominio.parametros import HUMEDAD, LUZ, PARAMETROS, TEMPERATURA
from dominio.plantas import Planta
from dominio.rango import Rango
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaHibrida
from dominio.servicio_diagnostico import ServicioDiagnostico
from dominio.usuarios import Rol
from tests.dobles import medicion, sansevieria
from tests.dobles_usuarios import (
    CifradorFalso,
    EspeciesEditablesEnMemoria,
    GeneradorSecretosFalso,
    HistorialEnMemoria,
    NotificadorEnMemoria,
    RelojFijo,
    RepositorioPlantasEnMemoria,
    RepositorioSensoresEnMemoria,
    RepositorioSesionesEnMemoria,
    RepositorioUsuariosEnMemoria,
    TokensFalsos,
    codigo,
)

AHORA = datetime(2026, 10, 12, 15, 0, tzinfo=timezone.utc)


def lavanda() -> Especie:
    return Especie(
        "Lavanda", {HUMEDAD: Rango(25, 50), LUZ: Rango(10760, 107640), TEMPERATURA: Rango(13, 27)}, "Lavandula"
    )


class Sistema:
    """Una admin (Ada), un usuario comun (Beto) y los casos de uso conectados a los mismos dobles."""

    def __init__(self):
        self.sensores = RepositorioSensoresEnMemoria()
        self.plantas = RepositorioPlantasEnMemoria(self.sensores)
        self.usuarios = RepositorioUsuariosEnMemoria(self.plantas)
        self.sesiones = RepositorioSesionesEnMemoria()
        self.especies = EspeciesEditablesEnMemoria(sansevieria())
        secretos, reloj = GeneradorSecretosFalso(), RelojFijo(AHORA)

        registrar = RegistrarUsuario(self.usuarios, self.usuarios, CifradorFalso())
        self.tokens = TokensFalsos()
        self.iniciar = IniciarSesion(
            self.usuarios, self.sesiones, CifradorFalso(), secretos, self.tokens, reloj, timedelta(days=7)
        )
        self.identificar = IdentificarUsuario(self.sesiones, self.usuarios, reloj)
        self.convertir = ConvertirEnAdministrador(self.usuarios, self.usuarios)
        self.listar = ListarUsuarios(self.usuarios)
        self.cambiar_estado = CambiarEstadoUsuario(self.usuarios, self.usuarios, self.sesiones)
        self.cambiar_rol = CambiarRol(self.usuarios, self.usuarios)
        self.eliminar = EliminarUsuario(self.usuarios, self.usuarios)
        self.agregar_especie = AgregarEspecie(self.especies, self.especies, PARAMETROS)
        servicio = ServicioDiagnostico(self.especies, EvaluadorPlanta(ReglaHibrida(), GeneradorRecomendaciones()))
        self.registrar_planta = RegistrarPlanta(self.plantas, self.plantas, self.sensores, self.especies, secretos)
        avisos = NotificadorEnMemoria()
        self.diagnosticar = DiagnosticarPlantaDeUsuario(self.plantas, servicio, HistorialEnMemoria(), reloj, avisos)

        registrar.ejecutar("Ada", "ada@correo.co", "clave-segura")
        self.beto = registrar.ejecutar("Beto", "beto@correo.co", "clave-segura")
        self.ada = self.convertir.ejecutar("ada@correo.co")


@pytest.fixture
def sistema():
    return Sistema()


@pytest.mark.parametrize(
    "accion",
    [
        lambda s: s.listar.ejecutar(s.beto),
        lambda s: s.cambiar_estado.ejecutar(s.beto, s.ada.id, False),
        lambda s: s.cambiar_rol.ejecutar(s.beto, s.ada.id, Rol.USUARIO),
        lambda s: s.eliminar.ejecutar(s.beto, s.ada.id),
        lambda s: s.agregar_especie.ejecutar(s.beto, lavanda()),
    ],
    ids=["listar", "cambiar estado", "cambiar rol", "eliminar", "agregar especie"],
)
def test_cada_caso_de_uso_de_administracion_rechaza_a_un_usuario_comun(sistema, accion):
    with pytest.raises(PermisoDenegado):
        accion(sistema)

    assert sistema.usuarios.por_id(sistema.ada.id) == sistema.ada
    assert sistema.especies.rangos_de("lavanda") is None


def test_crear_admin_convierte_una_cuenta_ya_registrada():
    assert Sistema().ada.rol is Rol.ADMIN


def test_crear_admin_con_un_correo_sin_cuenta_falla(sistema):
    with pytest.raises(UsuarioNoEncontrado):
        sistema.convertir.ejecutar("nadie@correo.co")


def test_el_admin_ve_cuantas_plantas_tiene_cada_usuario(sistema):
    sistema.plantas.guardar_con_sensor(Planta(None, sistema.beto.id, "Sala", "sansevieria"), codigo(1), "h")

    resumenes = sistema.listar.ejecutar(sistema.ada)

    assert [(r.nombre, r.rol, r.cantidad_plantas) for r in resumenes] == [
        ("Ada", Rol.ADMIN, 0),
        ("Beto", Rol.USUARIO, 1),
    ]


def test_desactivar_cierra_las_sesiones_y_bloquea_el_login(sistema):
    identidad = sistema.tokens.verificar_usuario(sistema.iniciar.ejecutar("beto@correo.co", "clave-segura").token)

    sistema.cambiar_estado.ejecutar(sistema.ada, sistema.beto.id, False)

    assert sistema.sesiones.sesiones == {}
    with pytest.raises(SesionInvalida):
        sistema.identificar.ejecutar(identidad)
    with pytest.raises(CuentaDesactivada):
        sistema.iniciar.ejecutar("beto@correo.co", "clave-segura")


def test_reactivar_devuelve_el_acceso(sistema):
    sistema.cambiar_estado.ejecutar(sistema.ada, sistema.beto.id, False)

    sistema.cambiar_estado.ejecutar(sistema.ada, sistema.beto.id, True)

    assert sistema.iniciar.ejecutar("beto@correo.co", "clave-segura").usuario.activo


def test_un_admin_puede_dar_y_quitar_el_rol_a_otro(sistema):
    beto_admin = sistema.cambiar_rol.ejecutar(sistema.ada, sistema.beto.id, Rol.ADMIN)
    assert beto_admin.es_admin()

    assert sistema.cambiar_rol.ejecutar(beto_admin, sistema.ada.id, Rol.USUARIO).rol is Rol.USUARIO


@pytest.mark.parametrize(
    "accion",
    [
        lambda s: s.cambiar_estado.ejecutar(s.ada, s.ada.id, False),
        lambda s: s.cambiar_rol.ejecutar(s.ada, s.ada.id, Rol.USUARIO),
        lambda s: s.eliminar.ejecutar(s.ada, s.ada.id),
    ],
    ids=["desactivarse", "quitarse el rol", "eliminarse"],
)
def test_un_admin_no_puede_actuar_sobre_si_mismo(sistema, accion):
    with pytest.raises(AccionSobreSiMismo):
        accion(sistema)

    assert sistema.usuarios.por_id(sistema.ada.id) == sistema.ada


@pytest.mark.parametrize(
    "accion",
    [
        lambda s: s.cambiar_estado.ejecutar(s.ada, 99, False),
        lambda s: s.cambiar_rol.ejecutar(s.ada, 99, Rol.ADMIN),
        lambda s: s.eliminar.ejecutar(s.ada, 99),
    ],
    ids=["estado", "rol", "eliminar"],
)
def test_actuar_sobre_un_usuario_que_no_existe_falla(sistema, accion):
    with pytest.raises(UsuarioNoEncontrado):
        accion(sistema)


def test_eliminar_borra_la_cuenta(sistema):
    sistema.eliminar.ejecutar(sistema.ada, sistema.beto.id)

    assert sistema.usuarios.por_id(sistema.beto.id) is None


def test_no_se_agrega_una_especie_que_ya_existe(sistema):
    with pytest.raises(EspecieYaExiste):
        sistema.agregar_especie.ejecutar(sistema.ada, sansevieria())


def test_una_especie_sin_rango_para_algun_parametro_no_se_agrega(sistema):
    incompleta = Especie("lavanda", {HUMEDAD: Rango(25, 50), LUZ: Rango(10760, 107640)})

    with pytest.raises(ParametroSinRango) as error:
        sistema.agregar_especie.ejecutar(sistema.ada, incompleta)
    assert error.value.parametro is TEMPERATURA


def test_una_especie_recien_agregada_sirve_para_registrar_una_planta_y_diagnosticarla(sistema):
    sistema.agregar_especie.ejecutar(sistema.ada, lavanda())

    planta = sistema.registrar_planta.ejecutar(sistema.beto, "Patio", "lavanda", "MT-0001-AA").planta
    resultado = sistema.diagnosticar.ejecutar(sistema.beto.id, planta.id, medicion(30, 20000, 20), "MT-0001-AA")

    assert resultado.diagnostico.especie == "lavanda"
    assert resultado.diagnostico.estado is EstadoGlobal.SALUDABLE
