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
