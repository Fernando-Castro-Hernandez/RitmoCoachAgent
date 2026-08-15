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
    # El prefijo «us.» no es opcional: Nova 2 Lite no admite invocación directa
    # («on-demand throughput isn't supported»), sólo a través de un perfil de
    # inferencia entre regiones. Verificado con list-inference-profiles.
    vision_model_id: str = "us.amazon.nova-2-lite-v1:0"
    vision_fallback_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

    database_url: str = "postgresql+psycopg://ritmo:ritmo@localhost:5432/ritmo"
    bedrock_guardrail_id: str = ""
    bedrock_guardrail_version: str = "DRAFT"
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    @property
    def endpoint_uri(self) -> str:
        return f"https://bedrock-runtime.{self.aws_region}.amazonaws.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
