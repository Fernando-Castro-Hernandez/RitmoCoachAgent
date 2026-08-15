"""Renovación transparente de la sesión de voz.

Nova Sonic corta la conexión a los 8 minutos (ADR 0002). Sin manejarlo, la
conversación muere a media frase.

La renovación tiene que ser **invisible**. Si el usuario ve «reconectando…» cada
ocho minutos, el producto se siente frágil aunque técnicamente funcione. Por eso
el orden es: se abre la sesión nueva, se confirma lista, y sólo entonces se
cierra la vieja. Ese solapamiento es lo que mantiene `renewal_gap_ms` cerca de
cero (ADR 0012).

Los eventos de salida pasan por una cola interna, así que el consumidor itera un
solo `events()` que sobrevive al relevo sin enterarse.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field

import structlog

from apps.api.bridge import BridgeEvent, NovaBridge

log = structlog.get_logger(__name__)

BridgeFactory = Callable[[], NovaBridge]


@dataclass
class ConversationContext:
    """Lo que la sesión nueva necesita saber para continuar sin costuras.

    Es memoria **de sesión**, no la memoria persistente del atleta: esa vive en
    la base de datos y llega en la tarea C1.
    """

    base_prompt: str
    max_turns: int = 20
    turns: list[tuple[str, str]] = field(default_factory=list)

    def remember(self, role: str, text: str) -> None:
        if not text.strip():
            return
        self.turns.append((role, text.strip()))
        # Se recorta por el frente: interesa lo reciente, y el prompt no puede
        # crecer sin límite aunque el modelo tenga un contexto de 1M tokens.
        if len(self.turns) > self.max_turns:
            self.turns = self.turns[-self.max_turns :]

    def build_prompt(self) -> str:
        if not self.turns:
            return self.base_prompt
        historial = "\n".join(
            f"{'Corredor' if rol == 'USER' else 'Tú'}: {texto}" for rol, texto in self.turns
        )
        return (
            f"{self.base_prompt}\n\n"
            "Ya venías conversando con este corredor. Esto es lo que se dijeron:\n"
            f"{historial}\n\n"
            "Continúa la conversación con naturalidad. No saludes de nuevo ni "
            "menciones que hubo una interrupción."
        )


class RenewingBridge:
    """Un `NovaBridge` que se releva a sí mismo antes de que Bedrock lo corte."""

    def __init__(
        self,
        factory: BridgeFactory,
        context: ConversationContext,
        *,
        renew_after_s: float = 450.0,
        voice_id: str | None = None,
    ) -> None:
        self._factory = factory
        self._context = context
        self._renew_after_s = renew_after_s
        self._voice_id = voice_id
        self._active: NovaBridge | None = None
        self._queue: asyncio.Queue[BridgeEvent] = asyncio.Queue()
        self._pump: asyncio.Task[None] | None = None
        self._timer: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()
        self._closed = False
        self.renewals = 0

    # ── ciclo de vida ────────────────────────────────────────────────

    async def start(self) -> None:
        self._active = await self._open()
        self._pump = asyncio.create_task(self._drain(self._active))
        self._timer = asyncio.create_task(self._schedule())

    async def close(self) -> None:
        self._closed = True
        for tarea in (self._timer, self._pump):
            if tarea is not None:
                tarea.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await tarea
        if self._active is not None:
            await self._active.close()

    # ── entrada ──────────────────────────────────────────────────────

    async def send_audio(self, pcm16_b64: str) -> None:
        async with self._lock:
            assert self._active is not None, "hay que llamar a start() primero"
            await self._active.send_audio(pcm16_b64)

    async def send_text(self, text: str) -> None:
        async with self._lock:
            assert self._active is not None, "hay que llamar a start() primero"
            self._context.remember("USER", text)
            await self._active.send_text(text)

    # ── salida ───────────────────────────────────────────────────────

    async def events(self) -> AsyncIterator[BridgeEvent]:
        """Un solo flujo de eventos que sobrevive a los relevos."""
        while not self._closed:
            yield await self._queue.get()

    # ── internos ─────────────────────────────────────────────────────

    async def _open(self) -> NovaBridge:
        puente = self._factory()
        await puente.start(self._context.build_prompt(), voice_id=self._voice_id)
        return puente

    async def _drain(self, puente: NovaBridge) -> None:
        """Vuelca los eventos de un puente a la cola común."""
        async for evento in puente.events():
            if evento.kind == "transcript":
                self._context.remember(
                    evento.payload.get("role", "ASSISTANT"), evento.payload.get("text", "")
                )
            await self._queue.put(evento)

    async def _schedule(self) -> None:
        while not self._closed:
            await asyncio.sleep(self._renew_after_s)
            if self._closed:
                return
            try:
                await self._renew()
            except Exception as exc:
                log.error("renewal.failed", error=str(exc))
                await self._queue.put(BridgeEvent("error", {"message": str(exc)}))
                return

    async def _renew(self) -> None:
        # 1 · Abrir la nueva y esperar a que esté lista. La vieja sigue viva y
        #     atendiendo mientras tanto: aquí está el solapamiento.
        nueva = await self._open()

        # 2 · Relevar bajo candado, para que ningún frame se vaya a la vieja.
        async with self._lock:
            vieja, self._active = self._active, nueva
            bomba_vieja, self._pump = self._pump, asyncio.create_task(self._drain(nueva))

        # 3 · Esperar a que la bomba vieja muera de verdad. `cancel()` sólo
        #     programa la cancelación: sin este await, la sesión moribunda
        #     alcanza a colar en la cola su payload de interrupción y una
        #     repetición del último turno.
        if bomba_vieja is not None:
            bomba_vieja.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await bomba_vieja

        # 4 · Y ahora sí, cerrar la vieja.
        if vieja is not None:
            with contextlib.suppress(Exception):
                await vieja.close()

        self.renewals += 1
        log.info("renewal.done", count=self.renewals, turns=len(self._context.turns))
