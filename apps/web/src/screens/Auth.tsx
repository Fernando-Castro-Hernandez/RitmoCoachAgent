/**
 * Entrar o crear cuenta.
 *
 * Un solo formulario con dos modos, no dos pantallas. Quien llega no siempre
 * sabe si ya tiene cuenta, y hacerle elegir antes de escribir nada es una
 * decisión que no puede tomar todavía. El campo del correo se conserva al
 * cambiar de modo, que es justo lo que hace falta cuando el intento de entrar
 * falla porque en realidad nunca se registró.
 *
 * Sigue la gramática de la hoja: cabecera de formulario, campos reglados,
 * ninguna esquina redondeada. Es la primera pantalla que ve alguien, así que es
 * donde el mundo visual tiene que quedar establecido — si aquí pareciera una
 * pantalla de login genérica, el resto ya no lo recupera.
 */

import { type FormEvent, useState } from "react";

import { ApiError, type Sesion, login, register, setToken } from "../api";
import { RegistrationMark } from "../components/Sheet";
import { useT } from "../i18n";

/** El mismo mínimo que valida el backend. Repetido aquí para avisar antes de
 *  gastar un viaje al servidor, no para sustituir su validación. */
const MIN_CLAVE = 8;

export function Auth({ onReady }: { onReady: (s: Sesion) => void }) {
  const { t } = useT();
  const [modo, setModo] = useState<"entrar" | "crear">("entrar");
  const [email, setEmail] = useState("");
  const [clave, setClave] = useState("");
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const claveCorta = modo === "crear" && clave.length > 0 && clave.length < MIN_CLAVE;
  const puedeEnviar = email.includes("@") && clave.length >= (modo === "crear" ? MIN_CLAVE : 1);

  const enviar = async (e: FormEvent) => {
    e.preventDefault();
    if (!puedeEnviar || enviando) return;
    setEnviando(true);
    setError("");
    try {
      const sesion = await (modo === "crear" ? register : login)(email, clave);
      setToken(sesion.token);
      onReady(sesion);
    } catch (err) {
      // El mensaje viene del backend, que a propósito no distingue «no existe»
      // de «contraseña mala»: distinguirlos convierte el login en un buscador
      // de correos registrados.
      setError(err instanceof ApiError ? err.message : t("authFailed"));
      setEnviando(false);
    }
  };

  return (
    <div className="mx-auto flex h-dvh max-w-lg flex-col">
      <header className="flex items-center justify-between border-b border-ink px-4 py-3">
        <span className="label">{t("formCodeAuth")}</span>
        <RegistrationMark />
      </header>

      <form onSubmit={enviar} className="min-h-0 flex-1 overflow-y-auto">
        <div className="border-b border-ink-15 px-4 py-6">
          <h1 className="text-2xl font-semibold">{t("brand")}</h1>
          <p className="mt-1 text-[0.9375rem] text-ink-70">
            {modo === "crear" ? t("authNewHint") : t("authBackHint")}
          </p>
        </div>

        <div className="divide-y divide-ink-15 border-b border-ink-15">
          <label className="block px-4 py-3">
            <span className="label">{t("authEmail")}</span>
            <input
              type="email"
              value={email}
              autoComplete="email"
              inputMode="email"
              onChange={(e) => setEmail(e.target.value)}
              className="mt-1 w-full border-b border-ink bg-transparent py-2 text-[1.0625rem] focus:outline-none"
            />
          </label>

          <label className="block px-4 py-3">
            <span className="label">{t("authPassword")}</span>
            <input
              type="password"
              value={clave}
              /* `new-password` al crear: es lo que hace que el gestor de
                 contraseñas ofrezca generar una en vez de rellenar la vieja. */
              autoComplete={modo === "crear" ? "new-password" : "current-password"}
              onChange={(e) => setClave(e.target.value)}
              className={`mt-1 w-full border-b bg-transparent py-2 text-[1.0625rem] focus:outline-none ${
                claveCorta ? "border-caution" : "border-ink"
              }`}
            />
            {modo === "crear" && (
              <span className={`label mt-1 block ${claveCorta ? "!text-caution" : ""}`}>
                {t("authMinChars", { n: MIN_CLAVE })}
              </span>
            )}
          </label>
        </div>

        {error && (
          <p role="alert" className="mx-4 mt-4 border-l-2 border-flag px-3 py-2 text-[0.875rem]">
            {error}
          </p>
        )}

        <div className="px-4 py-6">
          <button
            type="submit"
            disabled={!puedeEnviar || enviando}
            className="min-h-13 w-full bg-proof px-6 text-[1.0625rem] font-medium text-paper transition-colors hover:bg-proof-deep disabled:bg-ink-08 disabled:text-ink-70"
          >
            {enviando ? t("authWorking") : modo === "crear" ? t("authCreate") : t("authEnter")}
          </button>

          <button
            type="button"
            onClick={() => {
              // El correo se conserva: quien falla al entrar suele descubrir
              // aquí que en realidad nunca se registró.
              setModo(modo === "crear" ? "entrar" : "crear");
              setError("");
            }}
            className="label mt-3 w-full py-3 text-center underline decoration-ink-30 underline-offset-4 transition-colors hover:text-ink"
          >
            {modo === "crear" ? t("authHaveAccount") : t("authNoAccount")}
          </button>
        </div>
      </form>
    </div>
  );
}
