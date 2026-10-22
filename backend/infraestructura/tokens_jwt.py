"""Tokens JWT con PyJWT. Implementa los puertos EmisorTokens y VerificadorTokens.

Es el unico archivo del proyecto que importa jwt: lo comprueba una prueba de
arquitectura. Cambiar de libreria, o de JWT a otra cosa, es escribir otra clase
con los mismos metodos y cambiar una linea de main.py.

El token va firmado con HS256 y un secreto que solo conoce el servidor. Trae:
  iss      quien lo emitio (siempre "matera-inteligente")
  sub      a quien identifica: el id del usuario o el codigo del sensor
  alcance  para que sirve: "usuario" (sus rutas) o "lecturas" (solo reportar lecturas)
  jti      su id: el de usuario debe tener su sesion abierta, el de sensor debe ser el vigente
  iat/exp  cuando se emitio y cuando vence
"""
import secrets
from datetime import datetime
from pathlib import Path

import jwt

from dominio.errores import ErrorDominio
from dominio.errores_usuarios import (
    AlcanceInvalido,
    CodigoSensorInvalido,
    CredencialDispositivoInvalida,
    SesionInvalida,
)
from dominio.identidad import IdentidadDispositivo, IdentidadUsuario
from dominio.puertos_usuarios import EmisorTokens, Reloj, VerificadorTokens
from dominio.sensores import CodigoSensor

ALGORITMO = "HS256"
EMISOR = "matera-inteligente"
ALCANCE_USUARIO = "usuario"
ALCANCE_LECTURAS = "lecturas"
_RECLAMOS = ["iss", "sub", "alcance", "jti", "iat", "exp"]


class TokensJwt(EmisorTokens, VerificadorTokens):
    def __init__(self, secreto: str, reloj: Reloj):
        if len(secreto) < 32:
            # HS256 con un secreto corto se puede adivinar probando: se exige uno largo.
            raise ValueError("El secreto de los JWT debe tener al menos 32 caracteres.")
        self._secreto = secreto
        self._reloj = reloj

    def emitir(self, identidad: IdentidadUsuario | IdentidadDispositivo, vence_en: datetime) -> str:
        if isinstance(identidad, IdentidadUsuario):
            sujeto, alcance = str(identidad.usuario_id), ALCANCE_USUARIO
        else:
            sujeto, alcance = identidad.codigo.valor, ALCANCE_LECTURAS
        reclamos = {
            "iss": EMISOR,
            "sub": sujeto,
            "alcance": alcance,
            "jti": identidad.token_id,
            "iat": self._reloj.ahora(),
            "exp": vence_en,
        }
        return jwt.encode(reclamos, self._secreto, algorithm=ALGORITMO)

    def verificar_usuario(self, token: str) -> IdentidadUsuario:
        reclamos = self._decodificar(token, SesionInvalida)
        if reclamos["alcance"] != ALCANCE_USUARIO:
            raise AlcanceInvalido("usuario")
        try:
            return IdentidadUsuario(int(reclamos["sub"]), reclamos["jti"])
        except ValueError:
            raise SesionInvalida() from None

    def verificar_dispositivo(self, token: str) -> IdentidadDispositivo:
        reclamos = self._decodificar(token, CredencialDispositivoInvalida)
        if reclamos["alcance"] != ALCANCE_LECTURAS:
            raise AlcanceInvalido("dispositivo")
        try:
            return IdentidadDispositivo(CodigoSensor(reclamos["sub"]), reclamos["jti"])
        except CodigoSensorInvalido:
            raise CredencialDispositivoInvalida() from None

    def _decodificar(self, token: str, error: type[ErrorDominio]) -> dict:
        try:
            # algorithms fijo: un token con "alg": "none" o firmado con otro algoritmo se rechaza.
            return jwt.decode(
                token,
                self._secreto,
                algorithms=[ALGORITMO],
                issuer=EMISOR,
                options={"require": _RECLAMOS},
            )
        except jwt.InvalidTokenError:
            # Firma alterada, otro secreto, vencido, mal formado o sin algun reclamo: el mismo error.
            raise error() from None


def secreto_guardado(ruta: Path) -> str:
    """El secreto de los JWT guardado en ese archivo. Si no existe, crea uno aleatorio y lo guarda.

    Asi los tokens siguen sirviendo despues de reiniciar el backend. Va junto a la
    base de datos, fuera de Git; MATERA_JWT_SECRETO lo reemplaza.
    """
    if ruta.exists():
        return ruta.read_text(encoding="utf-8").strip()
    ruta.parent.mkdir(parents=True, exist_ok=True)
    secreto = secrets.token_urlsafe(48)
    ruta.write_text(secreto, encoding="utf-8")
    return secreto
