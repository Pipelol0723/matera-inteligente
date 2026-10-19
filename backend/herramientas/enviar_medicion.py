"""Herramienta de desarrollo: manda una medicion a la API como lo haria el ESP32.

No es parte de la app ni del front: sirve para ver Mis materas en vivo
mientras no estan los sensores, igual que se podria usar curl o Postman. No
importa nada del backend: le habla a la API por HTTP, como el dispositivo.

Uso, desde la carpeta backend/:
    python herramientas/enviar_medicion.py MT-0001-AA
    python herramientas/enviar_medicion.py MT-0001-AA --humedad 30 --luz 900 --temperatura 21
    python herramientas/enviar_medicion.py MT-0001-AA --cada 15      (una cada 15 s, hasta Ctrl+C)

Si no se le da la clave del sensor, la pide en la consola sin mostrarla: asi
no queda en el historial de la terminal. Para un script se puede usar la
variable MATERA_CLAVE_SENSOR o --clave=<clave>, con el signo igual, porque
una clave puede empezar con guion.
"""
import argparse
import getpass
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request

API_POR_DEFECTO = "http://127.0.0.1:5000/api/v1"
# Con --cada, cuanto puede alejarse cada valor del que se pidio.
_VARIACION = {"humedad": 3.0, "luz": 60.0, "temperatura": 0.5}
# Los limites fisicos que acepta la API: una variacion nunca los pasa.
_LIMITES = {"humedad": (0.0, 100.0), "luz": (0.0, 150000.0), "temperatura": (-50.0, 60.0)}


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
    lector = argparse.ArgumentParser(description="Manda una medicion como el sensor ESP32.")
    lector.add_argument("codigo", help="codigo del sensor, por ejemplo MT-0001-AA")
    lector.add_argument("--humedad", type=float, default=45.0, help="porcentaje (por defecto 45)")
    lector.add_argument("--luz", type=float, default=800.0, help="lux (por defecto 800)")
    lector.add_argument("--temperatura", type=float, default=22.0, help="grados Celsius (por defecto 22)")
    lector.add_argument("--api", default=os.environ.get("MATERA_API", API_POR_DEFECTO), help="URL base de la API")
    lector.add_argument("--clave", help="clave del sensor, como --clave=<clave> (si falta, se pide en la consola)")
    lector.add_argument("--cada", type=float, help="segundos entre mediciones; los valores varian un poco")
    lector.add_argument("--veces", type=int, help="cuantas mediciones mandar (por defecto 1, o sin fin con --cada)")
    return lector.parse_args(argv)


def enviar(api: str, codigo: str, clave: str, lecturas: dict[str, float]) -> tuple[int, dict]:
    """Devuelve (estado HTTP, cuerpo JSON). La API responde JSON tambien en los errores (RA1)."""
    peticion = urllib.request.Request(
        f"{api.rstrip('/')}/sensores/{codigo}/mediciones",
        data=json.dumps(lecturas).encode(),
        headers={"Content-Type": "application/json", "X-Clave-Sensor": clave},
        method="POST",
    )
    try:
        with urllib.request.urlopen(peticion, timeout=10) as respuesta:
            return respuesta.status, json.load(respuesta)
    except urllib.error.HTTPError as error:
        return error.code, json.load(error)


def variar(base: dict[str, float]) -> dict[str, float]:
    """Un poco alrededor de los valores pedidos, sin alejarse de ellos ni pasar los limites fisicos."""
    variadas = {}
    for nombre, valor in base.items():
        minimo, maximo = _LIMITES[nombre]
        cambio = random.uniform(-_VARIACION[nombre], _VARIACION[nombre])
        variadas[nombre] = round(min(max(valor + cambio, minimo), maximo), 1)
    return variadas


def _texto(lecturas: dict[str, float]) -> str:
    return f"humedad {lecturas['humedad']:g} %, luz {lecturas['luz']:g} lux, temperatura {lecturas['temperatura']:g} °C"


def main(argv: list[str] | None = None) -> int:
    args = _argumentos(argv)
    clave = args.clave or os.environ.get("MATERA_CLAVE_SENSOR") or getpass.getpass("Clave del sensor: ")
    veces = args.veces if args.veces is not None else (1 if args.cada is None else None)
    pedidas = {"humedad": args.humedad, "luz": args.luz, "temperatura": args.temperatura}
    lecturas = pedidas

    enviadas = 0
    try:
        while veces is None or enviadas < veces:
            if enviadas:
                time.sleep(args.cada or 0)
                lecturas = variar(pedidas)
            try:
                estado, cuerpo = enviar(args.api, args.codigo, clave, lecturas)
            except urllib.error.URLError as error:
                print(f"No se pudo contactar la API en {args.api}: {error.reason}", file=sys.stderr)
                return 2
            enviadas += 1
            if estado != 201:
                print(f"{estado} {cuerpo.get('error')}: {cuerpo.get('mensaje')}", file=sys.stderr)
                return 1
            planta = cuerpo["planta"]
            print(f"201 · {planta['apodo']} ({planta['especie']}): {cuerpo['diagnostico']['estado']} · {_texto(lecturas)}")
    except KeyboardInterrupt:
        print(f"\nSe mandaron {enviadas} mediciones.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
