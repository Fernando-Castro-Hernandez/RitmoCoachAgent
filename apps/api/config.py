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
    # Cadena de modelos de visión, en orden de preferencia y separada por comas.
    #
    # Es una cadena y no un modelo único porque la disponibilidad resultó ser
    # el problema real, no la capacidad: en esta cuenta los seis modelos con
    # visión están bloqueados por la misma cuota diaria en 0, y los de Anthropic
    # además por un acuerdo pendiente. Con una lista, desbloquear cualquiera de
    # ellos hace funcionar la ruta sin tocar código ni volver a desplegar.
    #
    # El prefijo «us.» no es opcional: estos modelos no admiten invocación
    # directa («on-demand throughput isn't supported»), sólo a través de un
    # perfil de inferencia entre regiones (ADR 0014).
    vision_model_chain: str = (
        "us.anthropic.claude-haiku-4-5-20251001-v1:0,us.amazon.nova-2-lite-v1:0"
    )

    database_url: str = "postgresql+psycopg://ritmo:ritmo@localhost:5432/ritmo"
    bedrock_guardrail_id: str = ""
    bedrock_guardrail_version: str = "DRAFT"
    telegram_bot_token: str = ""
    telegram_bot_username: str = ""

    @property
    def vision_models(self) -> list[str]:
        return [m.strip() for m in self.vision_model_chain.split(",") if m.strip()]

    @property
    def endpoint_uri(self) -> str:
        return f"https://bedrock-runtime.{self.aws_region}.amazonaws.com"


@lru_cache
def get_settings() -> Settings:
    return Settings()
