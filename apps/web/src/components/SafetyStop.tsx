/**
 * El formulario anulado.
 *
 * La regla 1 del producto, hecha gesto: en rojo la pantalla no prescribe. El
 * campo de la sesión queda vacío —reglado, en blanco, como un formulario sin
 * llenar— y encima cae un sello de anulación.
 *
 * Las cifras no se tachan: **no se renderizan**. Un número tachado sigue siendo
 * un número legible, y ocultar con CSS lo que no se puede prescribir es cumplir
 * la regla de boquilla. Aquí no hay nada que leer porque no hay nada que
 * prescribir.
 *
 * Y no se sale con un toque. El reconocimiento pide mantener pulsado: salir de
 * un alto médico no puede ser el mismo gesto con el que se llegó.
 */

import { useEffect, useRef, useState } from "react";

import { useT } from "../i18n";

const MANTENER_MS = 1200;

export function SafetyStop({
  message,
  onAcknowledge,
}: {
  message: string;
  onAcknowledge: () => void;
}) {
  const { t } = useT();
  const [avance, setAvance] = useState(0);
  const raf = useRef(0);
  const desde = useRef(0);

  const soltar = () => {
    cancelAnimationFrame(raf.current);
    desde.current = 0;
    setAvance(0);
  };

  const mantener = () => {
    desde.current = performance.now();
    const paso = (ahora: number) => {
      const p = Math.min(1, (ahora - desde.current) / MANTENER_MS);
      setAvance(p);
      if (p >= 1) {
        onAcknowledge();
        return;
      }
      raf.current = requestAnimationFrame(paso);
    };
    raf.current = requestAnimationFrame(paso);
  };

  useEffect(() => cancelAnimationFrame.bind(null, raf.current), []);

  return (
    <section aria-live="assertive">
      {/* El campo vacío donde iba la sesión, con el sello encima. */}
      <div className="relative border-b border-ink-15 px-4 py-14">
        <div aria-hidden="true" className="space-y-7">
          <hr className="border-0 border-t border-ink-15" />
          <hr className="border-0 border-t border-ink-15" />
          <hr className="border-0 border-t border-ink-15" />
        </div>

        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <p className="animate-[stamp_420ms_cubic-bezier(0.2,1.4,0.4,1)_both] -rotate-[9deg] border-[3px] border-flag px-6 py-2 text-3xl font-bold tracking-[0.18em] text-flag">
            {t("stampVoided")}
          </p>
        </div>
      </div>

      {/* La tarjeta de derivación: lo único que la pantalla tiene que decir. */}
      <div className="border-b-2 border-flag bg-flag/6 px-4 py-5">
        <h2 className="label !text-flag">{t("referralTitle")}</h2>
        <p className="mt-2 text-[1.0625rem] leading-relaxed font-medium text-ink">{message}</p>

        <button
          type="button"
          onPointerDown={mantener}
          onPointerUp={soltar}
          onPointerLeave={soltar}
          onPointerCancel={soltar}
          className="relative mt-5 w-full overflow-hidden border border-flag px-4 py-3 text-left transition-colors select-none"
        >
          <span
            aria-hidden="true"
            className="absolute inset-y-0 left-0 bg-flag/15"
            style={{ width: `${avance * 100}%` }}
          />
          <span className="relative block text-[0.9375rem] font-medium text-flag">{t("ack")}</span>
          <span className="label relative mt-0.5 block !text-flag/70">{t("ackHint")}</span>
        </button>
      </div>
    </section>
  );
}
