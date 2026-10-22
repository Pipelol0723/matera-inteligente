"""Capa de presentacion: los adaptadores de entrada (rutas REST y WebSocket) y la conversion entre JSON y objetos del dominio.

Solo responde JSON (RA1). Valida la forma de la peticion en el borde y le
entrega al nucleo objetos del dominio, nunca un request ni un dict (RA6).
Depende de los puertos de entrada (dominio.puertos_entrada), no de los casos de uso.
"""
