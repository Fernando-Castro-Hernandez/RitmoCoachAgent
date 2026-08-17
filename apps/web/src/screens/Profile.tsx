/**
 * Perfil y ajustes.
 *
 * Existe por una razón de composición, no por completar una pantalla: la hoja
 * había acumulado cinco botones auxiliares debajo del plan —Telegram, CSV,
 * captura, técnica, cerrar sesión— y el plan, que es el producto, había quedado
 * de tercero. Lo que se usa una vez al mes no puede competir por sitio con lo
 * que se mira cada día.
 *
 * Así que aquí baja **lo permanente**: quién eres, cómo te encuentra el coach,
 * tu plan en un archivo, y la salida. Lo que se queda en la hoja son las dos
 * cosas que se hacen *con* el entrenamiento del día: subir la actividad y
 * mirar la técnica.
 *
 * Cerrar sesión vive aquí y no en la hoja a propósito. Estaba junto al orbe,
 * donde el pulgar aterriza al querer hablar: el destino de un botón importa
 * tanto como su etiqueta, y ese vecindario era un accidente esperando.
 */

import { RegistrationMark } from "../components/Sheet";
import { TelegramLink } from "../components/TelegramLink";
import { useT } from "../i18n";

interface Props {
  email: string;
  nombre?: string | null;
  meta?: string;
  /** Si hay plan que descargar. Sin él la fila no aparece. */
  hasPlan: boolean;
  descargando: boolean;
  errorCsv: string;
  onDescargar: () => void;
  onSignOut: () => void;
  onClose: () => void;
}

function Dato({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="px-4 py-3">
      <div className="label">{label}</div>
      <div className="mt-0.5 text-[0.9375rem] font-medium break-words">{children}</div>
    </div>
  );
}

export function Profile({
  email,
  nombre,
  meta,
  hasPlan,
  descargando,
  errorCsv,
  onDescargar,
  onSignOut,
  onClose,
}: Props) {
  const { t } = useT();

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
          {t("close")}
        </button>
        <h1 className="text-center text-[0.9375rem] font-semibold">{t("profileTitle")}</h1>
        <RegistrationMark />
      </header>

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="divide-y divide-ink-15 border-b border-ink-15">
          {/* Sin nombre se dice que no lo hay, en vez de dejar el hueco. Un
              renglón vacío parece un fallo de carga; «sin nombre» es un dato. */}
          <Dato label={t("profileName")}>
            {nombre?.trim() || <span className="text-ink-50">{t("profileNoName")}</span>}
          </Dato>
          <Dato label={t("profileEmail")}>{email}</Dato>
          <Dato label={t("profileGoal")}>{meta || "—"}</Dato>
        </div>

        {hasPlan && (
          <div className="border-b border-ink-15">
            <button
              type="button"
              onClick={onDescargar}
              disabled={descargando}
              className="label w-full px-4 py-3 text-left transition-colors hover:bg-ink hover:text-paper disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-ink-70"
            >
              {t("exportCsv")}
            </button>
            {errorCsv && (
              <p role="alert" className="px-4 pb-3 text-[0.8125rem] text-ink-70">
                {errorCsv}
              </p>
            )}
          </div>
        )}

        <TelegramLink />

        {/* Separado del resto y abajo del todo: es la única acción de esta
            pantalla que deshace algo. */}
        <div className="mt-8 border-t border-ink-15">
          <button
            type="button"
            onClick={onSignOut}
            className="label w-full px-4 py-4 text-left transition-colors hover:bg-flag hover:text-paper"
          >
            {t("signOut")}
          </button>
        </div>
      </div>
    </div>
  );
}
