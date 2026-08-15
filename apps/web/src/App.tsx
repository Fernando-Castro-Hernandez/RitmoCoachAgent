/**
 * La aplicación.
 *
 * El primer arranque manda: sin perfil se entra al carrusel, con perfil se
 * entra a la hoja. Un desconocido que abre la URL en frío recorre lo mismo que
 * recorrería un corredor real, porque **es** lo mismo — no hay cuenta que crear
 * ni sesión que iniciar, la identidad es un UUID del navegador (ver api.ts).
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  type HardProfile,
  fetchProfile,
  getUserId,
  markOnboarded,
  saveProfile,
  startOver,
} from "./api";
import type { Safety, WeekContext } from "./components/Sheet";
import type { Session } from "./components/SessionField";
import type { Turn } from "./components/Transcript";
import { useT } from "./i18n";
import { Main } from "./screens/Main";
import { Onboarding } from "./screens/Onboarding";
import { Upload } from "./screens/Upload";
import { VoiceSession } from "./session";
import {
  type VoiceEvent,
  type VoiceMachine,
  initialMachine,
  transition,
} from "./state/voiceMachine";

type Pantalla = "cargando" | "onboarding" | "hoja" | "captura";

/**
 * Forzar un estado desde la URL: `?estado=safety-red`, `?estado=listening`…
 *
 * Existe para poder capturar y ensayar estados que sólo aparecen en vivo —el
 * formulario anulado, el error de red, el micrófono denegado— sin tener que
 * provocarlos de verdad. Lo usa el guion de capturas y sirve para el video.
 *
 * No es una puerta trasera: sólo pinta estados de interfaz. No salta la puerta
 * de seguridad del backend ni escribe nada; el veredicto real sigue viniendo
 * del motor, y forzar «safety-red» aquí no le da permiso a nadie de prescribir.
 */
function estadoForzado() {
  const p = new URLSearchParams(window.location.search).get("estado");
  return {
    voice: (
      { listening: "LISTENING", speaking: "SPEAKING", thinking: "THINKING",
        error: "ERROR", connecting: "CONNECTING" } as const
    )[p ?? ""],
    safety: p === "safety-red" ? ("flag" as const) : p === "safety-amber" ? ("caution" as const) : undefined,
    micDenied: p === "mic-denied",
    pantalla: p === "onboarding" ? ("onboarding" as const) : p === "upload" ? ("captura" as const) : undefined,
  };
}

/* Plan de demostración. Se sustituye por GET /api/plan cuando el motor haya
   generado uno; hoy el corredor recién creado todavía no tiene plan, así que
   esto es lo que ve mientras la conversación recoge el contexto que falta. */
const CTX_DEMO: WeekContext = {
  week: 7,
  totalWeeks: 16,
  phase: "construccion",
  race: "Maratón CDMX",
  daysLeft: 63,
};

const SESION_DEMO: Session = {
  kind: "largo",
  distanceKm: 18,
  pace: "6:15–6:40",
  effort: "conversacional",
  zone: 2,
  durationLabel: "1 h 55 min",
  why: "",
};

export default function App() {
  const { t, locale } = useT();
  const [pantalla, setPantalla] = useState<Pantalla>("cargando");
  const [userId] = useState(getUserId);
  const [maquina, setMaquina] = useState<VoiceMachine>(initialMachine);
  const [nivel, setNivel] = useState(0);
  const [turnos, setTurnos] = useState<Turn[]>([]);
  const [safety, setSafety] = useState<Safety>("clear");
  const [ttfa, setTtfa] = useState<number | null>(null);
  const forzado = useState(estadoForzado)[0];

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  // ¿Corredor nuevo o conocido? Es lo único que decide qué pantalla se abre.
  useEffect(() => {
    let vivo = true;
    fetchProfile(userId)
      .then((p) => {
        if (!vivo) return;
        setPantalla(forzado.pantalla ?? (p?.carousel_done ? "hoja" : "onboarding"));
      })
      .catch(() => {
        // Sin backend la aplicación no se queda en blanco: se entra al
        // carrusel, que es donde un corredor nuevo tiene que estar de todos
        // modos, y el guardado avisará si sigue caído.
        if (vivo) setPantalla(forzado.pantalla ?? "onboarding");
      });
    return () => {
      vivo = false;
    };
  }, [userId, forzado.pantalla]);

  const enviarEvento = useCallback((evento: VoiceEvent) => {
    setMaquina((m) => transition(m, evento));
  }, []);

  // La sesión de voz vive en un ref: sobrevive a los renders y sólo hay una.
  const sesion = useRef<VoiceSession | null>(null);

  const abrirSesion = useCallback(async (soloTexto = false) => {
    const s = new VoiceSession({
      onEvent: enviarEvento,
      onLevel: setNivel,
      onTranscript: (text, role) =>
        setTurnos((v) => [...v, { role: role === "USER" ? "user" : "coach", text }]),
      onTtfa: (ms) => setTtfa(ms),
    });
    sesion.current = s;
    try {
      if (soloTexto) await s.startTextOnly(userId);
      else await s.start(userId);
      return true;
    } catch (e) {
      enviarEvento({ type: "ERROR", message: e instanceof Error ? e.message : "no pude conectar" });
      sesion.current = null;
      return false;
    }
  }, [enviarEvento, userId]);

  const cerrarSesion = useCallback(async () => {
    await sesion.current?.stop();
    sesion.current = null;
    setNivel(0);
  }, []);

  // Cerrar la sesión al desmontar: un WebSocket y un micrófono abiertos
  // sobreviven a la pantalla si nadie los recoge.
  useEffect(() => {
    return () => {
      void sesion.current?.stop();
    };
  }, []);

  const tocarOrbe = async () => {
    if (maquina.state === "IDLE" || maquina.state === "ERROR") {
      enviarEvento({ type: "MIC_CLICK" });
      // Este `await` cuelga directamente del gesto del usuario, que es lo que
      // iOS Safari exige para dejar abrir el AudioContext. Meterlo en un
      // efecto lo rompe en iPhone y en ningún otro sitio.
      try {
        const flujo = await navigator.mediaDevices.getUserMedia({ audio: true });
        flujo.getTracks().forEach((t) => t.stop());
      } catch {
        enviarEvento({ type: "MIC_DENIED" });
        return;
      }
      enviarEvento({ type: "MIC_GRANTED" });
      await abrirSesion();
      return;
    }
    if (maquina.state === "INTERRUPTIBLE") {
      enviarEvento({ type: "COACH_ENDED" });
      return;
    }
    await cerrarSesion();
    enviarEvento({ type: "HANG_UP" });
  };

  const escribir = async (texto: string) => {
    setTurnos((v) => [...v, { role: "user", text: texto }]);

    // Escribir no debería exigir haber abierto la voz antes. Si no hay sesión,
    // se abre una sin micrófono y el turno sale por el mismo WebSocket: el
    // backend acepta texto y voz en la misma conversación.
    if (!sesion.current?.isOpen) {
      enviarEvento({ type: "MIC_CLICK" });
      enviarEvento({ type: "MIC_GRANTED" });
      const abierta = await abrirSesion(true);
      if (!abierta) return;
    }
    sesion.current?.sendText(texto);
  };

  const terminarOnboarding = async (perfil: HardProfile) => {
    await saveProfile(userId, perfil);
    markOnboarded();
    setPantalla("hoja");
  };

  if (pantalla === "cargando") {
    return (
      <div className="flex h-dvh items-center justify-center">
        <span className="label">{t("stConnecting")}</span>
      </div>
    );
  }

  if (pantalla === "onboarding") {
    return <Onboarding onDone={terminarOnboarding} />;
  }

  if (pantalla === "captura") {
    return (
      <Upload
        userId={userId}
        onClose={() => setPantalla("hoja")}
        onSave={({ distanceKm, paceSecPerKm }) => {
          setTurnos((v) => [
            ...v,
            {
              role: "coach",
              text: `${distanceKm} km · ${Math.floor(paceSecPerKm / 60)}:${String(
                paceSecPerKm % 60,
              ).padStart(2, "0")} /km`,
            },
          ]);
          setPantalla("hoja");
        }}
      />
    );
  }

  return (
    <Main
        ctx={CTX_DEMO}
        session={{ ...SESION_DEMO, why: t("demoWhy") }}
        safety={forzado.safety ?? safety}
        referral={t("demoReferral")}
        turns={turnos}
        voice={forzado.voice ?? maquina.state}
        level={forzado.voice === "LISTENING" ? 0.55 : nivel}
        micDenied={forzado.micDenied || maquina.context.micDenied}
        onOrbClick={tocarOrbe}
        onSend={escribir}
        onAcknowledge={() => {
          enviarEvento({ type: "SAFETY_ACK" });
          setSafety("clear");
        }}
      onUpload={() => setPantalla("captura")}
      ttfaMs={ttfa}
      /* Volver a ver el primer arranque sin borrar datos a mano: hace falta
         para ensayar la demo y para que cualquiera pruebe la app en frío. En
         producción viviría dentro de ajustes. */
      onStartOver={startOver}
      /* La hoja todavía no consume GET /api/plan: lo que se ve es una muestra,
         y se dice. Un desconocido que abre la URL en frío no puede confundir
         datos de ejemplo con una prescripción hecha para él — la regla 2 del
         producto es que toda cifra viene del motor y SE NOTA. */
      specimen
    />
  );
}
