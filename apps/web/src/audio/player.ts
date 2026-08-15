/**
 * Reproducción de la voz del coach: PCM16 a 24 kHz que llega en chunks.
 *
 * Los chunks se encadenan calculando el instante de arranque de cada uno en vez
 * de reproducirlos al llegar. Sin eso quedan huecos audibles entre chunk y
 * chunk y la voz suena entrecortada, que es la diferencia entre «suena a robot»
 * y «suena a persona».
 */

const OUTPUT_HZ = 24000;

export class VoicePlayer {
  private context: AudioContext | null = null;
  private nextStartTime = 0;
  private activos = new Set<AudioBufferSourceNode>();
  private onIdle?: () => void;

  constructor(onIdle?: () => void) {
    this.onIdle = onIdle;
  }

  async ensureContext(): Promise<AudioContext> {
    if (!this.context) this.context = new AudioContext({ sampleRate: OUTPUT_HZ });
    if (this.context.state === "suspended") await this.context.resume();
    return this.context;
  }

  async enqueue(pcm16Base64: string): Promise<void> {
    const context = await this.ensureContext();
    const samples = decode(pcm16Base64);
    if (samples.length === 0) return;

    const buffer = context.createBuffer(1, samples.length, OUTPUT_HZ);
    buffer.copyToChannel(samples, 0);

    const source = context.createBufferSource();
    source.buffer = buffer;
    source.connect(context.destination);

    // Si la cola se vació, arranca ya; si no, justo cuando termine lo anterior.
    const now = context.currentTime;
    const start = Math.max(now, this.nextStartTime);
    source.start(start);
    this.nextStartTime = start + buffer.duration;

    this.activos.add(source);
    source.onended = () => {
      this.activos.delete(source);
      if (this.activos.size === 0) this.onIdle?.();
    };
  }

  /** Corta la reproducción de golpe: es lo que hace posible el barge-in. */
  stop(): void {
    this.activos.forEach((source) => {
      try {
        source.stop();
      } catch {
        /* ya había terminado */
      }
    });
    this.activos.clear();
    this.nextStartTime = 0;
  }

  get isPlaying(): boolean {
    return this.activos.size > 0;
  }
}

// El parámetro de tipo es necesario: `Float32Array` a secas equivale a
// `Float32Array<ArrayBufferLike>`, que copyToChannel no acepta.
function decode(base64: string): Float32Array<ArrayBuffer> {
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);

  const view = new DataView(bytes.buffer);
  const samples = new Float32Array(bytes.length / 2);
  for (let i = 0; i < samples.length; i++) {
    samples[i] = view.getInt16(i * 2, true) / 0x8000;
  }
  return samples;
}
