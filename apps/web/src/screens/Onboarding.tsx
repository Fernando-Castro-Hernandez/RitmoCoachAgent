/**
 * El carrusel de onboarding: la capa dura del perfil.
 *
 * El reparto es la decisión, no el formulario. Esto captura lo que el corredor
 * **afirma** —edad, peso, días, meta— porque son datos discretos que un
 * formulario toma mejor, más rápido y sin error de transcripción. Lo que el
 * corredor **revela** —molestias, contradicciones, matices— sale hablando, y
 * por eso aquí no hay un campo de texto para «cuéntame de tus lesiones».
 *
 * Sólo la carrera es obligatoria. Un onboarding que exige nueve respuestas
 * antes de dejarte entrar es un onboarding que la gente abandona, y el corredor
 * que más nos importa es justo el que no sabe todavía cuánto corre.
 *
 * Sigue siendo la misma hoja: mismas reglas, mismas etiquetas, mismo azul. No
 * es una pantalla de bienvenida con otro lenguaje visual pegado delante.
 */

import { useState } from "react";

import { RegistrationMark } from "../components/Sheet";
import { type HardProfile, parseDuration } from "../api";
import { type TextKey, useT } from "../i18n";

type Paso = "goal" | "days" | "about" | "ref" | "injury" | "when";

const PASOS: Paso[] = ["goal", "days", "about", "ref", "injury", "when"];

const TITULO: Record<Paso, TextKey> = {
  goal: "onbGoal",
  days: "onbDays",
  about: "onbAbout",
  ref: "onbRef",
  injury: "onbInjury",
  when: "onbWhen",
};

const METAS = [
  { id: "5k", km: "5 km" },
  { id: "10k", km: "10 km" },
  { id: "21k", km: "21.1 km" },
  { id: "42k", km: "42.2 km" },
] as const;

/* ── validación ──────────────────────────────────────────────────────
 *
 * Se valida aquí y NO sólo en el backend por una razón de producto: el
 * carrusel guarda una vez, al final. Sin esto, alguien teclea «cincuenta
 * minutos» en el tiempo de referencia, avanza cinco pasos, y descubre el
 * problema al pulsar «Terminar» — con el dato ya olvidado y el error lejos del
 * campo que lo causó.
 *
 * Lo que NO cambia: el backend valida igual. Esto no es la comprobación, es la
 * cortesía de decirlo a tiempo. */

/** Un número positivo. Acepta coma o punto, que es como se escribe en español. */
export function esNumero(v: string): boolean {
  return /^\d+([.,]\d+)?$/.test(v.trim()) && Number(v.replace(",", ".")) > 0;
}

/** `mm:ss` o `hh:mm:ss`, con los minutos y segundos dentro de rango.
 *
 * `50:00` es válido y `50:99` no: un tiempo con 99 segundos no existe, y
 * aceptarlo produce un ritmo mal calculado que nadie va a cuestionar después. */
export function esTiempo(v: string): boolean {
  return /^\d{1,3}:[0-5]\d$/.test(v.trim()) || /^\d{1,2}:[0-5]\d:[0-5]\d$/.test(v.trim());
}

/** La plantilla de las cuatro que más se acerca a los km escritos.
 *
 * El motor valida cuatro planes, no una fórmula genérica: cada uno tiene su
 * progresión, su tirada larga y su descarga probadas. Se elige el más cercano
 * y **se dice cuál**, en vez de fabricar una plantilla nueva sin validar para
 * que el formulario quede bonito.
 */
export function plantillaMasCercana(km: string): string {
  const n = Number(km.replace(",", "."));
  const CANDIDATAS: [string, number][] = [
    ["5k", 5],
    ["10k", 10],
    ["21k", 21.1],
    ["42k", 42.2],
  ];
  return CANDIDATAS.reduce((mejor, actual) =>
    Math.abs(actual[1] - n) < Math.abs(mejor[1] - n) ? actual : mejor,
  )[0];
}

interface Borrador {
  goal_distance?: string;
  /** Los km que escribió si eligió «otra distancia». Se usa para elegir la
   *  plantilla más cercana, no para inventar una nueva. */
  goal_custom?: string;
  race_date?: string;
  days_per_week?: number;
  age?: string;
  weight_kg?: string;
  height_cm?: string;
  ref_distance?: string;
  ref_time?: string;
  injury?: boolean;
  usual_hour?: string;
}

/** Campo del formulario: etiqueta arriba, línea de respuesta abajo. */
function Entrada({
  label,
  suffix,
  ...props
}: { label: string; suffix?: string } & React.InputHTMLAttributes<HTMLInputElement>) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      <span className="mt-1 flex items-baseline gap-2 border-b border-ink">
        <input
          {...props}
          className="fig min-w-0 flex-1 bg-transparent py-2 text-2xl focus:outline-none"
        />
        {suffix && <span className="label shrink-0">{suffix}</span>}
      </span>
    </label>
  );
}

/** Opción seleccionable: casilla de formulario, no botón redondeado. */
function Casilla({
  selected,
  onClick,
  children,
  sub,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
  sub?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={selected}
      className={`flex min-h-14 w-full items-center gap-3 border px-4 py-3 text-left transition-colors ${
        selected ? "border-proof bg-proof text-paper" : "border-ink-15 hover:border-ink"
      }`}
    >
      <span
        aria-hidden="true"
        className={`h-3.5 w-3.5 shrink-0 border ${
          selected ? "border-paper bg-paper" : "border-ink-30"
        }`}
      />
      <span className="text-[1.0625rem] font-medium">{children}</span>
      {sub && (
        <span className={`fig ml-auto text-sm ${selected ? "text-paper" : "text-ink-70"}`}>
          {sub}
        </span>
      )}
    </button>
  );
}

export function Onboarding({ onDone }: { onDone: (p: HardProfile) => Promise<void> }) {
  const { t } = useT();
  const [i, setI] = useState(0);
  const [d, setD] = useState<Borrador>({});
  const [guardando, setGuardando] = useState(false);
  const [error, setError] = useState("");

  const paso = PASOS[i];
  const ultimo = i === PASOS.length - 1;
  // El paso de referencia es opcional, pero lo que se escriba tiene que ser
  // válido: vacío sí, basura no.
  const refDistanciaMal = Boolean(d.ref_distance?.trim()) && !esNumero(d.ref_distance!);
  const refTiempoMal = Boolean(d.ref_time?.trim()) && !esTiempo(d.ref_time!);
  // Un tiempo sin distancia (o al revés) no permite calcular ningún ritmo, así
  // que se piden los dos o ninguno.
  const refIncompleta =
    Boolean(d.ref_distance?.trim()) !== Boolean(d.ref_time?.trim());

  const puedeAvanzar =
    paso === "goal"
      ? Boolean(d.goal_distance)
      : paso === "ref"
        ? !refDistanciaMal && !refTiempoMal && !refIncompleta
        : true;

  const construir = (): HardProfile => {
    const seg = d.ref_time ? parseDuration(d.ref_time) : null;
    return {
      goal_distance: d.goal_distance!,
      race_date: d.race_date || null,
      days_per_week: d.days_per_week ?? null,
      age: d.age ? Number(d.age) : null,
      weight_kg: d.weight_kg ? Number(d.weight_kg) : null,
      height_cm: d.height_cm ? Number(d.height_cm) : null,
      reference_distance_km: d.ref_distance ? Number(d.ref_distance) : null,
      reference_time_sec: seg,
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || null,
    };
  };

  const avanzar = async () => {
    if (!ultimo) {
      setI(i + 1);
      return;
    }
    setGuardando(true);
    setError("");
    try {
      await onDone(construir());
    } catch {
      setError(t("offlineWhy"));
      setGuardando(false);
    }
  };

  return (
    <div className="mx-auto flex h-dvh max-w-lg flex-col">
      <header className="flex items-center justify-between border-b border-ink px-4 py-3">
        <span className="label">{t("formCode")}</span>
        <h1 className="text-xl font-semibold tracking-[0.2em] uppercase">{t("brand")}</h1>
        <span className="label fig">{t("step", { n: i + 1, total: PASOS.length })}</span>
      </header>

      {/* El avance como una regla que se va llenando de tinta. */}
      <div aria-hidden="true" className="h-1 bg-ink-08">
        <div
          className="h-full bg-proof transition-[width] duration-300 ease-out"
          style={{ width: `${((i + 1) / PASOS.length) * 100}%` }}
        />
      </div>

      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-7">
        <h2 className="text-[1.75rem] leading-tight font-semibold tracking-tight text-balance">
          {t(TITULO[paso])}
        </h2>

        <div className="mt-7 space-y-3">
          {paso === "goal" && (
            <>
              {METAS.map((m) => (
                <Casilla
                  key={m.id}
                  selected={d.goal_distance === m.id && !d.goal_custom}
                  onClick={() => setD({ ...d, goal_distance: m.id, goal_custom: undefined })}
                  sub={m.km}
                >
                  {m.id.toUpperCase()}
                </Casilla>
              ))}

              <Casilla
                selected={Boolean(d.goal_custom)}
                onClick={() => setD({ ...d, goal_custom: d.goal_custom ?? "" })}
                sub={t("otherDistanceSub")}
              >
                {t("otherDistance")}
              </Casilla>

              {d.goal_custom !== undefined && (
                <div className="border-l-2 border-ink-15 pt-2 pl-4">
                  <Entrada
                    label={t("otherDistanceLabel")}
                    suffix="km"
                    inputMode="decimal"
                    placeholder="15"
                    value={d.goal_custom}
                    onChange={(e) => {
                      const km = e.target.value;
                      setD({
                        ...d,
                        goal_custom: km,
                        // La plantilla más cercana se elige AL ESCRIBIR, no al
                        // guardar: así el aviso de abajo cambia mientras se
                        // teclea y nadie llega al final con una sorpresa.
                        goal_distance: esNumero(km) ? plantillaMasCercana(km) : undefined,
                      });
                    }}
                  />
                  {d.goal_custom.trim() !== "" && !esNumero(d.goal_custom) && (
                    <p className="label mt-2 !text-caution">{t("badNumber")}</p>
                  )}
                  {d.goal_distance && esNumero(d.goal_custom) && (
                    /* Se dice qué plan va a recibir. El motor tiene cuatro
                       plantillas validadas y no inventa una quinta; callarlo
                       sería prometer algo que no existe. */
                    <p className="mt-2 text-[0.875rem] text-ink-70">
                      {t("nearestTemplate", { plan: d.goal_distance.toUpperCase() })}
                    </p>
                  )}
                </div>
              )}
              <div className="pt-3">
                <Entrada
                  label={`${t("raceDate")} — ${t("raceDateOptional")}`}
                  type="date"
                  value={d.race_date ?? ""}
                  onChange={(e) => setD({ ...d, race_date: e.target.value })}
                />
              </div>
            </>
          )}

          {paso === "days" &&
            [2, 3, 4, 5, 6].map((n) => (
              <Casilla
                key={n}
                selected={d.days_per_week === n}
                onClick={() => setD({ ...d, days_per_week: n })}
              >
                <span className="fig">{n}</span>
              </Casilla>
            ))}

          {paso === "about" && (
            <div className="space-y-6">
              <Entrada
                label={t("age")}
                suffix={t("years")}
                inputMode="numeric"
                value={d.age ?? ""}
                onChange={(e) => setD({ ...d, age: e.target.value })}
              />
              <Entrada
                label={t("weight")}
                suffix="kg"
                inputMode="decimal"
                value={d.weight_kg ?? ""}
                onChange={(e) => setD({ ...d, weight_kg: e.target.value })}
              />
              <Entrada
                label={t("height")}
                suffix="cm"
                inputMode="numeric"
                value={d.height_cm ?? ""}
                onChange={(e) => setD({ ...d, height_cm: e.target.value })}
              />
            </div>
          )}

          {paso === "ref" && (
            <div className="space-y-6">
              <div>
                <Entrada
                  label={t("refDistance")}
                  suffix="km"
                  inputMode="decimal"
                  placeholder="10"
                  value={d.ref_distance ?? ""}
                  onChange={(e) => setD({ ...d, ref_distance: e.target.value })}
                />
                {refDistanciaMal && <p className="label mt-2 !text-caution">{t("badNumber")}</p>}
              </div>
              <div>
                <Entrada
                  label={t("refTime")}
                  inputMode="numeric"
                  placeholder="50:00"
                  value={d.ref_time ?? ""}
                  onChange={(e) => setD({ ...d, ref_time: e.target.value })}
                />
                {refTiempoMal && <p className="label mt-2 !text-caution">{t("badTime")}</p>}
              </div>
              {refIncompleta && !refDistanciaMal && !refTiempoMal && (
                <p className="label !text-caution">{t("refNeedsBoth")}</p>
              )}
            </div>
          )}

          {paso === "injury" && (
            <>
              <Casilla selected={d.injury === true} onClick={() => setD({ ...d, injury: true })}>
                {t("yes")}
              </Casilla>
              <Casilla selected={d.injury === false} onClick={() => setD({ ...d, injury: false })}>
                {t("no")}
              </Casilla>
              {/* El detalle NO se pide aquí: un campo de texto lo aplana. Sale
                  hablando, que es donde aparece «bueno, la rodilla a veces». */}
              {d.injury === true && (
                <p className="border-l-2 border-caution bg-caution/8 px-3 py-2 text-[0.875rem] text-ink">
                  {t("onbFootnote")}
                </p>
              )}
            </>
          )}

          {paso === "when" && (
            <Entrada
              label={t("onbWhen")}
              type="time"
              value={d.usual_hour ?? ""}
              onChange={(e) => setD({ ...d, usual_hour: e.target.value })}
            />
          )}
        </div>

        {paso === "goal" && (
          <p className="mt-8 text-[0.875rem] text-ink-70">{t("onbFootnote")}</p>
        )}

        {error && (
          <p role="alert" className="mt-6 border-l-2 border-flag px-3 py-2 text-[0.875rem]">
            {error}
          </p>
        )}
      </div>

      <footer className="flex items-stretch border-t border-ink pb-[max(0.75rem,env(safe-area-inset-bottom))]">
        <RegistrationMark className="mx-4 self-center shrink-0" />
        {!ultimo && paso !== "goal" && (
          <button
            type="button"
            onClick={() => setI(i + 1)}
            className="label border-l border-ink-15 px-5 transition-colors hover:bg-ink hover:text-paper"
          >
            {t("skip")}
          </button>
        )}
        {/* Sin meta elegida no hay botón: hay un campo sin llenar diciendo qué
            falta. Un primario oscuro y legible que no hace nada al tocarlo es
            peor que uno ilegible, y en la primera pantalla que ve alguien que
            llega en frío es la diferencia entre entender y quedarse atascado. */}
        {puedeAvanzar ? (
          <button
            type="button"
            onClick={avanzar}
            disabled={guardando}
            className="ml-auto min-h-14 flex-1 bg-proof px-5 text-[1.0625rem] font-medium text-paper transition-colors hover:bg-proof-deep disabled:opacity-70"
          >
            {guardando ? "…" : ultimo ? t("finish") : t("next")}
          </button>
        ) : (
          <p className="label ml-auto flex flex-1 items-center justify-center border-l border-ink-15 px-5 text-center">
            {/* El aviso dice QUÉ falta en ESTE paso. Antes decía siempre «elige
                una carrera para seguir», que en el paso del tiempo de
                referencia es desconcertante: el corredor mira arriba buscando
                una carrera que ya eligió hace tres pasos. */}
            {paso === "goal" ? t("pickOne") : t("fixFields")}
          </p>
        )}
      </footer>
    </div>
  );
}
