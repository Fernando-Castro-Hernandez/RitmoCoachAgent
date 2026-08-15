"""El protocolo de eventos de Nova Sonic.

Estas pruebas fijan las tres reglas que costaron el spike de la tarea A2 y que no
están en la documentación de AWS. Si alguien las rompe, falla aquí y no en una
demo. Ver ADR 0002.
"""

from __future__ import annotations

import base64

from apps.api.protocol import (
    AUDIO_IN_HZ,
    AUDIO_OUT_HZ,
    audio_block_start,
    audio_input,
    content_end,
    prompt_start,
    session_start,
    text_block,
)


def test_el_voice_id_se_fuerza_a_minusculas() -> None:
    """La documentación muestra «Carlos», pero la API responde
    ValidationException: Received invalid id. Ver ADR 0002."""
    evento = prompt_start("p1", voice_id="Carlos")
    assert evento["event"]["promptStart"]["audioOutputConfiguration"]["voiceId"] == "carlos"


def test_la_salida_de_audio_va_a_24_khz() -> None:
    cfg = prompt_start("p1", voice_id="carlos")["event"]["promptStart"]["audioOutputConfiguration"]
    assert cfg["sampleRateHertz"] == AUDIO_OUT_HZ == 24000
    assert cfg["sampleSizeBits"] == 16
    assert cfg["channelCount"] == 1


def test_la_entrada_de_audio_va_a_16_khz() -> None:
    cfg = audio_block_start("p1", "c1")["event"]["contentStart"]["audioInputConfiguration"]
    assert cfg["sampleRateHertz"] == AUDIO_IN_HZ == 16000
    assert cfg["mediaType"] == "audio/lpcm"


def test_el_bloque_de_texto_abre_y_cierra() -> None:
    eventos = text_block("p1", "c1", role="SYSTEM", text="eres un coach")
    tipos = [next(iter(e["event"])) for e in eventos]
    assert tipos == ["contentStart", "textInput", "contentEnd"]
    assert eventos[0]["event"]["contentStart"]["role"] == "SYSTEM"
    assert eventos[1]["event"]["textInput"]["content"] == "eres un coach"


def test_content_end_referencia_el_mismo_contenido() -> None:
    fin = content_end("p1", "c1")["event"]["contentEnd"]
    assert fin["promptName"] == "p1"
    assert fin["contentName"] == "c1"


def test_audio_input_transporta_base64_intacto() -> None:
    muestra = base64.b64encode(b"\x00\x01" * 10).decode("ascii")
    evento = audio_input("p1", "c1", muestra)
    assert evento["event"]["audioInput"]["content"] == muestra


def test_session_start_lleva_configuracion_de_inferencia() -> None:
    cfg = session_start(temperature=0.4)["event"]["sessionStart"]["inferenceConfiguration"]
    assert cfg["temperature"] == 0.4
    assert "maxTokens" in cfg and "topP" in cfg
