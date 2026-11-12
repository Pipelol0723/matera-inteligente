"""Casos de uso del juego (corte 3): puntuar cada lectura, el puntaje, la tabla y la matera Tamagotchi.

Solo leen lo que ya existe (plantas, historial y estados del corte 1): el
juego entra sin modificar ningun caso de uso anterior. Las reglas viven en
dominio.juego y dominio.mascota; aqui solo se orquestan.
"""
from dominio import puertos_juego as puertos
from dominio.diagnostico import Diagnostico
from dominio.errores_juego import ApodoRepetido
from dominio.historial import RegistroMedicion
from dominio.juego import ApodoJugador, Participacion, ReglaDeCuidado
from dominio.mascota import CuidadoDeMascota, Mascota, RitmoCrecimiento
from dominio.plantas import Planta
from dominio.puertos_juego import MovimientosPuntaje, RegistroJugadores, RitmosCrecimiento
from dominio.puertos_usuarios import ConsultaPlantas, HistorialMediciones, NotificadorDiagnosticos, Reloj
from dominio.resultados_juego import MovimientoReciente, PosicionTabla, PuntajeDeMatera, PuntajeUsuario
from dominio.usuarios import Usuario


class PuntuarLectura(NotificadorDiagnosticos):
    """Suscriptor del aviso que da DiagnosticarPlantaDeUsuario: cada lectura aceptada deja un movimiento.

    Llega despues de guardar la lectura, asi que una lectura rechazada no cuenta.
    El momento es la hora del servidor, no la del dispositivo: no se puede
    puntuar con fechas viejas ni repetir una hora. Si guardar falla, la lectura
    ya quedo guardada y esa lectura no suma ni resta.
    """

    def __init__(self, movimientos: MovimientosPuntaje, reloj: Reloj, regla: ReglaDeCuidado | None = None):
        self._movimientos = movimientos
        self._reloj = reloj
        self._regla = regla or ReglaDeCuidado()

    def publicar(self, usuario_id: int, planta: Planta, registro: RegistroMedicion, diagnostico: Diagnostico) -> None:
        # Los puntos son del dueno de la planta.
        self._movimientos.agregar(
            self._regla.movimiento(planta.usuario_id, planta.id, self._reloj.ahora(), diagnostico.estado)
        )


class ConsultarPuntaje(puertos.ConsultarPuntaje):
    def __init__(self, movimientos: MovimientosPuntaje, plantas: ConsultaPlantas, limite: int = puertos.LIMITE_MOVIMIENTOS):
        self._movimientos = movimientos
        self._plantas = plantas
        self._limite = limite

    def ejecutar(self, usuario: Usuario) -> PuntajeUsuario:
        propias = {planta.id: planta for planta in _plantas_propias(self._plantas, usuario)}
        totales = self._movimientos.totales_por_planta(usuario.id)
        recientes = self._movimientos.recientes_de(usuario.id, self._limite)
        return PuntajeUsuario(
            total=self._movimientos.total_de(usuario.id),
            materas=[PuntajeDeMatera(planta, totales.get(planta.id, 0)) for planta in propias.values()],
            movimientos=[
                MovimientoReciente(m.momento, m.estado, m.puntos, propias.get(m.planta_id)) for m in recientes
            ],
        )


class ConsultarParticipacion(puertos.ConsultarParticipacion):
    def __init__(self, jugadores: RegistroJugadores):
        self._jugadores = jugadores

    def ejecutar(self, usuario: Usuario) -> Participacion:
        return _participacion(self._jugadores, usuario)


class ElegirParticipacion(puertos.ElegirParticipacion):
    """Participar pide un apodo valido que no use nadie mas; dejar de participar lo libera."""

    def __init__(self, jugadores: RegistroJugadores):
        self._jugadores = jugadores

    def ejecutar(self, usuario: Usuario, participa: bool, apodo: str | None = None) -> Participacion:
        if not participa:
            elegida = Participacion.no_participa(usuario.id)
        else:
            valido = ApodoJugador(apodo)
            # Su propio apodo no cuenta como repetido: puede cambiarle las mayusculas.
            if self._jugadores.apodo_en_uso(valido, excepto_usuario_id=usuario.id):
                raise ApodoRepetido(valido.valor)
            elegida = Participacion.participa(usuario.id, valido)
        self._jugadores.guardar(elegida)
        return elegida


class ConsultarTablaPosiciones(puertos.ConsultarTablaPosiciones):
    """Solo la ve quien participa, y solo trae a quienes participan con la cuenta activa.

    Mismos puntos, misma posicion (1, 2, 2, 4); entre ellos, por apodo.
    """

    def __init__(self, jugadores: RegistroJugadores, movimientos: MovimientosPuntaje):
        self._jugadores = jugadores
        self._movimientos = movimientos

    def ejecutar(self, usuario: Usuario) -> list[PosicionTabla]:
        _participacion(self._jugadores, usuario).exigir_participacion()
        participantes = [p for p in self._jugadores.participantes_activos() if p.en_tabla]
        totales = self._movimientos.totales_de_usuarios([p.usuario_id for p in participantes])
        filas = sorted(
            ((totales.get(p.usuario_id, 0), p) for p in participantes),
            key=lambda fila: (-fila[0], fila[1].apodo.clave),
        )
        tabla: list[PosicionTabla] = []
        for indice, (puntos, participante) in enumerate(filas, start=1):
            posicion = tabla[-1].posicion if tabla and tabla[-1].puntos == puntos else indice
            tabla.append(PosicionTabla(posicion, participante.apodo, puntos, participante.usuario_id == usuario.id))
        return tabla


class ConsultarMascotas(puertos.ConsultarMascotas):
    """Arma la matera Tamagotchi de cada planta propia. Las reglas son de CuidadoDeMascota."""

    def __init__(
        self,
        plantas: ConsultaPlantas,
        historial: HistorialMediciones,
        movimientos: MovimientosPuntaje,
        ritmos: RitmosCrecimiento,
        cuidado: CuidadoDeMascota,
        reloj: Reloj,
    ):
        self._plantas = plantas
        self._historial = historial
        self._movimientos = movimientos
        self._ritmos = ritmos
        self._cuidado = cuidado
        self._reloj = reloj

    def ejecutar(self, usuario: Usuario) -> list[Mascota]:
        ahora = self._reloj.ahora()
        mascotas = []
        for planta in _plantas_propias(self._plantas, usuario):
            # Una especie sin ritmo propio, como una que agrego el admin, crece al ritmo por defecto.
            ritmo = self._ritmos.de_especie(planta.especie) or RitmoCrecimiento()
            resumen = self._movimientos.resumen_de(planta, self._cuidado.ventana)
            # El historial solo da el globo: la cara y si duerme salen de los movimientos.
            mascotas.append(self._cuidado.armar(planta, ritmo, resumen, self._historial.ultimo_de(planta.id), ahora))
        return mascotas


def _plantas_propias(plantas: ConsultaPlantas, usuario: Usuario) -> list[Planta]:
    """El puerto busca; que plantas puede ver el usuario lo decide Planta, en el dominio."""
    return [planta for planta in plantas.de_usuario(usuario.id) if planta.es_de(usuario.id)]


def _participacion(jugadores: RegistroJugadores, usuario: Usuario) -> Participacion:
    """Quien nunca respondio la pregunta de la app todavia no decidio."""
    return jugadores.participacion_de(usuario.id) or Participacion.sin_decidir(usuario.id)
