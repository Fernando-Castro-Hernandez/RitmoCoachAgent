/**
 * La portada. Lo primero que ve alguien que no tiene cuenta.
 *
 * Sigue siendo la Hoja de Valoración: cabecera de formulario, reglas de pelo,
 * versalitas espaciadas, cifras tabulares, cero esquinas redondeadas. Una
 * portada con degradados y tarjetas flotantes rompería el mundo antes de que
 * el corredor entre en él — y el mundo **es** el argumento: esto se parece a un
 * documento clínico porque se comporta como uno.
 *
 * ## Qué se cuenta, y en qué orden
 *
 * Las tres afirmaciones del producto, cada una con lo que la respalda:
 *
 * 1. **Habla, no escribe.** Es voz en tiempo real, no un chat con botón de
 *    micrófono.
 * 2. **Los números no los inventa.** Salen de un motor determinista. Es la
 *    diferencia entre un coach y un modelo de lenguaje con buen tono.
 * 3. **Sabe cuándo callarse.** Una puerta de seguridad evaluada ANTES de que
 *    el modelo redacte, que en rojo le quita las herramientas de prescripción.
 *
 * No hay capturas ni testimonios: no los hay de verdad, y ponerlos falsos sería
 * exactamente lo que este producto dice no hacer.
 */

import { useLocale, useT } from "../i18n";

const RITMO_DEMO = "5:34";

function Regla({ n, titulo, cuerpo }: { n: string; titulo: string; cuerpo: string }) {
  return (
    <article className="grid grid-cols-[2.5rem_1fr] gap-x-4 border-b border-ink-15 py-6">
      {/* Los números SÍ son una secuencia aquí: son tres afirmaciones que se
          apoyan en orden, no tres tarjetas intercambiables. */}
      <span className="label fig pt-1 text-ink-30">{n}</span>
      <div>
        <h3 className="text-[1.0625rem] font-semibold">{titulo}</h3>
        <p className="mt-1.5 max-w-prose text-[0.9375rem] leading-relaxed text-ink-70">{cuerpo}</p>
      </div>
    </article>
  );
}

export function Landing({ onEnter, onCreate }: { onEnter: () => void; onCreate: () => void }) {
  const { t, locale } = useT();
  const setLocale = useLocale((s) => s.setLocale);

  return (
    <div className="mx-auto flex min-h-dvh max-w-3xl flex-col px-4">
      <header className="flex items-center justify-between border-b border-ink py-3">
        <span className="label">{t("formCodeLanding")}</span>
        <span className="text-[0.9375rem] font-semibold tracking-[0.3em]">RITMO</span>
        <button
          type="button"
          onClick={() => setLocale(locale === "es" ? "en" : "es")}
          className="label border border-ink-15 px-2 py-1 transition-colors hover:border-ink"
        >
          {locale === "es" ? "EN" : "ES"}
        </button>
      </header>

      <main className="min-h-0 flex-1">
        {/* El titular es la tesis, no un eslogan. */}
        <section className="border-b border-ink-15 py-10">
          <h1 className="max-w-[18ch] text-4xl leading-[1.05] font-semibold tracking-tight text-balance sm:text-5xl">
            {t("landingTitle")}
          </h1>
          <p className="mt-4 max-w-prose text-[1.0625rem] leading-relaxed text-ink-70">
            {t("landingSub")}
          </p>

          <div className="mt-7 flex flex-col gap-3 sm:flex-row">
            <button
              type="button"
              onClick={onCreate}
              className="min-h-13 bg-proof px-7 text-[1.0625rem] font-medium text-paper transition-colors hover:bg-proof-deep sm:min-w-56"
            >
              {t("landingCreate")}
            </button>
            <button
              type="button"
              onClick={onEnter}
              className="min-h-13 border border-ink px-7 text-[1.0625rem] font-medium transition-colors hover:bg-ink hover:text-paper sm:min-w-48"
            >
              {t("landingEnter")}
            </button>
          </div>
        </section>

        {/* Un campo de la hoja de verdad, como muestra del mundo al que entras.
            Va marcado como ejemplo: enseñar una cifra sin marcar sería romper la
            regla que el propio bloque de al lado promete. */}
        <section className="border-b border-ink-15 py-8">
          <div className="flex items-baseline justify-between">
            <span className="label">{t("landingSampleLabel")}</span>
            <span className="label border border-dashed border-ink-30 px-1.5">{t("specimen")}</span>
          </div>
          <div className="mt-3 bg-proof px-5 py-6 text-paper">
            {/* `label-on-proof` y no `opacity`: la clase mezcla papel con azul
                para conservar el contraste. Bajarle la opacidad al gris de
                tinta lo deja casi invisible sobre el campo — lo vi en la
                primera captura. */}
            <span className="label label-on-proof">
              {t("today")} · {t("kindLong")}
            </span>
            <p className="fig mt-1 text-6xl leading-none font-semibold tracking-tight">
              18<span className="text-2xl"> km</span>
            </p>
            <p className="fig mt-3 text-[1.0625rem]">
              {RITMO_DEMO}–6:14 <span className="label label-on-proof">/km</span>
            </p>
          </div>
          <p className="mt-3 max-w-prose text-[0.875rem] text-ink-70">{t("landingSampleWhy")}</p>
        </section>

        <section className="py-2">
          <Regla n="01" titulo={t("landingR1")} cuerpo={t("landingR1Body")} />
          <Regla n="02" titulo={t("landingR2")} cuerpo={t("landingR2Body")} />
          <Regla n="03" titulo={t("landingR3")} cuerpo={t("landingR3Body")} />
        </section>

        <section className="border-b border-ink-15 py-8">
          <p className="max-w-prose text-[0.9375rem] leading-relaxed text-ink-70">
            {t("landingNotMedical")}
          </p>
        </section>
      </main>

      <footer className="flex items-center justify-between py-4">
        <span className="label">{t("landingFooter")}</span>
        <button
          type="button"
          onClick={onEnter}
          className="label underline decoration-ink-30 underline-offset-4 transition-colors hover:text-ink"
        >
          {t("landingEnter")}
        </button>
      </footer>
    </div>
  );
}
