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

const RENGLONES_MINIMOS = 1;

export function Transcript({ turns }: { turns: Turn[] }) {
  const { t } = useT();
  const caja = useRef<HTMLElement>(null);

  // Se desplaza el CONTENEDOR y no un elemento centinela: `scrollIntoView`
  // sobre un hijo también arrastra la página entera cuando el contenedor no es
  // el que scrollea, y en móvil eso mueve la hoja bajo el dedo.
  useEffect(() => {
    const c = caja.current;
    // Sin turnos no hay nada al final: desplazarse recorta el primer renglón
    // vacío y le come la etiqueta, que es el nombre del campo.
    if (!c || turns.length === 0) return;
    c.scrollTo({ top: c.scrollHeight, behavior: "smooth" });
  }, [turns.length, turns[turns.length - 1]?.text]);

  const vacios = Math.max(0, RENGLONES_MINIMOS - turns.length);

  return (
    <section
      ref={caja}
      aria-label={t("coach")}
      aria-live="polite"
      className="min-h-0 flex-1 overflow-y-auto scroll-smooth"
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
              turno.partial ? "text-ink-70 italic" : "text-ink"
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
    </section>
  );
}
