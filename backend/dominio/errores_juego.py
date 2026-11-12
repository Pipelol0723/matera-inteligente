"""Errores de negocio del juego (corte 3).

Heredan de ErrorDominio, como los del corte 1 y del corte 2: no saben nada de
HTTP, y la capa de presentacion decide con que codigo y con que mensaje se
muestran. ApodoInvalido y ApodoRepetido son del apodo de jugador; los de
dominio.errores_usuarios con el mismo nombre son del apodo de una planta.
"""
from dominio.errores import ErrorDominio


class ParticipacionRequerida(ErrorDominio):
    """Quien no acepto participar no ve la tabla de posiciones."""

    def __init__(self):
        super().__init__(
            "La tabla de posiciones es solo para quien participa: actívelo en Cuenta con un apodo de jugador."
        )


class ApodoInvalido(ErrorDominio):
    """El apodo de jugador no tiene el largo o los caracteres permitidos."""

    def __init__(self, texto: object, minimo: int, maximo: int):
        super().__init__(
            f"El apodo de jugador debe tener de {minimo} a {maximo} caracteres: "
            "letras sin tildes, números, _ o -."
        )
        self.texto = texto
        self.minimo = minimo
        self.maximo = maximo


class ApodoRepetido(ErrorDominio):
    """Otro jugador ya usa ese apodo, aunque lo haya escrito con otras mayusculas."""

    def __init__(self, apodo: str):
        super().__init__(f"El apodo de jugador '{apodo}' ya lo usa otra persona.")
        self.apodo = apodo
