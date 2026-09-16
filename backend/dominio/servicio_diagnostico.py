"""Servicio de dominio: busca los rangos de la especie y evalua la medicion."""
from dominio.diagnostico import Diagnostico
from dominio.errores import EspecieNoSoportada
from dominio.especie import normalizar_nombre
from dominio.evaluador import EvaluadorPlanta
from dominio.medicion import Medicion
from dominio.puertos import ConsultaRangos


class ServicioDiagnostico:
    """Depende del puerto ConsultaRangos, nunca de un CSV o una base de datos concretos.

    Cualquier implementacion del puerto sirve (LSP): la del CSV en produccion
    y un doble en memoria en las pruebas.
    """

    def __init__(self, consulta: ConsultaRangos, evaluador: EvaluadorPlanta):
        self._consulta = consulta
        self._evaluador = evaluador

    def diagnosticar(self, especie: str, medicion: Medicion) -> Diagnostico:
        encontrada = self._consulta.rangos_de(normalizar_nombre(especie))
        if encontrada is None:
            raise EspecieNoSoportada(especie)
        return self._evaluador.evaluar(encontrada, medicion)
