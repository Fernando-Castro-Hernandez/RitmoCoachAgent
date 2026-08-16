"""Endpoint WebSocket: el lado del navegador del puente.

Dos bombas corriendo en paralelo mientras dure la sesión:

    navegador → Bedrock    frames de micrófono y texto
    Bedrock → navegador    audio, transcripciones y fin de turno

Ninguna de las dos acumula: reenvían en cuanto reciben.
"""

from __future__ import annotations

import asyncio
import contextlib

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.api.bridge import NovaBridge
from apps.api.config import get_settings
from apps.api.prompts import build_system_prompt
from apps.api.renewal import ConversationContext, RenewingBridge

log = structlog.get_logger(__name__)
router = APIRouter()


async def _browser_to_bedrock(ws: WebSocket, bridge: RenewingBridge) -> None:
    while True:
        mensaje = await ws.receive_json()
        tipo = mensaje.get("type")
        if tipo == "audio":
            await bridge.send_audio(mensaje["data"])
        elif tipo == "text":
            await bridge.send_text(mensaje["text"])
        elif tipo == "barge_in":
            # No manda nada a Bedrock: sólo arranca el cronómetro de la
            # interrupción. Nova ya detecta el habla encima por su cuenta.
            bridge.mark_barge_in()
        elif tipo == "stop":
            return


async def _bedrock_to_browser(ws: WebSocket, bridge: RenewingBridge) -> None:
    async for evento in bridge.events():
        if evento.kind == "audio":
            await ws.send_json({"type": "audio", "data": evento.payload["audio_b64"]})
        elif evento.kind == "transcript":
            await ws.send_json(
                {
                    "type": "transcript",
                    "text": evento.payload["text"],
                    "role": evento.payload["role"],
                }
            )
        elif evento.kind == "turn_end":
            await ws.send_json({"type": "turn_end"})
        elif evento.kind == "error":
            await ws.send_json({"type": "error", "message": evento.payload["message"]})
            return


@router.websocket("/ws/voice/{user_id}")
async def voice_socket(ws: WebSocket, user_id: str) -> None:
    await ws.accept()
    settings = get_settings()

    # El puente se releva a sí mismo antes de que Bedrock corte a los 8 minutos.
    # El navegador no se entera: `events()` sobrevive al relevo (ADR 0002).
    bridge = RenewingBridge(
        NovaBridge,
        ConversationContext(base_prompt=build_system_prompt()),
        renew_after_s=settings.session_renew_after_s,
        voice_id=settings.nova_voice_id,
    )

    try:
        await bridge.start()
        await ws.send_json({"type": "ready"})
        log.info("ws.session_open", user_id=user_id)

        tareas = [
            asyncio.create_task(_browser_to_bedrock(ws, bridge)),
            asyncio.create_task(_bedrock_to_browser(ws, bridge)),
        ]
        # La primera que termine cierra la sesión: si el navegador se va, no
        # tiene sentido seguir leyendo de Bedrock, y viceversa.
        hechas, pendientes = await asyncio.wait(tareas, return_when=asyncio.FIRST_COMPLETED)
        for tarea in pendientes:
            tarea.cancel()
        for tarea in hechas:
            with contextlib.suppress(Exception):
                tarea.result()

    except WebSocketDisconnect:
        log.info("ws.disconnected", user_id=user_id)
    except Exception as exc:
        log.error("ws.failed", user_id=user_id, error=str(exc))
        with contextlib.suppress(Exception):
            await ws.send_json({"type": "error", "message": str(exc)})
    finally:
        await bridge.close()
        with contextlib.suppress(Exception):
            await ws.close()
        log.info("ws.session_closed", user_id=user_id)
