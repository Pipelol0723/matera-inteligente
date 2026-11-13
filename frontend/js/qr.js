// Un generador mínimo de códigos QR (ISO/IEC 18004), para el QR de Mi cuenta con la dirección del servidor.
// El proyecto no carga nada de afuera, así que va escrito aquí: solo modo byte (UTF-8), nivel de corrección
// M (15 %), la versión más chica que alcance (1 a 40) y la máscara con menos penalización, como pide la norma.
// Sigue la estructura del generador de Project Nayuki (licencia MIT), reescrita y recortada a lo que se usa.
// qrComoSvg() lo dibuja en negro sobre blanco, con su margen de 4 módulos, también en los temas oscuros: un
// QR claro sobre oscuro no lo leen todas las cámaras.
import { crearSvg } from "./formato.js";

// Por versión (índice 1 a 40), con el nivel M: bytes de corrección por bloque y cantidad de bloques.
const CORRECCION_POR_BLOQUE = [-1, 10, 16, 26, 18, 24, 16, 18, 22, 22, 26, 30, 22, 22, 24, 24, 28, 28, 26, 26, 26,
  26, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28, 28];
const BLOQUES = [-1, 1, 1, 1, 2, 2, 4, 4, 4, 5, 5, 5, 8, 9, 9, 10, 10, 11, 13, 14, 16, 17, 17, 18, 20, 21, 23, 25,
  26, 28, 29, 31, 33, 35, 37, 38, 40, 43, 45, 47, 49];
const BITS_DEL_NIVEL_M = 0; // en la información de formato: L = 1, M = 0, Q = 3, H = 2

const bit = (valor, i) => ((valor >>> i) & 1) !== 0;

// Los módulos que caben en la versión, sin los patrones fijos.
function modulosDeDatos(version) {
  let total = (16 * version + 128) * version + 64;
  if (version >= 2) {
    const alineaciones = Math.floor(version / 7) + 2;
    total -= (25 * alineaciones - 10) * alineaciones - 55;
    if (version >= 7) total -= 36;
  }
  return total;
}

const bytesDeDatos = (version) =>
  Math.floor(modulosDeDatos(version) / 8) - CORRECCION_POR_BLOQUE[version] * BLOQUES[version];

// ---- Reed-Solomon en GF(2^8), con el polinomio 0x11D ----

function multiplicar(x, y) {
  let z = 0;
  for (let i = 7; i >= 0; i -= 1) {
    z = (z << 1) ^ ((z >>> 7) * 0x11d);
    z ^= ((y >>> i) & 1) * x;
  }
  return z;
}

function divisor(grado) {
  const resultado = new Array(grado).fill(0);
  resultado[grado - 1] = 1;
  let raiz = 1;
  for (let i = 0; i < grado; i += 1) {
    for (let j = 0; j < resultado.length; j += 1) {
      resultado[j] = multiplicar(resultado[j], raiz);
      if (j + 1 < resultado.length) resultado[j] ^= resultado[j + 1];
    }
    raiz = multiplicar(raiz, 0x02);
  }
  return resultado;
}

function resto(datos, div) {
  const resultado = div.map(() => 0);
  for (const b of datos) {
    const factor = b ^ resultado.shift();
    resultado.push(0);
    div.forEach((coeficiente, i) => {
      resultado[i] ^= multiplicar(coeficiente, factor);
    });
  }
  return resultado;
}

// Los bytes de datos partidos en bloques, cada uno con su corrección, e intercalados.
function conCorreccion(datos, version) {
  const cantidad = BLOQUES[version];
  const largoCorreccion = CORRECCION_POR_BLOQUE[version];
  const total = Math.floor(modulosDeDatos(version) / 8);
  const cortos = cantidad - (total % cantidad);
  const largoCorto = Math.floor(total / cantidad);
  const div = divisor(largoCorreccion);
  const bloques = [];
  for (let i = 0, k = 0; i < cantidad; i += 1) {
    const parte = datos.slice(k, k + largoCorto - largoCorreccion + (i < cortos ? 0 : 1));
    k += parte.length;
    const correccion = resto(parte, div);
    if (i < cortos) parte.push(0);
    bloques.push(parte.concat(correccion));
  }
  const resultado = [];
  for (let i = 0; i < bloques[0].length; i += 1) {
    bloques.forEach((bloque, j) => {
      // El relleno de los bloques cortos no se escribe.
      if (i !== largoCorto - largoCorreccion || j >= cortos) resultado.push(bloque[i]);
    });
  }
  return resultado;
}

// ---- la matriz ----

class Matriz {
  constructor(version) {
    this.version = version;
    this.lado = version * 4 + 17;
    this.modulos = Array.from({ length: this.lado }, () => new Array(this.lado).fill(false));
    this.fijos = Array.from({ length: this.lado }, () => new Array(this.lado).fill(false));
  }

  fijar(x, y, oscuro) {
    this.modulos[y][x] = oscuro;
    this.fijos[y][x] = true;
  }

  dibujarPatrones() {
    const lado = this.lado;
    for (let i = 0; i < lado; i += 1) {
      this.fijar(6, i, i % 2 === 0);
      this.fijar(i, 6, i % 2 === 0);
    }
    this.buscador(3, 3);
    this.buscador(lado - 4, 3);
    this.buscador(3, lado - 4);
    const posiciones = this.posicionesDeAlineacion();
    const n = posiciones.length;
    for (let i = 0; i < n; i += 1) {
      for (let j = 0; j < n; j += 1) {
        // Donde están los buscadores no van alineaciones.
        if ((i === 0 && j === 0) || (i === 0 && j === n - 1) || (i === n - 1 && j === 0)) continue;
        this.alineacion(posiciones[i], posiciones[j]);
      }
    }
    this.formato(0); // provisorio: reserva los módulos; el real va después de elegir la máscara
    this.informacionDeVersion();
  }

  buscador(x, y) {
    for (let dy = -4; dy <= 4; dy += 1) {
      for (let dx = -4; dx <= 4; dx += 1) {
        const distancia = Math.max(Math.abs(dx), Math.abs(dy));
        const xx = x + dx;
        const yy = y + dy;
        if (xx >= 0 && xx < this.lado && yy >= 0 && yy < this.lado) this.fijar(xx, yy, distancia !== 2 && distancia !== 4);
      }
    }
  }

  alineacion(x, y) {
    for (let dy = -2; dy <= 2; dy += 1) {
      for (let dx = -2; dx <= 2; dx += 1) this.fijar(x + dx, y + dy, Math.max(Math.abs(dx), Math.abs(dy)) !== 1);
    }
  }

  posicionesDeAlineacion() {
    if (this.version === 1) return [];
    const cantidad = Math.floor(this.version / 7) + 2;
    const paso = Math.floor((this.version * 8 + cantidad * 3 + 5) / (cantidad * 4 - 4)) * 2;
    const resultado = [6];
    for (let posicion = this.lado - 7; resultado.length < cantidad; posicion -= paso) resultado.splice(1, 0, posicion);
    return resultado;
  }

  formato(mascara) {
    const datos = (BITS_DEL_NIVEL_M << 3) | mascara;
    let r = datos;
    for (let i = 0; i < 10; i += 1) r = (r << 1) ^ ((r >>> 9) * 0x537);
    const bits = ((datos << 10) | r) ^ 0x5412;
    const lado = this.lado;
    for (let i = 0; i <= 5; i += 1) this.fijar(8, i, bit(bits, i));
    this.fijar(8, 7, bit(bits, 6));
    this.fijar(8, 8, bit(bits, 7));
    this.fijar(7, 8, bit(bits, 8));
    for (let i = 9; i < 15; i += 1) this.fijar(14 - i, 8, bit(bits, i));
    for (let i = 0; i < 8; i += 1) this.fijar(lado - 1 - i, 8, bit(bits, i));
    for (let i = 8; i < 15; i += 1) this.fijar(8, lado - 15 + i, bit(bits, i));
    this.fijar(8, lado - 8, true); // el módulo oscuro de siempre
  }

  informacionDeVersion() {
    if (this.version < 7) return;
    let r = this.version;
    for (let i = 0; i < 12; i += 1) r = (r << 1) ^ ((r >>> 11) * 0x1f25);
    const bits = (this.version << 12) | r;
    for (let i = 0; i < 18; i += 1) {
      const oscuro = bit(bits, i);
      const a = this.lado - 11 + (i % 3);
      const b = Math.floor(i / 3);
      this.fijar(a, b, oscuro);
      this.fijar(b, a, oscuro);
    }
  }

  // En zigzag, de a dos columnas, de derecha a izquierda, saltando la columna 6 (la de sincronía).
  escribir(bytes) {
    const lado = this.lado;
    let i = 0;
    for (let derecha = lado - 1; derecha >= 1; derecha -= 2) {
      if (derecha === 6) derecha = 5;
      for (let vertical = 0; vertical < lado; vertical += 1) {
        for (let j = 0; j < 2; j += 1) {
          const x = derecha - j;
          const haciaArriba = ((derecha + 1) & 2) === 0;
          const y = haciaArriba ? lado - 1 - vertical : vertical;
          if (!this.fijos[y][x] && i < bytes.length * 8) {
            this.modulos[y][x] = bit(bytes[i >>> 3], 7 - (i & 7));
            i += 1;
          }
        }
      }
    }
  }

  // Invierte los módulos de datos según la máscara (0 a 7). Aplicarla dos veces la quita.
  enmascarar(mascara) {
    const condicion = [
      (x, y) => (x + y) % 2 === 0,
      (x, y) => y % 2 === 0,
      (x) => x % 3 === 0,
      (x, y) => (x + y) % 3 === 0,
      (x, y) => (Math.floor(x / 3) + Math.floor(y / 2)) % 2 === 0,
      (x, y) => ((x * y) % 2) + ((x * y) % 3) === 0,
      (x, y) => (((x * y) % 2) + ((x * y) % 3)) % 2 === 0,
      (x, y) => (((x + y) % 2) + ((x * y) % 3)) % 2 === 0,
    ][mascara];
    for (let y = 0; y < this.lado; y += 1) {
      for (let x = 0; x < this.lado; x += 1) {
        if (!this.fijos[y][x] && condicion(x, y)) this.modulos[y][x] = !this.modulos[y][x];
      }
    }
  }

  // La penalización de la norma: tiras de 5 o más iguales, cuadros de 2 × 2, figuras parecidas a un
  // buscador y desequilibrio entre claros y oscuros.
  penalizacion() {
    const lado = this.lado;
    const m = this.modulos;
    let puntos = 0;
    const fila = (y) => m[y];
    const columna = (x) => m.map((renglon) => renglon[x]);
    const parecidoAlBuscador = [true, false, true, true, true, false, true];
    for (let k = 0; k < lado; k += 1) {
      for (const linea of [fila(k), columna(k)]) {
        let largo = 1;
        for (let i = 1; i <= lado; i += 1) {
          if (i < lado && linea[i] === linea[i - 1]) {
            largo += 1;
          } else {
            if (largo >= 5) puntos += 3 + (largo - 5);
            largo = 1;
          }
        }
        // 1:1:3:1:1 con 4 claros a un lado (o fuera del borde, que es margen claro).
        const claro = (i) => i < 0 || i >= lado || !linea[i];
        for (let i = 0; i + 7 <= lado; i += 1) {
          if (!parecidoAlBuscador.every((oscuro, j) => linea[i + j] === oscuro)) continue;
          const antes = [1, 2, 3, 4].every((d) => claro(i - d));
          const despues = [0, 1, 2, 3].every((d) => claro(i + 7 + d));
          if (antes) puntos += 40;
          if (despues) puntos += 40;
        }
      }
    }
    for (let y = 0; y < lado - 1; y += 1) {
      for (let x = 0; x < lado - 1; x += 1) {
        const c = m[y][x];
        if (c === m[y][x + 1] && c === m[y + 1][x] && c === m[y + 1][x + 1]) puntos += 3;
      }
    }
    const oscuros = m.reduce((suma, renglon) => suma + renglon.filter(Boolean).length, 0);
    const total = lado * lado;
    puntos += (Math.ceil(Math.abs(oscuros * 20 - total * 10) / total) - 1) * 10;
    return puntos;
  }
}

// Los bytes del texto en modo byte, con el relleno de la norma, para la versión más chica que alcance.
function codificar(texto) {
  const bytes = Array.from(new TextEncoder().encode(texto));
  for (let version = 1; version <= 40; version += 1) {
    const bitsDelLargo = version <= 9 ? 8 : 16;
    const capacidad = bytesDeDatos(version) * 8;
    const usados = 4 + bitsDelLargo + bytes.length * 8;
    if (usados > capacidad) continue;
    const bits = [];
    const poner = (valor, largo) => {
      for (let i = largo - 1; i >= 0; i -= 1) bits.push((valor >>> i) & 1);
    };
    poner(0b0100, 4); // modo byte
    poner(bytes.length, bitsDelLargo);
    for (const b of bytes) poner(b, 8);
    poner(0, Math.min(4, capacidad - bits.length)); // terminador
    poner(0, (8 - (bits.length % 8)) % 8);
    for (let relleno = 0xec; bits.length < capacidad; relleno ^= 0xec ^ 0x11) poner(relleno, 8);
    const datos = [];
    for (let i = 0; i < bits.length; i += 8) datos.push(bits.slice(i, i + 8).reduce((byte, b) => (byte << 1) | b, 0));
    return { version, datos };
  }
  throw new RangeError("El texto no cabe en un código QR.");
}

// La matriz del QR: un arreglo de filas con verdadero en cada módulo oscuro.
export function generarQr(texto) {
  const { version, datos } = codificar(texto);
  const matriz = new Matriz(version);
  matriz.dibujarPatrones();
  matriz.escribir(conCorreccion(datos, version));
  let mejor = 0;
  let menor = Infinity;
  for (let mascara = 0; mascara < 8; mascara += 1) {
    matriz.enmascarar(mascara);
    matriz.formato(mascara);
    const puntos = matriz.penalizacion();
    if (puntos < menor) {
      menor = puntos;
      mejor = mascara;
    }
    matriz.enmascarar(mascara); // se quita para probar la siguiente
  }
  matriz.enmascarar(mejor);
  matriz.formato(mejor);
  return matriz.modulos;
}

// El QR como <svg>: un camino con los módulos oscuros sobre un fondo blanco, con 4 módulos de margen.
export function qrComoSvg(texto, { titulo = "" } = {}) {
  const modulos = generarQr(texto);
  const margen = 4;
  const lado = modulos.length + margen * 2;
  const trazos = [];
  modulos.forEach((renglon, y) => {
    renglon.forEach((oscuro, x) => {
      if (oscuro) trazos.push(`M${x + margen} ${y + margen}h1v1h-1z`);
    });
  });
  const svg = crearSvg("svg", {
    viewBox: `0 0 ${lado} ${lado}`, "shape-rendering": "crispEdges", role: "img", ...(titulo ? { "aria-label": titulo } : {}),
  });
  svg.append(
    crearSvg("rect", { width: lado, height: lado, fill: "#ffffff" }),
    crearSvg("path", { d: trazos.join(""), fill: "#000000" }));
  return svg;
}
