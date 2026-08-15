"""Dobles de prueba del stream bidireccional de Bedrock.

Permiten ejercitar el puente completo sin credenciales, sin red y sin gastar un
solo token.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest


class FakeInputStream:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []
        self.closed = False

    async def send(self, chunk: Any) -> None:
        self.sent.append(json.loads(chunk.value.bytes_.decode("utf-8")))

    async def close(self) -> None:
        self.closed = True


class FakeReceiver:
    def __init__(self, salidas: list[dict[str, Any]], retardo: float = 0.0) -> None:
        self._pendientes = list(salidas)
        self._retardo = retardo

    async def receive(self) -> Any:
        if not self._pendientes:
            # Se queda esperando, igual que el stream real cuando no hay nada.
            await asyncio.sleep(3600)
        if self._retardo:
            await asyncio.sleep(self._retardo)
        evento = self._pendientes.pop(0)

        class _Res:
            class value:  # noqa: N801
                bytes_ = json.dumps(evento).encode("utf-8")

        return _Res()


class FakeStream:
    """Imita el DuplexEventStream de smithy."""

    def __init__(self, salidas: list[dict[str, Any]] | None = None, retardo: float = 0.0) -> None:
        self.input_stream = FakeInputStream()
        self._receiver = FakeReceiver(salidas or [], retardo)

    async def await_output(self) -> tuple[Any, FakeReceiver]:
        return (None, self._receiver)


def tipos_enviados(stream: FakeStream) -> list[str]:
    """Los nombres de evento enviados, en orden."""
    return [next(iter(e["event"])) for e in stream.input_stream.sent]


async def transcripciones(bridge: Any) -> list[str]:
    """Consume eventos hasta el fin del turno y devuelve el texto.

    El corte en `turn_end` es obligatorio: `events()` es un flujo infinito y el
    receptor falso se queda esperando cuando se le acaban las salidas, igual que
    el stream real.
    """
    textos: list[str] = []
    async for evento in bridge.events():
        if evento.kind == "transcript":
            textos.append(evento.payload["text"])
        elif evento.kind == "turn_end":
            break
    return textos


@pytest.fixture
def hacer_stream() -> Any:
    def _hacer(salidas: list[dict[str, Any]] | None = None) -> FakeStream:
        return FakeStream(salidas)

    return _hacer
