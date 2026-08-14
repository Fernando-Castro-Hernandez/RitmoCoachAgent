"""Punto de entrada de la API de Ritmo.

El WebSocket de voz se añade en la tarea A3 y las herramientas de dominio en la
C2. Por ahora expone salud y configuración para que el compose sea verificable.
"""

from __future__ import annotations

import os
from typing import Any

from coach_domain import __version__ as domain_version
from fastapi import FastAPI

app = FastAPI(
    title="Ritmo",
    description="Coach de voz conversacional para runners de 5K a maratón",
    version="0.1.0",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)


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
        "voice_id": os.getenv("NOVA_VOICE_ID", "Lupe"),
        "telegram_configured": bool(os.getenv("TELEGRAM_BOT_TOKEN")),
        "langfuse_configured": bool(os.getenv("LANGFUSE_PUBLIC_KEY")),
    }
