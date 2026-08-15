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

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  // ¿Corredor nuevo o conocido? Es lo único que decide qué pantalla se abre.
  useEffect(() => {
    let vivo = true;
    fetchProfile(userId)
      .then((p) => {
        if (!vivo) return;
        setPantalla(p?.carousel_done ? "hoja" : "onboarding");
      })
      .catch(() => {
        // Sin backend la aplicación no se queda en blanco: se entra al
        // carrusel, que es donde un corredor nuevo tiene que estar de todos
        // modos, y el guardado avisará si sigue caído.
        if (vivo) setPantalla("onboarding");
      });
    return () => {
      vivo = false;
    };
  }, [userId]);

  const enviarEvento = useCallback((evento: VoiceEvent) => {
    setMaquina((m) => transition(m, evento));
  }, []);

  // La sesión de voz vive en un ref: sobrevive a los renders y sólo hay una.
  const sesion = useRef<VoiceSession | null>(null);

  const abrirSesion = useCallback(async () => {
    const s = new VoiceSession({
      onEvent: enviarEvento,
      onLevel: setNivel,
      onTranscript: (text, role) =>
        setTurnos((v) => [...v, { role: role === "USER" ? "user" : "coach", text }]),
      onTtfa: (ms) => setTtfa(ms),
    });
    sesion.current = s;
    try {
      await s.start(userId);
    } catch (e) {
      enviarEvento({ type: "ERROR", message: e instanceof Error ? e.message : "no pude conectar" });
      sesion.current = null;
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

  const escribir = (texto: string) => {
    setTurnos((v) => [...v, { role: "user", text: texto }]);
    if (sesion.current) {
      sesion.current.sendText(texto);
      return;
    }
    // Sin sesión abierta el texto no tiene por dónde salir. Decirlo es mejor
    // que tragárselo y dejar al corredor esperando una respuesta que no viene.
    setTurnos((v) => [...v, { role: "coach", text: t("stIdle") }]);
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
    <>
      <Main
        ctx={CTX_DEMO}
        session={{ ...SESION_DEMO, why: t("demoWhy") }}
        safety={safety}
        referral={t("demoReferral")}
        turns={turnos}
        voice={maquina.state}
        level={nivel}
        micDenied={maquina.context.micDenied}
        onOrbClick={tocarOrbe}
        onSend={escribir}
        onAcknowledge={() => {
          enviarEvento({ type: "SAFETY_ACK" });
          setSafety("clear");
        }}
        onUpload={() => setPantalla("captura")}
        ttfaMs={ttfa}
      />

      {/* Volver a ver el primer arranque sin borrar datos a mano. Está aquí
          para poder ensayar la demo y para que cualquiera pruebe la app como
          un corredor nuevo; en producción viviría dentro de ajustes. */}
      <button
        type="button"
        onClick={startOver}
        className="label fixed bottom-1 left-1/2 -translate-x-1/2 px-3 py-1 opacity-40 transition-opacity hover:opacity-100"
      >
        empezar de cero
      </button>
    </>
  );
}
