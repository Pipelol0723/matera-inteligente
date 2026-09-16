"""Evaluador: aplica las reglas de negocio a una especie y una medicion."""
from dominio.diagnostico import Diagnostico, ResultadoParametro
from dominio.especie import Especie
from dominio.medicion import Lectura, Medicion
from dominio.recomendaciones import GeneradorRecomendaciones
from dominio.reglas import ReglaAgregacion


class EvaluadorPlanta:
    """No sabe de donde salen la especie ni la medicion, ni nombra ningun parametro.

    Recibe la regla de agregacion y el generador de recomendaciones por
    constructor: cambiar cualquiera de los dos no modifica esta clase.
    """

    def __init__(self, regla: ReglaAgregacion, recomendaciones: GeneradorRecomendaciones):
        self._regla = regla
        self._recomendaciones = recomendaciones

    def evaluar(self, especie: Especie, medicion: Medicion) -> Diagnostico:
        resultados = tuple(self._evaluar_lectura(especie, lectura) for lectura in medicion.lecturas)
        textos = (self._recomendaciones.para(resultado) for resultado in resultados)
        return Diagnostico(
            especie=especie.nombre,
            estado=self._regla.agregar(resultados),
            resultados=resultados,
            recomendaciones=tuple(texto for texto in textos if texto),
        )

    @staticmethod
    def _evaluar_lectura(especie: Especie, lectura: Lectura) -> ResultadoParametro:
        rango = especie.rango_de(lectura.parametro)
        return ResultadoParametro(
            parametro=lectura.parametro,
            valor=lectura.valor,
            rango=rango,
            estado=rango.clasificar(lectura.valor),
            desviacion=rango.desviacion(lectura.valor),
        )
