/**
 * De un clip de vídeo a diez fotogramas, en el navegador.
 *
 * **El vídeo no sale del teléfono.** Se abre con un `<video>` local, se salta a
 * diez instantes repartidos y se dibuja cada uno en un canvas. Al servidor
 * llegan diez JPEG —unos cientos de kilobytes— en vez de quince segundos de
 * vídeo, que en una red móvil son megas y una espera larga mirando una barra.
 *
 * Hay una razón menos obvia y más importante: un clip de alguien corriendo
 * contiene su cara, su calle y su casa. Diez cuadros recortados a lo que hace
 * falta para mirar la zancada es bastante menos, y lo que no se sube no se puede
 * filtrar.
 *
 * El límite de segundos se valida aquí y no sólo en el servidor porque la
 * respuesta útil llega antes de subir nada: decirle a alguien que su vídeo es
 * muy largo después de esperar la subida es hacerle esperar para nada.
 */

/** Cuántos cuadros se extraen. Tiene que coincidir con `MAX_FRAMES` del
 *  servidor, y una prueba de Python lee este archivo para comprobarlo. */
export const NUM_FOTOGRAMAS = 10;

/** Con menos de esto no hay secuencia que mirar, y se prefiere decirlo a
 *  gastar una llamada al modelo por dos fotos sueltas. */
export const MIN_FOTOGRAMAS = 3;

/** Duración máxima aceptada. Diez cuadros de un clip más largo se separan
 *  tanto entre sí que dejan de ser una secuencia de zancadas. */
export const MAX_SEGUNDOS = 15;

/** Lado mayor de cada fotograma. Suficiente para ver la postura, y una décima
 *  parte de los bytes de un cuadro a resolución de teléfono. */
export const LADO_MAXIMO = 640;

const CALIDAD_JPEG = 0.82;

/**
 * Por qué no se pudo usar el vídeo.
 *
 * Va como campo y no como texto del mensaje porque quien lo muestra necesita
 * elegir la frase traducida: comparar contra el texto del error ata la interfaz
 * a una cadena en español que nadie recuerda que es un contrato.
 */
export type MotivoInvalido = "muy-largo" | "ilegible";

export class VideoInvalidoError extends Error {
  constructor(readonly motivo: MotivoInvalido) {
    super(motivo);
  }
}

/** El tamaño de salida, manteniendo la proporción del vídeo. */
export function escalar(
  ancho: number,
  alto: number,
  lado = LADO_MAXIMO,
): { ancho: number; alto: number } {
  const mayor = Math.max(ancho, alto);
  if (mayor <= lado || mayor === 0) return { ancho, alto };
  const factor = lado / mayor;
  return { ancho: Math.round(ancho * factor), alto: Math.round(alto * factor) };
}

/**
 * Los instantes que se capturan, en segundos.
 *
 * No empieza en 0 ni termina en la duración exacta: el primer cuadro suele
 * pillar el teléfono todavía moviéndose y el último puede no existir —pedir el
 * segundo final de un vídeo deja el `seeked` sin disparar en Safari. Se toman
 * los diez repartidos DENTRO del clip.
 */
export function instantes(duracion: number, n = NUM_FOTOGRAMAS): number[] {
  const paso = duracion / (n + 1);
  return Array.from({ length: n }, (_, i) => Number((paso * (i + 1)).toFixed(3)));
}

/**
 * Cuánto se espera un evento del vídeo antes de darlo por perdido.
 *
 * **El tiempo límite no es defensa por si acaso: sin él la pantalla se cuelga.**
 * Un `seek` a un archivo cuyo contenedor no trae índice —los que graba
 * MediaRecorder, y algunos que llegan por mensajería— no dispara `seeked`
 * NUNCA. No hay error, no hay evento, no hay nada: la promesa se queda abierta
 * y el corredor mira «sacando fotogramas… 0 de 10» hasta que cierra la pestaña.
 * Lo vi pasar con un clip de prueba antes de que esto existiera.
 */
const ESPERA_MS = 4000;

class EsperaAgotadaError extends Error {}

function esperar(video: HTMLVideoElement, evento: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const reloj = setTimeout(() => {
      limpiar();
      reject(new EsperaAgotadaError(evento));
    }, ESPERA_MS);
    const ok = () => {
      limpiar();
      resolve();
    };
    const mal = () => {
      limpiar();
      reject(new VideoInvalidoError("ilegible"));
    };
    const limpiar = () => {
      clearTimeout(reloj);
      video.removeEventListener(evento, ok);
      video.removeEventListener("error", mal);
    };
    video.addEventListener(evento, ok, { once: true });
    video.addEventListener("error", mal, { once: true });
  });
}

/**
 * La duración, incluso cuando el contenedor no la trae.
 *
 * Algunos vídeos —los grabados por otra aplicación con MediaRecorder, y los que
 * llegan de ciertas mensajerías— no llevan la duración escrita en la cabecera, y
 * Chrome contesta `Infinity`. Sin esto, un vídeo perfectamente legible se
 * rechazaba con «eso no parece un vídeo», que además es mentira.
 *
 * El truco es el estándar: se pide un instante imposiblemente lejano, el
 * navegador tiene que recorrer el archivo para llegar y al hacerlo aprende
 * cuánto dura.
 */
async function duracionReal(video: HTMLVideoElement): Promise<number> {
  if (Number.isFinite(video.duration)) return video.duration;

  video.currentTime = 1e6;
  try {
    await esperar(video, "durationchange");
  } catch {
    return Number.NaN;
  }
  const d = video.duration;
  video.currentTime = 0;
  return d;
}

/**
 * Extrae los fotogramas de un archivo de vídeo.
 *
 * @param archivo el clip elegido por el corredor.
 * @param onProgreso se llama con cuántos cuadros van, para la barra.
 * @throws VideoInvalidoError si no es un vídeo legible o dura de más.
 */
export async function extraerFotogramas(
  archivo: File,
  onProgreso?: (hechos: number, total: number) => void,
): Promise<Blob[]> {
  const url = URL.createObjectURL(archivo);
  const video = document.createElement("video");
  video.preload = "auto";
  video.muted = true;
  // Sin esto, iOS abre el reproductor a pantalla completa en cuanto se le pide
  // que cargue, y el usuario ve su vídeo en vez de la pantalla de análisis.
  video.playsInline = true;
  video.src = url;

  try {
    await esperar(video, "loadedmetadata");

    const duracion = await duracionReal(video);
    if (!Number.isFinite(duracion) || duracion <= 0) {
      throw new VideoInvalidoError("ilegible");
    }
    if (duracion > MAX_SEGUNDOS + 0.5) {
      throw new VideoInvalidoError("muy-largo");
    }

    const { ancho, alto } = escalar(video.videoWidth, video.videoHeight);
    const canvas = document.createElement("canvas");
    canvas.width = ancho;
    canvas.height = alto;
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new VideoInvalidoError("ilegible");

    const cuadros: Blob[] = [];
    for (const t of instantes(duracion)) {
      try {
        video.currentTime = t;
        await esperar(video, "seeked");
      } catch (e) {
        // Un cuadro que no llega no cancela los que sí: con seis de diez se
        // puede mirar una zancada, y es mejor que no ofrecer nada. Se corta al
        // primer fallo porque si un salto no funciona los siguientes tampoco.
        if (e instanceof EsperaAgotadaError) break;
        throw e;
      }
      ctx.drawImage(video, 0, 0, ancho, alto);
      const blob = await new Promise<Blob | null>((r) =>
        canvas.toBlob(r, "image/jpeg", CALIDAD_JPEG),
      );
      if (blob) cuadros.push(blob);
      onProgreso?.(cuadros.length, NUM_FOTOGRAMAS);
    }

    // Menos de tres cuadros no es una secuencia: no se ve una zancada completa,
    // y preguntarle al modelo por dos fotos sueltas gasta una llamada para
    // devolver una impresión que no vale.
    if (cuadros.length < MIN_FOTOGRAMAS) {
      throw new VideoInvalidoError("ilegible");
    }
    return cuadros;
  } finally {
    // Siempre, también cuando falla: un object URL vivo mantiene el vídeo
    // entero en memoria, y son decenas de megas.
    video.src = "";
    URL.revokeObjectURL(url);
  }
}
