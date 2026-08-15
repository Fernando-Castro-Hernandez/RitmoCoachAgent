/**
 * Pantalla mínima de verificación para la tarea A3.
 *
 * Su único trabajo es demostrar que el circuito completo funciona: micrófono →
 * WebSocket → Bedrock → audio de vuelta. El orbe de voz, la tarjeta de sesión y
 * el contexto de semana llegan en la Fase D.
 */

import { useRef, useState } from "react";

import { VoiceSession, type SessionState } from "./session";

const ETIQUETAS: Record<SessionState, string> = {
  idle: "Toca para hablar",
  connecting: "Conectando…",
  listening: "Escuchando…",
  speaking: "Ritmo está hablando",
  error: "Algo falló",
};

export default function App() {
  const [state, setState] = useState<SessionState>("idle");
  const [turnos, setTurnos] = useState<{ role: string; text: string }[]>([]);
  const [level, setLevel] = useState(0);
  const [error, setError] = useState("");
  const [texto, setTexto] = useState("");
  const session = useRef<VoiceSession | null>(null);

  async function toggle() {
    if (state !== "idle" && state !== "error") {
      await session.current?.stop();
      return;
    }
    setError("");
    setTurnos([]);
    session.current = new VoiceSession({
      onState: setState,
      onLevel: setLevel,
      onTranscript: (text, role) =>
        setTurnos((prev) => [...prev, { role, text }]),
      onError: setError,
    });
    try {
      await session.current.start("demo");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : String(exc));
      setState("error");
    }
  }

  const activa = state !== "idle" && state !== "error";
  const escala = 1 + Math.min(level * 3, 0.6);

  return (
    <main style={estilos.main}>
      <h1 style={estilos.h1}>Ritmo</h1>
      <p style={estilos.dek}>Verificación de la ruta de voz — tarea A3</p>

      <button onClick={toggle} style={estilos.orbe(state, escala)} aria-label={ETIQUETAS[state]}>
        {activa ? "■" : "●"}
      </button>
      <p style={estilos.estado}>{ETIQUETAS[state]}</p>
      {error && <p style={estilos.error}>{error}</p>}

      <div style={estilos.transcripcion}>
        {turnos.map((t, i) => (
          <p key={i} style={estilos.turno}>
            <strong>{t.role === "USER" ? "Tú" : "Ritmo"}</strong> {t.text}
          </p>
        ))}
      </div>

      <form
        style={estilos.form}
        onSubmit={(e) => {
          e.preventDefault();
          if (!texto.trim()) return;
          session.current?.sendText(texto);
          setTurnos((prev) => [...prev, { role: "USER", text: texto }]);
          setTexto("");
        }}
      >
        <input
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          placeholder="…o escríbele"
          disabled={!activa}
          style={estilos.input}
        />
      </form>
    </main>
  );
}

const COLORES: Record<SessionState, string> = {
  idle: "#5A6178",
  connecting: "#8390FF",
  listening: "#3D4EE8",
  speaking: "#128550",
  error: "#BC332B",
};

const estilos = {
  main: {
    fontFamily: "system-ui, sans-serif",
    maxWidth: 520,
    margin: "0 auto",
    padding: "48px 24px",
    textAlign: "center" as const,
    color: "#11141e",
  },
  h1: { fontSize: 32, letterSpacing: "-0.03em", margin: 0 },
  dek: { color: "#5A6178", marginTop: 4, fontSize: 14 },
  orbe: (state: SessionState, escala: number) => ({
    width: 132,
    height: 132,
    borderRadius: "50%",
    border: "none",
    background: COLORES[state],
    color: "white",
    fontSize: 30,
    cursor: "pointer",
    marginTop: 40,
    transform: `scale(${escala})`,
    transition: "transform 80ms linear, background 200ms",
  }),
  estado: { marginTop: 24, fontSize: 15, color: "#5A6178" },
  error: { color: "#BC332B", fontSize: 14 },
  transcripcion: { marginTop: 32, textAlign: "left" as const, fontSize: 15 },
  turno: { margin: "8px 0", lineHeight: 1.5 },
  form: { marginTop: 24 },
  input: {
    width: "100%",
    padding: "12px 14px",
    fontSize: 15,
    borderRadius: 10,
    border: "1px solid #DDE2EF",
    fontFamily: "inherit",
  },
};
