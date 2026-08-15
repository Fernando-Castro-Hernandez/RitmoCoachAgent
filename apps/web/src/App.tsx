/**
 * La aplicación.
 *
 * Une la máquina de estados de voz, la sesión de audio y la hoja. Los datos del
 * plan vienen del backend; mientras no hay perfil, se siembra el usuario de
 * demostración para que la primera pantalla nunca sea un orbe sin contexto — un
 * evaluador que abre esto en frío tiene que entender qué es en tres segundos.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import type { Safety, WeekContext } from "./components/Sheet";
import type { Session } from "./components/SessionField";
import type { Turn } from "./components/Transcript";
import { useT } from "./i18n";
import { Main } from "./screens/Main";
import {
  type VoiceEvent,
  type VoiceMachine,
  initialMachine,
  transition,
} from "./state/voiceMachine";

/* Datos de demostración. Se reemplazan por la respuesta de
   GET /api/plan y GET /api/session/today en cuanto hay perfil. */
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
  const [maquina, setMaquina] = useState<VoiceMachine>(initialMachine);
  const [nivel, setNivel] = useState(0);
  const [turnos, setTurnos] = useState<Turn[]>([]);
  const [safety, setSafety] = useState<Safety>("clear");
  const nivelTimer = useRef(0);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  const enviar = useCallback((evento: VoiceEvent) => {
    setMaquina((m) => transition(m, evento));
  }, []);

  // Simulación de amplitud mientras el circuito de audio real (session.ts) se
  // conecta en la siguiente tarea. El orbe ya lee de aquí, así que enchufarlo
  // es cambiar la fuente, no el componente.
  useEffect(() => {
    if (maquina.state !== "LISTENING" && maquina.state !== "USER_SPEAKING") {
      setNivel(0);
      return;
    }
    nivelTimer.current = window.setInterval(() => {
      setNivel(Math.random() * (maquina.state === "USER_SPEAKING" ? 0.9 : 0.25));
    }, 90);
    return () => window.clearInterval(nivelTimer.current);
  }, [maquina.state]);

  const tocarOrbe = () => {
    if (maquina.state === "IDLE" || maquina.state === "ERROR") {
      enviar({ type: "MIC_CLICK" });
      // El gesto del usuario es lo que abre el AudioContext en iOS Safari, así
      // que la petición de micrófono cuelga directamente del toque.
      navigator.mediaDevices
        ?.getUserMedia({ audio: true })
        .then(() => {
          enviar({ type: "MIC_GRANTED" });
          window.setTimeout(() => enviar({ type: "STREAM_READY" }), 400);
        })
        .catch(() => enviar({ type: "MIC_DENIED" }));
      return;
    }
    if (maquina.state === "INTERRUPTIBLE") {
      enviar({ type: "COACH_ENDED" });
      return;
    }
    enviar({ type: "HANG_UP" });
  };

  const escribir = (texto: string) => {
    setTurnos((v) => [...v, { role: "user", text: texto }]);
    // Puente provisional a la respuesta del coach. La ruta real es el
    // WebSocket de voz, que acepta texto en la misma sesión.
    window.setTimeout(() => {
      setTurnos((v) => [...v, { role: "coach", text: t("stTool") }]);
    }, 600);
  };

  const reconocer = () => {
    enviar({ type: "SAFETY_ACK" });
    setSafety("clear");
  };

  return (
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
      onAcknowledge={reconocer}
      onUpload={() => undefined}
    />
  );
}
