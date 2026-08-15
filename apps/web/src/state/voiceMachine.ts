/**
 * La máquina de estados del orbe de voz.
 *
 * Doce estados, lógica pura y sin React: se puede probar sin montar nada y sin
 * un micrófono. Dos de ellos son los que hacen el producto:
 *
 * RENOVANDO no existe para el usuario. La sesión con el modelo se corta a los
 * ocho minutos y se releva por debajo (ADR 0002). Si alguien ve «reconectando…»
 * cada ocho minutos, el producto se siente frágil aunque funcione, así que la
 * renovación viaja como una bandera interna y el estado visible no se mueve.
 *
 * ALTO_SEGURIDAD no se sale con un toque. Es la regla 1 del producto: en rojo
 * la pantalla no prescribe, y salir de ahí tiene que costar un gesto
 * deliberado. Un `MIC_CLICK` no lo saca; sólo un reconocimiento explícito.
 */

export const VOICE_STATES = [
  "IDLE",
  "REQUESTING_MIC",
  "CONNECTING",
  "LISTENING",
  "USER_SPEAKING",
  "THINKING",
  "TOOL_RUNNING",
  "SPEAKING",
  "INTERRUPTIBLE",
  "ERROR",
  "SAFETY_STOP",
] as const;

export type VoiceState = (typeof VOICE_STATES)[number];

export type VoiceEvent =
  | { type: "MIC_CLICK" }
  | { type: "MIC_GRANTED" }
  | { type: "MIC_DENIED" }
  | { type: "STREAM_READY" }
  | { type: "USER_STARTED" }
  | { type: "USER_ENDED" }
  | { type: "TOOL_STARTED" }
  | { type: "COACH_STARTED" }
  | { type: "COACH_INTERRUPTIBLE" }
  | { type: "COACH_ENDED" }
  | { type: "RENEWAL_START" }
  | { type: "RENEWAL_DONE" }
  | { type: "SAFETY_RED" }
  | { type: "SAFETY_ACK" }
  | { type: "ERROR"; message: string }
  | { type: "HANG_UP" };

export interface VoiceContext {
  /** Invisible por diseño: la renovación de los 8 minutos no se anuncia. */
  renewing: boolean;
  micDenied: boolean;
  error: string;
}

export interface VoiceMachine {
  state: VoiceState;
  context: VoiceContext;
}

export const initialMachine: VoiceMachine = {
  state: "IDLE",
  context: { renewing: false, micDenied: false, error: "" },
};

/** Estados en los que el micrófono está abierto de verdad. */
const MIC_ABIERTO = new Set<VoiceState>([
  "LISTENING",
  "USER_SPEAKING",
  "INTERRUPTIBLE",
]);

/** Estados en los que hay una sesión de voz viva. */
const EN_SESION = new Set<VoiceState>([
  "LISTENING",
  "USER_SPEAKING",
  "THINKING",
  "TOOL_RUNNING",
  "SPEAKING",
  "INTERRUPTIBLE",
]);

export function micIsOpen(state: VoiceState): boolean {
  return MIC_ABIERTO.has(state);
}

export function inSession(state: VoiceState): boolean {
  return EN_SESION.has(state);
}

export function transition(actual: VoiceMachine, evento: VoiceEvent): VoiceMachine {
  const { state, context } = actual;

  // El alto por seguridad gana sobre cualquier otra cosa, venga de donde venga.
  if (evento.type === "SAFETY_RED") {
    return { state: "SAFETY_STOP", context: { ...context, renewing: false } };
  }

  // Y no se sale de él con nada que no sea el reconocimiento explícito.
  if (state === "SAFETY_STOP") {
    if (evento.type === "SAFETY_ACK") return { ...initialMachine, context };
    if (evento.type === "HANG_UP") return { ...initialMachine, context };
    return actual;
  }

  // La renovación no toca el estado visible. Sólo la bandera interna.
  if (evento.type === "RENEWAL_START") {
    return { state, context: { ...context, renewing: true } };
  }
  if (evento.type === "RENEWAL_DONE") {
    return { state, context: { ...context, renewing: false } };
  }

  if (evento.type === "ERROR") {
    return { state: "ERROR", context: { ...context, error: evento.message, renewing: false } };
  }

  if (evento.type === "HANG_UP") {
    return { state: "IDLE", context: { ...context, renewing: false, error: "" } };
  }

  switch (state) {
    case "IDLE":
    case "ERROR":
      if (evento.type === "MIC_CLICK") {
        // Sin micrófono no se vuelve a pedir: se degrada a texto y se sigue.
        return context.micDenied
          ? actual
          : { state: "REQUESTING_MIC", context: { ...context, error: "" } };
      }
      return actual;

    case "REQUESTING_MIC":
      if (evento.type === "MIC_GRANTED") return { state: "CONNECTING", context };
      if (evento.type === "MIC_DENIED") {
        return { state: "IDLE", context: { ...context, micDenied: true } };
      }
      return actual;

    case "CONNECTING":
      if (evento.type === "STREAM_READY") return { state: "LISTENING", context };
      return actual;

    case "LISTENING":
      if (evento.type === "USER_STARTED") return { state: "USER_SPEAKING", context };
      if (evento.type === "TOOL_STARTED") return { state: "TOOL_RUNNING", context };
      if (evento.type === "COACH_STARTED") return { state: "SPEAKING", context };
      return actual;

    case "USER_SPEAKING":
      if (evento.type === "USER_ENDED") return { state: "THINKING", context };
      return actual;

    case "THINKING":
      if (evento.type === "TOOL_STARTED") return { state: "TOOL_RUNNING", context };
      if (evento.type === "COACH_STARTED") return { state: "SPEAKING", context };
      return actual;

    case "TOOL_RUNNING":
      if (evento.type === "COACH_STARTED") return { state: "SPEAKING", context };
      return actual;

    case "SPEAKING":
      // El micrófono está silenciado mientras el coach habla, o se interrumpe
      // solo por el altavoz. INTERRUPTIBLE es lo que avisa de que aun así se
      // le puede cortar.
      if (evento.type === "COACH_INTERRUPTIBLE") return { state: "INTERRUPTIBLE", context };
      if (evento.type === "COACH_ENDED") return { state: "LISTENING", context };
      return actual;

    case "INTERRUPTIBLE":
      if (evento.type === "COACH_ENDED") return { state: "LISTENING", context };
      if (evento.type === "USER_STARTED") return { state: "USER_SPEAKING", context };
      return actual;

    default:
      return actual;
  }
}

/** Aplica una secuencia. Útil en pruebas y para reproducir una sesión. */
export function run(eventos: VoiceEvent[], desde: VoiceMachine = initialMachine): VoiceMachine {
  return eventos.reduce(transition, desde);
}
