"""Punto de entrada de la API de Ritmo.

El WebSocket de voz se añade en la tarea A3 y las herramientas de dominio en la
C2. Por ahora expone salud y configuración para que el compose sea verificable.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from coach_domain import __version__ as domain_version
from fastapi import FastAPI

from apps.api.auth_api import router as auth_router
from apps.api.automation_api import router as automation_router
from apps.api.config import get_settings
from apps.api.credentials import ensure_aws_credentials
from apps.api.debug import router as debug_router
from apps.api.logging_setup import configure_logging
from apps.api.profile_api import router as profile_router
from apps.api.prompts import VERSION as PROMPT_VERSION
from apps.api.telegram_api import router as telegram_router
from apps.api.today_api import router as today_router
from apps.api.vision_api import router as vision_router
from apps.api.ws import router as ws_router


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    configure_logging()
    # Se resuelven al arrancar, no en cada sesión: si faltan, el problema se ve
    # en el log de inicio y no a mitad de una conversación.
    ensure_aws_credentials()
    yield


app = FastAPI(
    lifespan=lifespan,
    title="Ritmo",
    description="Coach de voz conversacional para runners de 5K a maratón",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

app.include_router(auth_router)
app.include_router(ws_router)
app.include_router(profile_router)
app.include_router(vision_router)
app.include_router(today_router)
app.include_router(telegram_router)
app.include_router(automation_router)
app.include_router(debug_router)


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Sonda de salud. La usa el healthcheck de Docker y el balanceador."""
    return {"status": "ok", "domain": domain_version}


@app.get("/api/config")
def config() -> dict[str, Any]:
    """Configuración efectiva, sin secretos.

    **Lee `Settings`, no `os.getenv`.** Es la corrección de un endpoint que
    mentía: `os.getenv` no ve el archivo `.env`, así que esto informaba «sin
    configurar» de cosas que sí lo estaban. Un panel de diagnóstico que miente
    es peor que no tenerlo — se usa justo cuando algo va mal, que es cuando
    menos se puede permitir despistar.
    """
    ajustes = get_settings()
    return {
        "region": ajustes.aws_region,
        "model_id": ajustes.nova_model_id,
        "voice_id": ajustes.nova_voice_id,
        "vision_model_chain": ajustes.vision_models,
        "prompt_version": PROMPT_VERSION,
        # Éstas sí son del entorno del proceso: las resuelve el SDK de AWS desde
        # el perfil o el rol de instancia, no desde `.env`.
        "aws_credentials_resolved": bool(os.getenv("AWS_ACCESS_KEY_ID")),
        "telegram_configured": bool(ajustes.telegram_bot_token and ajustes.telegram_bot_username),
        "telegram_webhook_configured": bool(ajustes.telegram_webhook_secret),
        "automation_configured": bool(ajustes.automation_api_key),
        "vision_configured": bool(ajustes.anthropic_api_key),
        # Sin esto los tokens se firman con un secreto de proceso y reiniciar
        # la API cierra la sesión de todo el mundo. Ver auth.py.
        "jwt_secret_configured": bool(ajustes.jwt_secret),
        "langfuse_configured": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
    }
