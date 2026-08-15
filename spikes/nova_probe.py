"""Sonda de conectividad contra Nova Sonic — tarea A2.

Código de exploración, no de producción. Su salida es una respuesta:
**¿puede esta cuenta abrir un stream bidireccional de voz, y con qué modelo?**

Prueba en orden `amazon.nova-2-sonic-v1:0` y luego `amazon.nova-sonic-v1:0`, y
reporta cuál responde. Usa entrada de texto (Nova Sonic acepta audio y texto en la
misma sesión) para que la prueba sea automática y no dependa de un micrófono.

Credenciales: no existe un resolvedor de perfil en smithy, así que en local se
exportan desde el AWS CLI antes de correr. En EC2 el resolvedor de IMDS toma el
rol de instancia sin credenciales estáticas — que es lo que dice el ADR 0008.

Uso:
    eval "$(aws configure export-credentials --format env)"
    uv run python spikes/nova_probe.py
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import os
import sys
import uuid

from aws_sdk_bedrock_runtime.client import AsyncBedrockRuntimeClient
from aws_sdk_bedrock_runtime.config import Config
from aws_sdk_bedrock_runtime.models import (
    BidirectionalInputPayloadPart,
    InvokeModelWithBidirectionalStreamInputChunk,
    InvokeModelWithBidirectionalStreamOperationInput,
)
from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REGION = os.getenv("AWS_REGION", "us-east-1")
CANDIDATES = ["amazon.nova-2-sonic-v1:0", "amazon.nova-sonic-v1:0"]
VOICE_ID = os.getenv("NOVA_VOICE_ID", "Carlos")

SYSTEM_PROMPT = (
    "Eres Ritmo, un coach de running mexicano. Hablas de tú, cercano y directo, "
    "sin jerga innecesaria. Responde en una sola frase corta."
)
USER_TEXT = "Hola, ¿me escuchas?"


def build_config() -> Config:
    """Credenciales desde variables de entorno.

    En producción se sustituye por `IMDSCredentialsResolver`, que toma el rol de
    instancia del EC2 sin credenciales estáticas (ADR 0008). Aquí no aplica: es
    una sonda local.
    """
    return Config(
        endpoint_uri=f"https://bedrock-runtime.{REGION}.amazonaws.com",
        region=REGION,
        aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
    )


def session_events(prompt_name: str, system_name: str, user_name: str) -> list[dict]:
    """Secuencia mínima del protocolo: sesión, prompt, sistema, usuario, cierre."""
    audio_out = {
        "mediaType": "audio/lpcm",
        "sampleRateHertz": 24000,
        "sampleSizeBits": 16,
        "channelCount": 1,
        "voiceId": VOICE_ID,
        "encoding": "base64",
        "audioType": "SPEECH",
    }
    text_cfg = {"mediaType": "text/plain"}

    def text_block(content_name: str, role: str, text: str) -> list[dict]:
        return [
            {
                "event": {
                    "contentStart": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "type": "TEXT",
                        "interactive": True,
                        "role": role,
                        "textInputConfiguration": text_cfg,
                    }
                }
            },
            {
                "event": {
                    "textInput": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "content": text,
                    }
                }
            },
            {
                "event": {
                    "contentEnd": {"promptName": prompt_name, "contentName": content_name}
                }
            },
        ]

    def audio_block(content_name: str) -> list[dict]:
        """Nova Sonic exige al menos un bloque de audio en el prompt, aunque la
        entrada real sea texto. Se manda medio segundo de silencio a 16 kHz."""
        silencio = base64.b64encode(b"\x00\x00" * 8000).decode("ascii")
        return [
            {
                "event": {
                    "contentStart": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "type": "AUDIO",
                        "interactive": True,
                        "role": "USER",
                        "audioInputConfiguration": {
                            "mediaType": "audio/lpcm",
                            "sampleRateHertz": 16000,
                            "sampleSizeBits": 16,
                            "channelCount": 1,
                            "audioType": "SPEECH",
                            "encoding": "base64",
                        },
                    }
                }
            },
            {
                "event": {
                    "audioInput": {
                        "promptName": prompt_name,
                        "contentName": content_name,
                        "content": silencio,
                    }
                }
            },
            {
                "event": {
                    "contentEnd": {"promptName": prompt_name, "contentName": content_name}
                }
            },
        ]

    return [
        {
            "event": {
                "sessionStart": {
                    "inferenceConfiguration": {
                        "maxTokens": 512,
                        "topP": 0.9,
                        "temperature": 0.7,
                    }
                }
            }
        },
        {
            "event": {
                "promptStart": {
                    "promptName": prompt_name,
                    "textOutputConfiguration": text_cfg,
                    "audioOutputConfiguration": audio_out,
                }
            }
        },
        *text_block(system_name, "SYSTEM", SYSTEM_PROMPT),
        *text_block(user_name, "USER", USER_TEXT),
        *audio_block(str(uuid.uuid4())),
    ]


def teardown_events(prompt_name: str) -> list[dict]:
    return [
        {"event": {"promptEnd": {"promptName": prompt_name}}},
        {"event": {"sessionEnd": {}}},
    ]


async def probe(model_id: str) -> bool:
    print(f"\n─── {model_id} ───")
    client = AsyncBedrockRuntimeClient(config=build_config())

    try:
        stream = await asyncio.wait_for(
            client.invoke_model_with_bidirectional_stream(
                InvokeModelWithBidirectionalStreamOperationInput(model_id=model_id)
            ),
            timeout=25,
        )
        print("  ✓ stream abierto — la cuenta SÍ puede invocar este modelo")
    except TimeoutError:
        print("  ✗ tiempo agotado al abrir el stream")
        return False
    except Exception as exc:  # noqa: BLE001 — es una sonda, cualquier fallo interesa
        print(f"  ✗ no abrió el stream: {type(exc).__name__}: {exc}")
        return False

    prompt_name, system_name, user_name = (str(uuid.uuid4()) for _ in range(3))

    async def send(events: list[dict]) -> None:
        for event in events:
            await stream.input_stream.send(
                InvokeModelWithBidirectionalStreamInputChunk(
                    value=BidirectionalInputPayloadPart(
                        bytes_=json.dumps(event).encode("utf-8")
                    )
                )
            )
            await asyncio.sleep(0.05)

    audio_chunks = 0
    text_out: list[str] = []
    kinds: set[str] = set()

    async def read_until_done() -> None:
        nonlocal audio_chunks
        while True:
            output = await stream.await_output()
            result = await output[1].receive()
            if result is None or result.value is None or result.value.bytes_ is None:
                continue
            event = json.loads(result.value.bytes_.decode("utf-8")).get("event", {})
            kinds.update(event.keys())
            if "audioOutput" in event:
                audio_chunks += 1
            elif "textOutput" in event:
                text_out.append(event["textOutput"].get("content", ""))
            elif "completionEnd" in event:
                return

    # El stream se mantiene abierto mientras se lee: cerrar la entrada antes de
    # tiempo termina la sesión antes de que el modelo alcance a generar.
    try:
        await send(session_events(prompt_name, system_name, user_name))
        await asyncio.wait_for(read_until_done(), timeout=40)
    except TimeoutError:
        print("  · tiempo agotado esperando la respuesta")
    except Exception as exc:  # noqa: BLE001 — es una sonda
        print(f"  ✗ {type(exc).__name__}: {exc}")
    finally:
        with contextlib.suppress(Exception):
            await send(teardown_events(prompt_name))
            await stream.input_stream.close()

    print(f"  eventos vistos : {', '.join(sorted(kinds)) or '(ninguno)'}")

    print(f"  texto devuelto : {' '.join(text_out).strip()[:160] or '(ninguno)'}")
    print(f"  chunks de audio: {audio_chunks}")

    if audio_chunks:
        print(f"  ✓ FUNCIONA — {model_id} devuelve audio")
        return True
    print("  ✗ sin audio de salida")
    return False


async def main() -> int:
    if not os.getenv("AWS_ACCESS_KEY_ID"):
        print("Faltan credenciales en el entorno. Corre primero:")
        print('  eval "$(aws configure export-credentials --format env)"')
        return 2

    print(f"región: {REGION}   voz: {VOICE_ID}")
    for model_id in CANDIDATES:
        if await probe(model_id):
            print(f"\n>>> USAR NOVA_MODEL_ID={model_id}")
            return 0

    print("\n>>> Ningún modelo de voz respondió. Ver propuestas de respaldo.")
    return 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
