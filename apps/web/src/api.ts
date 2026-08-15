/**
 * Identidad y cliente de la API.
 *
 * **No hay cuentas.** Ni registro, ni contraseña, ni correo. La identidad es un
 * UUID que vive en el navegador, y el backend confía en él.
 *
 * Es una decisión de alcance, no un descuido, y conviene poder defenderla: la
 * autenticación no prueba nada de la tesis del producto —que el coach pregunte
 * antes de prescribir y que los números salgan de un motor— y sí cuesta horas
 * que hacen falta en la voz. Queda declarado en el README como fuera de alcance.
 *
 * La consecuencia buena: cualquiera que abra la URL entra como usuario nuevo y
 * recorre el primer arranque completo, que es exactamente lo que un evaluador
 * tiene que poder hacer.
 *
 * La consecuencia mala, y hay que decirla: borrar los datos del navegador borra
 * al corredor. No hay recuperación porque no hay a dónde recuperar.
 */

const CLAVE_ID = "ritmo.userId";

export function getUserId(): string {
  let id = window.localStorage.getItem(CLAVE_ID);
  if (!id) {
    id = crypto.randomUUID();
    window.localStorage.setItem(CLAVE_ID, id);
  }
  return id;
}

/** Borra la identidad y todo lo local. Para volver a ver el primer arranque. */
export function startOver(): void {
  window.localStorage.removeItem(CLAVE_ID);
  window.localStorage.removeItem("ritmo.onboarded");
  window.location.reload();
}

export function markOnboarded(): void {
  window.localStorage.setItem("ritmo.onboarded", "1");
}

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

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
  ) {
    super(message);
  }
}

async function pedir<T>(ruta: string, init?: RequestInit): Promise<T> {
  const r = await fetch(ruta, init);
  if (!r.ok) {
    throw new ApiError(`${init?.method ?? "GET"} ${ruta}`, r.status);
  }
  return (await r.json()) as T;
}

export async function fetchProfile(userId: string): Promise<ProfileResponse | null> {
  try {
    return await pedir<ProfileResponse>(`/api/profile/${userId}`);
  } catch (e) {
    // 404 no es un fallo: es un corredor que todavía no existe.
    if (e instanceof ApiError && e.status === 404) return null;
    throw e;
  }
}

export function saveProfile(userId: string, perfil: HardProfile) {
  return pedir<{ ok: boolean; next_voice_question: string | null }>(`/api/profile/${userId}`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(perfil),
  });
}

export function readWatchScreenshot(userId: string, archivo: File) {
  const form = new FormData();
  form.append("user_id", userId);
  form.append("file", archivo);
  return pedir<VisionResponse>("/api/vision/workout", { method: "POST", body: form });
}

export function planCsvUrl(userId: string): string {
  return `/api/plan/${userId}/export.csv`;
}

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
