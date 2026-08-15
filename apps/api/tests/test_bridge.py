"""El puente entre el navegador y Nova Sonic.

La propiedad que más importa es que **no bufferice**: cada frame de audio que
entra sale en el mismo await. Acumular frames añade latencia percibida
directamente al `ttfa_ms`, que es la métrica titular del proyecto (ADR 0012).
"""

from __future__ import annotations

import pytest

from apps.api.bridge import BridgeEvent, NovaBridge
from apps.api.tests.conftest import FakeStream, tipos_enviados, transcripciones


@pytest.mark.asyncio
async def test_start_envia_la_secuencia_de_apertura() -> None:
    stream = FakeStream()
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="eres un coach", voice_id="carlos")

    tipos = tipos_enviados(stream)
    assert tipos[:2] == ["sessionStart", "promptStart"]
    # El bloque SYSTEM y la apertura del bloque de audio del usuario.
    assert "contentStart" in tipos and "textInput" in tipos
    assert tipos[-1] == "contentStart"  # queda abierto el bloque de audio


@pytest.mark.asyncio
async def test_el_audio_se_reenvia_sin_bufferizar() -> None:
    stream = FakeStream()
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")
    antes = len(stream.input_stream.sent)

    await bridge.send_audio("QUJDRA==")

    assert len(stream.input_stream.sent) == antes + 1, "el frame no salió de inmediato"
    ultimo = stream.input_stream.sent[-1]["event"]["audioInput"]
    assert ultimo["content"] == "QUJDRA=="


@pytest.mark.asyncio
async def test_el_texto_cierra_el_turno_del_usuario() -> None:
    """Sin cerrar el bloque de audio, el modelo recibe el texto y se queda
    esperando para siempre: ni responde ni da error. Ver ADR 0002."""
    stream = FakeStream()
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")
    antes = len(stream.input_stream.sent)

    await bridge.send_text("hola")

    nuevos = tipos_enviados(stream)[antes:]
    assert nuevos == [
        "contentStart",  # bloque de texto del usuario
        "textInput",
        "contentEnd",
        "audioInput",  # silencio: un bloque vacío no se puede cerrar
        "contentEnd",  # cierra el bloque de audio: fin del turno
        "contentStart",  # y abre uno nuevo para lo que siga
    ]


@pytest.mark.asyncio
async def test_no_mete_silencio_si_ya_hubo_audio_real() -> None:
    stream = FakeStream()
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")
    await bridge.send_audio("QUJDRA==")
    antes = len(stream.input_stream.sent)

    await bridge.send_text("hola")

    audios = [
        e["event"]["audioInput"]["content"]
        for e in stream.input_stream.sent[antes:]
        if "audioInput" in e["event"]
    ]
    assert audios == [], "no debe rellenar con silencio un bloque que ya tiene audio"


@pytest.mark.asyncio
async def test_los_eventos_de_salida_se_traducen() -> None:
    stream = FakeStream(
        salidas=[
            {"event": {"textOutput": {"content": "hola", "role": "ASSISTANT"}}},
            {"event": {"audioOutput": {"content": "QUJD"}}},
            {"event": {"completionEnd": {}}},
        ]
    )
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")

    recibidos: list[BridgeEvent] = []
    async for evento in bridge.events():
        recibidos.append(evento)
        if evento.kind == "turn_end":
            break

    assert [e.kind for e in recibidos] == ["transcript", "audio", "turn_end"]
    assert recibidos[0].payload["text"] == "hola"
    assert recibidos[1].payload["audio_b64"] == "QUJD"


@pytest.mark.asyncio
async def test_descarta_el_payload_de_interrupcion() -> None:
    """Nova Sonic manda {"interrupted": true} como textOutput. No es habla."""
    stream = FakeStream(
        salidas=[
            {"event": {"textOutput": {"content": '{ "interrupted" : true }', "role": "ASSISTANT"}}},
            {"event": {"textOutput": {"content": "hola", "role": "ASSISTANT"}}},
            {"event": {"completionEnd": {}}},
        ]
    )
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")

    textos = await transcripciones(bridge)
    assert textos == ["hola"]


@pytest.mark.asyncio
async def test_no_duplica_el_texto_especulativo_y_el_final() -> None:
    """El modelo emite cada respuesta dos veces: especulativa y final.

    Se muestra la especulativa, que llega antes, y se descarta la final. Sin
    esto la transcripción repite cada frase."""
    stream = FakeStream(
        salidas=[
            {
                "event": {
                    "contentStart": {
                        "role": "ASSISTANT",
                        "additionalModelFields": '{"generationStage":"SPECULATIVE"}',
                    }
                }
            },
            {"event": {"textOutput": {"content": "vas muy bien", "role": "ASSISTANT"}}},
            {
                "event": {
                    "contentStart": {
                        "role": "ASSISTANT",
                        "additionalModelFields": '{"generationStage":"FINAL"}',
                    }
                }
            },
            {"event": {"textOutput": {"content": "vas muy bien", "role": "ASSISTANT"}}},
            {"event": {"completionEnd": {}}},
        ]
    )
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")

    textos = await transcripciones(bridge)
    assert textos == ["vas muy bien"], "la transcripción no debe repetirse"


@pytest.mark.asyncio
async def test_el_texto_del_usuario_siempre_pasa() -> None:
    """Las transcripciones del usuario no traen etapa y no deben filtrarse."""
    stream = FakeStream(
        salidas=[
            {"event": {"contentStart": {"role": "USER"}}},
            {"event": {"textOutput": {"content": "me duele la rodilla", "role": "USER"}}},
            {"event": {"completionEnd": {}}},
        ]
    )
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")

    textos = await transcripciones(bridge)
    assert textos == ["me duele la rodilla"]


@pytest.mark.asyncio
async def test_close_cierra_el_prompt_y_la_sesion() -> None:
    stream = FakeStream()
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")
    await bridge.close()

    tipos = tipos_enviados(stream)
    assert tipos[-3:] == ["contentEnd", "promptEnd", "sessionEnd"]
    assert stream.input_stream.closed


async def test_la_transcripcion_del_usuario_no_se_pierde(hacer_stream) -> None:
    """Regresión: el corredor hablaba y su turno no llegaba nunca al navegador.

    La deduplicación especulativa/FINAL existe porque el modelo emite cada
    respuesta SUYA dos veces. Pero lo que dijo el usuario llega una sola vez y
    marcado FINAL, así que la misma regla lo borraba. El resultado era una
    conversación donde sólo se veía hablar al coach.
    """
    stream = hacer_stream(
        [
            {
                "event": {
                    "contentStart": {
                        "role": "USER",
                        "additionalModelFields": '{"generationStage":"FINAL"}',
                    }
                }
            },
            {"event": {"textOutput": {"content": "me duele la rodilla", "role": "USER"}}},
            {"event": {"contentStart": {"role": "ASSISTANT"}}},
            {"event": {"textOutput": {"content": "¿en qué parte?", "role": "ASSISTANT"}}},
            {"event": {"completionEnd": {}}},
        ]
    )
    bridge = NovaBridge(stream=stream)
    await bridge.start("eres un coach")

    roles = []
    async for evento in bridge.events():
        if evento.kind == "transcript":
            roles.append((evento.payload["role"], evento.payload["text"]))
        elif evento.kind == "turn_end":
            break

    assert ("USER", "me duele la rodilla") in roles
    assert ("ASSISTANT", "¿en qué parte?") in roles


async def test_el_coach_sigue_sin_duplicarse(hacer_stream) -> None:
    """Y la deduplicación que motivó todo esto tiene que seguir en pie."""
    stream = hacer_stream(
        [
            {"event": {"contentStart": {"role": "ASSISTANT"}}},
            {"event": {"textOutput": {"content": "hola", "role": "ASSISTANT"}}},
            {
                "event": {
                    "contentStart": {
                        "role": "ASSISTANT",
                        "additionalModelFields": '{"generationStage":"FINAL"}',
                    }
                }
            },
            {"event": {"textOutput": {"content": "hola", "role": "ASSISTANT"}}},
            {"event": {"completionEnd": {}}},
        ]
    )
    bridge = NovaBridge(stream=stream)
    await bridge.start("eres un coach")

    assert await transcripciones(bridge) == ["hola"]
