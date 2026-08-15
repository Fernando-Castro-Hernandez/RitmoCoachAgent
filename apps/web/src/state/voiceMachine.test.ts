import { describe, expect, it } from "vitest";

import {
  type VoiceEvent,
  initialMachine,
  inSession,
  micIsOpen,
  run,
  transition,
} from "./voiceMachine";

const abrir: VoiceEvent[] = [
  { type: "MIC_CLICK" },
  { type: "MIC_GRANTED" },
  { type: "STREAM_READY" },
];

describe("el camino normal", () => {
  it("va de reposo a escuchando", () => {
    expect(run(abrir).state).toBe("LISTENING");
  });

  it("recorre un turno completo", () => {
    const m = run([
      ...abrir,
      { type: "USER_STARTED" },
      { type: "USER_ENDED" },
      { type: "TOOL_STARTED" },
      { type: "COACH_STARTED" },
      { type: "COACH_ENDED" },
    ]);
    expect(m.state).toBe("LISTENING");
  });

  it("colgar vuelve a reposo desde donde sea", () => {
    const m = run([...abrir, { type: "COACH_STARTED" }, { type: "HANG_UP" }]);
    expect(m.state).toBe("IDLE");
  });
});

describe("la renovación de los 8 minutos es invisible", () => {
  it("no cambia el estado que ve el usuario", () => {
    const antes = run(abrir);
    const durante = transition(antes, { type: "RENEWAL_START" });

    expect(durante.state).toBe("LISTENING");
    expect(durante.context.renewing).toBe(true);
  });

  it("tampoco interrumpe al coach a media frase", () => {
    const hablando = run([...abrir, { type: "COACH_STARTED" }]);
    const durante = transition(hablando, { type: "RENEWAL_START" });

    expect(durante.state).toBe("SPEAKING");
  });

  it("al terminar sólo baja la bandera", () => {
    const m = run([...abrir, { type: "RENEWAL_START" }, { type: "RENEWAL_DONE" }]);
    expect(m.state).toBe("LISTENING");
    expect(m.context.renewing).toBe(false);
  });
});

describe("el alto por seguridad", () => {
  it("gana desde cualquier estado", () => {
    for (const previo of [initialMachine, run(abrir), run([...abrir, { type: "COACH_STARTED" }])]) {
      expect(transition(previo, { type: "SAFETY_RED" }).state).toBe("SAFETY_STOP");
    }
  });

  it("no se sale con un toque en el orbe", () => {
    const parado = run([...abrir, { type: "SAFETY_RED" }]);
    expect(transition(parado, { type: "MIC_CLICK" }).state).toBe("SAFETY_STOP");
  });

  it("no lo desbloquea que el coach termine de hablar", () => {
    const parado = run([...abrir, { type: "COACH_STARTED" }, { type: "SAFETY_RED" }]);
    expect(transition(parado, { type: "COACH_ENDED" }).state).toBe("SAFETY_STOP");
  });

  it("sólo sale con un reconocimiento explícito", () => {
    const parado = run([...abrir, { type: "SAFETY_RED" }]);
    expect(transition(parado, { type: "SAFETY_ACK" }).state).toBe("IDLE");
  });

  it("cierra la renovación en curso al entrar", () => {
    const m = run([...abrir, { type: "RENEWAL_START" }, { type: "SAFETY_RED" }]);
    expect(m.context.renewing).toBe(false);
  });
});

describe("sin micrófono la aplicación sigue sirviendo", () => {
  it("denegar el permiso vuelve a reposo y lo recuerda", () => {
    const m = run([{ type: "MIC_CLICK" }, { type: "MIC_DENIED" }]);
    expect(m.state).toBe("IDLE");
    expect(m.context.micDenied).toBe(true);
  });

  it("no vuelve a pedirlo una y otra vez", () => {
    const denegado = run([{ type: "MIC_CLICK" }, { type: "MIC_DENIED" }]);
    expect(transition(denegado, { type: "MIC_CLICK" }).state).toBe("IDLE");
  });
});

describe("errores", () => {
  it("guardan el mensaje para poder decirlo", () => {
    const m = transition(run(abrir), { type: "ERROR", message: "se cayó la red" });
    expect(m.state).toBe("ERROR");
    expect(m.context.error).toBe("se cayó la red");
  });

  it("se puede reintentar desde el error", () => {
    const roto = transition(run(abrir), { type: "ERROR", message: "x" });
    expect(transition(roto, { type: "MIC_CLICK" }).state).toBe("REQUESTING_MIC");
  });

  it("reintentar limpia el mensaje anterior", () => {
    const roto = transition(run(abrir), { type: "ERROR", message: "x" });
    expect(transition(roto, { type: "MIC_CLICK" }).context.error).toBe("");
  });
});

describe("el micrófono se silencia mientras habla el coach", () => {
  it("está cerrado en SPEAKING", () => {
    expect(micIsOpen("SPEAKING")).toBe(false);
  });

  it("y abierto cuando se puede interrumpir", () => {
    expect(micIsOpen("INTERRUPTIBLE")).toBe(true);
  });

  it("interrumpir hablando corta al coach", () => {
    const m = run([
      ...abrir,
      { type: "COACH_STARTED" },
      { type: "COACH_INTERRUPTIBLE" },
      { type: "USER_STARTED" },
    ]);
    expect(m.state).toBe("USER_SPEAKING");
  });

  it("nunca está abierto en un estado sin sesión", () => {
    for (const s of ["IDLE", "ERROR", "SAFETY_STOP", "CONNECTING", "REQUESTING_MIC"] as const) {
      expect(micIsOpen(s)).toBe(false);
      expect(inSession(s)).toBe(false);
    }
  });
});

describe("robustez", () => {
  it("un evento que no aplica no rompe nada", () => {
    expect(transition(initialMachine, { type: "COACH_ENDED" })).toEqual(initialMachine);
  });

  it("nunca sale de la lista de estados conocidos", () => {
    const todos: VoiceEvent[] = [
      { type: "MIC_CLICK" },
      { type: "MIC_GRANTED" },
      { type: "MIC_DENIED" },
      { type: "STREAM_READY" },
      { type: "USER_STARTED" },
      { type: "USER_ENDED" },
      { type: "TOOL_STARTED" },
      { type: "COACH_STARTED" },
      { type: "COACH_INTERRUPTIBLE" },
      { type: "COACH_ENDED" },
      { type: "RENEWAL_START" },
      { type: "RENEWAL_DONE" },
      { type: "SAFETY_RED" },
      { type: "SAFETY_ACK" },
      { type: "HANG_UP" },
    ];
    let m = initialMachine;
    // Todas las secuencias de tres eventos sobre el alfabeto completo.
    for (const a of todos)
      for (const b of todos)
        for (const c of todos) {
          m = run([a, b, c]);
          expect(m.state).toBeTypeOf("string");
        }
  });
});
