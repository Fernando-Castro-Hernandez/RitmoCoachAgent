/**
 * La aplicación.
 *
 * Dos rutas y tres puertas.
 *
 *   /      portada. Si ya hay sesión válida, se va sola a /app.
 *   /app   la aplicación: sin token → Auth, sin carrusel → Onboarding, si no la hoja.
 *
 * El enrutado se hace con `history.pushState` y `location.pathname`, sin
 * librería. Son dos rutas; meter un router de 20 kB para esto sería peso sin
 * beneficio. Caddy ya devuelve `index.html` para cualquier ruta
 * (`try_files {path} /index.html`), así que recargar en `/app` funciona.
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
  ApiError,
  type Cuenta,
  type HardProfile,
  type Sesion,
  type TodaySheet,
  descargarPlanCsv,
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
import { Calendar } from "./screens/Calendar";
import { GaitUpload } from "./screens/GaitUpload";
import { Landing } from "./screens/Landing";
import { Main } from "./screens/Main";
import { Onboarding } from "./screens/Onboarding";
import { Profile } from "./screens/Profile";
import { Upload } from "./screens/Upload";
import { VoiceSession } from "./session";
import {
  type VoiceEvent,
  type VoiceMachine,
  initialMachine,
  transition,
} from "./state/voiceMachine";

type Pantalla =
  | "cargando"
  | "portada"
  | "auth"
  | "onboarding"
  | "hoja"
  | "captura"
  | "tecnica"
  | "calendario"
  | "perfil";

/** Cambia la URL sin recargar. La portada y la aplicación son sitios
 *  distintos y el botón de atrás del navegador tiene que notarlo. */
function irA(ruta: string) {
  if (window.location.pathname !== ruta) {
    window.history.pushState({}, "", ruta);
  }
}

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

/* Plan de ejemplo. **Sólo para el guion de capturas** (`?estado=…`), nunca
   para un corredor de verdad.

   Antes se usaba como respaldo cuando `/api/today` no traía plan, y el efecto
   era el peor posible: una cuenta recién creada veía «semana 7 de 16, maratón,
   faltan 70 días» — el historial de otra persona, presentado como suyo. En un
   producto que promete que toda cifra viene del motor, ninguna de ésas venía.

   Ahora sin plan se enseña el estado real: la meta elegida y de dónde saldrá
   el plan. Menos vistoso, y cierto. */
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
  const [modoAuth, setModoAuth] = useState<"entrar" | "crear">("entrar");
  const [cuenta, setCuenta] = useState<Cuenta | null>(null);
  const [descargando, setDescargando] = useState(false);
  const [errorCsv, setErrorCsv] = useState("");

  // El nombre sale de la hoja, que ya lee el perfil. Ver `TodaySheet.name`.
  const nombre = hoja?.name ?? null;

  // La descarga no puede ser un `<a href>`: el endpoint pide el token y un
  // enlace no lleva cabeceras. Se pide, se convierte en blob y se dispara.
  const descargar = async () => {
    setDescargando(true);
    setErrorCsv("");
    try {
      await descargarPlanCsv();
    } catch (e) {
      // Un 404 aquí significa que el motor todavía no generó nada, y decirlo
      // así es más útil que un «error» genérico que no sugiere qué hacer.
      setErrorCsv(e instanceof ApiError && e.status === 404 ? t("exportEmpty") : t("exportFailed"));
    } finally {
      setDescargando(false);
    }
  };

  /**
   * Cerrar sesión: suelta el token y vuelve a la portada.
   *
   * A la portada y no a un recargar a secas. `logout()` recarga sobre `/app`,
   * que sin token pinta el formulario de entrada — es decir, al salir aparecía
   * otra vez la pantalla de entrar, que se lee como «te rechazó» en vez de como
   * «saliste».
   */
  const salirDeLaCuenta = () => {
    window.history.pushState({}, "", "/");
    logout();
  };

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
    const enLaPortada = window.location.pathname === "/";

    if (!getToken()) {
      // Sin sesión: la portada se queda, y /app manda a la entrada.
      setPantalla(forzado.pantalla ?? (enLaPortada ? "portada" : "auth"));
      return;
    }

    me()
      .then((r) => {
        if (!vivo) return;
        // Con sesión válida, la portada no aporta nada: se pasa a /app sola.
        // Es lo que pidió el enunciado y también lo sensato — quien ya entró no
        // quiere leer otra vez qué es esto.
        irA("/app");
        setCuenta(r.user);
        setPantalla(forzado.pantalla ?? (r.onboarded ? "hoja" : "onboarding"));
      })
      .catch(() => {
        // `pedir` ya limpia el token y recarga ante un 401. Si se llega aquí es
        // otra cosa —backend caído, red— y la portada es el sitio honesto donde
        // esperar: no hay datos que enseñar sin servidor.
        if (vivo) setPantalla(forzado.pantalla ?? (enLaPortada ? "portada" : "auth"));
      });
    return () => {
      vivo = false;
    };
  }, [forzado.pantalla]);

  // El botón de atrás del navegador. Sin esto, volver desde /app deja la URL en
  // «/» y la aplicación pintada: la barra de direcciones miente.
  useEffect(() => {
    const alNavegar = () => {
      const enLaPortada = window.location.pathname === "/";
      if (enLaPortada) setPantalla("portada");
      else if (!getToken()) setPantalla("auth");
    };
    window.addEventListener("popstate", alNavegar);
    return () => window.removeEventListener("popstate", alNavegar);
  }, []);

  // La hoja se recarga cuando el coach termina de hablar.
  //
  // Hace falta porque la conversación CAMBIA el estado que la hoja pinta: el
  // corredor cuenta de dónde parte, el coach llama a `create_plan`, y el plan
  // pasa a existir. Sin esto la pantalla se queda diciendo «todavía no hay
  // plan» junto a un coach que acaba de describirlo — lo vi en producción, y
  // es la clase de incoherencia que hace dudar de todo lo demás.
  //
  // Se recarga al terminar el turno y no en cada evento: durante el turno la
  // herramienta puede no haber corrido todavía, y pedirlo diez veces por
  // conversación es gasto sin información nueva.
  const [recargas, setRecargas] = useState(0);

  const enviarEvento = useCallback((evento: VoiceEvent) => {
    setMaquina((m) => transition(m, evento));
    if (evento.type === "COACH_ENDED") setRecargas((n) => n + 1);
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
    irA("/app");
    setPantalla(sesion.onboarded ? "hoja" : "onboarding");
  };

  const desdeLaPortada = (modo: "entrar" | "crear") => {
    irA("/app");
    setModoAuth(modo);
    setPantalla("auth");
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
  }, [pantalla, recargas]);

  if (pantalla === "cargando") {
    return (
      <div className="flex h-dvh items-center justify-center">
        <span className="label">{t("stConnecting")}</span>
      </div>
    );
  }

  if (pantalla === "portada") {
    return (
      <Landing
        onEnter={() => desdeLaPortada("entrar")}
        onCreate={() => desdeLaPortada("crear")}
      />
    );
  }

  if (pantalla === "auth") {
    return <Auth onReady={entrar} modoInicial={modoAuth} />;
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

  if (pantalla === "tecnica") {
    return <GaitUpload onClose={() => setPantalla("hoja")} />;
  }

  if (pantalla === "calendario") {
    return <Calendar onClose={() => setPantalla("hoja")} />;
  }

  if (pantalla === "perfil") {
    return (
      <Profile
        email={cuenta?.email ?? ""}
        nombre={nombre}
        meta={hoja?.goal}
        hasPlan={hoja?.has_plan ?? false}
        descargando={descargando}
        errorCsv={errorCsv}
        onDescargar={descargar}
        onSignOut={salirDeLaCuenta}
        onClose={() => setPantalla("hoja")}
      />
    );
  }

  return (
    <Main
        /* Con `?estado=…` se pintan los datos de ejemplo, que es para lo que
           existen. Sin él manda `/api/today`, y si no hay plan se enseña que no
           lo hay — nunca el plan de otra persona. */
        ctx={forzado.pantalla || forzado.voice || forzado.safety ? CTX_DEMO : hoja?.week ?? null}
        goal={hoja?.goal}
        hasPlan={hoja?.has_plan ?? true}
        session={
          forzado.pantalla || forzado.voice || forzado.safety
            ? { ...SESION_DEMO, why: t("demoWhy") }
            : hoja?.session
              ? { ...hoja.session, why: hoja.session.why || t("demoWhy") }
              : null
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
      onGait={() => setPantalla("tecnica")}
      onCalendar={() => setPantalla("calendario")}
      onProfile={() => setPantalla("perfil")}
      ttfaMs={ttfa}
      /* El sello MUESTRA sólo mientras las cifras no vengan del motor. En
         cuanto `/api/today` responde con un plan, desaparece — y si el corredor
         aún no tiene plan, se queda, porque entonces sí es un ejemplo. La regla
         2 del producto es que toda cifra viene del motor y SE NOTA. */
      /* El sello MUESTRA es del guion de capturas. En la aplicación de verdad
         no hace falta: sin plan ya no se enseña un ejemplo que haya que
         desmentir, se enseña que no hay plan. */
      specimen={Boolean(forzado.pantalla || forzado.voice || forzado.safety)}
    />
  );
}
