"""Renovación de sesión a los 8 minutos.

Nova Sonic corta la conexión a los 8 minutos (ADR 0002). La renovación tiene que
ser **invisible**: si el usuario percibe un corte cada ocho minutos, el producto
se siente frágil. Por eso la sesión nueva se abre y se confirma lista ANTES de
cerrar la vieja — ese solapamiento es lo que mantiene el hueco cerca de cero.
"""

from __future__ import annotations

import asyncio

import pytest

from apps.api.bridge import NovaBridge
from apps.api.renewal import ConversationContext, RenewingBridge
from apps.api.tests.conftest import FakeStream, tipos_enviados


def hacer_fabrica(streams: list[FakeStream]):
    """Devuelve puentes nuevos sobre streams falsos, y registra cuáles creó."""
    creados: list[NovaBridge] = []

    def fabrica() -> NovaBridge:
        stream = streams[len(creados)]
        puente = NovaBridge(stream=stream)
        creados.append(puente)
        return puente

    return fabrica, creados


def test_el_contexto_arranca_con_el_prompt_base() -> None:
    ctx = ConversationContext(base_prompt="eres un coach")
    assert ctx.build_prompt() == "eres un coach"


def test_el_contexto_acumula_lo_hablado() -> None:
    ctx = ConversationContext(base_prompt="eres un coach")
    ctx.remember("USER", "me molesta la rodilla")
    ctx.remember("ASSISTANT", "¿en qué parte exactamente?")

    prompt = ctx.build_prompt()
    assert "eres un coach" in prompt
    assert "me molesta la rodilla" in prompt


def test_el_contexto_no_crece_sin_límite() -> None:
    ctx = ConversationContext(base_prompt="base", max_turns=3)
    for i in range(10):
        ctx.remember("USER", f"turno {i}")

    prompt = ctx.build_prompt()
    assert "turno 9" in prompt
    assert "turno 0" not in prompt, "los turnos viejos deben caer"


@pytest.mark.asyncio
async def test_renueva_la_sesion_al_cumplirse_el_plazo() -> None:
    streams = [FakeStream(), FakeStream()]
    fabrica, creados = hacer_fabrica(streams)
    ctx = ConversationContext(base_prompt="eres un coach")

    puente = RenewingBridge(fabrica, ctx, renew_after_s=0.05)
    await puente.start()
    assert len(creados) == 1

    await asyncio.sleep(0.25)

    assert len(creados) == 2, "debió abrir una sesión nueva"
    await puente.close()


@pytest.mark.asyncio
async def test_la_sesion_nueva_hereda_el_contexto() -> None:
    streams = [FakeStream(), FakeStream()]
    fabrica, _ = hacer_fabrica(streams)
    ctx = ConversationContext(base_prompt="eres un coach")
    ctx.remember("USER", "entreno para un 21k y me molesta la rodilla")

    puente = RenewingBridge(fabrica, ctx, renew_after_s=0.05)
    await puente.start()
    await asyncio.sleep(0.25)

    enviados = streams[1].input_stream.sent
    textos = [e["event"]["textInput"]["content"] for e in enviados if "textInput" in e["event"]]
    assert any("me molesta la rodilla" in t for t in textos), (
        "la sesión nueva debe arrancar sabiendo lo que ya se habló"
    )
    await puente.close()


@pytest.mark.asyncio
async def test_la_vieja_se_cierra_despues_de_que_la_nueva_esta_lista() -> None:
    """El orden es lo que hace que el hueco sea imperceptible."""
    streams = [FakeStream(), FakeStream()]
    fabrica, _ = hacer_fabrica(streams)

    puente = RenewingBridge(fabrica, ConversationContext("base"), renew_after_s=0.05)
    await puente.start()
    await asyncio.sleep(0.25)

    # La nueva ya abrió sesión antes de que la vieja se cerrara.
    assert "sessionStart" in tipos_enviados(streams[1])
    assert streams[0].input_stream.closed
    await puente.close()


@pytest.mark.asyncio
async def test_el_audio_posterior_va_a_la_sesion_nueva() -> None:
    streams = [FakeStream(), FakeStream()]
    fabrica, _ = hacer_fabrica(streams)

    puente = RenewingBridge(fabrica, ConversationContext("base"), renew_after_s=0.05)
    await puente.start()
    await asyncio.sleep(0.25)
    await puente.send_audio("QUJDRA==")

    assert "audioInput" in tipos_enviados(streams[1])
    await puente.close()


@pytest.mark.asyncio
async def test_la_sesion_moribunda_no_cuela_eventos() -> None:
    """Al cerrarse, la sesión vieja emite su payload de interrupción y repite el
    último turno. Nada de eso debe llegar al navegador.

    `cancel()` sólo programa la cancelación: si no se espera a que la bomba vieja
    muera, alcanza a colar esos eventos en la cola común."""
    vieja = FakeStream(
        [{"event": {"textOutput": {"content": "basura de cierre", "role": "ASSISTANT"}}}],
        retardo=0.12,  # llega justo después del relevo
    )
    nueva = FakeStream()
    fabrica, _ = hacer_fabrica([vieja, nueva])

    puente = RenewingBridge(fabrica, ConversationContext("base"), renew_after_s=0.05)
    await puente.start()

    recibidos: list[str] = []

    async def consumir() -> None:
        async for evento in puente.events():
            if evento.kind == "transcript":
                recibidos.append(evento.payload["text"])

    tarea = asyncio.create_task(consumir())
    await asyncio.sleep(0.4)
    tarea.cancel()
    await puente.close()

    assert "basura de cierre" not in recibidos


@pytest.mark.asyncio
async def test_los_eventos_siguen_fluyendo_a_traves_del_relevo() -> None:
    streams = [
        FakeStream([{"event": {"textOutput": {"content": "antes", "role": "ASSISTANT"}}}]),
        FakeStream([{"event": {"textOutput": {"content": "después", "role": "ASSISTANT"}}}]),
    ]
    fabrica, _ = hacer_fabrica(streams)

    puente = RenewingBridge(fabrica, ConversationContext("base"), renew_after_s=0.1)
    await puente.start()

    recibidos: list[str] = []

    async def consumir() -> None:
        async for evento in puente.events():
            if evento.kind == "transcript":
                recibidos.append(evento.payload["text"])

    tarea = asyncio.create_task(consumir())
    await asyncio.sleep(0.35)
    tarea.cancel()
    await puente.close()

    assert "antes" in recibidos
    assert "después" in recibidos, "el relevo cortó el flujo de eventos"
