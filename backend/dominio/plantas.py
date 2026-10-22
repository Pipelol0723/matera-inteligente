"""Planta de un usuario: su apodo, su especie y su dueno (corte 2).

Va en su propio modulo y no en usuarios.py: las reglas de la cuenta y las de
la planta cambian por razones distintas (SRP).
"""
from dataclasses import dataclass

from dominio.errores_usuarios import ApodoInvalido, PlantaNoEncontrada
from dominio.especie import normalizar_nombre

APODO_MAXIMO = 40


@dataclass(frozen=True)
class Planta:
    """El id es None hasta que el repositorio la guarda. La especie va normalizada, como en Especie."""

    id: int | None
    usuario_id: int
    apodo: str
    especie: str

    def __post_init__(self) -> None:
        apodo = " ".join(self.apodo.split())
        if not apodo or len(apodo) > APODO_MAXIMO:
            raise ApodoInvalido(APODO_MAXIMO)
        object.__setattr__(self, "apodo", apodo)
        object.__setattr__(self, "especie", normalizar_nombre(self.especie))

    def es_de(self, usuario_id: int) -> bool:
        return self.usuario_id == usuario_id

    def exigir_dueno(self, usuario_id: int) -> None:
        """La regla «un usuario solo ve sus plantas», venga la orden por HTTP, por MQTT o por consola.

        Una planta ajena da el mismo error que una que no existe: no se confirma que exista.
        """
        if not self.es_de(usuario_id):
            raise PlantaNoEncontrada(self.id)

    def mismo_apodo(self, apodo: str) -> bool:
        """'Potos de la sala' y 'potos  de la SALA' son el mismo apodo."""
        return self.apodo.casefold() == " ".join(apodo.split()).casefold()
