"""La matera Tamagotchi: como se ve una planta en el juego (corte 3).

Cada capa del dibujo sale de un dato distinto, y todas las decide el dominio:
el front solo dibuja lo que recibe.

- Tamano: las horas de juego bien cuidada, al ritmo de su especie.
- Condicion: el promedio de puntos de las lecturas de las 6 horas de juego que
  terminan en la ultima lectura.
- Cara: el estado de la ultima lectura, o dormida si hace rato no llegan lecturas.
- Necesidad: el parametro fuera de rango de la ultima lectura.
- Aviso: lo que cambio con la ultima lectura.

Todo se mide desde las lecturas, con la hora del servidor, y no desde la hora de
la consulta: mientras no llegan lecturas, la matera no cambia, hasta que se duerme.

El reloj del juego solo cambia la escala: un dia de juego puede durar 6 minutos
en la demo. Los minutos para dormirse son reales y no se escalan.
"""
import math
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from types import MappingProxyType

from dominio.estados import EstadoGlobal, EstadoParametro
from dominio.historial import RegistroMedicion
from dominio.juego import MovimientoPuntaje
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA
from dominio.plantas import Planta

HORAS_POR_DIA = 24

# Desde aqui se numeran las horas de juego. Con el reloj real, cada hora de juego es una hora UTC.
EPOCA = datetime(1970, 1, 1, tzinfo=timezone.utc)


class EtapaCrecimiento(str, Enum):
    SEMILLA = "SEMILLA"
    BROTE = "BROTE"
    PLANTA = "PLANTA"
    FLORECIDA = "FLORECIDA"


class Condicion(str, Enum):
    SANA = "SANA"
    DECAIDA = "DECAIDA"
    MARCHITA = "MARCHITA"


class Necesidad(str, Enum):
    SED = "SED"
    EXCESO_AGUA = "EXCESO_AGUA"
    FRIO = "FRIO"
    CALOR = "CALOR"
    POCA_LUZ = "POCA_LUZ"
    MUCHA_LUZ = "MUCHA_LUZ"


class Aviso(str, Enum):
    """Lo que la matera pide con urgencia: la app manda una notificacion y la placa parpadea."""

    PASO_A_CRITICO = "PASO_A_CRITICO"
    SE_MARCHITO = "SE_MARCHITO"


# Primero el agua, despues la temperatura y despues la luz: si faltan varias, se pide la mas urgente.
_NECESIDADES: tuple[tuple[str, Mapping[EstadoParametro, Necesidad]], ...] = (
    (HUMEDAD.nombre, {EstadoParametro.BAJO: Necesidad.SED, EstadoParametro.ALTO: Necesidad.EXCESO_AGUA}),
    (TEMPERATURA.nombre, {EstadoParametro.BAJO: Necesidad.FRIO, EstadoParametro.ALTO: Necesidad.CALOR}),
    (LUZ.nombre, {EstadoParametro.BAJO: Necesidad.POCA_LUZ, EstadoParametro.ALTO: Necesidad.MUCHA_LUZ}),
)


def necesidad_principal(estados: Iterable[tuple[str, EstadoParametro]]) -> Necesidad | None:
    """Lo que mas necesita la planta, a partir del estado de cada parametro de una lectura.

    Recibe pares (nombre del parametro, estado), para servir igual con el
    Diagnostico de una lectura recien llegada que con un registro del historial.
    Un parametro sin globo propio, como un pH agregado despues, no pide nada.
    """
    por_parametro = dict(estados)
    for nombre, necesidades in _NECESIDADES:
        necesidad = necesidades.get(por_parametro.get(nombre))
        if necesidad is not None:
            return necesidad
    return None


@dataclass(frozen=True)
class RitmoCrecimiento:
    """Cuantos dias de juego bien cuidada necesita una especie para llegar a cada etapa.

    Son valores de juego, no botanicos. El valor por defecto (1/3/7) es el de una
    especie que agrego el admin y no tiene ritmo propio.
    """

    dias_brote: int = 1
    dias_planta: int = 3
    dias_florecida: int = 7

    def __post_init__(self) -> None:
        if not 0 < self.dias_brote < self.dias_planta < self.dias_florecida:
            raise ValueError("El ritmo de crecimiento debe ser creciente y mayor que cero: brote < planta < florecida.")

    def etapa(self, horas_cuidada: int) -> EtapaCrecimiento:
        for dias, etapa in (
            (self.dias_florecida, EtapaCrecimiento.FLORECIDA),
            (self.dias_planta, EtapaCrecimiento.PLANTA),
            (self.dias_brote, EtapaCrecimiento.BROTE),
        ):
            if horas_cuidada >= dias * HORAS_POR_DIA:
                return etapa
        return EtapaCrecimiento.SEMILLA


@dataclass(frozen=True)
class RelojDeJuego:
    """Cuanto dura en tiempo real un dia de juego.

    1440 minutos es el tiempo real. En la demo, con 2, un dia de juego dura 2
    minutos y una hora de juego, 5 segundos: las reglas no cambian, solo la escala.
    """

    minutos_por_dia: float = 1440

    def __post_init__(self) -> None:
        if not math.isfinite(self.minutos_por_dia) or self.minutos_por_dia <= 0 or self.hora <= timedelta(0):
            raise ValueError("Los minutos por dia de juego deben ser un numero mayor que cero.")

    @property
    def dia(self) -> timedelta:
        return timedelta(minutes=self.minutos_por_dia)

    @property
    def hora(self) -> timedelta:
        return self.dia / HORAS_POR_DIA

    def horas(self, cantidad: float) -> timedelta:
        return self.hora * cantidad

    def dias(self, cantidad: float) -> timedelta:
        return self.dia * cantidad

    def numero_de_hora(self, momento: datetime) -> int:
        """En que hora de juego cae un momento, contadas desde EPOCA. Asi se agrupan las lecturas por hora."""
        return (momento - EPOCA) // self.hora


@dataclass(frozen=True)
class Tramo:
    """Las lecturas de un tramo de tiempo: cuantas hubo y cuanto sumaron sus puntos.

    Guarda la suma y no el promedio: asi la comparacion con los umbrales es exacta.
    """

    cantidad: int = 0
    suma: int = 0

    def __post_init__(self) -> None:
        if self.cantidad < 0:
            raise ValueError("Un tramo no puede tener menos de cero lecturas.")

    @property
    def vacio(self) -> bool:
        return self.cantidad == 0

    def promedio_mayor_que(self, umbral: int) -> bool:
        """suma / cantidad > umbral, sin dividir. Solo tiene sentido si el tramo tiene lecturas."""
        return self.suma > umbral * self.cantidad

    def promedio_al_menos(self, umbral: int) -> bool:
        """suma / cantidad >= umbral, sin dividir. Solo tiene sentido si el tramo tiene lecturas."""
        return self.suma >= umbral * self.cantidad


@dataclass(frozen=True)
class ResumenCuidado:
    """Los movimientos de una planta, ya agrupados por el puerto MovimientosPuntaje.

    El adaptador solo agrupa y cuenta; las reglas las aplica CuidadoDeMascota.
    - horas: de cada hora de juego que tuvo lecturas (numerada con
      RelojDeJuego.numero_de_hora), cuantas hubo y cuanto sumaron.
    - ultimo y anterior: los dos movimientos mas recientes, o None si no hay.
    - al_ultimo: las lecturas de la ventana de la condicion que termina en la
      ultima, con ella incluida: momento en (ultimo.momento - ventana, ultimo.momento].
    - al_anterior: las de la ventana que termina en la anterior, sin la ultima:
      momento en (anterior.momento - ventana, anterior.momento]. Es como estaba
      la matera antes de que llegara la ultima lectura.
    Las dos ventanas se anclan en lecturas y no en la hora de la consulta: asi no
    cambian mientras no llegan lecturas, y con la ventana llena la lectura que sale
    por detras no se confunde con la que entro.
    """

    horas: Mapping[int, Tramo]
    ultimo: MovimientoPuntaje | None = None
    anterior: MovimientoPuntaje | None = None
    al_ultimo: Tramo = Tramo()
    al_anterior: Tramo = Tramo()

    def __post_init__(self) -> None:
        object.__setattr__(self, "horas", MappingProxyType(dict(self.horas)))
        # Cada ventana trae al menos la lectura en que termina, y no hay ventana sin esa lectura.
        if self.anterior is not None and self.ultimo is None:
            raise ValueError("Un resumen con lectura anterior tiene que tener una ultima.")
        for movimiento, tramo in ((self.ultimo, self.al_ultimo), (self.anterior, self.al_anterior)):
            if (movimiento is None) != tramo.vacio:
                raise ValueError("La ventana de una lectura la incluye, y sin esa lectura la ventana esta vacia.")

    @classmethod
    def sin_lecturas(cls) -> "ResumenCuidado":
        return cls({})

    @property
    def puntos(self) -> int:
        """Todo lo que lleva sumado la matera."""
        return sum(tramo.suma for tramo in self.horas.values())


@dataclass(frozen=True)
class Mascota:
    """La matera Tamagotchi lista para dibujar. Ninguna de estas capas la calcula el front.

    cara es el estado global de la ultima lectura puntuada, o None si nunca hubo.
    ultima_lectura es cuando llego esa lectura, con la hora del servidor (no la
    del dispositivo): con el, la app avisa una sola vez por lectura aunque
    consulte cada 10 s. Dormida, necesidad y aviso son None: la ultima lectura es
    vieja y no se muestra como si fuera de ahora.
    """

    planta: Planta
    etapa: EtapaCrecimiento
    condicion: Condicion
    cara: EstadoGlobal | None
    dormida: bool
    necesidad: Necesidad | None
    aviso: Aviso | None
    puntos: int
    horas_cuidada: int
    ultima_lectura: datetime | None


class CuidadoDeMascota:
    """Arma la matera Tamagotchi de una planta a partir de sus puntos y de su ultima lectura."""

    # La condicion mira las lecturas de las ultimas horas de juego, no solo la ultima.
    HORAS_DE_LA_CONDICION = 6
    # Promedio mayor que UMBRAL_SANA: sana. Menor que UMBRAL_MARCHITA: marchita. En medio, con los dos
    # umbrales incluidos, decaida: una matera que esta siempre EN_RIESGO (-5) queda decaida y sigue creciendo.
    UMBRAL_SANA = 0
    UMBRAL_MARCHITA = -5
    MINUTOS_PARA_DORMIR = 30

    def __init__(self, reloj: RelojDeJuego, minutos_para_dormir: float = MINUTOS_PARA_DORMIR):
        if not math.isfinite(minutos_para_dormir) or minutos_para_dormir <= 0:
            raise ValueError("Los minutos para dormirse deben ser un numero mayor que cero.")
        self._reloj = reloj
        self._para_dormir = timedelta(minutes=minutos_para_dormir)

    @property
    def reloj(self) -> RelojDeJuego:
        return self._reloj

    @property
    def ventana(self) -> timedelta:
        """Cuanto mira hacia atras la condicion, desde cada lectura: 6 horas de juego, escaladas con el reloj."""
        return self._reloj.horas(self.HORAS_DE_LA_CONDICION)

    def armar(
        self,
        planta: Planta,
        ritmo: RitmoCrecimiento,
        resumen: ResumenCuidado,
        ultima: RegistroMedicion | None,
        ahora: datetime,
    ) -> Mascota:
        """resumen debe venir con ventanas que duren self.ventana; ultima es la del historial, solo para el globo.

        La cara, si duerme y la ultima lectura salen del ultimo movimiento, que
        guarda el estado con la hora del servidor: una placa con la hora atrasada
        no puede dejar la cara de una lectura vieja ni dormir a una matera despierta.
        """
        ultimo = resumen.ultimo
        horas = self.horas_cuidada(resumen)
        dormida = self.dormida(ultimo, ahora)
        return Mascota(
            planta=planta,
            etapa=ritmo.etapa(horas),
            condicion=self.condicion(resumen.al_ultimo),
            cara=ultimo.estado if ultimo is not None else None,
            dormida=dormida,
            # Dormida, la ultima lectura es vieja: no se muestra lo que pedia ni se repite su aviso.
            necesidad=None if dormida else self.necesidad(ultima),
            aviso=None if dormida else self.aviso(resumen),
            puntos=resumen.puntos,
            horas_cuidada=horas,
            ultima_lectura=ultimo.momento if ultimo is not None else None,
        )

    def condicion(self, tramo: Tramo) -> Condicion:
        """Sin lecturas en el tramo queda sana: no hay evidencia de descuido."""
        if tramo.vacio or tramo.promedio_mayor_que(self.UMBRAL_SANA):
            return Condicion.SANA
        if tramo.promedio_al_menos(self.UMBRAL_MARCHITA):
            return Condicion.DECAIDA
        return Condicion.MARCHITA

    def horas_cuidada(self, resumen: ResumenCuidado) -> int:
        """Las horas de juego bien cuidada: cuenta cada hora con su propio promedio de -5 o mas.

        Cada hora se mira sola, no con la ventana de 6 horas de la condicion: una
        hora con una sola lectura EN_RIESGO (-5) cuenta aunque la matera siga
        marchita por las horas anteriores. Si la descuidan, deja de crecer.
        """
        return sum(
            1 for tramo in resumen.horas.values() if not tramo.vacio and self.condicion(tramo) is not Condicion.MARCHITA
        )

    def dormida(self, ultimo: MovimientoPuntaje | None, ahora: datetime) -> bool:
        """Duerme si su ultima lectura llego hace mas de los minutos para dormir, que son reales, o si nunca hubo una."""
        return ultimo is None or ahora - ultimo.momento > self._para_dormir

    @staticmethod
    def necesidad(ultima: RegistroMedicion | None) -> Necesidad | None:
        if ultima is None:
            return None
        return necesidad_principal((lectura.parametro.nombre, lectura.estado) for lectura in ultima.lecturas)

    def aviso(self, resumen: ResumenCuidado) -> Aviso | None:
        """Lo que cambio con la ultima lectura.

        - SE_MARCHITO: en la ventana que termina en la ultima lectura la condicion
          es marchita, y en la que terminaba en la anterior no lo era (o no habia
          anterior). Asi el aviso sale una vez al marchitarse, aunque la ventana
          este llena y entre lectura y lectura salga la mas vieja.
        - PASO_A_CRITICO: la ultima lectura es CRITICO y la anterior no lo era, o
          no habia anterior.
        Si pasan las dos cosas con la misma lectura, gana SE_MARCHITO: es la que
        detiene el crecimiento, y la cara triste ya muestra el CRITICO.
        """
        ultimo, anterior = resumen.ultimo, resumen.anterior
        if ultimo is None:
            return None
        marchita_ahora = self.condicion(resumen.al_ultimo) is Condicion.MARCHITA
        marchita_antes = anterior is not None and self.condicion(resumen.al_anterior) is Condicion.MARCHITA
        if marchita_ahora and not marchita_antes:
            return Aviso.SE_MARCHITO
        if ultimo.estado is EstadoGlobal.CRITICO and (anterior is None or anterior.estado is not EstadoGlobal.CRITICO):
            return Aviso.PASO_A_CRITICO
        return None
