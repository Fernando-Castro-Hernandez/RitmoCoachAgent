"""Verificación del endpoint WebSocket — tarea A3.

Se conecta como si fuera el navegador, manda un turno de texto y cuenta el audio
que vuelve. Comprueba el circuito completo del servidor sin necesitar micrófono:

    cliente → WebSocket → NovaBridge → Bedrock → audio → WebSocket → cliente

Uso (con la API corriendo en el puerto 8000):
    uv run python spikes/ws_check.py
"""

from __future__ import annotations

import asyncio
import json
import sys
import time

import websockets

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

URL = "ws://localhost:8000/ws/voice/verificacion"


async def main() -> int:
    audio_chunks = 0
    transcripciones: list[str] = []
    t_envio: float | None = None
    ttfa_ms: float | None = None

    async with websockets.connect(URL, open_timeout=20) as ws:
        listo = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
        if listo.get("type") != "ready":
            print(f"✗ el servidor no reportó listo: {listo}")
            return 1
        print("✓ sesión abierta contra Bedrock")

        await ws.send(
            json.dumps({"type": "text", "text": "Hola, ¿me escuchas? Contesta en una frase."})
        )
        t_envio = time.monotonic()

        try:
            while True:
                mensaje = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                tipo = mensaje.get("type")
                if tipo == "audio":
                    if audio_chunks == 0 and t_envio:
                        ttfa_ms = (time.monotonic() - t_envio) * 1000
                    audio_chunks += 1
                elif tipo == "transcript":
                    transcripciones.append(f"{mensaje['role']}: {mensaje['text']}")
                elif tipo == "error":
                    print(f"✗ error del servidor: {mensaje['message']}")
                    return 1
        except TimeoutError:
            pass

    for linea in transcripciones:
        print(f"  {linea}")
    print(f"  chunks de audio : {audio_chunks}")
    if ttfa_ms is not None:
        print(f"  ttfa            : {ttfa_ms:.0f} ms  (desde texto, no desde voz)")

    if audio_chunks == 0:
        print("✗ no llegó audio por el WebSocket")
        return 1
    print("✓ CIRCUITO COMPLETO: el audio del coach llega al cliente")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
