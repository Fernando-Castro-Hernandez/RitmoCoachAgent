"""Endpoint WebSocket: el lado del navegador del puente.

Dos bombas corriendo en paralelo mientras dure la sesión:

    navegador → Bedrock    frames de micrófono y texto
    Bedrock → navegador    audio, transcripciones y fin de turno

Ninguna de las dos acumula: reenvían en cuanto reciben.

**El token viaja en la URL, y hay que decir por qué.** Los navegadores no dejan
poner cabeceras al abrir un WebSocket, así que la única forma de autenticar el
apretón de manos es la query string — y eso significa que el token acaba en los
logs del proxy. Se acota con la vida corta del token (siete días, ver `auth.py`)
y sabiendo que es el precio de no tener un segundo mecanismo de sesión.

Lo que NO se hace es aceptar el `user_id` de la ruta. Antes cualquiera podía
abrir `/ws/voice/<lo-que-sea>` y hablar como esa persona. Ahora la ruta no lleva
identificador: lo pone el token o no hay sesión.
"""

from __future__ import annotations

import asyncio
import contextlib

import structlog
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from apps.api.auth import usuario_de_token
from apps.api.bridge import NovaBridge
from apps.api.config import get_settings
from apps.api.db.session import get_sessionmaker
from apps.api.prompts import build_system_prompt
from apps.api.renewal import ConversationContext, RenewingBridge
from apps.api.tool_runner import ToolRunner

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


@router.websocket("/ws/voice")
async def voice_socket(ws: WebSocket, token: str = "") -> None:
    settings = get_settings()

    # Se autentica ANTES de aceptar. Aceptar y cerrar después deja el micrófono
    # del navegador abierto un instante y le dice a quien prueba que la ruta
    # existe y responde.
    async with get_sessionmaker()() as sesion:
        usuario = await usuario_de_token(sesion, token)
    if usuario is None:
        # 1008 · violación de política. El frontend lo distingue de una caída de
        # red y manda a la pantalla de entrada en vez de reintentar en bucle.
        await ws.close(code=1008, reason="sesión inválida")
        log.info("ws.rechazado")
        return

    user_id = usuario.id
    await ws.accept()

    # El `user_id` sale del WebSocket y se le impone a cada herramienta. El que
    # mande el modelo en los argumentos se descarta: ver `tool_runner.py`.
    herramientas = ToolRunner(get_sessionmaker(), user_id=user_id)

    # El puente se releva a sí mismo antes de que Bedrock corte a los 8 minutos.
    # El navegador no se entera: `events()` sobrevive al relevo (ADR 0002).
    #
    # El ejecutor viaja en la fábrica para que el puente NUEVO de cada relevo
    # nazca con las herramientas ya declaradas. Sin esto el coach perdería la
    # capacidad de consultar nada a los siete minutos y medio de conversación,
    # que es el momento en que menos se nota mirando y más duele.
    bridge = RenewingBridge(
        lambda: NovaBridge(tool_runner=herramientas),
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
