"""Verificación de la renovación de sesión contra Bedrock real — tarea A4.

Manda un turno, espera a que se cumpla el plazo de renovación, y manda un
segundo turno que **sólo puede contestar bien si conserva el contexto**.

Arranca la API con el plazo bajado para no esperar ocho minutos:
    SESSION_RENEW_AFTER_S=15 uv run poe api

Luego:
    uv run python spikes/renewal_check.py
"""

from __future__ import annotations

import asyncio
import json
import sys

import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "ws://localhost:8000/ws/voice/verificacion-renovacion"
ESPERA_RENOVACION = 22  # debe superar SESSION_RENEW_AFTER_S


async def turno(ws: websockets.ClientConnection, texto: str) -> tuple[int, str]:
    """Manda un turno y recoge la respuesta hasta que se hace el silencio."""
    await ws.send(json.dumps({"type": "text", "text": texto}))
    chunks = 0
    partes: list[str] = []
    try:
        while True:
            mensaje = json.loads(await asyncio.wait_for(ws.recv(), timeout=12))
            if mensaje["type"] == "audio":
                chunks += 1
            elif mensaje["type"] == "transcript" and mensaje["role"] == "ASSISTANT":
                partes.append(mensaje["text"])
            elif mensaje["type"] == "error":
                return 0, f"ERROR: {mensaje['message']}"
    except TimeoutError:
        pass
    return chunks, " ".join(partes).strip()


async def main() -> int:
    async with websockets.connect(URL, open_timeout=20) as ws:
        listo = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if listo.get("type") != "ready":
            print(f"✗ el servidor no reportó listo: {listo}")
            return 1
        print("✓ sesión abierta\n")

        chunks1, texto1 = await turno(
            ws, "Me llamo Fernando y entreno para un maratón. Salúdame por mi nombre."
        )
        print(f"TURNO 1 · {chunks1} chunks")
        print(f"  {texto1}\n")

        print(f"esperando {ESPERA_RENOVACION}s para que ocurra la renovación…\n")
        await asyncio.sleep(ESPERA_RENOVACION)

        chunks2, texto2 = await turno(ws, "¿Cómo me llamo y para qué entreno?")
        print(f"TURNO 2 · {chunks2} chunks  (después de la renovación)")
        print(f"  {texto2}\n")

    if chunks1 == 0 or chunks2 == 0:
        print("✗ algún turno se quedó sin audio")
        return 1

    recuerda = "fernando" in texto2.lower() and (
        "maratón" in texto2.lower() or "maraton" in texto2.lower()
    )
    if not recuerda:
        print("✗ la sesión nueva perdió el contexto de la anterior")
        return 1

    print("✓ RENOVACIÓN TRANSPARENTE: la conversación sobrevivió con su contexto")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
