/**
 * El plan entero, en rejilla.
 *
 * La hoja contesta «¿qué hago hoy?». Esto contesta la otra pregunta, la que
 * hace todo corredor con un plan delante: **«¿hacia dónde va esto?»**. Son
 * distintas y por eso son dos vistas — meter doce semanas en la columna del día
 * habría convertido la hoja en un tablón.
 *
 * Optimizada para escritorio, que es donde alguien se sienta a mirar su plan
 * completo. En móvil las semanas siguen siendo legibles, apiladas: la rejilla no
 * se rompe, se estrecha.
 *
 * Tres decisiones que no son de maquetación:
 *
 * 1. **Siete casillas siempre.** El descanso se dibuja, con su nombre. Dejarlo
 *    en blanco lo haría parecer un hueco del plan en vez de parte del plan, que
 *    es justo lo que el producto lleva repitiendo desde la primera pantalla.
 *
 * 2. **Hoy va marcado con su color de seguridad.** El mismo verde, ámbar y rojo
 *    del resto: si el corredor está en ámbar, verlo en el calendario le dice por
 *    qué la sesión de hoy no se parece a la que está escrita.
 *
 * 3. **Las cifras vienen del servidor tal cual.** Aquí no se sumó, no se dividió
 *    y no se estimó nada. Ni siquiera los totales de la semana: los manda el
 *    motor. Es la misma regla de siempre, y una rejilla es justo donde apetece
 *    romperla «porque es sólo una suma».
 */

import { useEffect, useState } from "react";

import { type CalendarWeek, type PlanCalendar, fetchCalendar } from "../api";
import { RegistrationMark } from "../components/Sheet";
import { type TextKey, useT } from "../i18n";

const DIAS: TextKey[] = ["dayMon", "dayTue", "dayWed", "dayThu", "dayFri", "daySat", "daySun"];

const TIPO: Record<string, TextKey> = {
  largo: "kindLong",
  suave: "kindEasy",
  tempo: "kindTempo",
  intervalos: "kindIntervals",
};

const FASE: Record<CalendarWeek["phase"], TextKey> = {
  base: "phaseBase",
  construccion: "phaseBuild",
  pico: "phasePeak",
  taper: "phaseTaper",
};

// El borde de «hoy» habla el idioma del código de seguridad. No es decoración:
// es la misma clave de color que la hoja, y por eso se puede leer sin leyenda.
const HOY_BORDE: Record<PlanCalendar["safety"], string> = {
  clear: "border-clear",
  caution: "border-caution",
  flag: "border-flag",
};

function iso(fecha: string, masDias: number): string {
  // Se construye en UTC a propósito. Con `new Date("2026-08-17")` el navegador
  // interpreta medianoche UTC y la pinta en local: en México eso es el día
  // ANTERIOR a las 18:00, y el calendario resaltaría el martes el miércoles.
  const d = new Date(`${fecha}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + masDias);
  return d.toISOString().slice(0, 10);
}

function Casilla({
  dia,
  fecha,
  esHoy,
  safety,
}: {
  dia: CalendarWeek["days"][number];
  fecha: string;
  esHoy: boolean;
  safety: PlanCalendar["safety"];
}) {
  const { t } = useT();
  const numero = Number(fecha.slice(8, 10));

  return (
    <div
      className={`min-h-24 px-2 py-2 ${esHoy ? `border-2 ${HOY_BORDE[safety]}` : ""}`}
      aria-current={esHoy ? "date" : undefined}
    >
      <div className="flex items-baseline justify-between">
        <span className="fig text-[0.75rem] text-ink-50">{numero}</span>
        {esHoy && <span className="label !text-[0.625rem]">{t("calendarToday")}</span>}
      </div>

      {dia === null ? (
        <p className="mt-1 text-[0.8125rem] text-ink-50">{t("calendarRest")}</p>
      ) : (
        <>
          <p className="mt-1 text-[0.8125rem] leading-tight font-medium">{t(TIPO[dia.kind])}</p>
          <p className="fig mt-0.5 text-[1.0625rem] leading-none">{dia.distanceKm}</p>
          <p className="label !text-[0.625rem]">{t("km")}</p>
          {dia.pace && <p className="fig mt-1 text-[0.6875rem] text-ink-70">{dia.pace}</p>}
        </>
      )}
    </div>
  );
}

export function Calendar({ onClose }: { onClose: () => void }) {
  const { t } = useT();
  const [plan, setPlan] = useState<PlanCalendar | null>(null);
  const [cargando, setCargando] = useState(true);

  useEffect(() => {
    let vivo = true;
    fetchCalendar()
      .then((p) => vivo && setPlan(p))
      .catch(() => vivo && setPlan(null))
      .finally(() => vivo && setCargando(false));
    return () => {
      vivo = false;
    };
  }, []);

  return (
    <div className="mx-auto flex h-dvh max-w-6xl flex-col">
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
          {t("close")}
        </button>
        <h1 className="text-center text-[0.9375rem] font-semibold">{t("calendarTitle")}</h1>
        <RegistrationMark />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        {cargando ? (
          <div className="flex flex-col items-center gap-4 px-4 py-20">
            <span className="h-3 w-3 animate-pulse bg-proof" aria-hidden="true" />
          </div>
        ) : plan === null ? (
          <p className="px-4 py-20 text-center text-[0.9375rem] text-ink-70">
            {t("calendarEmpty")}
          </p>
        ) : (
          <>
            {/* Cabecera de días: fija arriba, porque un plan de dieciséis
                semanas se recorre y al llegar abajo ya no se sabe qué columna
                es qué día. */}
            <div className="sticky top-0 z-10 hidden grid-cols-[6.5rem_repeat(7,minmax(0,1fr))] border-b border-ink-15 bg-paper sm:grid">
              <span className="label px-2 py-2">{plan.goal}</span>
              {DIAS.map((d) => (
                <span key={d} className="label px-2 py-2">
                  {t(d)}
                </span>
              ))}
            </div>

            {plan.weeks.map((semana) => (
              <section
                key={semana.index}
                className="grid grid-cols-1 border-b border-ink-15 sm:grid-cols-[6.5rem_repeat(7,minmax(0,1fr))] sm:divide-x sm:divide-ink-15"
              >
                <div className="flex items-baseline gap-2 bg-ink-08/40 px-2 py-2 sm:block">
                  <span className="fig text-[0.9375rem] font-medium">
                    {t("calendarWeek", { n: semana.index })}
                  </span>
                  <span className="label block !text-[0.625rem] break-words hyphens-auto">
                    {t(FASE[semana.phase])}
                  </span>
                  {/* El total lo manda el motor. No se suma aquí. */}
                  <span className="fig text-[0.6875rem] text-ink-70">
                    {t("calendarTotal", { km: semana.totalKm })}
                  </span>
                </div>

                <div className="grid grid-cols-7 sm:contents">
                  {semana.days.map((dia, i) => {
                    const fecha = iso(semana.startDate, i);
                    return (
                      <Casilla
                        key={fecha}
                        dia={dia}
                        fecha={fecha}
                        esHoy={fecha === plan.today}
                        safety={plan.safety}
                      />
                    );
                  })}
                </div>
              </section>
            ))}

            <p className="px-4 py-4 text-[0.8125rem] text-ink-70">{t("calendarLegend")}</p>
          </>
        )}
      </div>
    </div>
  );
}
