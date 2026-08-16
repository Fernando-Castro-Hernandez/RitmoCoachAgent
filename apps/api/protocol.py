"""Construcción de eventos del protocolo de Amazon Nova Sonic.

Módulo puro: sólo arma diccionarios. No habla con la red, así que se prueba sin
credenciales y sin gastar un solo token.

La secuencia completa de una sesión:

    sessionStart
    promptStart                          ← configura voz y salida de audio
    contentStart/textInput/contentEnd    ← rol SYSTEM: la personalidad
    contentStart/audioInput…/contentEnd  ← rol USER: el micrófono
    promptEnd
    sessionEnd

Ver ADR 0002 para las reglas no documentadas que este módulo encapsula.
"""

from __future__ import annotations

import json
from typing import Any

AUDIO_IN_HZ = 16_000
AUDIO_OUT_HZ = 24_000
BITS = 16
CHANNELS = 1

_TEXT_CFG = {"mediaType": "text/plain"}

Event = dict[str, Any]


def session_start(*, max_tokens: int = 1024, top_p: float = 0.9, temperature: float = 0.7) -> Event:
    return {
        "event": {
            "sessionStart": {
                "inferenceConfiguration": {
                    "maxTokens": max_tokens,
                    "topP": top_p,
                    "temperature": temperature,
                }
            }
        }
    }


def prompt_start(
    prompt_name: str, *, voice_id: str, tools: list[dict[str, Any]] | None = None
) -> Event:
    """Configura la salida del prompt.

    El `voiceId` se fuerza a minúsculas: la documentación de AWS muestra «Carlos»
    y «Lupe», pero la API rechaza esos valores con
    `ValidationException: Received invalid id`. Ver ADR 0002.
    """
    payload: dict[str, Any] = {
        "promptName": prompt_name,
        "textOutputConfiguration": _TEXT_CFG,
        "audioOutputConfiguration": {
            "mediaType": "audio/lpcm",
            "sampleRateHertz": AUDIO_OUT_HZ,
            "sampleSizeBits": BITS,
            "channelCount": CHANNELS,
            "voiceId": voice_id.lower(),
            "encoding": "base64",
            "audioType": "SPEECH",
        },
    }
    if tools:
        payload["toolUseOutputConfiguration"] = {"mediaType": "application/json"}
        payload["toolConfiguration"] = {"tools": tools}
    return {"event": {"promptStart": payload}}


def text_block(prompt_name: str, content_name: str, *, role: str, text: str) -> list[Event]:
    """Bloque de texto completo: apertura, contenido y cierre."""
    return [
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "type": "TEXT",
                    "interactive": True,
                    "role": role,
                    "textInputConfiguration": _TEXT_CFG,
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
        content_end(prompt_name, content_name),
    ]


def audio_block_start(prompt_name: str, content_name: str) -> Event:
    """Abre el bloque de audio del usuario.

    Nova Sonic exige al menos un bloque de tipo AUDIO en el prompt, incluso si la
    entrada real llega como texto. Ver ADR 0002.
    """
    return {
        "event": {
            "contentStart": {
                "promptName": prompt_name,
                "contentName": content_name,
                "type": "AUDIO",
                "interactive": True,
                "role": "USER",
                "audioInputConfiguration": {
                    "mediaType": "audio/lpcm",
                    "sampleRateHertz": AUDIO_IN_HZ,
                    "sampleSizeBits": BITS,
                    "channelCount": CHANNELS,
                    "audioType": "SPEECH",
                    "encoding": "base64",
                },
            }
        }
    }


def audio_input(prompt_name: str, content_name: str, pcm16_b64: str) -> Event:
    return {
        "event": {
            "audioInput": {
                "promptName": prompt_name,
                "contentName": content_name,
                "content": pcm16_b64,
            }
        }
    }


def tool_result_block(
    prompt_name: str, content_name: str, *, tool_use_id: str, result: Any
) -> list[Event]:
    """Devuelve al modelo lo que dio una herramienta.

    Tres eventos, como todo bloque de contenido: apertura, contenido y cierre.
    El `toolUseId` es lo que empareja la respuesta con la llamada — sin él el
    modelo no sabe a cuál de sus preguntas se le está contestando.

    El resultado viaja **serializado como texto**, no como objeto. Es lo que
    exige el bloque de tipo TOOL, y tiene una consecuencia que conviene tener
    presente: el modelo lee un JSON, así que los nombres de campo de las
    herramientas son parte del prompt efectivo. Por eso se llaman `needs_context`
    y `next_question` y no `nc` y `q`.
    """
    return [
        {
            "event": {
                "contentStart": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "interactive": False,
                    "type": "TOOL",
                    "role": "TOOL",
                    "toolResultInputConfiguration": {
                        "toolUseId": tool_use_id,
                        "type": "TEXT",
                        "textInputConfiguration": {"mediaType": "text/plain"},
                    },
                }
            }
        },
        {
            "event": {
                "toolResult": {
                    "promptName": prompt_name,
                    "contentName": content_name,
                    "content": json.dumps(result, ensure_ascii=False, default=str),
                }
            }
        },
        content_end(prompt_name, content_name),
    ]


def content_end(prompt_name: str, content_name: str) -> Event:
    return {"event": {"contentEnd": {"promptName": prompt_name, "contentName": content_name}}}


def prompt_end(prompt_name: str) -> Event:
    return {"event": {"promptEnd": {"promptName": prompt_name}}}


def session_end() -> Event:
    return {"event": {"sessionEnd": {}}}
