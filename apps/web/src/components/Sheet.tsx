/**
 * Las piezas impresas de la hoja.
 *
 * Todas comparten la misma gramática: reglas de pelo, etiquetas en versalitas
 * espaciadas sobre su valor, cifras tabulares, cero esquinas redondeadas y cero
 * sombras. Un componente que necesite un contenedor lo resuelve con una regla,
 * no con una tarjeta.
 */

import type { ReactNode } from "react";

import { type Locale, type TextKey, useLocale, useT } from "../i18n";

/* ── cabecera del formulario ─────────────────────────────────────── */

export function FormHeader({ specimen = false }: { specimen?: boolean }) {
  const { t, locale } = useT();
  const setLocale = useLocale((s) => s.setLocale);
  const otro: Locale = locale === "es" ? "en" : "es";

  return (
    <header className="grid grid-cols-[1fr_auto_1fr] items-center gap-3 border-b border-ink px-4 py-3">
      <span className="label">{t(specimen ? "formCodeDemo" : "formCode")}</span>
      <h1 className="text-center text-2xl font-semibold tracking-[0.2em] uppercase">
        {t("brand")}
      </h1>
      <div className="justify-self-end">
        <button
          type="button"
          onClick={() => setLocale(otro)}
          aria-label={`${locale === "es" ? "Switch to English" : "Cambiar a español"}`}
          className="label border border-ink px-2 py-1 transition-colors hover:bg-ink hover:text-paper"
        >
          {locale.toUpperCase()}
        </button>
      </div>
    </header>
  );
}

/* ── campo reglado genérico ──────────────────────────────────────── */

export function Field({
  label,
  children,
  className = "",
}: {
  label: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`min-w-0 px-4 py-2 ${className}`}>
      <div className="label truncate">{label}</div>
      <div className="mt-0.5 truncate text-[0.9375rem] font-medium">{children}</div>
    </div>
  );
}

/* ── tira de contexto ────────────────────────────────────────────── */

export interface WeekContext {
  week: number;
  totalWeeks: number;
  phase: "base" | "construccion" | "pico" | "taper";
  race: string;
  daysLeft: number | null;
}

const FASE: Record<WeekContext["phase"], TextKey> = {
  base: "phaseBase",
  construccion: "phaseBuild",
  pico: "phasePeak",
  taper: "phaseTaper",
};

export function ContextStrip({ ctx }: { ctx: WeekContext }) {
  const { t } = useT();
  return (
    <section className="grid grid-cols-[auto_auto_1fr] divide-x divide-ink-15 border-b border-ink-15">
      <Field label={t("week")}>
        <span className="fig">
          {ctx.week} / {ctx.totalWeeks}
        </span>
      </Field>
      <Field label={t("phase")}>{t(FASE[ctx.phase])}</Field>
      <Field label={ctx.race}>
        {ctx.daysLeft === null ? "—" : <span className="fig">{t("daysLeft", { n: ctx.daysLeft })}</span>}
      </Field>
    </section>
  );
}

/* ── clave del código de color ───────────────────────────────────── */

export type Safety = "clear" | "caution" | "flag";

const CLAVE: Record<Safety, { key: TextKey; dot: string }> = {
  clear: { key: "keyClear", dot: "bg-clear" },
  caution: { key: "keyCaution", dot: "bg-caution" },
  flag: { key: "keyFlag", dot: "bg-flag" },
};

/**
 * El color codifica una regla y lleva su clave a la vista. Sin esto sería
 * decoración, y un usuario que no distingue verde de ámbar se quedaría sin la
 * información más importante de la pantalla.
 */
export function SafetyKey({ level }: { level: Safety }) {
  const { t } = useT();
  const { key, dot } = CLAVE[level];
  return (
    <div className="flex items-center gap-2 px-4 py-3 whitespace-nowrap">
      <span className="label">{t("keyTitle")}</span>
      <span aria-hidden="true" className={`h-2.5 w-2.5 ${dot}`} />
      <span className="label !text-ink">{t(key)}</span>
    </div>
  );
}

/* ── marca de registro ───────────────────────────────────────────── */

/** La cruz de registro de la imprenta. Marca que esto es una hoja impresa. */
export function RegistrationMark({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className={`h-4 w-4 text-ink-30 ${className}`}
      fill="none"
      stroke="currentColor"
      strokeWidth="1"
    >
      <circle cx="12" cy="12" r="6" />
      <path d="M12 0v24M0 12h24" />
    </svg>
  );
}
