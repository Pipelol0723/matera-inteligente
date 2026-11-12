"""Modo prueba (corte 3): un admin le pone a una matera suya un estado de mentira para ver como se dibuja.

Sirve para mostrar en la demo cada estado de la matera Tamagotchi (semilla,
florecida, marchita, dormida, con sed...) sin esperar a que la planta llegue
ahi. Solo cambia lo que se ve, en la app y en la pantalla de la placa: el
tamano, la condicion, la cara, si duerme y el globo. Los puntos, las horas bien
cuidada, las lecturas y el diagnostico siguen siendo los reales, y no sale
ningun aviso. Quitar el estado de prueba deja la matera como estaba.

Quien puede usarlo lo decide Usuario.exigir_admin(), y sobre que matera, Planta.exigir_dueno().
"""
from dataclasses import dataclass

from dominio.estados import EstadoGlobal
from dominio.mascota import Condicion, EtapaCrecimiento, Mascota, Necesidad
from dominio.resultados import ResultadoMedicion


@dataclass(frozen=True)
class EstadoDePrueba:
    """Lo que se dibuja mientras dure la prueba. Si duerme, no hay globo."""

    etapa: EtapaCrecimiento
    condicion: Condicion
    cara: EstadoGlobal
    dormida: bool
    necesidad: Necesidad | None

    def __post_init__(self) -> None:
        if not isinstance(self.etapa, EtapaCrecimiento):
            raise TypeError("etapa debe ser una EtapaCrecimiento")
        if not isinstance(self.condicion, Condicion):
            raise TypeError("condicion debe ser una Condicion")
        if not isinstance(self.cara, EstadoGlobal):
            raise TypeError("cara debe ser un EstadoGlobal")
        if not isinstance(self.dormida, bool):
            raise TypeError("dormida debe ser True o False")
        if self.necesidad is not None and not isinstance(self.necesidad, Necesidad):
            raise TypeError("necesidad debe ser una Necesidad o None")
        if self.dormida and self.necesidad is not None:
            # Igual que en CuidadoDeMascota: una matera dormida no pide nada.
            object.__setattr__(self, "necesidad", None)

    def aplicar(self, mascota: Mascota) -> "MascotaEnPrueba":
        """La misma matera con las capas de la prueba. Puntos, horas y ultima lectura quedan reales."""
        return MascotaEnPrueba(
            planta=mascota.planta,
            etapa=self.etapa,
            condicion=self.condicion,
            cara=self.cara,
            dormida=self.dormida,
            necesidad=self.necesidad,
            aviso=None,
            puntos=mascota.puntos,
            horas_cuidada=mascota.horas_cuidada,
            ultima_lectura=mascota.ultima_lectura,
            prueba=self,
        )


@dataclass(frozen=True)
class MascotaEnPrueba(Mascota):
    """Una matera Tamagotchi dibujada con un estado de prueba. prueba es el estado que puso el admin."""

    prueba: EstadoDePrueba | None = None


@dataclass(frozen=True)
class ResultadoEnPrueba(ResultadoMedicion):
    """La respuesta a una lectura de una matera en prueba: el diagnostico es el real, y la placa dibuja prueba."""

    prueba: EstadoDePrueba | None = None
