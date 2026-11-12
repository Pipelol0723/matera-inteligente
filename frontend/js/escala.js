// Geometría de las escalas. Solo ubica en pantalla números que ya existen.

// Se muestra el rango óptimo con un margen del 80 % de su ancho a cada lado.
const MARGEN = 0.8;

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
