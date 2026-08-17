/**
 * Analizar la técnica desde un clip corto.
 *
 * La segunda ruta multimodal, y la que más cuidado pide. Tres reglas del
 * producto viven en esta pantalla:
 *
 * 1. **El vídeo no sale del teléfono.** Los fotogramas se extraen aquí
 *    (`frames.ts`) y sólo suben esos diez. Se dice en la pantalla, antes de
 *    elegir el archivo: quien va a grabarse tiene derecho a saberlo antes.
 *
 * 2. **Lo que se ve y lo que se corrige son cosas distintas, y se enseñan
 *    aparte.** Los hallazgos los describe el modelo; la señal sale de la
 *    biblioteca curada del motor. Mezclarlas en un solo bloque sería sugerir
 *    que el modelo prescribe, que es justo lo que no hace.
 *
 * 3. **Con molestia activa no hay señal, y se dice por qué.** «Se te ve bien» y
 *    «hoy no te corrijo porque te duele algo» son mensajes opuestos, y el
 *    servidor manda la bandera precisamente para no confundirlos.
 *
 * Va como modal sobre la hoja y no como pantalla aparte: es una consulta
 * puntual, no un paso del flujo, y volver tiene que costar un toque.
 */

import { useRef, useState } from "react";

import { type GaitFinding, type GaitResponse, analizarTecnica } from "../api";
import { RegistrationMark } from "../components/Sheet";
import {
  MAX_SEGUNDOS,
  NUM_FOTOGRAMAS,
  VideoInvalidoError,
  extraerFotogramas,
} from "../frames";
import { type TextKey, useT } from "../i18n";

type Fase = "elegir" | "extrayendo" | "leyendo" | "resultado";

const OBSERVABLE: Record<GaitFinding["observable"], TextKey> = {
  foot_strike_position: "obsFootStrike",
  hip_drop: "obsHipDrop",
  arm_crossover: "obsArmCrossover",
  trunk_lean: "obsTrunkLean",
  cadence_impression: "obsCadence",
};

const EVALUACION: Record<GaitFinding["assessment"], { key: TextKey; punto: string }> = {
  ok: { key: "gaitOk", punto: "bg-clear" },
  watch: { key: "gaitWatch", punto: "bg-caution" },
  flag: { key: "gaitFlag", punto: "bg-flag" },
};

export function GaitUpload({ onClose }: { onClose: () => void }) {
  const { t } = useT();
  const [fase, setFase] = useState<Fase>("elegir");
  const [hechos, setHechos] = useState(0);
  const [error, setError] = useState("");
  const [resultado, setResultado] = useState<GaitResponse | null>(null);
  const archivo = useRef<HTMLInputElement>(null);

  const elegir = async (f: File) => {
    setError("");
    setResultado(null);
    setHechos(0);

    if (!f.type.startsWith("video/")) {
      setError(t("gaitNotVideo"));
      return;
    }

    setFase("extrayendo");
    let fotogramas: Blob[];
    try {
      fotogramas = await extraerFotogramas(f, (n) => setHechos(n));
    } catch (e) {
      // El vídeo se valida aquí y no sólo en el servidor: la respuesta útil
      // llega antes de subir nada.
      setError(
        e instanceof VideoInvalidoError && e.motivo === "muy-largo"
          ? t("gaitTooLong", { n: MAX_SEGUNDOS })
          : t("gaitNotVideo"),
      );
      setFase("elegir");
      return;
    }

    setFase("leyendo");
    try {
      setResultado(await analizarTecnica(fotogramas));
      setFase("resultado");
    } catch {
      setError(t("exportFailed"));
      setFase("elegir");
    }
  };

  const senal = resultado?.cue ?? null;
  const bloqueada = resultado?.cue_blocked_by_safety === true;

  return (
    <div className="mx-auto flex h-dvh max-w-lg flex-col">
      <header className="flex items-center justify-between border-b border-ink px-4 py-3">
        <button
          type="button"
          onClick={onClose}
          className="label flex items-center gap-1.5 transition-colors hover:text-ink"
        >
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
        <h1 className="text-center text-[0.9375rem] font-semibold">{t("gaitTitle")}</h1>
        <RegistrationMark />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {fase === "elegir" && (
          <>
            {/* El estado vacío lleva la gramática de la hoja: los campos que se
                van a llenar, esperando su valor. */}
            <div className="divide-y divide-ink-15 border-b border-ink-15">
              {(Object.keys(OBSERVABLE) as GaitFinding["observable"][]).map((o) => (
                <div key={o} className="flex items-baseline justify-between px-4 py-2.5">
                  <span className="label">{t(OBSERVABLE[o])}</span>
                  <span className="fig text-ink-30" aria-hidden="true">
                    —
                  </span>
                </div>
              ))}
            </div>

            <div className="px-4 py-8">
              <p className="text-[0.9375rem] text-ink-70">
                {t("gaitLead", { n: MAX_SEGUNDOS })}
              </p>
              <button
                type="button"
                onClick={() => archivo.current?.click()}
                className="mt-5 min-h-13 w-full bg-proof px-6 text-[1.0625rem] font-medium text-paper transition-colors hover:bg-proof-deep"
              >
                {t("gaitCta")}
              </button>
              {/* Antes de elegir el archivo, no después: quien va a grabarse
                  tiene derecho a saber qué sube antes de subirlo. */}
              <p className="label mt-3 text-center !text-ink-70">
                {t("gaitPrivacy", { n: NUM_FOTOGRAMAS })}
              </p>
            </div>

            {error && (
              <p
                role="alert"
                className="mx-4 border-l-2 border-flag px-3 py-2 text-[0.875rem]"
              >
                {error}
              </p>
            )}

            <div className="mt-6 flex items-center justify-between border-t border-ink-15 px-4 py-3">
              <span className="label">RIT-11</span>
              <RegistrationMark />
            </div>
          </>
        )}

        {(fase === "extrayendo" || fase === "leyendo") && (
          <div className="flex flex-col items-center gap-4 px-4 py-20">
            <span className="h-3 w-3 animate-pulse bg-proof" aria-hidden="true" />
            <p className="label text-center">
              {fase === "extrayendo"
                ? t("gaitExtracting", { n: hechos, total: NUM_FOTOGRAMAS })
                : t("gaitReading")}
            </p>
          </div>
        )}

        {fase === "resultado" && resultado && (
          <>
            {!resultado.ok && (
              <p className="border-b border-ink-15 px-4 py-4 text-[0.9375rem]">
                {resultado.reason}
              </p>
            )}

            {resultado.findings.length > 0 && (
              <>
                <h2 className="label border-b border-ink-15 px-4 py-2.5">{t("gaitFindings")}</h2>
                <div className="divide-y divide-ink-15 border-b border-ink-15">
                  {resultado.findings.map((h) => (
                    <div key={h.observable} className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <span
                          aria-hidden="true"
                          className={`h-2 w-2 shrink-0 ${EVALUACION[h.assessment].punto}`}
                        />
                        <span className="label">{t(OBSERVABLE[h.observable])}</span>
                        {/* El color codifica y la palabra lo dice: quien no
                            distingue ámbar de rojo no puede quedarse fuera. */}
                        <span className="label ml-auto !text-ink-70">
                          {t(EVALUACION[h.assessment].key)}
                        </span>
                      </div>
                      <p className="mt-1 text-[0.9375rem]">{h.note}</p>
                    </div>
                  ))}
                </div>
              </>
            )}

            {/* La señal, aparte y etiquetada. Sale de la biblioteca del motor,
                no del texto del modelo, y la separación lo hace visible. */}
            <div className="border-b border-ink-15 px-4 py-4">
              <span className="label">{t("gaitCue")}</span>
              {senal ? (
                <p className="mt-1.5 text-[1.0625rem] leading-snug font-medium">{senal.text}</p>
              ) : (
                <p className="mt-1.5 text-[0.9375rem] text-ink-70">
                  {bloqueada ? t("gaitBlocked") : t("gaitNoCue")}
                </p>
              )}
            </div>

            <p className="px-4 py-4 text-[0.8125rem] text-ink-70">{t("gaitDisclaimer")}</p>
          </>
        )}
      </div>

      {fase === "resultado" && (
        <footer className="border-t border-ink pb-[max(0.75rem,env(safe-area-inset-bottom))]">
          <button
            type="button"
            onClick={() => {
              setFase("elegir");
              setResultado(null);
            }}
            className="label min-h-13 w-full transition-colors hover:bg-ink hover:text-paper"
          >
            {t("gaitAgain")}
          </button>
        </footer>
      )}

      <input
        ref={archivo}
        type="file"
        accept="video/*"
        className="sr-only"
        onChange={(e) => {
          const f = e.target.files?.[0];
          // Se limpia el valor para que elegir DOS VECES el mismo archivo
          // vuelva a disparar el change. Sin esto, «probar con otro vídeo» y
          // reelegir el mismo no hace nada y parece que la app se colgó.
          e.target.value = "";
          if (f) void elegir(f);
        }}
      />
    </div>
  );
}
