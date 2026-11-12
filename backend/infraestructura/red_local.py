"""Las direcciones del PC en la red local, para que una placa sepa a donde mandar sus lecturas.

Solo usa `socket` de la biblioteca estandar. No abre conexiones: el truco del UDP
(connect sin enviar nada) solo le pregunta al sistema por cual interfaz saldria a internet.
"""
import ipaddress
import socket

PREFIJO_API = "/api/v1"
AVISO_SIN_RED = (
    "Ninguna placa puede alcanzar este servidor. Arranquelo con MATERA_HOST=0.0.0.0 "
    "(o con la IP de la red) y permita el puerto en el firewall."
)


def _es_de_red(texto: str) -> bool:
    try:
        direccion = ipaddress.IPv4Address(texto)
    except ValueError:
        return False
    return not (direccion.is_loopback or direccion.is_link_local or direccion.is_unspecified)


def ips_ipv4() -> list[str]:
    """Las IPv4 del PC, sin 127.x ni 169.254.x, sin repetir y en orden estable."""
    encontradas: list[str] = []
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            encontradas.append(info[4][0])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sonda:
            sonda.connect(("10.255.255.255", 1))  # UDP: no envia nada
            encontradas.append(sonda.getsockname()[0])
    except OSError:
        pass
    vistas: list[str] = []
    for ip in encontradas:
        if _es_de_red(ip) and ip not in vistas:
            vistas.append(ip)
    return vistas


def direcciones_alcanzables(host: str) -> list[str]:
    """Las IPs por las que otro equipo de la red puede llegar al servidor, segun MATERA_HOST."""
    host = host.strip()
    if host in ("0.0.0.0", ""):
        return ips_ipv4()
    return [host] if _es_de_red(host) else []


class RedLocal:
    """Lo que `GET /red` responde: las bases de la API alcanzables desde la red local."""

    def __init__(self, host: str, puerto: int):
        self._host = host
        self._puerto = puerto

    def servidores(self) -> list[str]:
        return [f"http://{ip}:{self._puerto}{PREFIJO_API}" for ip in direcciones_alcanzables(self._host)]

    def aviso(self) -> str | None:
        return None if self.servidores() else AVISO_SIN_RED
