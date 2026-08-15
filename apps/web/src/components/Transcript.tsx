/**
 * La transcripción, como los renglones de un formulario.
 *
 * Cada turno es una entrada reglada con su etiqueta en el margen — «TÚ»,
 * «COACH» — igual que un campo llenado a mano. El renglón vacío existe desde el
 * principio: un formulario en blanco enseña qué se va a llenar, y eso hace que
 * el primer arranque no sea una pantalla vacía sino una hoja lista.
 *
 * Los dos hablantes se distinguen con TRES señales a la vez, ninguna de ellas
 * el color:
 *
 *   · Peso de etiqueta — TÚ va en tinta plena y seminegrita; COACH en ink-70.
 *   · Fondo — lo que dice el coach cae sobre una trama de tinta al 8 %, como la
 *     zona de respuesta impresa de un formulario. Lo que dice el corredor va
 *     sobre papel limpio, porque es su letra.
 *   · Sangría — el renglón del coach entra un poco, así que el ojo baja por el
 *     margen izquierdo y ve el diálogo alternarse sin leer una palabra.
 *
 * Por qué no con color: el azul de proceso significa «aquí puedes actuar o el
 * sistema está vivo» (disciplina donada, verificada en la revisión), y una
 * etiqueta estática no es ninguna de las dos cosas. Y `ink-50` está en 3.61:1,
 * por debajo del suelo de `ink-70` que la revisión estableció para todo lo que
 * se lee. Las tres señales de arriba consiguen el mismo escaneo inmediato sin
 * gastar el acento ni bajar el contraste.
 */

import { useEffect, useRef } from "react";

import { useT } from "../i18n";

export interface Turn {
  role: "user" | "coach";
  text: string;
  partial?: boolean;
}

const RENGLONES_MINIMOS = 1;

function Renglon({
  role,
  children,
  partial = false,
  hidden = false,
}: {
  role: "user" | "coach";
  children: React.ReactNode;
  partial?: boolean;
  hidden?: boolean;
}) {
  const { t } = useT();
  const esCoach = role === "coach";

  return (
    <div
      aria-hidden={hidden || undefined}
      className={`grid grid-cols-[4.5rem_1fr] border-b border-dashed border-ink-15 ${
        esCoach ? "bg-ink-08/60" : ""
      }`}
    >
      <div
        className={`label border-r border-ink-15 px-4 py-3 ${
          esCoach ? "" : "!font-semibold !text-ink"
        }`}
      >
        {t(esCoach ? "coach" : "you")}
      </div>
      <div
        className={`py-3 text-[0.9375rem] leading-relaxed ${esCoach ? "pr-4 pl-6" : "px-4"} ${
          partial ? "text-ink-70 italic" : "text-ink"
        }`}
      >
        {children}
      </div>
    </div>
  );
}

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
        <Renglon key={`${i}-${turno.role}`} role={turno.role} partial={turno.partial}>
          {turno.text}
        </Renglon>
      ))}

      {Array.from({ length: vacios }, (_, i) => (
        <Renglon key={`vacio-${i}`} role="user" hidden>
          &nbsp;
        </Renglon>
      ))}
    </section>
  );
}
