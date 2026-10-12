"""Contrasenas y secretos con la biblioteca estandar: hashlib, secrets y hmac.

Implementa los puertos Cifrador y GeneradorSecretos. Es el unico archivo del
proyecto que sabe que se usa PBKDF2 o SHA-256.
"""
import hashlib
import hmac
import secrets

from dominio.puertos_usuarios import Cifrador, GeneradorSecretos

# Las que recomienda OWASP para PBKDF2-HMAC-SHA256.
ITERACIONES_RECOMENDADAS = 600_000


class CifradorPbkdf2(Cifrador):
    """Guarda pbkdf2_sha256$iteraciones$sal$huella, con una sal aleatoria de 16 bytes por contrasena.

    Las iteraciones quedan en el texto guardado, asi que subirlas despues no
    invalida las contrasenas que ya existen.
    """

    ALGORITMO = "pbkdf2_sha256"

    def __init__(self, iteraciones: int = ITERACIONES_RECOMENDADAS):
        self._iteraciones = iteraciones

    def cifrar(self, texto: str) -> str:
        sal = secrets.token_bytes(16)
        huella = self._derivar(texto, sal, self._iteraciones)
        return f"{self.ALGORITMO}${self._iteraciones}${sal.hex()}${huella}"

    def verificar(self, texto: str, cifrado: str) -> bool:
        try:
            algoritmo, iteraciones, sal, huella = cifrado.split("$")
            calculada = self._derivar(texto, bytes.fromhex(sal), int(iteraciones))
        except ValueError:
            return False
        return algoritmo == self.ALGORITMO and hmac.compare_digest(calculada, huella)

    @staticmethod
    def _derivar(texto: str, sal: bytes, iteraciones: int) -> str:
        return hashlib.pbkdf2_hmac("sha256", texto.encode("utf-8"), sal, iteraciones).hex()


class GeneradorSecretosSeguro(GeneradorSecretos):
    """Tokens de sesion y claves de sensor de 32 bytes aleatorios. La base guarda su SHA-256.

    Con 32 bytes aleatorios no hace falta una funcion lenta como PBKDF2: no hay
    diccionario que probar.
    """

    def nuevo(self) -> str:
        return secrets.token_urlsafe(32)

    def huella(self, secreto: str) -> str:
        return hashlib.sha256(secreto.encode("utf-8")).hexdigest()

    def coincide(self, secreto: str, huella: str) -> bool:
        return hmac.compare_digest(self.huella(secreto), huella)
