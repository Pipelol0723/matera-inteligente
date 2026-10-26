// Consulta periódica: mientras una pantalla y la pestaña están a la vista, le vuelve a pedir sus datos
// a la API cada CONSULTA_MS. Así la pantalla se actualiza sola aunque la conexión en vivo (tiempo-real.js)
// esté caída; el WebSocket solo hace que la medición se vea al instante, sin esperar la próxima consulta.
export const CONSULTA_MS = 10000;

const HORA = new Intl.DateTimeFormat("es-CO", { hour: "2-digit", minute: "2-digit", second: "2-digit" });

// consultar() devuelve una promesa; si la anterior no terminó, esa vuelta se salta.
// Al volver a la pestaña se consulta enseguida, sin esperar la vuelta siguiente.
export function consultarCadaRato(estaALaVista, consultar, ms = CONSULTA_MS) {
  let enCurso = false;
  const vuelta = async () => {
    if (enCurso || document.hidden || !estaALaVista()) return;
    enCurso = true;
    try {
      await consultar();
    } finally {
      enCurso = false;
    }
  };
  setInterval(vuelta, ms);
  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) vuelta();
  });
}

// El texto que dice cuándo se consultó la API por última vez.
export function textoConsulta(momento = new Date()) {
  return `Se consulta la API cada ${CONSULTA_MS / 1000} s · última consulta ${HORA.format(momento)}`;
}
