"""Tokens JWT con PyJWT. Implementa los puertos EmisorTokens y VerificadorTokens.

Es el unico archivo del proyecto que importa jwt: lo comprueba una prueba de
arquitectura. Cambiar de libreria, o de JWT a otra cosa, es escribir otra clase
con los mismos metodos y cambiar una linea de main.py.

El token va firmado con HS256 y un secreto que solo conoce el servidor. Trae:
  iss      quien lo emitio (siempre "matera-inteligente")
  sub      a quien identifica (el id del usuario)
  alcance  para que sirve ("usuario")
  jti      su id, el que guarda la sesion: sin sesion abierta, el token no sirve
  iat/exp  cuando se emitio y cuando vence
"""
import secrets
from datetime import datetime
from pathlib import Path

import jwt

from dominio.errores_usuarios import AlcanceInvalido, SesionInvalida
from dominio.identidad import IdentidadUsuario
from dominio.puertos_usuarios import EmisorTokens, Reloj, VerificadorTokens

ALGORITMO = "HS256"
EMISOR = "matera-inteligente"
ALCANCE_USUARIO = "usuario"
_RECLAMOS = ["iss", "sub", "alcance", "jti", "iat", "exp"]


class TokensJwt(EmisorTokens, VerificadorTokens):
    def __init__(self, secreto: str, reloj: Reloj):
        if len(secreto) < 32:
            # HS256 con un secreto corto se puede adivinar probando: se exige uno largo.
            raise ValueError("El secreto de los JWT debe tener al menos 32 caracteres.")
        self._secreto = secreto
        self._reloj = reloj

    def emitir(self, identidad: IdentidadUsuario, vence_en: datetime) -> str:
        reclamos = {
            "iss": EMISOR,
            "sub": str(identidad.usuario_id),
            "alcance": ALCANCE_USUARIO,
            "jti": identidad.token_id,
            "iat": self._reloj.ahora(),
            "exp": vence_en,
        }
        return jwt.encode(reclamos, self._secreto, algorithm=ALGORITMO)

    def verificar_usuario(self, token: str) -> IdentidadUsuario:
        reclamos = self._decodificar(token)
        if reclamos["alcance"] != ALCANCE_USUARIO:
            raise AlcanceInvalido("usuario")
        try:
            return IdentidadUsuario(int(reclamos["sub"]), reclamos["jti"])
        except ValueError:
            raise SesionInvalida() from None

    def _decodificar(self, token: str) -> dict:
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
            raise SesionInvalida() from None


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
