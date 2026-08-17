/**
 * Subir la captura del reloj.
 *
 * Esto sustituye a la integración con Garmin y Strava: cero OAuth, cero
 * secretos de terceros, y funciona con cualquier reloj que tenga pantalla.
 *
 * Dos reglas del producto viven en esta pantalla y no se negocian:
 *
 * 1. **Nada se guarda sin que lo vea.** Lo que el modelo leyó se muestra en
 *    campos editables y hay que confirmarlo. Una cifra mal leída que entra sola
 *    a la bitácora contamina la progresión, y la progresión es el producto.
 *
 * 2. **El ritmo no se edita.** Sale de la distancia y el tiempo, lo calcula el
 *    motor, y se muestra etiquetado como calculado. Si el corredor lo corrigiera
 *    a mano, su bitácora dejaría de cuadrar consigo misma.
 *
 * Y si no hay modelo disponible, la pantalla no muere: se convierte en captura
 * manual. La visión es una comodidad, no un requisito — escribir cuatro números
 * sigue siendo más rápido que registrar una aplicación en Strava.
 */

import { useRef, useState } from "react";

import {
  type ProposedSession,
  type VisionResponse,
  formatDuration,
  formatPace,
  guardarSesion,
  parseDuration,
  readWatchScreenshot,
} from "../api";
import { RegistrationMark } from "../components/Sheet";
import { useT } from "../i18n";

type Fase = "elegir" | "leyendo" | "revisar" | "manual";

interface Props {
  onClose: () => void;
  onSave: (s: { distanceKm: number; durationSec: number; paceSecPerKm: number }) => void;
}

/** Campo editable de la revisión. */
function Campo({
  label,
  value,
  onChange,
  suffix,
  warn,
  inputMode = "decimal",
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  suffix?: string;
  warn?: string;
  inputMode?: "decimal" | "numeric" | "text";
}) {
  return (
    <label className="block px-4 py-3">
      <span className="label">{label}</span>
      <span
        className={`mt-1 flex items-baseline gap-2 border-b ${warn ? "border-caution" : "border-ink"}`}
      >
        <input
          value={value}
          inputMode={inputMode}
          onChange={(e) => onChange(e.target.value)}
          className="fig min-w-0 flex-1 bg-transparent py-2 text-2xl focus:outline-none"
        />
        {suffix && <span className="label shrink-0">{suffix}</span>}
      </span>
      {warn && <span className="label mt-1 block !text-caution">{warn}</span>}
    </label>
  );
}

export function Upload({ onClose, onSave }: Props) {
  const { t } = useT();
  const [fase, setFase] = useState<Fase>("elegir");
  const [respuesta, setRespuesta] = useState<VisionResponse | null>(null);
  const [km, setKm] = useState("");
  const [tiempo, setTiempo] = useState("");
  const [pulso, setPulso] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  const archivo = useRef<HTMLInputElement>(null);

  const cargarPropuesta = (p: ProposedSession) => {
    setKm(String(p.distance_km));
    setTiempo(formatDuration(p.duration_sec));
    setPulso(p.avg_hr === null ? "" : String(p.avg_hr));
  };

  const elegir = async (f: File) => {
    setFase("leyendo");
    setError("");
    try {
      const r = await readWatchScreenshot(f);
      setRespuesta(r);
      if (r.mode === "manual" || !r.proposed) {
        setFase("manual");
        return;
      }
      cargarPropuesta(r.proposed);
      setFase("revisar");
    } catch {
      // Ni siquiera llegó al modelo. Sigue habiendo camino: teclearlo.
      setRespuesta(null);
      setFase("manual");
    }
  };

  // El ritmo se recalcula en vivo desde lo que el usuario tenga escrito. Es la
  // misma fórmula que el motor, y por eso el campo no se puede editar: mostrar
  // uno editable invitaría a romper la coherencia de la bitácora.
  const kmNum = Number(km.replace(",", "."));
  const segNum = parseDuration(tiempo);
  const ritmo =
    Number.isFinite(kmNum) && kmNum > 0 && segNum && segNum > 0
      ? Math.round(segNum / kmNum)
      : null;

  const guardable = ritmo !== null && ritmo >= 120 && ritmo <= 1200;

  /**
   * Guardar de verdad.
   *
   * **Antes esto sólo pintaba una línea en la transcripción.** El corredor veía
   * su entrenamiento aparecer, creía haberlo registrado, y no había llegado a
   * ninguna parte: ni el motor progresaba con él, ni el coach se enteraba. El
   * mismo entrenamiento contado hablando sí se guardaba, así que el producto
   * tenía dos memorias y una era falsa.
   *
   * Se cierra sólo si el servidor confirmó. Cerrar antes es lo que hacía que un
   * fallo de red se viera exactamente igual que un guardado correcto.
   */
  const guardar = async () => {
    if (ritmo === null || segNum === null) return;
    setGuardando(true);
    setError("");
    try {
      const { session } = await guardarSesion({
        distanceKm: kmNum,
        durationSec: segNum,
        // El que el modelo creyó leer, para que el motor pueda marcar la
        // discrepancia. NO es el que se guarda.
        reportedPaceSecPerKm: respuesta?.extraction?.avg_pace_sec_per_km ?? null,
        avgHr: pulso.trim() ? Number(pulso) : null,
        source: fase === "manual" ? "manual" : "vision",
      });
      onSave({
        distanceKm: session.distance_km,
        durationSec: session.duration_sec,
        // El ritmo que se enseña es el que devolvió el motor, no el de aquí.
        paceSecPerKm: session.pace_sec_per_km,
      });
    } catch {
      setError(t("saveFailed"));
      setGuardando(false);
    }
  };
  const dudoso = respuesta?.extraction?.confidence !== "high";
  const ilegibles = respuesta?.extraction?.unreadable_fields ?? [];

  return (
    <div className="mx-auto flex h-dvh max-w-lg flex-col">
      <header className="flex items-center justify-between border-b border-ink px-4 py-3">
        <button
          type="button"
          onClick={onClose}
          className="label flex items-center gap-1.5 transition-colors hover:text-ink"
        >
          {/* Icono dibujado, no un glifo Unicode: un carácter tipográfico
              hereda la métrica de la fuente y no la del sistema de iconos. */}
          <svg
            aria-hidden="true"
            viewBox="0 0 16 16"
            className="h-3.5 w-3.5"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.25"
          >
            <path d="M10 2 4 8l6 6" />
          </svg>
          {t("cancel")}
        </button>
        <h1 className="text-center text-[0.9375rem] font-semibold">
          {fase === "manual" ? t("manualTitle") : t("uploadTitle")}
        </h1>
        <RegistrationMark />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {fase === "elegir" && (
          <>
            {/* El estado vacío lleva la gramática de la hoja: campos reglados
                esperando su valor. Un rectángulo punteado sobre papel en blanco
                era una página de subida genérica con el fondo del producto. */}
            <div className="divide-y divide-ink-15 border-b border-ink-15">
              {[t("distance"), t("duration"), t("heartRate")].map((etiqueta) => (
                <div key={etiqueta} className="px-4 py-3">
                  <span className="label">{etiqueta}</span>
                  <div className="mt-1 flex items-baseline gap-2 border-b border-ink-15">
                    <span className="fig py-2 text-2xl text-ink-30" aria-hidden="true">
                      —
                    </span>
                  </div>
                </div>
              ))}
            </div>

            <div className="px-4 py-8">
              <p className="text-[0.9375rem] text-ink-70">
                Garmin, Strava, Apple Watch, Coros — el que sea. Con que tenga
                pantalla, sirve.
              </p>
              <button
                type="button"
                onClick={() => archivo.current?.click()}
                className="mt-5 min-h-13 w-full bg-proof px-6 text-[1.0625rem] font-medium text-paper transition-colors hover:bg-proof-deep"
              >
                {t("uploadCta")}
              </button>
              <button
                type="button"
                onClick={() => setFase("manual")}
                className="label mt-3 w-full border border-ink-15 py-3 text-center transition-colors hover:border-ink"
              >
                {t("manualTitle")}
              </button>
            </div>

            <div className="flex items-center justify-between border-t border-ink-15 px-4 py-3">
              <span className="label">RIT-09</span>
              <RegistrationMark />
            </div>
          </>
        )}

        {fase === "leyendo" && (
          <div className="flex flex-col items-center gap-4 px-4 py-20">
            <span className="h-3 w-3 animate-pulse bg-proof" aria-hidden="true" />
            <p className="label">{t("uploadReading")}</p>
          </div>
        )}

        {(fase === "revisar" || fase === "manual") && (
          <>
            <div className="border-b border-ink-15 px-4 py-4">
              <h2 className="text-xl font-semibold">
                {fase === "manual" ? t("manualTitle") : t("reviewTitle")}
              </h2>
              <p className="mt-1 text-[0.875rem] text-ink-70">
                {fase === "manual" ? respuesta?.reason ?? t("manualWhy") : t("reviewHint")}
              </p>
            </div>

            <div className="divide-y divide-ink-15">
              <Campo
                label={t("distance")}
                value={km}
                onChange={setKm}
                suffix="km"
                warn={ilegibles.includes("distance_km") ? t("checkThis") : undefined}
              />
              <Campo
                label={t("duration")}
                value={tiempo}
                onChange={setTiempo}
                inputMode="text"
                warn={ilegibles.includes("duration_sec") ? t("checkThis") : undefined}
              />

              {/* Regla 2 hecha interfaz: el ritmo se muestra, no se edita. */}
              <div className="bg-ink-08/60 px-4 py-3">
                <span className="label">{t("pace")}</span>
                <p className="mt-1 flex items-baseline gap-2">
                  <output className="text-2xl">{ritmo === null ? "—" : formatPace(ritmo)}</output>
                  <span className="label">{t("perKm")}</span>
                  <span className="label ml-auto !text-proof">{t("computed")}</span>
                </p>
                <p className="mt-1 text-[0.8125rem] text-ink-70">{t("computedWhy")}</p>
              </div>

              <Campo
                label={t("heartRate")}
                value={pulso}
                onChange={setPulso}
                suffix="ppm"
                inputMode="numeric"
                warn={ilegibles.includes("avg_hr") ? t("checkThis") : undefined}
              />
            </div>

            {respuesta?.proposed?.discrepancy_flag && (
              <p className="mx-4 mt-4 border-l-2 border-caution bg-caution/8 px-3 py-2 text-[0.875rem]">
                {t("computedWhy")}
              </p>
            )}

            {dudoso && fase === "revisar" && ilegibles.length > 0 && (
              <p className="mx-4 mt-4 text-[0.875rem] text-ink-70">
                {t("unreadable", { fields: ilegibles.join(", ") })}
              </p>
            )}

            {error && (
              <p role="alert" className="mx-4 mt-4 border-l-2 border-flag px-3 py-2 text-[0.875rem]">
                {error}
              </p>
            )}
          </>
        )}
      </div>

      {(fase === "revisar" || fase === "manual") && (
        <footer className="border-t border-ink pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <button
            type="button"
            disabled={!guardable || guardando}
            onClick={guardar}
            className="min-h-14 w-full bg-proof text-[1.0625rem] font-medium text-paper transition-colors hover:bg-proof-deep disabled:bg-ink-08 disabled:text-ink-70"
          >
            {guardando ? t("saving") : t("save")}
          </button>
        </footer>
      )}

      <input
        ref={archivo}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) void elegir(f);
        }}
      />
    </div>
  );
}
