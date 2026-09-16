// Geometría de las escalas y de los anillos. Solo ubica en pantalla números que ya existen.

// Se muestra el rango óptimo con un margen del 80 % de su ancho a cada lado.
const MARGEN = 0.8;
const CENTRO = 170;

export const limitar = (valor, minimo, maximo) => Math.max(minimo, Math.min(maximo, valor));

// Tramo visible de la escala, recortado a los límites físicos que entrega GET /parametros.
export function dominioVisual(rango, parametro) {
  const ancho = rango.max - rango.min;
  return [
    Math.max(parametro.minimoFisico, rango.min - ancho * MARGEN),
    Math.min(parametro.maximoFisico, rango.max + ancho * MARGEN),
  ];
}

export const fraccion = (valor, [desde, hasta]) => limitar((valor - desde) / (hasta - desde), 0, 1);

export const porcentaje = (parte) => `${(parte * 100).toFixed(1)}%`;

// Los anillos cubren 270°, de -135° a 135°.
export const angulo = (parte) => -135 + parte * 270;

export function punto(radio, grados) {
  const radianes = ((grados - 90) * Math.PI) / 180;
  return [CENTRO + radio * Math.cos(radianes), CENTRO + radio * Math.sin(radianes)];
}

export function arco(radio, desde, hasta) {
  const [x0, y0] = punto(radio, desde);
  const [x1, y1] = punto(radio, hasta);
  const grande = Math.abs(hasta - desde) > 180 ? 1 : 0;
  return `M ${x0.toFixed(1)} ${y0.toFixed(1)} A ${radio} ${radio} 0 ${grande} 1 ${x1.toFixed(1)} ${y1.toFixed(1)}`;
}
