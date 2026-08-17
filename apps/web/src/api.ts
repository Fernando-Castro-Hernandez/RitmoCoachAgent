/**
 * Identidad y cliente de la API.
 *
 * **Hay cuentas.** Correo, contraseña y un JWT. Sustituye al UUID del navegador
 * que había antes, y el cambio de fondo no es «ahora hay login»: es que el
 * `user_id` deja de viajar en la URL. Antes `GET /api/profile/<lo-que-sea>`
 * contestaba con el perfil de cualquiera; ahora no hay dónde poner el ajeno,
 * porque el backend lo saca del token firmado.
 *
 * El token vive en `localStorage` y no en una cookie `httpOnly`, que resistiría
 * mejor un XSS. La razón es concreta: el WebSocket de voz necesita el token al
 * abrirse y los navegadores no dejan poner cabeceras ahí, así que el JavaScript
 * tiene que poder leerlo de todas formas. Guardarlo en dos sitios sería
 * complejidad sin beneficio. Queda anotado como deuda consciente, no olvidada.
 *
 * Lo que se perdió con el cambio, y hay que decirlo: ya no basta con abrir la
 * URL para entrar. Un evaluador tiene que registrarse —quince segundos— o usar
 * la cuenta de demostración que siembra `scripts/seed_demo.py`.
 */

const CLAVE_TOKEN = "ritmo.token";

export interface Cuenta {
  id: string;
  email: string;
}

export interface Sesion {
  token: string;
  user: Cuenta;
  /**
   * Si ya completó el carrusel. Lo decide el SERVIDOR, no el navegador: si
   * viviera en `localStorage`, entrar desde otro teléfono le repetiría el
   * onboarding a alguien que ya lo hizo.
   */
  onboarded: boolean;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

export function getToken(): string | null {
  return window.localStorage.getItem(CLAVE_TOKEN);
}

export function setToken(token: string): void {
  window.localStorage.setItem(CLAVE_TOKEN, token);
}

/** Cierra la sesión y vuelve a la entrada. */
export function logout(): void {
  window.localStorage.removeItem(CLAVE_TOKEN);
  window.location.reload();
}

const RUTAS_DE_ENTRADA = ["/api/auth/login", "/api/auth/register"];

/**
 * Toda petición pasa por aquí, y por eso el token se pone en un solo sitio.
 *
 * Un 401 no se propaga como un error cualquiera: borra el token y recarga. Es
 * la única respuesta útil a «tu sesión venció» — dejar la aplicación andando
 * con un token muerto produce una pantalla que falla en cada acción sin decir
 * por qué. Se excluyen las rutas de entrada: ahí un 401 significa «contraseña
 * incorrecta» y tiene que llegar al formulario para poder mostrarse.
 */
async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const token = getToken();
  const cabeceras = new Headers(init?.headers);
  if (token) cabeceras.set("Authorization", `Bearer ${token}`);

  const r = await fetch(ruta, { ...init, headers: cabeceras });

  if (r.status === 401 && !RUTAS_DE_ENTRADA.some((x) => ruta.startsWith(x))) {
    window.localStorage.removeItem(CLAVE_TOKEN);
    window.location.reload();
  }

  if (!r.ok) {
    let detalle = "";
    try {
      detalle = ((await r.json()) as { detail?: string }).detail ?? "";
    } catch {
      // Un cuerpo que no es JSON no puede tumbar el manejo del error.
    }
    throw new ApiError(detalle || `${init?.method ?? "GET"} ${ruta}`, r.status);
  }
  return (await r.json()) as T;
}

// ── cuentas ──────────────────────────────────────────────────────────

function credenciales(ruta: string, email: string, password: string) {
  return pedir<Sesion>(ruta, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
}

export function register(email: string, password: string) {
  return credenciales("/api/auth/register", email, password);
}

export function login(email: string, password: string) {
  return credenciales("/api/auth/login", email, password);
}

/** Confirma al arrancar que el token guardado sigue valiendo. */
export function me() {
  return pedir<{ user: Cuenta; onboarded: boolean }>("/api/auth/me");
}

// ── perfil ───────────────────────────────────────────────────────────

export interface HardProfile {
  goal_distance: string;
  race_date?: string | null;
  days_per_week?: number | null;
  age?: number | null;
  weight_kg?: number | null;
  height_cm?: number | null;
  reference_distance_km?: number | null;
  reference_time_sec?: number | null;
  timezone?: string | null;
}

export interface ProfileResponse {
  profile: Record<string, unknown>;
  completeness: number;
  carousel_done: boolean;
  next_voice_question: string | null;
}

export async function fetchProfile(): Promise<ProfileResponse | null> {
  try {
    return await pedir<ProfileResponse>("/api/profile");
  } catch (e) {
    // 404 no es un fallo: es una cuenta que todavía no llenó el carrusel.
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function saveProfile(perfil: HardProfile) {
  return pedir<{ ok: boolean; next_voice_question: string | null }>("/api/profile", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(perfil),
  });
}

// ── visión ───────────────────────────────────────────────────────────

export interface WorkoutExtraction {
  distance_km: number | null;
  duration_sec: number | null;
  avg_pace_sec_per_km: number | null;
  avg_hr: number | null;
  confidence: "high" | "medium" | "low";
  unreadable_fields: string[];
}

export interface ProposedSession {
  distance_km: number;
  duration_sec: number;
  pace_sec_per_km: number;
  avg_hr: number | null;
  needs_confirmation: boolean;
  discrepancy_flag: boolean;
  source: string;
  notes: string;
}

export interface VisionResponse {
  ok: boolean;
  mode?: "manual";
  reason?: string;
  fields?: string[];
  extraction: WorkoutExtraction | null;
  proposed: ProposedSession | null;
  pace_is_computed?: boolean;
}

export function readWatchScreenshot(archivo: File) {
  const form = new FormData();
  form.append("file", archivo);
  return pedir<VisionResponse>("/api/vision/workout", { method: "POST", body: form });
}

// ── técnica en vídeo ─────────────────────────────────────────────────

export interface GaitFinding {
  observable:
    | "foot_strike_position"
    | "hip_drop"
    | "arm_crossover"
    | "trunk_lean"
    | "cadence_impression";
  assessment: "ok" | "watch" | "flag";
  note: string;
}

export interface GaitResponse {
  ok: boolean;
  reason?: string;
  findings: GaitFinding[];
  /** Sale de la biblioteca curada del motor, nunca del texto del modelo. */
  cue: { id: string; category: string; text: string } | null;
  /** Por qué no hay señal, cuando no la hay. Sin esto la pantalla no puede
   *  distinguir «se te ve bien» de «hoy no te corrijo porque te duele algo». */
  cue_blocked_by_safety?: boolean;
  safety?: "green" | "amber" | "red";
}

/** Sube los fotogramas ya extraídos. El vídeo se queda en el teléfono. */
export function analizarTecnica(fotogramas: Blob[]) {
  const form = new FormData();
  fotogramas.forEach((f, i) => form.append("files", f, `f${i}.jpg`));
  return pedir<GaitResponse>("/api/vision/gait", { method: "POST", body: form });
}

// ── Telegram ─────────────────────────────────────────────────────────

export interface TelegramLink {
  /** `null` cuando no hay bot configurado en el servidor. La pantalla lo dice
   *  en vez de ofrecer un enlace que no lleva a ninguna parte. */
  deep_link: string | null;
  expires_in_s: number;
  configured: boolean;
}

export function crearEnlaceTelegram() {
  return pedir<TelegramLink>("/api/telegram/link", { method: "POST" });
}

export function estadoTelegram() {
  return pedir<{ linked: boolean; bot_configured: boolean }>("/api/telegram/status");
}

// ── la hoja ──────────────────────────────────────────────────────────

export interface TodaySheet {
  /** La meta que eligió el corredor, ya legible. Viaja con plan y sin él: es lo
   *  que la hoja enseña mientras el motor no ha generado nada. */
  goal: string;
  /** Ya traducido al vocabulario de la interfaz: clear / caution / flag. */
  safety: "clear" | "caution" | "flag";
  safety_reason: string;
  referral: string | null;
  has_plan: boolean;
  week: {
    week: number;
    totalWeeks: number;
    phase: "base" | "construccion" | "pico" | "taper";
    race: string;
    daysLeft: number | null;
  } | null;
  /** `null` en rojo y en día de descanso. En rojo NO viaja: la pantalla no
   *  puede enseñar una prescripción que no tiene. */
  session: {
    kind: "largo" | "suave" | "tempo" | "intervalos";
    distanceKm: number;
    pace: string | null;
    effort: string;
    zone: number;
    durationLabel: string;
    why: string;
  } | null;
  rest_day: boolean;
}

export function fetchToday() {
  return pedir<TodaySheet>("/api/today");
}

// ── plan ─────────────────────────────────────────────────────────────

/**
 * La descarga del CSV no puede ser un `<a href>`: necesita la cabecera del
 * token y un enlace no la lleva. Se pide, se convierte en blob y se dispara.
 */
export async function descargarPlanCsv(): Promise<void> {
  const r = await fetch("/api/plan/export.csv", {
    headers: { Authorization: `Bearer ${getToken() ?? ""}` },
  });
  if (!r.ok) throw new ApiError("no hay plan que exportar", r.status);

  const url = URL.createObjectURL(await r.blob());
  const a = document.createElement("a");
  a.href = url;
  a.download = "plan-ritmo.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// ── formato ──────────────────────────────────────────────────────────

/** «47:18» → 2838. Devuelve null si no se entiende. */
export function parseDuration(texto: string): number | null {
  const partes = texto.trim().split(":").map(Number);
  if (partes.some((n) => !Number.isFinite(n) || n < 0)) return null;
  if (partes.length === 2) return partes[0] * 60 + partes[1];
  if (partes.length === 3) return partes[0] * 3600 + partes[1] * 60 + partes[2];
  return null;
}

/** 2838 → «47:18». */
export function formatDuration(segundos: number): string {
  const h = Math.floor(segundos / 3600);
  const m = Math.floor((segundos % 3600) / 60);
  const s = segundos % 60;
  const dosDigitos = (n: number) => String(n).padStart(2, "0");
  return h > 0 ? `${h}:${dosDigitos(m)}:${dosDigitos(s)}` : `${m}:${dosDigitos(s)}`;
}

/** 337 → «5:37». El ritmo siempre se muestra formateado, nunca en segundos. */
export function formatPace(segundosPorKm: number): string {
  return `${Math.floor(segundosPorKm / 60)}:${String(segundosPorKm % 60).padStart(2, "0")}`;
}
