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

from apps.api.automation_api import router as automation_router
from apps.api.credentials import ensure_aws_credentials
from apps.api.logging_setup import configure_logging
from apps.api.profile_api import router as profile_router
from apps.api.prompts import VERSION as PROMPT_VERSION
from apps.api.telegram_api import router as telegram_router
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

app.include_router(ws_router)
app.include_router(profile_router)
app.include_router(vision_router)
app.include_router(telegram_router)
app.include_router(automation_router)


@app.get("/api/health")
def health() -> dict[str, Any]:
    """Sonda de salud. La usa el healthcheck de Docker y el balanceador."""
    return {"status": "ok", "domain": domain_version}


@app.get("/api/config")
def config() -> dict[str, Any]:
    """Configuración efectiva, sin secretos.

    Sirve para confirmar de un vistazo qué modelo de voz está activo, que es la
    variable que cambia si la cuenta no tiene cuota para Nova 2 Sonic.
    """
    return {
        "region": os.getenv("AWS_REGION", "us-east-1"),
        "model_id": os.getenv("NOVA_MODEL_ID", "amazon.nova-2-sonic-v1:0"),
        "voice_id": os.getenv("NOVA_VOICE_ID", "carlos"),
        "vision_model_id": os.getenv("VISION_MODEL_ID", "us.amazon.nova-2-lite-v1:0"),
        "prompt_version": PROMPT_VERSION,
        "aws_credentials_resolved": bool(os.getenv("AWS_ACCESS_KEY_ID")),
        "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "langfuse_configured": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
    }
