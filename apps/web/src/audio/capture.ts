/**
 * Micrófono → frames PCM16 en base64, listos para el WebSocket.
 *
 * La cancelación de eco va activada desde el primer día: con altavoz, el
 * micrófono capta la voz del coach y el modelo se auto-interrumpe. Es el punto
 * ciego número 1 de la Fase 1 y rompe demos.
 */

export type FrameHandler = (pcm16Base64: string, peak: number) => void;

export class MicCapture {
  private context: AudioContext | null = null;
  private stream: MediaStream | null = null;
  private node: AudioWorkletNode | null = null;
  private muted = false;

  async start(onFrame: FrameHandler): Promise<void> {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1,
      },
    });

    // Safari e iOS exigen que el AudioContext nazca de un gesto del usuario.
    this.context = new AudioContext();
    if (this.context.state === "suspended") await this.context.resume();

    await this.context.audioWorklet.addModule("/capture-worklet.js");

    const source = this.context.createMediaStreamSource(this.stream);
    this.node = new AudioWorkletNode(this.context, "capture-processor");

    this.node.port.onmessage = (event) => {
      if (this.muted) return;
      const { pcm, peak } = event.data as { pcm: ArrayBuffer; peak: number };
      onFrame(toBase64(pcm), peak);
    };

    source.connect(this.node);
    // El worklet no produce salida audible; conectarlo al destino mantiene vivo
    // el grafo en algunos navegadores.
    this.node.connect(this.context.destination);
  }

  /** Silencia el envío mientras habla el coach, para no auto-interrumpirlo. */
  setMuted(muted: boolean): void {
    this.muted = muted;
  }

  async stop(): Promise<void> {
    this.node?.disconnect();
    this.stream?.getTracks().forEach((t) => t.stop());
    await this.context?.close();
    this.context = null;
    this.stream = null;
    this.node = null;
  }
}

function toBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = "";
  for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i]);
  return btoa(binary);
}
