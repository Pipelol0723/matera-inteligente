"""Simulador del ESP32 (R3): manda lecturas a la API como la placa, sin hardware.

Hace lo mismo que el firmware: canjea la clave del sensor por un token de
alcance «lecturas» y reporta cada lectura con su hora, en el cuerpo
{dispositivo, momento, lecturas}. No importa nada del backend: le habla a la
API por HTTP, como cualquier dispositivo, y solo usa la biblioteca estandar.

Dos modos:
  continuo (por defecto): una lectura cada --intervalo segundos, hasta Ctrl+C o --veces.
      Los valores cambian poco a poco, como en una matera de verdad: la humedad baja
      despacio y sube de golpe cuando se riega. Con --fuera-de-rango y --invalidas se
      mezclan lecturas fuera de rango y datos invalidos, en esas proporciones (0 a 1).
  --casos: manda una vez cada caso de error y dice si la API respondio lo esperado.

Uso, desde la raiz del repositorio:
    python simulador/simulador_esp32.py MT-0002-AB --clave=<clave>
    python simulador/simulador_esp32.py MT-0002-AB --clave=<clave> --intervalo 5 --fuera-de-rango 0.2 --invalidas 0.1
    python simulador/simulador_esp32.py MT-0002-AB --clave=<clave> --casos

La clave es la que muestra la API una sola vez al crear la matera. Si no se da,
se pide en la consola sin mostrarla; tambien sirve MATERA_CLAVE_SENSOR. Va con
signo igual (--clave=<clave>) porque una clave puede empezar con guion. Conviene
que el simulador tenga su propia matera: cada canje deja sin efecto el token
anterior del mismo sensor.
"""
import argparse
import getpass
import json
import math
import os
import random
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

API_POR_DEFECTO = "http://127.0.0.1:5000/api/v1"
# Valores posibles que casi ninguna especie tolera: la API los acepta y los diagnostica fuera de rango.
FUERA_DE_RANGO = (("humedad", 8.0, "humedad muy baja"), ("luz", 50.0, "casi sin luz"), ("temperatura", 38.0, "demasiado calor"))
# Lo que responde la API cuando el token vencio o lo reemplazo otro canje: el simulador canjea otra vez.
CREDENCIAL_INVALIDA = "CREDENCIAL_DISPOSITIVO_INVALIDA"


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def momento_iso(momento: datetime) -> str:
    """Como la manda la placa: en UTC, con Z y sin microsegundos."""
    return momento.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class MateraSimulada:
    """Valores que cambian poco a poco: la tierra se seca, se riega, y el dia se calienta y se enfria."""

    def __init__(self, azar: random.Random):
        self._azar = azar
        self._paso = 0
        self.humedad = azar.uniform(55, 68)

    def siguiente(self) -> dict[str, float]:
        self._paso += 1
        self.humedad -= self._azar.uniform(0.2, 0.8)
        if self.humedad < 35:
            self.humedad = self._azar.uniform(62, 72)  # se riega
        temperatura = 22 + 3 * math.sin(self._paso / 20) + self._azar.uniform(-0.3, 0.3)
        luz = 1200 + 300 * math.sin(self._paso / 30) + self._azar.uniform(-80, 80)
        return {"humedad": round(self.humedad, 1), "luz": round(luz), "temperatura": round(temperatura, 1)}


@dataclass
class Envio:
    """Lo que se manda a /lecturas: el cuerpo (o bytes crudos), el token y el codigo de la URL."""

    cuerpo: dict | bytes
    token: str | None
    codigo: str


@dataclass(frozen=True)
class Caso:
    """Un dato invalido y lo que la API tiene que responder."""

    nombre: str
    estado: int
    error: str
    armar: Callable[["Simulador", dict[str, float]], Envio] | None = None


@dataclass
class Resumen:
    normales: int = 0
    fuera_de_rango: int = 0
    invalidas: int = 0
    inesperadas: list[str] = field(default_factory=list)


class Simulador:
    def __init__(self, api: str, codigo: str, clave: str, salida: Callable[[str], None] = print):
        self.api = api.rstrip("/")
        self.codigo = codigo.strip().upper()
        self.clave = clave
        self.token: str | None = None
        self._salida = salida

    def cuerpo(self, lecturas: dict, momento: datetime | None = None, dispositivo: str | None = None) -> dict:
        return {
            "dispositivo": dispositivo or self.codigo,
            "momento": momento_iso(momento or ahora()),
            "lecturas": lecturas,
        }

    def canjear(self, clave: str | None = None) -> tuple[int, dict]:
        estado, respuesta = _pedir(f"{self.api}/dispositivos/{self.codigo}/token", {"clave": clave or self.clave})
        if estado == 200 and clave is None:
            self.token = respuesta["token"]
        return estado, respuesta

    def enviar(self, envio: Envio) -> tuple[int, dict]:
        return _pedir(f"{self.api}/dispositivos/{envio.codigo}/lecturas", envio.cuerpo, envio.token)

    def reportar(self, lecturas: dict) -> tuple[int, dict]:
        """Una lectura con el token vigente. Si el token vencio o lo reemplazo otro canje, canjea otra vez."""
        estado, respuesta = self.enviar(Envio(self.cuerpo(lecturas), self.token, self.codigo))
        if estado == 401 and respuesta.get("error") == CREDENCIAL_INVALIDA:
            estado_canje, respuesta_canje = self.canjear()
            if estado_canje != 200:
                return estado_canje, respuesta_canje
            estado, respuesta = self.enviar(Envio(self.cuerpo(lecturas), self.token, self.codigo))
        return estado, respuesta


def _token_alterado(sim: Simulador) -> str:
    cabecera, cuerpo, firma = (sim.token or "a.b.c").split(".")
    return f"{cabecera}.{cuerpo}.{'A' if firma[:1] != 'A' else 'B'}{firma[1:]}"


def _sin(lecturas: dict, parametro: str) -> dict:
    return {nombre: valor for nombre, valor in lecturas.items() if nombre != parametro}


CASOS: tuple[Caso, ...] = (
    Caso("humedad imposible (150 %)", 400, "PARAMETRO_INVALIDO",
         lambda s, l: Envio(s.cuerpo({**l, "humedad": 150}), s.token, s.codigo)),
    Caso("texto en vez de numero", 400, "PARAMETRO_INVALIDO",
         lambda s, l: Envio(s.cuerpo({**l, "luz": "mucha"}), s.token, s.codigo)),
    Caso("falta la temperatura", 400, "PARAMETRO_INVALIDO",
         lambda s, l: Envio(s.cuerpo(_sin(l, "temperatura")), s.token, s.codigo)),
    Caso("hora en el futuro", 400, "MOMENTO_INVALIDO",
         lambda s, l: Envio(s.cuerpo(l, momento=ahora() + timedelta(minutes=10)), s.token, s.codigo)),
    Caso("hora sin zona horaria", 400, "MOMENTO_INVALIDO",
         lambda s, l: Envio({**s.cuerpo(l), "momento": ahora().replace(tzinfo=None, microsecond=0).isoformat()}, s.token, s.codigo)),
    Caso("JSON mal formado", 400, "SOLICITUD_INVALIDA",
         lambda s, l: Envio(json.dumps(s.cuerpo(l)).encode()[:-5], s.token, s.codigo)),
    Caso("lectura de otro sensor", 403, "DISPOSITIVO_AJENO",
         lambda s, l: Envio(s.cuerpo(l, dispositivo="MT-9999-ZZ"), s.token, s.codigo)),
    Caso("sin token", 401, CREDENCIAL_INVALIDA,
         lambda s, l: Envio(s.cuerpo(l), None, s.codigo)),
    Caso("token alterado", 401, CREDENCIAL_INVALIDA,
         lambda s, l: Envio(s.cuerpo(l), _token_alterado(s), s.codigo)),
)


def _pedir(url: str, cuerpo: dict | bytes | None, token: str | None = None) -> tuple[int, dict]:
    """Devuelve (estado HTTP, cuerpo JSON). La API responde JSON tambien en los errores (RA1)."""
    datos = cuerpo if isinstance(cuerpo, bytes) else json.dumps(cuerpo).encode()
    cabeceras = {"Content-Type": "application/json"}
    if token:
        cabeceras["Authorization"] = f"Bearer {token}"
    peticion = urllib.request.Request(url, data=datos, headers=cabeceras, method="POST")
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def _texto(lecturas: dict) -> str:
    def numero(valor):
        return f"{valor:g}".replace(".", ",") if isinstance(valor, (int, float)) else str(valor)

    return ", ".join(
        f"{nombre} {numero(valor)} {unidad}"
        for nombre, unidad in (("humedad", "%"), ("luz", "lux"), ("temperatura", "°C"))
        if (valor := lecturas.get(nombre)) is not None
    )


def _hora() -> str:
    return datetime.now().strftime("%H:%M:%S")


def modo_continuo(sim: Simulador, args: argparse.Namespace, azar: random.Random) -> int:
    matera = MateraSimulada(azar)
    resumen = Resumen()
    enviadas = 0
    try:
        while args.veces is None or enviadas < args.veces:
            if enviadas:
                time.sleep(args.intervalo)
            lecturas = matera.siguiente()
            tirada = azar.random()
            if tirada < args.invalidas:
                caso = azar.choice(CASOS)
                estado, respuesta = sim.enviar(caso.armar(sim, lecturas))
                como_se_esperaba = (estado, respuesta.get("error")) == (caso.estado, caso.error)
                resumen.invalidas += 1
                if not como_se_esperaba:
                    resumen.inesperadas.append(caso.nombre)
                nota = "rechazada, como se esperaba" if como_se_esperaba else f"INESPERADO: se esperaba {caso.estado} {caso.error}"
                sim._salida(f"{_hora()}  {estado}  invalida        {caso.nombre} -> {respuesta.get('error')} ({nota})")
            else:
                fuera = tirada < args.invalidas + args.fuera_de_rango
                if fuera:
                    parametro, valor, _ = azar.choice(FUERA_DE_RANGO)
                    lecturas = {**lecturas, parametro: valor}
                estado, respuesta = sim.reportar(lecturas)
                if estado != 201:
                    sim._salida(f"{_hora()}  {estado}  {respuesta.get('error')}: {respuesta.get('mensaje')}")
                    return 1
                if fuera:
                    resumen.fuera_de_rango += 1
                else:
                    resumen.normales += 1
                tipo = "fuera de rango" if fuera else "normal        "
                sim._salida(f"{_hora()}  201  {tipo}  {_texto(lecturas)} -> {respuesta['diagnostico']['estado']}")
            enviadas += 1
    except KeyboardInterrupt:
        pass
    sim._salida(
        f"Se mandaron {enviadas} lecturas: {resumen.normales} normales, {resumen.fuera_de_rango} fuera de rango"
        f" y {resumen.invalidas} invalidas."
    )
    if resumen.inesperadas:
        sim._salida(f"La API no respondio lo esperado en: {', '.join(resumen.inesperadas)}.")
        return 1
    return 0


def modo_casos(sim: Simulador, azar: random.Random) -> int:
    lecturas = MateraSimulada(azar).siguiente()
    resultados = []
    for caso in CASOS:
        estado, respuesta = sim.enviar(caso.armar(sim, lecturas))
        resultados.append((caso, estado, respuesta.get("error")))
    # La clave equivocada va en el canje, no en las lecturas.
    estado, respuesta = sim.canjear("una-clave-que-no-es")
    resultados.append((Caso("clave equivocada en el canje", 401, "CLAVE_SENSOR_INVALIDA"), estado, respuesta.get("error")))

    bien = 0
    for caso, estado, error in resultados:
        como_se_esperaba = (estado, error) == (caso.estado, caso.error)
        bien += como_se_esperaba
        sim._salida(
            f"{caso.nombre:<30} esperaba {caso.estado} {caso.error:<32} recibio {estado} {error or '':<32}"
            f" {'ok' if como_se_esperaba else 'NO'}"
        )
    sim._salida(f"{bien} de {len(resultados)} como se esperaba.")
    return 0 if bien == len(resultados) else 1


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    lector = argparse.ArgumentParser(description="Manda lecturas a la API como el ESP32, sin hardware.")
    lector.add_argument("codigo", help="codigo del sensor de la matera, por ejemplo MT-0002-AB")
    lector.add_argument("--clave", help="clave del sensor, como --clave=<clave> (si falta, se pide en la consola)")
    lector.add_argument("--api", default=os.environ.get("MATERA_API", API_POR_DEFECTO), help="URL base de la API")
    lector.add_argument("--intervalo", type=float, default=5.0, help="segundos entre lecturas (por defecto 5)")
    lector.add_argument("--veces", type=int, help="cuantas lecturas mandar (por defecto, hasta Ctrl+C)")
    lector.add_argument("--fuera-de-rango", type=float, default=0.0, help="proporcion de lecturas fuera de rango, de 0 a 1")
    lector.add_argument("--invalidas", type=float, default=0.0, help="proporcion de datos invalidos, de 0 a 1")
    lector.add_argument("--casos", action="store_true", help="manda una vez cada caso de error y lo compara con lo esperado")
    lector.add_argument("--semilla", type=int, help="para repetir la misma secuencia de valores")
    args = lector.parse_args(argv)
    if not (0 <= args.fuera_de_rango <= 1 and 0 <= args.invalidas <= 1 and args.fuera_de_rango + args.invalidas <= 1):
        lector.error("--fuera-de-rango y --invalidas van de 0 a 1, y juntas no pueden pasar de 1")
    return args


def main(argv: list[str] | None = None, salida: Callable[[str], None] = print) -> int:
    args = _argumentos(argv)
    clave = args.clave or os.environ.get("MATERA_CLAVE_SENSOR") or getpass.getpass("Clave del sensor: ")
    sim = Simulador(args.api, args.codigo, clave, salida)
    azar = random.Random(args.semilla)
    try:
        estado, respuesta = sim.canjear()
        if estado != 200:
            salida(f"No se pudo canjear la clave: {estado} {respuesta.get('error')}: {respuesta.get('mensaje')}")
            return 1
        salida(f"Token del sensor {sim.codigo} listo; vence {respuesta['venceEn']}.")
        return modo_casos(sim, azar) if args.casos else modo_continuo(sim, args, azar)
    except urllib.error.URLError as error:
        salida(f"No se pudo contactar la API en {args.api}: {error.reason}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
