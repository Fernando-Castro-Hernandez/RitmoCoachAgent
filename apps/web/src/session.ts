/**
 * Une las tres piezas de una sesión de voz: micrófono, WebSocket y reproducción.
 *
 * La máquina de estados completa de 12 estados llega en la tarea D1. Aquí sólo
 * está lo necesario para probar el circuito de extremo a extremo.
 */

import { MicCapture } from "./audio/capture";
import { VoicePlayer } from "./audio/player";

export type SessionState = "idle" | "connecting" | "listening" | "speaking" | "error";

export interface SessionHandlers {
  onState: (state: SessionState) => void;
  onTranscript: (text: string, role: string) => void;
  onLevel: (peak: number) => void;
  onError: (message: string) => void;
}

export class VoiceSession {
  private ws: WebSocket | null = null;
  private mic = new MicCapture();
  private player: VoicePlayer;
  private handlers: SessionHandlers;
  private speechEndedAt: number | null = null;

  constructor(handlers: SessionHandlers) {
    this.handlers = handlers;
    this.player = new VoicePlayer(() => {
      // Terminó de hablar el coach: se reabre el micrófono.
      this.mic.setMuted(false);
      this.handlers.onState("listening");
    });
  }

  async start(userId: string): Promise<void> {
    this.handlers.onState("connecting");

    // El AudioContext debe nacer del gesto del usuario que llamó a start().
    await this.player.ensureContext();

    const protocol = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${protocol}://${location.host}/ws/voice/${userId}`);

    this.ws.onmessage = (event) => this.handleMessage(JSON.parse(event.data));
    this.ws.onerror = () => this.handlers.onError("Se perdió la conexión");
    this.ws.onclose = () => this.handlers.onState("idle");

    await new Promise<void>((resolve, reject) => {
      if (!this.ws) return reject(new Error("sin socket"));
      this.ws.onopen = () => resolve();
      setTimeout(() => reject(new Error("tiempo agotado al conectar")), 10000);
    });

    await this.mic.start((pcm, peak) => {
      this.handlers.onLevel(peak);
      if (peak > 0.02) this.speechEndedAt = Date.now();
      this.ws?.send(JSON.stringify({ type: "audio", data: pcm }));
    });
  }

  sendText(text: string): void {
    this.ws?.send(JSON.stringify({ type: "text", text }));
  }

  async stop(): Promise<void> {
    this.ws?.send(JSON.stringify({ type: "stop" }));
    this.player.stop();
    await this.mic.stop();
    this.ws?.close();
    this.ws = null;
    this.handlers.onState("idle");
  }

  private handleMessage(message: Record<string, string>): void {
    switch (message.type) {
      case "ready":
        this.handlers.onState("listening");
        break;
      case "audio":
        if (!this.player.isPlaying) {
          // Primer chunk del turno: aquí se mide el ttfa_ms real (ADR 0012).
          if (this.speechEndedAt) {
            console.info(`[ritmo] ttfa_ms=${Date.now() - this.speechEndedAt}`);
            this.speechEndedAt = null;
          }
          // Silencia el micrófono mientras habla el coach: con altavoz se
          // escucharía a sí mismo y se auto-interrumpiría.
          this.mic.setMuted(true);
          this.handlers.onState("speaking");
        }
        void this.player.enqueue(message.data);
        break;
      case "transcript":
        this.handlers.onTranscript(message.text, message.role);
        break;
      case "turn_end":
        break;
      case "error":
        this.handlers.onError(message.message);
        this.handlers.onState("error");
        break;
    }
  }
}
