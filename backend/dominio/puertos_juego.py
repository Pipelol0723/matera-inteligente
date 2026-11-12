"""Puertos del juego (corte 3): lo que el juego ofrece y lo que necesita de afuera.

Van en un archivo nuevo, y no en dominio.puertos_entrada ni en
dominio.puertos_usuarios, para que el juego entre sin modificar ningun archivo
existente del dominio.

Los de entrada tienen un solo metodo, ejecutar, y se llaman igual que el caso
de uso de aplicacion.juego que los hereda. Los de salida se implementan en
infraestructura; en las pruebas, cada uno tiene un doble en memoria.
"""
from abc import ABC, abstractmethod
from collections.abc import Collection
from datetime import datetime

from dominio.juego import ApodoJugador, MovimientoPuntaje, Participacion
from dominio.mascota import Mascota, RelojDeJuego, ResumenCuidado, RitmoCrecimiento
from dominio.plantas import Planta
from dominio.resultados_juego import PosicionTabla, PuntajeUsuario
from dominio.usuarios import Usuario

# Cuantos movimientos recientes trae el puntaje.
LIMITE_MOVIMIENTOS = 20


# --- Entrada: lo que ofrece el juego. Cada uno recibe el Usuario ya identificado ---


class ConsultarPuntaje(ABC):
    """Tus puntos: el total, lo de cada matera y los ultimos movimientos."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario) -> PuntajeUsuario: ...


class ConsultarTablaPosiciones(ABC):
    """Solo para quien participa: lanza ParticipacionRequerida si no."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario) -> list[PosicionTabla]: ...


class ConsultarParticipacion(ABC):
    """Si participa, si no participa o si todavia no decidio."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario) -> Participacion: ...


class ElegirParticipacion(ABC):
    """Participar con un apodo, cambiar de apodo o dejar de participar.

    Lanza ApodoInvalido o ApodoRepetido si participa con un apodo que no sirve.
    Al no participar, el apodo se ignora.
    """

    @abstractmethod
    def ejecutar(self, usuario: Usuario, participa: bool, apodo: str | None = None) -> Participacion: ...


class ConsultarMascotas(ABC):
    """La matera Tamagotchi de cada planta del usuario, y solo de las suyas."""

    @abstractmethod
    def ejecutar(self, usuario: Usuario) -> list[Mascota]: ...


# --- Salida: lo que el juego necesita de afuera ---


class MovimientosPuntaje(ABC):
    """Los movimientos del puntaje: uno por cada lectura aceptada.

    Los de una planta borrada se quedan con su dueno, sin planta: cuentan en su
    total, pero no en los de la planta ni en su resumen. Asi una planta nueva que
    reciba el mismo id no hereda sus puntos ni su tamano.
    """

    @abstractmethod
    def agregar(self, movimiento: MovimientoPuntaje) -> None:
        """Lo guarda solo si la planta sigue existiendo y es de ese usuario; si no, lanza PlantaNoEncontrada."""

    @abstractmethod
    def total_de(self, usuario_id: int) -> int:
        """La suma de todos sus movimientos, tambien los de materas borradas. 0 si no tiene."""

    @abstractmethod
    def totales_por_planta(self, usuario_id: int) -> dict[int, int]:
        """planta_id -> suma de sus movimientos, solo de las plantas que existen y tienen alguno."""

    @abstractmethod
    def recientes_de(self, usuario_id: int, limite: int) -> list[MovimientoPuntaje]:
        """Los mas recientes primero, como maximo `limite`. Si dos tienen el mismo momento, primero el ultimo guardado."""

    @abstractmethod
    def totales_de_usuarios(self, usuario_ids: Collection[int]) -> dict[int, int]:
        """usuario_id -> su total, para la tabla de posiciones. Quien no tiene movimientos puede faltar."""

    @abstractmethod
    def resumen_de(self, planta: Planta, reloj: RelojDeJuego, desde: datetime) -> ResumenCuidado:
        """Los movimientos de esa planta y de su dueno (planta.id y planta.usuario_id), agrupados.

        - horas: hora de juego -> Tramo(cantidad, suma), solo las horas con
          movimientos. La hora de un movimiento es reloj.numero_de_hora(momento):
          floor((momento - EPOCA) / reloj.hora).
        - ventana: Tramo de los movimientos con momento posterior a `desde`.
        - ultimo y anterior: los dos mas recientes, por momento y, si empatan,
          por orden de guardado.
        Solo agrupa y cuenta: que hora fue bien cuidada lo decide CuidadoDeMascota.
        """


class RegistroJugadores(ABC):
    """Quien participa en la tabla de posiciones, y con que apodo."""

    @abstractmethod
    def participacion_de(self, usuario_id: int) -> Participacion | None:
        """La ultima que eligio, o None si nunca respondio."""

    @abstractmethod
    def guardar(self, participacion: Participacion) -> None:
        """Crea o reemplaza la de ese usuario.

        Lanza ApodoRepetido si otro usuario ya tiene ese apodo sin importar
        mayusculas (ApodoJugador.clave): lo asegura la base aunque dos lo pidan a la vez.
        """

    @abstractmethod
    def apodo_en_uso(self, apodo: ApodoJugador, excepto_usuario_id: int) -> bool:
        """Si alguien que no es ese usuario participa con ese apodo, sin importar mayusculas."""

    @abstractmethod
    def participantes_activos(self) -> list[Participacion]:
        """Los que participan y tienen la cuenta activa: las cuentas desactivadas no aparecen en la tabla."""


class RitmosCrecimiento(ABC):
    """El ritmo de crecimiento de cada especie. Va aparte de la tabla de especies del corte 1."""

    @abstractmethod
    def de_especie(self, especie: str) -> RitmoCrecimiento | None:
        """Recibe el nombre ya normalizado. None si la especie no tiene ritmo propio, como una que agrego el admin."""
