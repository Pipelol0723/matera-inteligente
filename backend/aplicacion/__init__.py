"""Capa de aplicacion: casos de uso que orquestan el dominio.

Depende solo del dominio. No conoce HTTP, Flask ni el CSV: recibe objetos del
dominio ya validados y devuelve objetos del dominio. Cada caso de uso que llama
un adaptador implementa su puerto de entrada, de dominio.puertos_entrada.
"""
