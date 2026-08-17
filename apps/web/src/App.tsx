/**
 * La aplicación.
 *
 * Tres puertas, en orden: cuenta, carrusel, hoja.
 *
 *   sin token          → Auth
 *   con token, sin carrusel → Onboarding
 *   con token y carrusel    → la hoja
 *
 * Quién decide la segunda es el SERVIDOR: `onboarded` llega en la respuesta de
 * entrar y de registrarse. Si viviera en `localStorage`, entrar desde otro
 * teléfono le repetiría el carrusel a alguien que ya lo hizo.
 *
 * Registrarse cae directo en el carrusel, sin pantalla intermedia: quien acaba
 * de escribir su contraseña ya demostró lo que hay que demostrar.
 */

import { useCallback, useEffect, useRef, useState } from "react";

import {
  type HardProfile,
  type Sesion,
  type TodaySheet,
  fetchToday,
  getToken,
  logout,
  me,
  saveProfile,
} from "./api";
import type { Safety, WeekContext } from "./components/Sheet";
import type { Session } from "./components/SessionField";
import type { Turn } from "./components/Transcript";
import { useT } from "./i18n";
import { Auth } from "./screens/Auth";
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

type Pantalla = "cargando" | "auth" | "onboarding" | "hoja" | "captura";

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
    // Turnos de ejemplo para poder capturar la transcripción, incluido un turno
    // parcial: es el estado que el revisor no podía ver y que sólo existe a
    // media frase.
    turnos:
      p === "listening" || p === "transcript"
        ? ([
            { role: "user", text: "ayer me molestó algo la rodilla" },
            { role: "coach", text: "¿En qué parte exactamente? ¿Por dentro o por fuera?" },
            { role: "user", text: "por fuera, cuando bajo escaleras", partial: true },
          ] as const)
        : undefined,
    pantalla: p === "onboarding" ? ("onboarding" as const) : p === "upload" ? ("captura" as const) : undefined,
  };
}

/* Plan de ejemplo. Ya NO es lo normal: se usa sólo mientras `GET /api/today`
   responde, y para el corredor que todavía no tiene plan. En cuanto llega el
   dato real, el sello MUESTRA desaparece — porque a partir de ahí las cifras
   sí salieron del motor, que es la única condición para quitarlo. */
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
  const [maquina, setMaquina] = useState<VoiceMachine>(initialMachine);
  const [nivel, setNivel] = useState(0);
  const [turnos, setTurnos] = useState<Turn[]>([]);
  const [safety, setSafety] = useState<Safety>("clear");
  const [hoja, setHoja] = useState<TodaySheet | null>(null);
  const [ttfa, setTtfa] = useState<number | null>(null);
  const forzado = useState(estadoForzado)[0];

  useEffect(() => {
    document.documentElement.lang = locale;
  }, [locale]);

  // ¿Hay sesión, y hasta dónde llegó? Es lo único que decide qué se abre.
  //
  // Se pregunta al servidor en vez de confiar en que el token exista: un token
  // guardado hace siete días puede estar vencido, y descubrirlo al fallar la
  // primera acción de verdad es peor que descubrirlo al arrancar.
  useEffect(() => {
    let vivo = true;
    if (!getToken()) {
      setPantalla(forzado.pantalla ?? "auth");
      return;
    }
    me()
      .then((r) => {
        if (!vivo) return;
        setPantalla(forzado.pantalla ?? (r.onboarded ? "hoja" : "onboarding"));
      })
      .catch(() => {
        // `pedir` ya limpia el token y recarga ante un 401. Si se llega aquí es
        // otra cosa —backend caído, red— y la entrada es el sitio honesto donde
        // esperar: no hay datos que enseñar sin servidor.
        if (vivo) setPantalla(forzado.pantalla ?? "auth");
      });
    return () => {
      vivo = false;
    };
  }, [forzado.pantalla]);

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
      if (soloTexto) await s.startTextOnly();
      else await s.start();
      return true;
    } catch (e) {
      enviarEvento({ type: "ERROR", message: e instanceof Error ? e.message : "no pude conectar" });
      sesion.current = null;
      return false;
    }
  }, [enviarEvento]);

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
    await saveProfile(perfil);
    setPantalla("hoja");
  };

  const entrar = (sesion: Sesion) => {
    setPantalla(sesion.onboarded ? "hoja" : "onboarding");
  };

  // La hoja se carga cuando se entra a ella, y se vuelve a cargar al volver de
  // la captura: registrar una carrera puede cambiar la sesión de hoy y el
  // veredicto de la puerta.
  useEffect(() => {
    if (pantalla !== "hoja") return;
    let vivo = true;
    fetchToday()
      .then((h) => {
        if (!vivo) return;
        setHoja(h);
        setSafety(h.safety);
      })
      .catch(() => {
        // Sin backend se queda la muestra, con su sello puesto. Lo que no puede
        // pasar es que un fallo de red deje al corredor viendo datos de ejemplo
        // creyendo que son suyos, y el sello es justo lo que lo impide.
        if (vivo) setHoja(null);
      });
    return () => {
      vivo = false;
    };
  }, [pantalla]);

  if (pantalla === "cargando") {
    return (
      <div className="flex h-dvh items-center justify-center">
        <span className="label">{t("stConnecting")}</span>
      </div>
    );
  }

  if (pantalla === "auth") {
    return <Auth onReady={entrar} />;
  }

  if (pantalla === "onboarding") {
    return <Onboarding onDone={terminarOnboarding} />;
  }

  if (pantalla === "captura") {
    return (
      <Upload
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
        ctx={hoja?.week ?? CTX_DEMO}
        session={
          hoja
            ? hoja.session && { ...hoja.session, why: hoja.session.why || t("demoWhy") }
            : { ...SESION_DEMO, why: t("demoWhy") }
        }
        safety={forzado.safety ?? safety}
        referral={hoja?.referral ?? t("demoReferral")}
        turns={forzado.turnos ? [...forzado.turnos] : turnos}
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
      /* Cerrar sesión. Antes esto borraba el UUID del navegador y con él al
         corredor entero; ahora sólo suelta el token y los datos siguen en su
         cuenta, que es lo que la gente espera de un «cerrar sesión». */
      onStartOver={logout}
      /* El sello MUESTRA sólo mientras las cifras no vengan del motor. En
         cuanto `/api/today` responde con un plan, desaparece — y si el corredor
         aún no tiene plan, se queda, porque entonces sí es un ejemplo. La regla
         2 del producto es que toda cifra viene del motor y SE NOTA. */
      specimen={!hoja?.has_plan}
    />
  );
}
