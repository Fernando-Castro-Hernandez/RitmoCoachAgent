/**
 * Captura del micrófono: remuestrea 48 kHz Float32 → 16 kHz PCM16.
 *
 * Corre en el hilo de audio, no en el principal. Se usa AudioWorkletNode y no
 * ScriptProcessorNode: el segundo está deprecado y procesa en el hilo de UI, lo
 * que produce cortes audibles en cuanto React renderiza algo.
 *
 * Nova Sonic exige exactamente 16 kHz, mono, PCM de 16 bits (ADR 0002).
 */

const TARGET_HZ = 16000;
// Frames de 20 ms a 16 kHz: suficientemente chico para no añadir latencia,
// suficientemente grande para no saturar el WebSocket con mensajes.
const FRAME_SAMPLES = 320;

class CaptureProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.ratio = sampleRate / TARGET_HZ;
    this.buffer = [];
    this.position = 0;
  }

  process(inputs) {
    const input = inputs[0];
    if (!input || !input[0]) return true;

    const channel = input[0];

    // Remuestreo por promediado: recorre la entrada a paso `ratio` y promedia
    // las muestras que caen en cada salto. El promedio actúa como filtro
    // paso-bajo simple y evita el aliasing de la decimación cruda.
    while (this.position < channel.length) {
      const start = Math.floor(this.position);
      const end = Math.min(Math.floor(this.position + this.ratio), channel.length);
      let sum = 0;
      let count = 0;
      for (let i = start; i < end; i++) {
        sum += channel[i];
        count++;
      }
      if (count > 0) this.buffer.push(sum / count);
      this.position += this.ratio;
    }
    this.position -= channel.length;

    while (this.buffer.length >= FRAME_SAMPLES) {
      const frame = this.buffer.splice(0, FRAME_SAMPLES);
      const pcm = new Int16Array(FRAME_SAMPLES);
      let peak = 0;
      for (let i = 0; i < FRAME_SAMPLES; i++) {
        const s = Math.max(-1, Math.min(1, frame[i]));
        pcm[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
        peak = Math.max(peak, Math.abs(s));
      }
      // `peak` alimenta la amplitud reactiva del orbe de voz (tarea D1).
      this.port.postMessage({ pcm: pcm.buffer, peak }, [pcm.buffer]);
    }

    return true;
  }
}

registerProcessor("capture-processor", CaptureProcessor);
