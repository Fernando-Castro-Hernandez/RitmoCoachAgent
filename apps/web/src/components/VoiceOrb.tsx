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

/**
 * Cada estado: tinta, sangrado y si la gota respira.
 *
 * Todos los estados operables son AZUL DE PROCESO, por la disciplina donada:
 * el acento es el control. El coach hablando es el sistema vivo, y lo vivo es
 * azul igual que lo tocable. Los estados se distinguen por cuánto sangra la
 * tinta y a qué ritmo, no por cambiar de color — cambiar de color aquí robaría
 * las tintas de señal, que pertenecen sólo al código de seguridad.
 */
const TINTA: Record<VoiceState, { color: string; rings: number; breathes: boolean }> = {
  IDLE: { color: "var(--color-proof)", rings: 2, breathes: false },
  REQUESTING_MIC: { color: "var(--color-proof)", rings: 3, breathes: true },
  CONNECTING: { color: "var(--color-proof)", rings: 4, breathes: true },
  LISTENING: { color: "var(--color-proof)", rings: 6, breathes: true },
  USER_SPEAKING: { color: "var(--color-proof)", rings: 9, breathes: true },
  THINKING: { color: "var(--color-proof-deep)", rings: 3, breathes: true },
  TOOL_RUNNING: { color: "var(--color-proof-deep)", rings: 4, breathes: true },
  SPEAKING: { color: "var(--color-proof)", rings: 7, breathes: true },
  INTERRUPTIBLE: { color: "var(--color-proof)", rings: 5, breathes: true },
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

/** Aplica alfa a un color ya resuelto, sin volver a leer estilos. */
function mezcla(hex: string, alfa: number): string {
  const limpio = hex.replace("#", "");
  const n = parseInt(
    limpio.length === 3
      ? limpio
          .split("")
          .map((c) => c + c)
          .join("")
      : limpio,
    16,
  );
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alfa})`;
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

    // Se mide contra el CONTENEDOR y no contra el propio lienzo: escribir
    // `canvas.width` cambia su tamaño intrínseco, y un ResizeObserver sobre el
    // elemento que estás redimensionando es una invitación a un bucle.
    const medir = () => {
      const r = (lienzo.parentElement ?? lienzo).getBoundingClientRect();
      const ancho = Math.min(r.width, 352);
      lienzo.width = Math.round(ancho * dpr);
      lienzo.height = Math.round(112 * dpr);
    };
    // Redimensionar limpia el lienzo, así que hay que volver a pintarlo. Si el
    // bucle está dormido —y en reposo lo está— nadie lo haría, y el orbe se
    // quedaría en blanco al girar el teléfono. Se descubrió capturando: la
    // captura de página completa redimensiona, y el orbe salió vacío.
    const remedir = () => {
      medir();
      arrancar();
    };
    medir();
    window.addEventListener("resize", remedir);

    // A 30 fps. La tinta se difunde despacio; sesenta fotogramas por segundo no
    // se ven mejor y sí se notan en la batería de un teléfono que va en el
    // bolsillo durante una hora de carrera.
    const PASO_MS = 1000 / 30;
    let ultimo = 0;

    const arrancar = () => {
      if (!raf) {
        ultimo = 0;
        raf = requestAnimationFrame(pintar);
      }
    };

    const pintar = (ms: number) => {
      if (!t0) t0 = ms;
      if (ms - ultimo < PASO_MS) {
        raf = requestAnimationFrame(pintar);
        return;
      }
      ultimo = ms;
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

      // ── Tinta húmeda ────────────────────────────────────────────
      // El contrato designa este orbe como el ÚNICO degradado del mundo, y la
      // única cosa no impresa de la hoja. Anillos de trazo parejo eran un
      // diagrama vectorial de una onda; esto es tinta: densidad que cae hacia
      // el papel, borde que sangra irregular, y manchas donde la fibra chupó
      // más de la cuenta.

      const contorno = (radio: number, semilla: number, rugosidad: number) => {
        ctx.beginPath();
        const pasos = 84;
        for (let i = 0; i <= pasos; i += 1) {
          const a = (i / pasos) * Math.PI * 2;
          const onda =
            1 +
            rugosidad * 0.55 * Math.sin(a * 3 + semilla + tiempo * 0.5) +
            rugosidad * 0.32 * Math.sin(a * 5 - semilla * 1.7 + tiempo * 0.31) +
            rugosidad * 0.2 * Math.sin(a * 8 + semilla * 2.3 - tiempo * 0.7);
          const r = radio * onda;
          const x = cx + Math.cos(a) * r;
          const y = cy + Math.sin(a) * r * 0.9;
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.closePath();
      };

      // El halo: la tinta que ya se corrió por la fibra y se está secando.
      // Es un degradado radial de verdad, no un trazo.
      const halo = nucleo * (2.1 + suave * 1.6);
      const difusion = ctx.createRadialGradient(cx, cy, nucleo * 0.6, cx, cy, halo);
      difusion.addColorStop(0, mezcla(tinta, 0.42 + suave * 0.28));
      difusion.addColorStop(0.45, mezcla(tinta, 0.14 + suave * 0.14));
      difusion.addColorStop(1, mezcla(tinta, 0));
      ctx.fillStyle = difusion;
      contorno(halo, 1.3, 0.055);
      ctx.fill();

      // Los frentes de avance: la tinta empujando hacia afuera. Rellenos y no
      // trazados, porque la tinta no dibuja circunferencias.
      for (let k = 1; k <= rings; k += 1) {
        const avance = quieto ? k / (rings + 1) : ((tiempo * 0.22 + k / rings) % 1);
        const r = nucleo * (1.1 + avance * (1.9 + suave * 1.3));
        const alfa = (1 - avance) ** 1.7 * (0.2 + suave * 0.3);
        if (alfa <= 0.008) continue;
        const frente = ctx.createRadialGradient(cx, cy, r * 0.82, cx, cy, r);
        frente.addColorStop(0, mezcla(tinta, 0));
        frente.addColorStop(1, mezcla(tinta, alfa));
        ctx.fillStyle = frente;
        contorno(r, k * 1.9, 0.045);
        ctx.fill();
      }

      // El núcleo: tinta saturada, con el borde mordido por el papel.
      const cuerpo = ctx.createRadialGradient(
        cx - nucleo * 0.18,
        cy - nucleo * 0.2,
        nucleo * 0.15,
        cx,
        cy,
        nucleo * 1.12,
      );
      cuerpo.addColorStop(0, mezcla(tinta, 1));
      cuerpo.addColorStop(0.7, mezcla(tinta, 0.97));
      cuerpo.addColorStop(1, mezcla(tinta, 0.55));
      ctx.fillStyle = cuerpo;
      contorno(nucleo, 0.4, 0.038);
      ctx.fill();

      // Tres manchas donde la fibra chupó más. Sin esto el borde es demasiado
      // parejo para leerse como líquido.
      for (let k = 0; k < 3; k += 1) {
        const a = (k / 3) * Math.PI * 2 + tiempo * 0.13 + k;
        const d = nucleo * (0.92 + 0.1 * Math.sin(tiempo * 0.6 + k * 2));
        ctx.fillStyle = mezcla(tinta, 0.5);
        ctx.beginPath();
        ctx.ellipse(
          cx + Math.cos(a) * d,
          cy + Math.sin(a) * d * 0.9,
          nucleo * (0.16 + 0.05 * Math.sin(tiempo + k)),
          nucleo * 0.11,
          a,
          0,
          Math.PI * 2,
        );
        ctx.fill();
      }

      ctx.globalAlpha = 1;

      // En reposo y sin señal no hay nada que animar: se dibuja una vez y el
      // bucle se detiene hasta que algo cambie. Un orbe gris quieto no necesita
      // treinta fotogramas por segundo.
      const dormido = !breathes && suave < 0.01 && rings <= 2;
      if (quieto || dormido || document.hidden) {
        raf = 0;
        return;
      }
      raf = requestAnimationFrame(pintar);
    };

    arrancar();
    // Se despierta cuando cambia el estado o cuando la pestaña vuelve al frente.
    const observador = window.setInterval(arrancar, 250);
    document.addEventListener("visibilitychange", arrancar);

    return () => {
      cancelAnimationFrame(raf);
      window.clearInterval(observador);
      window.removeEventListener("resize", remedir);
      document.removeEventListener("visibilitychange", arrancar);
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
