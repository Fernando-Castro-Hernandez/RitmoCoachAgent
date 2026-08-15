/**
 * El campo de la sesión: la unidad de decisión del producto.
 *
 * Es el único elemento que ocupa una región entera en azul de proceso. El color
 * no es un acento repartido por la pantalla — es un campo macizo, como la tinta
 * plana de un formulario impreso, y aparece aquí porque aquí está lo que el
 * corredor tiene que hacer hoy.
 *
 * En rojo este componente NO SE RENDERIZA. La regla 1 del producto no se cumple
 * ocultando el texto con CSS: si no se puede prescribir, las cifras no llegan
 * al DOM. Lo que se ve en su lugar es el sello de anulación.
 */

import { useT } from "../i18n";

export interface Session {
  kind: "largo" | "suave" | "tempo" | "intervalos";
  distanceKm: number;
  pace: string | null;
  effort: string;
  zone: number;
  durationLabel: string;
  why: string;
}

const TIPO = {
  largo: "kindLong",
  suave: "kindEasy",
  tempo: "kindTempo",
  intervalos: "kindIntervals",
} as const;

export function SessionField({ session }: { session: Session }) {
  const { t } = useT();
  const [entero, decimal] = session.distanceKm.toFixed(1).split(".");

  return (
    <section className="bg-proof px-4 pt-5 pb-6 text-paper">
      <h2 className="label label-on-proof">
        {t("today")} · {t(TIPO[session.kind])}
      </h2>

      <p className="mt-2 flex items-baseline gap-2 leading-none">
        <output className="text-figure font-semibold tracking-[-0.04em]">
          {decimal === "0" ? entero : `${entero}.${decimal}`}
        </output>
        <span className="text-2xl font-medium">{t("km")}</span>
      </p>

      <p className="mt-4 text-[1.375rem] leading-tight font-medium">
        {session.pace ? (
          <>
            <span className="fig">{session.pace}</span>
            <span className="ml-1 text-base">{t("perKm")}</span>
          </>
        ) : (
          /* Sin esfuerzo de referencia el motor no inventa un ritmo, así que la
             pantalla tampoco: se prescribe por esfuerzo. */
          <span className="text-lg">{session.effort}</span>
        )}
      </p>

      <p className="label label-on-proof mt-2">
        {t("zone")} {session.zone} · <span className="fig">{t("approxTime", { time: session.durationLabel })}</span>
      </p>

      {/* La línea de respuesta del formulario, en negativo. */}
      <hr className="mt-5 border-0 border-t border-paper/45" />
    </section>
  );
}

export function WhyNote({ why }: { why: string }) {
  const { t } = useT();
  return (
    <p className="border-b border-ink-15 px-4 py-3 text-[0.875rem] leading-relaxed text-ink-70">
      <span className="label !text-ink">{t("why")}</span>
      <span aria-hidden="true"> — </span>
      {why}
    </p>
  );
}

export function RestField({ why }: { why: string }) {
  const { t } = useT();
  return (
    <section className="border-b border-ink-15 px-4 pt-5 pb-6">
      <h2 className="label">{t("today")}</h2>
      <p className="mt-2 text-4xl font-semibold tracking-tight">{t("restDay")}</p>
      <p className="mt-3 text-[0.9375rem] text-ink-70">{why}</p>
    </section>
  );
}
