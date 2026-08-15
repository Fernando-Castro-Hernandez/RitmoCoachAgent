/**
 * Une las tres piezas de una sesión de voz: micrófono, WebSocket y reproducción.
 *
 * No decide nada: **traduce**. El circuito de audio produce hechos —llegó
 * audio, el nivel subió, se cerró el socket— y esta clase los convierte en
 * eventos de la máquina de estados. Quién puede pasar de qué a qué vive en
 * `voiceMachine.ts`, que es puro y se prueba sin micrófono.
 *
 * Dos cosas que el circuito resuelve y la máquina no puede:
 *
 * - **La detección de fin de habla.** No hay una señal del navegador que diga
 *   «dejó de hablar»: hay un nivel que baja y se queda bajo. Ese umbral y esa
 *   espera están aquí, con el ruido de fondo del mundo real en mente.
 * - **El silencio del micrófono mientras habla el coach.** Con altavoz se
 *   escucharía a sí mismo y se auto-interrumpiría. Es el punto ciego número 1
 *   de la Fase 1 y se paga en la primera demo si no está.
 */

import { MicCapture } from "./audio/capture";
import { VoicePlayer } from "./audio/player";
import type { VoiceEvent } from "./state/voiceMachine";

/** Por encima de esto se considera que hay voz, no ruido de calle. */
const UMBRAL_VOZ = 0.045;

/** Cuánto silencio cierra un turno. Menos corta a quien piensa a media frase. */
const SILENCIO_MS = 900;

/** Desde que el coach arranca hasta que se anuncia interrumpible. */
const INTERRUMPIBLE_MS = 700;

export interface SessionHandlers {
  onEvent: (e: VoiceEvent) => void;
  onTranscript: (text: string, role: string) => void;
  onLevel: (peak: number) => void;
  /** Latencia real de respuesta, para la métrica del ADR 0012. */
  onTtfa?: (ms: number) => void;
}

export class VoiceSession {
  private ws: WebSocket | null = null;
  private mic = new MicCapture();
  private player: VoicePlayer;
  private handlers: SessionHandlers;

  private hablando = false;
  private ultimoSonido = 0;
  private vigilante = 0;
  private finDeHabla: number | null = null;
  private temporizadorInterrumpible = 0;
  /** Se resuelve cuando el backend confirma que el modelo está listo. */
  private avisarListo: (() => void) | null = null;
  /** Hay un turno del coach en curso, con o sin audio. */
  private turnoDelCoach = false;

  constructor(handlers: SessionHandlers) {
    this.handlers = handlers;
    this.player = new VoicePlayer(() => {
      // El coach terminó de hablar: se reabre el micrófono.
      window.clearTimeout(this.temporizadorInterrumpible);
      this.mic.setMuted(false);
      this.turnoDelCoach = false;
      this.handlers.onEvent({ type: "COACH_ENDED" });
    });
  }

  /**
   * Sesión sin micrófono, para el modo texto.
   *
   * El backend acepta texto y voz por el mismo WebSocket y en la misma sesión,
   * así que escribir no necesita otra ruta ni otro modelo: necesita no pedir
   * permiso de micrófono. Es lo que hace que la aplicación siga sirviendo
   * cuando alguien lo deniega — o cuando simplemente no quiere hablar en el
   * transporte público.
   */
  async startTextOnly(userId: string): Promise<void> {
    await this.conectar(userId);
  }

  async start(userId: string): Promise<void> {
    await this.conectar(userId);

    await this.mic.start((pcm, peak) => {
      this.handlers.onLevel(peak);
      if (peak > UMBRAL_VOZ) {
        this.ultimoSonido = Date.now();
        if (!this.hablando) {
          this.hablando = true;
          this.handlers.onEvent({ type: "USER_STARTED" });
        }
      }
      this.ws?.send(JSON.stringify({ type: "audio", data: pcm }));
    });

    // El fin de turno se vigila por reloj y no dentro del callback de audio:
    // si el usuario se queda callado dejan de llegar frames con voz, y una
    // comprobación que vive en el callback nunca llegaría a dispararse.
    this.vigilante = window.setInterval(() => {
      if (!this.hablando) return;
      if (Date.now() - this.ultimoSonido < SILENCIO_MS) return;
      this.hablando = false;
      this.finDeHabla = Date.now();
      this.handlers.onEvent({ type: "USER_ENDED" });
    }, 150);
  }

  /** Abre el socket y el contexto de audio. Común a los dos modos. */
  private async conectar(userId: string): Promise<void> {
    // El AudioContext tiene que nacer del gesto del usuario que llamó aquí, o
    // iOS Safari lo deja suspendido y no suena nada. También en modo texto: el
    // coach responde hablando aunque le hayas escrito.
    await this.player.ensureContext();

    const protocolo = location.protocol === "https:" ? "wss" : "ws";
    this.ws = new WebSocket(`${protocolo}://${location.host}/ws/voice/${userId}`);
    this.ws.onmessage = (e) => this.recibir(JSON.parse(e.data));
    this.ws.onerror = () =>
      this.handlers.onEvent({ type: "ERROR", message: "Se perdió la conexión" });
    this.ws.onclose = () => this.handlers.onEvent({ type: "HANG_UP" });

    // Se espera al `ready` del backend y no sólo al `open` del socket. Abrir el
    // WebSocket sólo dice que hay tubería; `ready` dice que el modelo aceptó la
    // sesión. Enviar entre esos dos momentos manda el turno a un modelo que aún
    // no existe, y el usuario ve su mensaje salir sin que nadie conteste.
    const listo = new Promise<void>((resolve) => {
      this.avisarListo = resolve;
    });

    await new Promise<void>((resolve, reject) => {
      if (!this.ws) return reject(new Error("sin socket"));
      this.ws.onopen = () => resolve();
      window.setTimeout(() => reject(new Error("tiempo agotado al conectar")), 10_000);
    });

    await Promise.race([
      listo,
      new Promise<void>((_, reject) =>
        window.setTimeout(() => reject(new Error("el modelo no respondió a tiempo")), 15_000),
      ),
    ]);
  }

  get isOpen(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }

  sendText(text: string): void {
    this.finDeHabla = Date.now();
    this.ws?.send(JSON.stringify({ type: "text", text }));
    // Los dos eventos: el turno del usuario empieza y termina en el mismo acto
    // de pulsar ENVIAR. Sin el primero la máquina se queda en LISTENING y el
    // orbe nunca pasa por PENSANDO, que es la señal de que algo está ocurriendo.
    this.handlers.onEvent({ type: "USER_STARTED" });
    this.handlers.onEvent({ type: "USER_ENDED" });
  }

  async stop(): Promise<void> {
    window.clearInterval(this.vigilante);
    window.clearTimeout(this.temporizadorInterrumpible);
    this.ws?.send(JSON.stringify({ type: "stop" }));
    this.player.stop();
    await this.mic.stop();
    this.ws?.close();
    this.ws = null;
    this.hablando = false;
  }

  private recibir(mensaje: Record<string, string>): void {
    switch (mensaje.type) {
      case "ready":
        this.handlers.onEvent({ type: "STREAM_READY" });
        this.avisarListo?.();
        this.avisarListo = null;
        break;

      case "audio":
        if (!this.player.isPlaying) {
          if (this.finDeHabla) {
            const ttfa = Date.now() - this.finDeHabla;
            console.info(`[ritmo] ttfa_ms=${ttfa}`);
            this.handlers.onTtfa?.(ttfa);
            this.finDeHabla = null;
          }
          // Silenciar el micrófono mientras habla el coach. Sin esto, con
          // altavoz se escucha a sí mismo y se corta solo.
          this.mic.setMuted(true);
          this.hablando = false;
          if (!this.turnoDelCoach) {
            this.turnoDelCoach = true;
            this.handlers.onEvent({ type: "COACH_STARTED" });
          }

          // Se anuncia interrumpible un momento después: decirlo desde el
          // primer milisegundo invita a cortar antes de haber oído nada.
          this.temporizadorInterrumpible = window.setTimeout(() => {
            this.mic.setMuted(false);
            this.handlers.onEvent({ type: "COACH_INTERRUPTIBLE" });
          }, INTERRUMPIBLE_MS);
        }
        void this.player.enqueue(mensaje.data);
        break;

      case "transcript":
        this.handlers.onTranscript(mensaje.text, mensaje.role);
        // El coach puede contestar SÓLO con texto, sin un chunk de audio. Pasa
        // en los turnos escritos. Si el estado sólo avanzara con audio, la
        // máquina se quedaría en PENSANDO para siempre y el orbe mentiría.
        if (mensaje.role === "ASSISTANT" && !this.player.isPlaying && !this.turnoDelCoach) {
          this.turnoDelCoach = true;
          if (this.finDeHabla) {
            const ttfa = Date.now() - this.finDeHabla;
            console.info(`[ritmo] ttfa_ms=${ttfa}`);
            this.handlers.onTtfa?.(ttfa);
            this.finDeHabla = null;
          }
          this.handlers.onEvent({ type: "COACH_STARTED" });
        }
        break;

      case "tool_call":
        this.handlers.onEvent({ type: "TOOL_STARTED" });
        break;

      case "turn_end":
        // Cierra el turno cuando no hubo audio que reproducir; si lo hubo, el
        // que manda es el reproductor al vaciarse.
        if (this.turnoDelCoach && !this.player.isPlaying) {
          this.turnoDelCoach = false;
          this.handlers.onEvent({ type: "COACH_ENDED" });
        }
        break;

      case "error":
        this.handlers.onEvent({ type: "ERROR", message: mensaje.message });
        break;
    }
  }
}
