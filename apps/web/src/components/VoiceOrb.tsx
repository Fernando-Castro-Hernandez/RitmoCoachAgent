/**
 * El orbe: la única tinta húmeda de una hoja impresa.
 *
 * Todo lo demás en la pantalla está impreso, fijo y es autoridad. Esto no: es
 * un depósito de tinta que ondula. El contraste entre lo impreso y lo vivo ES
 * la idea, así que se dibuja en canvas con anillos de difusión irregulares en
 * vez de resolverlo con un degradado radial, que sería la versión barata del
 * efecto.
 *
 * Los anillos responden a la **amplitud real del micrófono**, no a una
 * animación en bucle. Es la diferencia entre un sistema que está oyendo y uno
 * que finge oír, y es la mitad de la confianza en un producto de voz.
 *
 * Cada estado se distingue sin leer, y además lleva su texto: el teléfono
 * puede ir en el bolsillo y el usuario puede no distinguir el azul del verde.
 */

import { useEffect, useRef } from "react";

import { type TextKey, useT } from "../i18n";
import type { VoiceState } from "../state/voiceMachine";

interface Props {
  state: VoiceState;
  /** 0–1, amplitud real del micrófono. */
  level: number;
  onClick: () => void;
}

/** Cada estado: tinta, anillos, y si el disco respira. */
const TINTA: Record<VoiceState, { color: string; rings: number; breathes: boolean }> = {
  IDLE: { color: "var(--color-ink-30)", rings: 2, breathes: false },
  REQUESTING_MIC: { color: "var(--color-ink-50)", rings: 3, breathes: true },
  CONNECTING: { color: "var(--color-ink-50)", rings: 4, breathes: true },
  LISTENING: { color: "var(--color-proof)", rings: 6, breathes: true },
  USER_SPEAKING: { color: "var(--color-proof)", rings: 9, breathes: true },
  THINKING: { color: "var(--color-proof-deep)", rings: 3, breathes: true },
  TOOL_RUNNING: { color: "var(--color-proof-deep)", rings: 4, breathes: true },
  SPEAKING: { color: "var(--color-clear)", rings: 7, breathes: true },
  INTERRUPTIBLE: { color: "var(--color-clear)", rings: 5, breathes: true },
  ERROR: { color: "var(--color-flag)", rings: 1, breathes: false },
  SAFETY_STOP: { color: "var(--color-flag)", rings: 0, breathes: false },
};

const ETIQUETA: Record<VoiceState, TextKey> = {
  IDLE: "stIdle",
  REQUESTING_MIC: "stMic",
  CONNECTING: "stConnecting",
  LISTENING: "stListening",
  USER_SPEAKING: "stUserSpeaking",
  THINKING: "stThinking",
  TOOL_RUNNING: "stTool",
  SPEAKING: "stSpeaking",
  INTERRUPTIBLE: "stInterruptible",
  ERROR: "stError",
  SAFETY_STOP: "stSafety",
};

/**
 * Resuelve las once tintas UNA vez.
 *
 * Leerlas con `getComputedStyle` dentro del bucle de dibujo fuerza un recálculo
 * de estilos sesenta veces por segundo y deja el hilo principal sin aire — la
 * pestaña deja de responder incluso a un `screenshot`. Es el tipo de fallo que
 * no aparece en una prueba unitaria y sí en cuanto alguien abre la página.
 */
function resolverTintas(): Record<VoiceState, string> {
  const raiz = getComputedStyle(document.documentElement);
  const leer = (nombre: string) =>
    (nombre.startsWith("var(")
      ? raiz.getPropertyValue(nombre.slice(4, -1)).trim()
      : nombre) || "#1b4fd8";

  return Object.fromEntries(
    Object.entries(TINTA).map(([estado, { color }]) => [estado, leer(color)]),
  ) as Record<VoiceState, string>;
}

export function VoiceOrb({ state, level, onClick }: Props) {
  const { t } = useT();
  const canvas = useRef<HTMLCanvasElement>(null);
  // El nivel entra por ref y no por estado: dibujar a 60 fps no puede pasar por
  // el ciclo de render de React.
  const nivel = useRef(level);
  nivel.current = level;
  const estado = useRef(state);
  estado.current = state;

  useEffect(() => {
    const lienzo = canvas.current;
    if (!lienzo) return;
    const ctx = lienzo.getContext("2d");
    if (!ctx) return;

    const quieto = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const tintas = resolverTintas();
    const dpr = Math.min(window.devicePixelRatio || 1, 2);
    let raf = 0;
    let t0 = 0;
    // Suavizado del nivel: el micrófono da picos, y el papel no salta.
    let suave = 0;

    const medir = () => {
      const r = lienzo.getBoundingClientRect();
      lienzo.width = Math.round(r.width * dpr);
      lienzo.height = Math.round(r.height * dpr);
    };
    medir();
    const ro = new ResizeObserver(medir);
    ro.observe(lienzo);

    const pintar = (ms: number) => {
      if (!t0) t0 = ms;
      const tiempo = (ms - t0) / 1000;
      const { rings, breathes } = TINTA[estado.current];
      const tinta = tintas[estado.current];

      const w = lienzo.width;
      const h = lienzo.height;
      const cx = w / 2;
      const cy = h / 2;
      ctx.clearRect(0, 0, w, h);

      suave += (nivel.current - suave) * 0.18;
      const respiro = breathes && !quieto ? 0.06 * Math.sin(tiempo * 1.9) : 0;
      const base = Math.min(w, h) * 0.11;
      const nucleo = base * (1 + respiro + suave * 0.55);

      // El núcleo: tinta densa, con el borde ligeramente irregular como una
      // gota que todavía no seca.
      ctx.fillStyle = tinta;
      ctx.beginPath();
      const pasos = 72;
      for (let i = 0; i <= pasos; i += 1) {
        const a = (i / pasos) * Math.PI * 2;
        const onda =
          1 +
          0.018 * Math.sin(a * 3 + tiempo * 1.1) +
          0.012 * Math.sin(a * 5 - tiempo * 0.7) +
          suave * 0.05 * Math.sin(a * 7 + tiempo * 2.3);
        const r = nucleo * onda;
        const x = cx + Math.cos(a) * r;
        const y = cy + Math.sin(a) * r * 0.92;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.closePath();
      ctx.fill();

      // Los anillos de difusión: la tinta corriéndose por la fibra del papel.
      ctx.lineWidth = Math.max(1, dpr * 0.75);
      for (let k = 1; k <= rings; k += 1) {
        const avance = quieto ? k / (rings + 1) : ((tiempo * 0.28 + k / rings) % 1);
        const r = nucleo * (1.25 + avance * (2.6 + suave * 1.8));
        const alfa = (1 - avance) * (0.32 + suave * 0.4) * (quieto ? 0.7 : 1);
        if (alfa <= 0.01) continue;
        ctx.globalAlpha = alfa;
        ctx.strokeStyle = tinta;
        ctx.beginPath();
        for (let i = 0; i <= pasos; i += 1) {
          const a = (i / pasos) * Math.PI * 2;
          const onda = 1 + 0.03 * Math.sin(a * 4 + k + tiempo * 0.6);
          const x = cx + Math.cos(a) * r * onda;
          const y = cy + Math.sin(a) * r * onda * 0.92;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
        ctx.stroke();
      }
      ctx.globalAlpha = 1;

      if (!quieto) raf = requestAnimationFrame(pintar);
    };

    raf = requestAnimationFrame(pintar);
    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
    };
  }, []);

  const detenido = state === "SAFETY_STOP";

  return (
    <button
      type="button"
      onClick={onClick}
      disabled={detenido}
      aria-live="polite"
      aria-label={t(ETIQUETA[state])}
      className="group flex w-full flex-col items-center gap-2 bg-transparent py-3 disabled:cursor-not-allowed"
    >
      <canvas
        ref={canvas}
        aria-hidden="true"
        className="h-28 w-full max-w-[22rem] transition-opacity duration-300 group-disabled:opacity-40"
      />
      <span className="label" data-state={state}>
        {t(ETIQUETA[state])}
      </span>
    </button>
  );
}
