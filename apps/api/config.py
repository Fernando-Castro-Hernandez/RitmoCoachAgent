"""Configuración de la API, leída del entorno."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_region: str = "us-east-1"
    nova_model_id: str = "amazon.nova-2-sonic-v1:0"
    # En minúsculas por obligación de la API, no por estilo. Ver ADR 0002.
    nova_voice_id: str = "carlos"

    max_tokens: int = 1024
    top_p: float = 0.9
    temperature: float = 0.7

    # Nova Sonic corta la conexión a los 8 minutos. Se renueva antes, con
    # solapamiento, para que el usuario no perciba el corte (tarea A4).
    session_renew_after_s: int = 450

    # Ruta de visión (ADR 0014). Modelo distinto y protocolo distinto: Nova 2
    # Sonic sólo acepta SPEECH, así que no puede leer una imagen.
    # ─── Visión · API directa de Anthropic (ADR 0014) ────────────────
    #
    # La ruta de visión salió de AWS. No es preferencia de modelo: en la cuenta
    # de Bedrock los seis modelos con visión tenían la cuota diaria en 0 y los
    # de Anthropic además el acuerdo pendiente. Con saldo propio en la
    # plataforma de Anthropic, la ruta deja de depender de eso.
    #
    # La voz se queda en Bedrock y no se toca: Anthropic no tiene streaming
    # bidireccional de voz y Nova Sonic sí.
    anthropic_api_key: str = ""

    # Cadena ordenada, separada por comas. Sigue siendo una lista aunque hoy
    # lleve un solo modelo: es lo que permitió sobrevivir al bloqueo de AWS sin
    # tocar código, y cuesta cero mantenerla.
    #
    # OJO con el modelo: Claude 3.5 Haiku **no acepta imágenes**. El Haiku que
    # sí las acepta es el 4.5. Ver la nota del ADR 0014.
    vision_model_chain: str = "claude-haiku-4-5-20251001"

    database_url: str = "postgresql+psycopg://ritmo:ritmo@localhost:5432/ritmo"
    bedrock_guardrail_id: str = ""
    bedrock_guardrail_version: str = "DRAFT"
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""
    # El webhook es un endpoint público que escribe vinculaciones. Telegram
    # reenvía este valor en `X-Telegram-Bot-Api-Secret-Token`; sin él configurado
    # el endpoint se cierra en vez de abrirse (ver `telegram_api.py`).
    telegram_webhook_secret: str = ""

    # Con lo que se firman los tokens de sesión. Vive aquí y no en os.getenv
    # porque `os.getenv` NO ve el archivo `.env` — sólo el entorno del proceso.
    # Estuvo leyéndose así y el resultado era silencioso y malo: la clave puesta
    # en `.env` se ignoraba y la API firmaba con un secreto efímero, así que
    # cada reinicio cerraba la sesión de todo el mundo sin que nada lo dijera.
    jwt_secret: str = ""

    # Llave que usa n8n para preguntar a quién le toca un aviso. Esas respuestas
    # llevan datos de salud de personas concretas, así que sin llave el endpoint
    # cierra (503) en vez de caer abierto. Ver `automation_api.py`.
    automation_api_key: str = ""

    @property
    def vision_models(self) -> list[str]:
        return [m.strip() for m in self.vision_model_chain.split(",") if m.strip()]

    @property
    def endpoint_uri(self) -> str:
        return f"https://bedrock-runtime.{self.aws_region}.amazonaws.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
