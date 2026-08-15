/**
 * La pantalla principal.
 *
 * Móvil primero, una columna, con el orbe anclado abajo al alcance del pulgar.
 * En escritorio la misma hoja se abre a dos columnas: la estructura del plan a
 * la izquierda, la conversación a la derecha. Mismo componente, distinta
 * densidad — no dos modos que se desincronizan a la primera semana.
 *
 * El respaldo de texto no es una pantalla aparte: es un campo que aparece
 * dentro de la hoja cuando la voz no está disponible. Un evaluador que abre
 * esto en frío y deniega el micrófono tiene que poder seguir usándolo.
 */

import { useState } from "react";

import { SafetyStop } from "../components/SafetyStop";
import {
  ContextStrip,
  FormHeader,
  RegistrationMark,
  type Safety,
  SafetyKey,
  type WeekContext,
} from "../components/Sheet";
import { RestField, type Session, SessionField, WhyNote } from "../components/SessionField";
import { Transcript, type Turn } from "../components/Transcript";
import { VoiceOrb } from "../components/VoiceOrb";
import { useT } from "../i18n";
import type { VoiceState } from "../state/voiceMachine";

interface Props {
  ctx: WeekContext;
  session: Session | null;
  safety: Safety;
  referral: string;
  turns: Turn[];
  voice: VoiceState;
  level: number;
  micDenied: boolean;
  onOrbClick: () => void;
  onSend: (text: string) => void;
  onAcknowledge: () => void;
  onUpload: () => void;
  /** Latencia real del último turno, en ms (ADR 0012). */
  ttfaMs?: number | null;
}

export function Main({
  ctx,
  session,
  safety,
  referral,
  turns,
  voice,
  level,
  micDenied,
  onOrbClick,
  onSend,
  onAcknowledge,
  onUpload,
  ttfaMs,
}: Props) {
  const { t } = useT();
  const [texto, setTexto] = useState("");
  const [escribiendo, setEscribiendo] = useState(false);

  // El campo de texto se impone solo cuando la voz no puede: sin micrófono no
  // hay nada que ofrecer detrás de un botón.
  const textoVisible = escribiendo || micDenied || voice === "ERROR";

  const enviar = (e: React.FormEvent) => {
    e.preventDefault();
    const limpio = texto.trim();
    if (!limpio) return;
    onSend(limpio);
    setTexto("");
  };

  return (
    <div className="mx-auto flex h-dvh max-w-6xl flex-col">
      <FormHeader />

      <div className="flex min-h-0 flex-1 flex-col lg:grid lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)] lg:divide-x lg:divide-ink-15">
        {/* Columna izquierda en escritorio: la estructura. */}
        <div className="min-h-0 lg:overflow-y-auto">
          <ContextStrip ctx={ctx} />

          {safety === "flag" ? (
            <SafetyStop message={referral} onAcknowledge={onAcknowledge} />
          ) : session ? (
            <>
              <SessionField session={session} />
              <WhyNote why={session.why} />
            </>
          ) : (
            <RestField why={t("restWhy")} />
          )}

          <div className="flex items-stretch justify-between border-b border-ink-15">
            <SafetyKey level={safety} />
            {/* La latencia medida, no prometida. Sale del primer chunk de
                audio del coach y es lo que va al README. */}
            {ttfaMs !== null && ttfaMs !== undefined && (
              <span className="label fig self-center px-2" title="tiempo hasta el primer audio">
                {ttfaMs} ms
              </span>
            )}
            <button
              type="button"
              onClick={onUpload}
              className="label border-l border-ink-15 px-4 py-3 transition-colors hover:bg-ink hover:text-paper"
            >
              {t("uploadTitle")}
            </button>
          </div>
        </div>

        {/* Columna derecha en escritorio: la conversación. */}
        <div className="flex min-h-0 flex-1 flex-col">
          <Transcript turns={turns} />

          {micDenied && (
            <p className="border-t border-caution bg-caution/8 px-4 py-3 text-[0.875rem] text-ink">
              <span className="label !text-caution">{t("micDenied")}</span>
              <span aria-hidden="true"> — </span>
              {t("micDeniedWhy")}
            </p>
          )}

          <footer className="relative border-t border-ink">
            {textoVisible && (
              <form onSubmit={enviar} className="flex border-b border-ink-15">
                <input
                  value={texto}
                  onChange={(e) => setTexto(e.target.value)}
                  placeholder={t("typeHere")}
                  aria-label={t("typeHere")}
                  autoComplete="off"
                  className="min-w-0 flex-1 bg-transparent px-4 py-3 text-[0.9375rem] placeholder:text-ink-30 focus:outline-none"
                />
                <button
                  type="submit"
                  disabled={!texto.trim()}
                  className="label border-l border-ink-15 px-4 transition-colors hover:bg-ink hover:text-paper disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-ink-70"
                >
                  {t("send")}
                </button>
              </form>
            )}

            <div className="flex items-end gap-2 px-4 pb-[max(0.5rem,env(safe-area-inset-bottom))]">
              <RegistrationMark className="mb-6 shrink-0" />
              <VoiceOrb state={voice} level={level} onClick={onOrbClick} />
              <button
                type="button"
                onClick={() => setEscribiendo((v) => !v)}
                aria-pressed={escribiendo}
                className="label mb-6 shrink-0 border border-ink-15 px-2 py-1 transition-colors hover:bg-ink hover:text-paper"
              >
                {t("write")}
              </button>
            </div>
          </footer>
        </div>
      </div>
    </div>
  );
}
