"""El puente entre el navegador y Nova Sonic.

La propiedad que más importa es que **no bufferice**: cada frame de audio que
entra sale en el mismo await. Acumular frames añade latencia percibida
directamente al `ttfa_ms`, que es la métrica titular del proyecto (ADR 0012).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest

from apps.api.bridge import BridgeEvent, NovaBridge


class FakeInputStream:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    async def send(self, chunk: Any) -> None:
        self.sent.append(json.loads(chunk.value.bytes_.decode("utf-8")))

    async def close(self) -> None:
        self.closed = True


class FakeReceiver:
    def __init__(self, salidas: list[dict[str, Any]]) -> None:
        self._pendientes = list(salidas)

    async def receive(self) -> Any:
        if not self._pendientes:
            await asyncio.sleep(3600)  # se queda esperando, como el stream real
        evento = self._pendientes.pop(0)

        class _Res:
            class value:  # noqa: N801
                bytes_ = json.dumps(evento).encode("utf-8")

        return _Res()


class FakeStream:
    """Imita el DuplexEventStream de smithy."""

    def __init__(self, salidas: list[dict[str, Any]] | None = None) -> None:
        self.input_stream = FakeInputStream()
        self._receiver = FakeReceiver(salidas or [])

    async def await_output(self) -> tuple[Any, FakeReceiver]:
        return (None, self._receiver)


def tipos_enviados(stream: FakeStream) -> list[str]:
    return [next(iter(e["event"])) for e in stream.input_stream.sent]


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
async def test_close_cierra_el_prompt_y_la_sesion() -> None:
    stream = FakeStream()
    bridge = NovaBridge(stream=stream)
    await bridge.start(system_prompt="x", voice_id="carlos")
    await bridge.close()

    tipos = tipos_enviados(stream)
    assert tipos[-3:] == ["contentEnd", "promptEnd", "sessionEnd"]
    assert stream.input_stream.closed
