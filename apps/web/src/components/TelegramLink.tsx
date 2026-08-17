/**
 * Vincular Telegram, desde la hoja.
 *
 * Es el canal por el que sale el coach proactivo: el recordatorio de la mañana,
 * el check-in después de correr y —el que importa— el aviso cuando una molestia
 * lleva tres días. Sin esto vinculado, los cinco flujos de n8n no tienen a dónde
 * escribir.
 *
 * Tres decisiones que valen la pena decir:
 *
 * - **El enlace se pide al tocar, no al pintar la pantalla.** El token dura
 *   quince minutos y es de un solo uso; emitirlo al montar significa que casi
 *   siempre estaría caducado cuando alguien por fin lo toca.
 * - **Si no hay bot configurado, se dice.** No se ofrece un botón que lleva a
 *   una URL rota: el backend devuelve `deep_link: null` y aquí se convierte en
 *   una línea que explica que el canal no está disponible.
 * - **Vinculado se muestra en azul de proceso**, que en este producto significa
 *   «el sistema está vivo por aquí». Es el mismo azul del orbe y del campo de
 *   la sesión, no un verde de éxito que no existe en la paleta.
 */

import { useEffect, useState } from "react";

import { crearEnlaceTelegram, estadoTelegram } from "../api";
import { useT } from "../i18n";

type Estado = "cargando" | "sin-vincular" | "vinculado" | "sin-bot" | "error";

export function TelegramLink() {
  const { t } = useT();
  const [estado, setEstado] = useState<Estado>("cargando");
  const [pidiendo, setPidiendo] = useState(false);

  useEffect(() => {
    let vivo = true;
    estadoTelegram()
      .then((r) => {
        if (!vivo) return;
        setEstado(!r.bot_configured ? "sin-bot" : r.linked ? "vinculado" : "sin-vincular");
      })
      .catch(() => vivo && setEstado("error"));
    return () => {
      vivo = false;
    };
  }, []);

  const vincular = async () => {
    setPidiendo(true);
    try {
      const { deep_link } = await crearEnlaceTelegram();
      if (!deep_link) {
        setEstado("sin-bot");
        return;
      }
      // `noopener` es obligatorio con `_blank`: sin él la pestaña abierta puede
      // manipular la nuestra a través de `window.opener`.
      window.open(deep_link, "_blank", "noopener,noreferrer");
    } catch {
      setEstado("error");
    } finally {
      setPidiendo(false);
    }
  };

  if (estado === "cargando") return null;

  return (
    <div className="border-t border-ink-15 px-4 py-3">
      <div className="flex items-baseline justify-between gap-3">
        <span className="label">{t("tgTitle")}</span>
        {estado === "vinculado" && <span className="label !text-proof">{t("tgLinked")}</span>}
      </div>

      {estado === "vinculado" && (
        <p className="mt-1 text-[0.875rem] text-ink-70">{t("tgLinkedWhy")}</p>
      )}

      {estado === "sin-vincular" && (
        <>
          <p className="mt-1 text-[0.875rem] text-ink-70">{t("tgWhy")}</p>
          <button
            type="button"
            onClick={vincular}
            disabled={pidiendo}
            className="mt-3 min-h-11 w-full border border-ink px-4 text-[0.9375rem] font-medium transition-colors hover:bg-ink hover:text-paper disabled:border-ink-15 disabled:text-ink-70"
          >
            {pidiendo ? t("tgOpening") : t("tgConnect")}
          </button>
          <p className="label mt-2">{t("tgExpires")}</p>
        </>
      )}

      {estado === "sin-bot" && <p className="mt-1 text-[0.875rem] text-ink-70">{t("tgNoBot")}</p>}

      {estado === "error" && (
        <p className="mt-1 text-[0.875rem] text-ink-70">{t("tgError")}</p>
      )}
    </div>
  );
}
