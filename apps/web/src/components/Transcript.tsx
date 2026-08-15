/**
 * La transcripción, como los renglones de un formulario.
 *
 * Cada turno es una entrada reglada con su etiqueta en el margen — «TÚ»,
 * «COACH» — igual que un campo llenado a mano. Los renglones vacíos existen
 * desde el principio: un formulario en blanco enseña qué se va a llenar, y eso
 * hace que el primer arranque no sea una pantalla vacía sino una hoja lista.
 */

import { useEffect, useRef } from "react";

import { useT } from "../i18n";

export interface Turn {
  role: "user" | "coach";
  text: string;
  partial?: boolean;
}

const RENGLONES_MINIMOS = 2;

export function Transcript({ turns }: { turns: Turn[] }) {
  const { t } = useT();
  const fin = useRef<HTMLDivElement>(null);

  useEffect(() => {
    fin.current?.scrollIntoView({ block: "end", behavior: "smooth" });
  }, [turns.length]);

  const vacios = Math.max(0, RENGLONES_MINIMOS - turns.length);

  return (
    <section
      aria-label={t("coach")}
      aria-live="polite"
      className="min-h-0 flex-1 overflow-y-auto"
    >
      {turns.map((turno, i) => (
        <div
          key={`${i}-${turno.role}`}
          className="grid grid-cols-[4.5rem_1fr] border-b border-dashed border-ink-15"
        >
          <div className="label border-r border-ink-15 px-4 py-3">
            {t(turno.role === "user" ? "you" : "coach")}
          </div>
          <p
            className={`px-4 py-3 text-[0.9375rem] leading-relaxed ${
              turno.partial ? "text-ink-50" : "text-ink"
            }`}
          >
            {turno.text}
          </p>
        </div>
      ))}

      {Array.from({ length: vacios }, (_, i) => (
        <div
          key={`vacio-${i}`}
          aria-hidden="true"
          className="grid grid-cols-[4.5rem_1fr] border-b border-dashed border-ink-15"
        >
          <div className="label border-r border-ink-15 px-4 py-3">
            {t(turns.length + i === 0 ? "you" : "coach")}
          </div>
          <div className="px-4 py-3">&nbsp;</div>
        </div>
      ))}
      <div ref={fin} />
    </section>
  );
}
