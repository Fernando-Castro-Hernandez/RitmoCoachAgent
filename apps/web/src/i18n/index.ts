/**
 * Textos de la interfaz, en español e inglés.
 *
 * Centralizados desde el primer componente y no traducidos al final: una cadena
 * suelta dentro de un componente es la que nadie encuentra cuando llega el
 * segundo idioma. El diccionario es la fuente, y TypeScript obliga a que el
 * inglés tenga exactamente las mismas claves que el español — si falta una, no
 * compila.
 *
 * El español es el original. El inglés es traducción, no al revés: el producto
 * se pensó en mexicano y el tono es lo primero que se pierde traduciendo hacia
 * atrás.
 */

import { create } from "zustand";

export const LOCALES = ["es", "en"] as const;
export type Locale = (typeof LOCALES)[number];

const es = {
  formCode: "FORMULARIO RIT-07",
  formCodeDemo: "FORMULARIO RIT-07 · MUESTRA",
  specimen: "MUESTRA",
  specimenWhy: "Datos de ejemplo. Tu plan aparece aquí en cuanto el motor lo genere.",
  brand: "Ritmo",

  week: "Semana",
  phase: "Fase",
  daysLeft: "faltan {n} días",
  raceOn: "{race}",

  phaseBase: "Base",
  phaseBuild: "Construcción",
  phasePeak: "Pico",
  phaseTaper: "Afinamiento",

  today: "Hoy",
  restDay: "Descanso",
  restWhy: "El descanso es parte del plan, no una pausa.",
  why: "Por qué esta sesión",
  zone: "Zona",
  perKm: "/km",
  km: "km",
  approxTime: "~{time}",

  kindLong: "Tirada larga",
  kindEasy: "Suave",
  kindTempo: "Tempo",
  kindIntervals: "Intervalos",

  you: "Tú",
  coach: "Coach",

  // Estados del orbe. Cada uno lleva señal textual además de visual: el
  // teléfono puede ir en el bolsillo.
  stIdle: "Toca para hablar",
  stMic: "Permite el micrófono",
  stConnecting: "Conectando…",
  stListening: "Escuchando…",
  stUserSpeaking: "Te escucho",
  stThinking: "Pensando…",
  stTool: "Revisando tu plan…",
  stSpeaking: "Ritmo está hablando",
  stInterruptible: "Toca para interrumpir",
  stError: "Algo falló",
  stSafety: "Alto",

  end: "Terminar",
  write: "Escribir",
  close: "Cerrar",
  startOver: "Empezar de cero",
  send: "Enviar",
  typeHere: "Escríbele a Ritmo",

  // Puerta de seguridad. La clave del código de color, siempre visible.
  keyTitle: "Estado",
  keyClear: "Puedes entrenar",
  keyCaution: "Entrena con ajuste",
  keyFlag: "No se prescribe",

  stampVoided: "ANULADO",
  referralTitle: "Derivación",
  ack: "Entendido, lo voy a revisar",
  ackHint: "Mantén pulsado para confirmar",

  micDenied: "Sin micrófono",
  micDeniedWhy: "Denegaste el permiso o el navegador lo bloqueó. Puedes escribirle igual.",
  offline: "Sin conexión",
  offlineWhy: "Revisa tu red. Lo que escribiste no se perdió.",
  retry: "Reintentar",

  // Onboarding
  onbGoal: "¿Para qué carrera entrenas?",
  onbDays: "¿Cuántos días a la semana puedes correr?",
  onbAbout: "Cuéntanos de ti",
  onbRef: "¿Tienes un tiempo de referencia?",
  onbInjury: "¿Alguna lesión en el último año?",
  onbWhen: "¿A qué hora entrenas?",
  raceDate: "Fecha de la carrera",
  raceDateOptional: "si ya tienes una",
  age: "Edad",
  weight: "Peso",
  height: "Estatura",
  years: "años",
  refDistance: "Distancia",
  refTime: "Tiempo",
  yes: "Sí",
  no: "No",
  skip: "Saltar",
  pickOne: "Elige una carrera para seguir",
  next: "Siguiente",
  finish: "Empezar",
  step: "Paso {n} de {total}",
  onbFootnote: "Sólo la carrera es obligatoria. Lo demás lo platicamos hablando.",

  // Captura del reloj
  uploadTitle: "Subir captura del reloj",
  uploadCta: "Elegir imagen",
  uploadReading: "Leyendo…",
  reviewTitle: "Revisa lo que leí",
  reviewHint: "Corrige lo que esté mal antes de guardarlo.",
  distance: "Distancia",
  duration: "Tiempo",
  pace: "Ritmo",
  heartRate: "Pulso",
  computed: "lo calcula Ritmo",
  computedWhy: "El ritmo sale de la distancia y el tiempo. Si lo cambias a mano, tu bitácora deja de cuadrar.",
  save: "Guardar en mi bitácora",
  cancel: "Cancelar",
  manualTitle: "Escríbelos tú",
  manualWhy: "Ahorita no puedo leer la imagen. Escribe los números y seguimos igual.",
  unreadable: "No pude leer: {fields}",
  checkThis: "Revisa este dato",

  // Descarga del plan
  exportCsv: "Descargar plan (CSV)",
  exportEmpty: "Todavía no hay plan que descargar.",
  exportFailed: "No pude armar el archivo. Vuelve a intentarlo.",

  // Técnica en vídeo
  gaitTitle: "Analizar técnica",
  gaitLead: "Que alguien te grabe corriendo de lado, unos {n} segundos. Con el teléfono basta.",
  gaitCta: "Elegir vídeo",
  gaitPrivacy: "El vídeo se queda en tu teléfono. Sólo viajan {n} fotogramas.",
  gaitExtracting: "Sacando fotogramas… {n} de {total}",
  gaitReading: "Mirando tu zancada…",
  gaitTooLong: "El vídeo dura de más. Máximo {n} segundos.",
  gaitNotVideo: "Eso no parece un vídeo. Elige un clip corto.",
  gaitFindings: "Lo que veo",
  gaitCue: "Señal para esta semana",
  gaitNoCue: "Nada que corregir hoy. Se te ve bien.",
  gaitBlocked: "Hoy no te toco la zancada: con molestia activa se cambia la carga donde no debe.",
  gaitDisclaimer:
    "Esto es observación, no un diagnóstico. Sin ángulos y sin medidas: un vídeo de teléfono no mide.",
  gaitAgain: "Probar con otro vídeo",
  gaitOk: "Se ve bien",
  gaitWatch: "A mirar",
  gaitFlag: "Marcado",
  obsFootStrike: "Cómo cae el pie",
  obsHipDrop: "Cadera",
  obsArmCrossover: "Brazos",
  obsTrunkLean: "Tronco",
  obsCadence: "Cadencia",
  demoWhy:
    "Construye la base aeróbica. Va lento a propósito: el objetivo es el tiempo de pie, no el ritmo.",
  demoReferral:
    "Eso que sientes merece que lo revise un profesional antes de que sigamos. No voy a darte entrenamiento hasta que lo veas.",

  // ── portada ──────────────────────────────────────────────────────
  formCodeLanding: "FORMULARIO RIT-00",
  landingTitle: "Un entrenador que te escucha y no se inventa los números.",
  landingSub:
    "Ritmo es un coach de running por voz, en tiempo real, de 5K a maratón. Le hablas como a una persona; los kilómetros y los ritmos los calcula un motor determinista, no el modelo.",
  landingCreate: "Crear cuenta",
  landingEnter: "Iniciar sesión",
  landingSampleLabel: "Así se ve tu sesión de hoy",
  landingSampleWhy:
    "Datos de ejemplo, y por eso lleva el sello. Dentro, cada cifra sale del motor y la pantalla lo dice cuando no.",
  landingR1: "Hablas, no escribes",
  landingR1Body:
    "Voz bidireccional de verdad: puedes interrumpirlo a media frase y te escucha. Está pensado para usarse con el teléfono en el bolsillo, antes de salir a correr y al volver.",
  landingR2: "Los números vienen de un motor, no del modelo",
  landingR2Body:
    "Distancias, ritmos y progresión los calcula un motor determinista con ocho reglas escritas y auditables. El modelo redacta y conversa; no calcula. Si no tiene el dato, lo pregunta.",
  landingR3: "Sabe cuándo callarse",
  landingR3Body:
    "Una puerta de seguridad se evalúa antes de que el coach diga una palabra. Si reportas dolor persistente o una señal de alarma, deja de prescribir entrenamiento y te manda con un profesional — y no es el prompt quien lo decide: el código le quita las herramientas.",
  landingNotMedical:
    "Ritmo no diagnostica ni sustituye a un profesional de la salud. Es un filtro conservador que decide cuándo un coach automático debe callarse.",
  landingFooter: "PRUEBA TÉCNICA · ADIVOR",

  fixFields: "Corrige lo marcado para seguir",
  otherDistance: "Otra distancia",
  otherDistanceSub: "la que tú quieras",
  otherDistanceLabel: "¿Cuántos kilómetros?",
  nearestTemplate: "Te prepararé con el plan de {plan}, que es el más cercano de los que el motor tiene validados.",
  badNumber: "Sólo números. Por ejemplo: 10 o 10.5",
  badTime: "Formato mm:ss o hh:mm:ss. Por ejemplo: 50:00",
  refNeedsBoth: "Hacen falta los dos para calcular tu ritmo, o ninguno.",
  goal: "Meta",
  plan: "Plan",
  planPending: "Sale de la conversación",
  noPlanTitle: "Todavía no hay plan",
  noPlanWhy:
    "Toca el orbe y cuéntame de dónde partes. Con eso el motor arma el plan — y cada cifra que veas aquí saldrá de él.",

  // ── cuentas ──────────────────────────────────────────────────────
  formCodeAuth: "FORMULARIO RIT-01 · ALTA",
  authEmail: "Correo",
  authPassword: "Contraseña",
  authEnter: "Entrar",
  authCreate: "Crear cuenta",
  authWorking: "Un momento…",
  authNoAccount: "No tengo cuenta todavía",
  authHaveAccount: "Ya tengo cuenta",
  authNewHint: "Crea tu cuenta y empezamos con unas preguntas.",
  authBackHint: "Entra y seguimos donde lo dejamos.",
  authMinChars: "Mínimo {n} caracteres",
  authFailed: "No pude entrar. Inténtalo otra vez.",
  logout: "Cerrar sesión",

  // ── Telegram ─────────────────────────────────────────────────────
  tgTitle: "Telegram",
  tgWhy: "Te escribo la sesión del día por la mañana y te busco si algo va mal.",
  tgConnect: "Conectar Telegram",
  tgOpening: "Abriendo Telegram…",
  tgLinked: "CONECTADO",
  tgLinkedWhy: "Ya te escribo por aquí. Puedes silenciarme desde Telegram cuando quieras.",
  tgNoBot: "El canal de Telegram no está disponible en este servidor.",
  tgError: "No pude comprobar tu Telegram ahorita.",
} as const;

type Dict = Record<keyof typeof es, string>;

const en: Dict = {
  formCode: "FORM RIT-07",
  formCodeDemo: "FORM RIT-07 · SPECIMEN",
  specimen: "SPECIMEN",
  specimenWhy: "Example data. Your plan appears here as soon as the engine generates it.",
  brand: "Ritmo",

  week: "Week",
  phase: "Phase",
  daysLeft: "{n} days out",
  raceOn: "{race}",

  phaseBase: "Base",
  phaseBuild: "Build",
  phasePeak: "Peak",
  phaseTaper: "Taper",

  today: "Today",
  restDay: "Rest",
  restWhy: "Rest is part of the plan, not a pause in it.",
  why: "Why this session",
  zone: "Zone",
  perKm: "/km",
  km: "km",
  approxTime: "~{time}",

  kindLong: "Long run",
  kindEasy: "Easy",
  kindTempo: "Tempo",
  kindIntervals: "Intervals",

  you: "You",
  coach: "Coach",

  stIdle: "Tap to talk",
  stMic: "Allow the microphone",
  stConnecting: "Connecting…",
  stListening: "Listening…",
  stUserSpeaking: "I hear you",
  stThinking: "Thinking…",
  stTool: "Checking your plan…",
  stSpeaking: "Ritmo is talking",
  stInterruptible: "Tap to interrupt",
  stError: "Something broke",
  stSafety: "Stop",

  end: "End",
  write: "Type",
  close: "Close",
  startOver: "Start over",
  send: "Send",
  typeHere: "Write to Ritmo",

  keyTitle: "Status",
  keyClear: "Clear to train",
  keyCaution: "Train, adjusted",
  keyFlag: "No prescription",

  stampVoided: "VOIDED",
  referralTitle: "Referral",
  ack: "Understood, I'll get it looked at",
  ackHint: "Press and hold to confirm",

  micDenied: "No microphone",
  micDeniedWhy: "You denied the permission or the browser blocked it. You can still type.",
  offline: "Offline",
  offlineWhy: "Check your network. What you typed was not lost.",
  retry: "Try again",

  onbGoal: "Which race are you training for?",
  onbDays: "How many days a week can you run?",
  onbAbout: "Tell us about you",
  onbRef: "Any recent time to go on?",
  onbInjury: "Any injury in the last year?",
  onbWhen: "When do you train?",
  raceDate: "Race date",
  raceDateOptional: "if you have one",
  age: "Age",
  weight: "Weight",
  height: "Height",
  years: "years",
  refDistance: "Distance",
  refTime: "Time",
  yes: "Yes",
  no: "No",
  skip: "Skip",
  pickOne: "Pick a race to continue",
  next: "Next",
  finish: "Start",
  step: "Step {n} of {total}",
  onbFootnote: "Only the race is required. The rest we'll talk through.",

  uploadTitle: "Upload a watch screenshot",
  uploadCta: "Choose image",
  uploadReading: "Reading…",
  reviewTitle: "Check what I read",
  reviewHint: "Fix anything wrong before saving it.",
  distance: "Distance",
  duration: "Time",
  pace: "Pace",
  heartRate: "Heart rate",
  computed: "Ritmo computes this",
  computedWhy: "Pace comes from distance and time. Edit it by hand and your log stops adding up.",
  save: "Save to my log",
  cancel: "Cancel",
  manualTitle: "Type them in",
  manualWhy: "I can't read the image right now. Type the numbers and we carry on.",
  unreadable: "Couldn't read: {fields}",
  checkThis: "Check this one",

  exportCsv: "Download plan (CSV)",
  exportEmpty: "There is no plan to download yet.",
  exportFailed: "I couldn't build the file. Try again.",

  gaitTitle: "Analyse form",
  gaitLead: "Have someone film you running from the side, about {n} seconds. A phone is plenty.",
  gaitCta: "Choose video",
  gaitPrivacy: "The video stays on your phone. Only {n} frames travel.",
  gaitExtracting: "Pulling frames… {n} of {total}",
  gaitReading: "Looking at your stride…",
  gaitTooLong: "That video is too long. {n} seconds max.",
  gaitNotVideo: "That doesn't look like a video. Pick a short clip.",
  gaitFindings: "What I see",
  gaitCue: "Cue for this week",
  gaitNoCue: "Nothing to fix today. You look good.",
  gaitBlocked: "Not touching your stride today: with a niggle, changing form moves load the wrong way.",
  gaitDisclaimer:
    "This is observation, not a diagnosis. No angles, no measurements: a phone video doesn't measure.",
  gaitAgain: "Try another video",
  gaitOk: "Looks good",
  gaitWatch: "Watch",
  gaitFlag: "Flagged",
  obsFootStrike: "Foot strike",
  obsHipDrop: "Hip",
  obsArmCrossover: "Arms",
  obsTrunkLean: "Trunk",
  obsCadence: "Cadence",
  demoWhy: "Builds your aerobic base. It is slow on purpose: the goal is time on feet, not pace.",
  demoReferral:
    "What you are describing deserves a professional look before we carry on. I am not giving you training until you get it checked.",

  formCodeLanding: "FORM RIT-00",
  landingTitle: "A coach that listens to you and does not make the numbers up.",
  landingSub:
    "Ritmo is a real-time voice running coach, from 5K to marathon. You talk to it like a person; the kilometres and paces are worked out by a deterministic engine, not by the model.",
  landingCreate: "Create account",
  landingEnter: "Sign in",
  landingSampleLabel: "This is what today looks like",
  landingSampleWhy:
    "Sample data, which is why it carries the stamp. Inside, every figure comes from the engine and the screen says so when it does not.",
  landingR1: "You talk, you do not type",
  landingR1Body:
    "Real bidirectional voice: you can cut in mid-sentence and it listens. Built to be used with the phone in your pocket, before a run and after it.",
  landingR2: "The numbers come from an engine, not the model",
  landingR2Body:
    "Distances, paces and progression are computed by a deterministic engine with eight written, auditable rules. The model talks; it does not calculate. If it lacks a figure, it asks.",
  landingR3: "It knows when to stop talking",
  landingR3Body:
    "A safety gate is evaluated before the coach says a word. If you report persistent pain or a red flag, it stops prescribing training and refers you to a professional — and the prompt does not decide that: the code takes the tools away.",
  landingNotMedical:
    "Ritmo does not diagnose and is not a substitute for a health professional. It is a conservative filter that decides when an automated coach should stop talking.",
  landingFooter: "TECHNICAL TEST · ADIVOR",

  fixFields: "Fix what is marked to continue",
  otherDistance: "Another distance",
  otherDistanceSub: "whichever you like",
  otherDistanceLabel: "How many kilometres?",
  nearestTemplate: "I will prepare you with the {plan} plan, the closest one the engine has validated.",
  badNumber: "Numbers only. For example: 10 or 10.5",
  badTime: "Format mm:ss or hh:mm:ss. For example: 50:00",
  refNeedsBoth: "I need both to work out your pace, or neither.",
  goal: "Goal",
  plan: "Plan",
  planPending: "Comes out of the conversation",
  noPlanTitle: "No plan yet",
  noPlanWhy:
    "Tap the orb and tell me where you are starting from. The engine builds the plan from that — and every figure you see here will come from it.",

  formCodeAuth: "FORM RIT-01 · SIGN UP",
  authEmail: "Email",
  authPassword: "Password",
  authEnter: "Sign in",
  authCreate: "Create account",
  authWorking: "One moment…",
  authNoAccount: "I do not have an account yet",
  authHaveAccount: "I already have an account",
  authNewHint: "Create your account and we start with a few questions.",
  authBackHint: "Sign in and we pick up where we left off.",
  authMinChars: "At least {n} characters",
  authFailed: "I could not sign you in. Try again.",
  logout: "Sign out",

  tgTitle: "Telegram",
  tgWhy: "I send you the day's session in the morning, and I check on you if something is off.",
  tgConnect: "Connect Telegram",
  tgOpening: "Opening Telegram…",
  tgLinked: "CONNECTED",
  tgLinkedWhy: "I write to you here now. You can mute me from Telegram whenever you want.",
  tgNoBot: "The Telegram channel is not available on this server.",
  tgError: "I could not check your Telegram right now.",
};

const DICTS: Record<Locale, Dict> = { es, en };

/** El idioma se recuerda: cambiarlo en cada visita es un impuesto. */
const GUARDADO = "ritmo.locale";

function inicial(): Locale {
  if (typeof window === "undefined") return "es";
  const guardado = window.localStorage.getItem(GUARDADO);
  if (guardado === "es" || guardado === "en") return guardado;
  return navigator.language?.toLowerCase().startsWith("en") ? "en" : "es";
}

interface LocaleState {
  locale: Locale;
  setLocale: (l: Locale) => void;
}

export const useLocale = create<LocaleState>((set) => ({
  locale: inicial(),
  setLocale: (locale) => {
    window.localStorage.setItem(GUARDADO, locale);
    document.documentElement.lang = locale;
    set({ locale });
  },
}));

export type TextKey = keyof Dict;

/**
 * Traduce e interpola. `t("daysLeft", { n: 63 })` → «faltan 63 días».
 *
 * Devuelve la clave misma si falta la traducción, en vez de una cadena vacía:
 * un hueco silencioso en la interfaz es más difícil de encontrar que un
 * `daysLeft` a la vista.
 */
export function translate(
  locale: Locale,
  key: TextKey,
  vars?: Record<string, string | number>,
): string {
  const plantilla = DICTS[locale][key] ?? key;
  if (!vars) return plantilla;
  return plantilla.replace(/\{(\w+)\}/g, (_, nombre: string) =>
    nombre in vars ? String(vars[nombre]) : `{${nombre}}`,
  );
}

export function useT() {
  const locale = useLocale((s) => s.locale);
  return {
    locale,
    t: (key: TextKey, vars?: Record<string, string | number>) => translate(locale, key, vars),
  };
}
