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
  demoWhy:
    "Construye la base aeróbica. Va lento a propósito: el objetivo es el tiempo de pie, no el ritmo.",
  demoReferral:
    "Eso que sientes merece que lo revise un profesional antes de que sigamos. No voy a darte entrenamiento hasta que lo veas.",
} as const;

type Dict = Record<keyof typeof es, string>;

const en: Dict = {
  formCode: "FORM RIT-07",
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
  demoWhy: "Builds your aerobic base. It is slow on purpose: the goal is time on feet, not pace.",
  demoReferral:
    "What you are describing deserves a professional look before we carry on. I am not giving you training until you get it checked.",
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
