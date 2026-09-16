"""Recomendacion textual por cada parametro fuera de rango (RF4)."""
from dominio.diagnostico import ResultadoParametro
from dominio.estados import EstadoParametro
from dominio.parametros import HUMEDAD, LUZ, TEMPERATURA

_TEXTOS = {
    (HUMEDAD, EstadoParametro.BAJO):
        "La humedad del sustrato está por debajo del rango recomendado: riegue moderadamente.",
    (HUMEDAD, EstadoParametro.ALTO):
        "El sustrato tiene más humedad de la recomendada: suspenda el riego hasta que se seque y revise el drenaje.",
    (LUZ, EstadoParametro.BAJO):
        "La planta recibe menos luz de la recomendada: acérquela a una ventana o a una fuente de luz.",
    (LUZ, EstadoParametro.ALTO):
        "La planta recibe más luz de la recomendada: aléjela del sol directo o fíltrelo con una cortina.",
    (TEMPERATURA, EstadoParametro.BAJO):
        "La temperatura está por debajo del rango recomendado: aléjela de ventanas frías y corrientes de aire.",
    (TEMPERATURA, EstadoParametro.ALTO):
        "La temperatura está por encima del rango recomendado: llévela a un lugar más fresco y ventilado.",
}


class GeneradorRecomendaciones:
    def para(self, resultado: ResultadoParametro) -> str | None:
        """Texto para un parametro fuera de rango; None si esta en OPTIMO.

        Un parametro sin texto propio (por ejemplo, un pH recien agregado)
        recibe un mensaje generico en lugar de romper el diagnostico.
        """
        if not resultado.fuera_de_rango:
            return None
        texto = _TEXTOS.get((resultado.parametro, resultado.estado))
        if texto is not None:
            return texto
        p, r = resultado.parametro, resultado.rango
        direccion = "por debajo" if resultado.estado is EstadoParametro.BAJO else "por encima"
        unidad = f" {p.unidad}" if p.unidad else ""
        return f"El valor de {p.nombre} está {direccion} del rango recomendado ({r.minimo:g} a {r.maximo:g}{unidad})."
