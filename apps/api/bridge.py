"""Puente con estado entre el navegador y Amazon Nova Sonic.

Sostiene dos conexiones largas por sesión: el WebSocket contra el navegador (lo
maneja `ws.py`) y el stream HTTP/2 bidireccional contra Bedrock. Esta clase se
encarga del segundo.

Regla de diseño que gobierna todo el módulo: **passthrough, no acumulación.**
Cada frame de audio que llega se reenvía en el mismo `await`. Bufferizar aquí
suma latencia directamente a `ttfa_ms`, la métrica titular (ADR 0012).
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import json
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from typing import Any, Literal

import structlog

from apps.api import protocol
from apps.api.config import Settings, get_settings
from apps.api.credentials import ensure_fresh_credentials
from apps.api.metrics import TurnTimer
from apps.api.tool_specs import tool_specs

log = structlog.get_logger(__name__)

EventKind = Literal["audio", "transcript", "tool_call", "turn_end", "error"]

# 100 ms de silencio a 16 kHz, PCM16. Ver `_end_user_turn`.
_SILENCIO = base64.b64encode(b"\x00\x00" * 1600).decode("ascii")


@dataclass(frozen=True)
class BridgeEvent:
    """Un evento ya traducido, listo para mandar al navegador."""

    kind: EventKind
    payload: dict[str, Any] = field(default_factory=dict)


def _new_id() -> str:
    return str(uuid.uuid4())


def _debe_emitir(content_start: dict[str, Any]) -> bool:
    """Decide si el texto que viene tras este `contentStart` se muestra.

    El modelo emite cada respuesta del asistente **dos veces**: primero una
    versión especulativa y luego la final, idéntica. Se muestra la especulativa
    —llega antes, así que la transcripción aparece cuanto antes— y se descarta la
    final. Sin esto cada frase sale repetida.

    El texto del usuario no trae etapa: pasa siempre.
    """
    campos = content_start.get("additionalModelFields")
    if not campos:
        return True
    try:
        etapa = json.loads(campos).get("generationStage")
    except (json.JSONDecodeError, TypeError):
        return True
    return etapa != "FINAL"


def _argumentos_de(peticion: dict[str, Any]) -> dict[str, Any]:
    """Los argumentos de un `toolUse`, vengan como objeto o como cadena.

    Nova los manda serializados en `content`, pero no siempre: en algunos turnos
    llegan ya como diccionario. Aceptar las dos formas cuesta cuatro líneas y
    evita un fallo que sólo aparecería en la conversación número treinta.
    """
    crudo = peticion.get("content", peticion.get("input", {}))
    if isinstance(crudo, dict):
        return crudo
    if isinstance(crudo, str):
        try:
            cargado = json.loads(crudo)
        except json.JSONDecodeError:
            return {}
        return cargado if isinstance(cargado, dict) else {}
    return {}


def _es_payload_de_control(contenido: str) -> bool:
    """`{"interrupted": true}` llega como textOutput, pero no es habla."""
    texto = contenido.strip()
    if not (texto.startswith("{") and texto.endswith("}")):
        return False
    try:
        return isinstance(json.loads(texto), dict)
    except json.JSONDecodeError:
        return False


class NovaBridge:
    """Envuelve un stream bidireccional de Bedrock con una interfaz usable.

    Se le puede inyectar un `stream` ya abierto, que es como lo prueban los
    tests sin tocar la red ni gastar tokens.
    """

    def __init__(
        self,
        *,
        stream: Any | None = None,
        settings: Settings | None = None,
        clock: Callable[[], float] | None = None,
        tool_runner: Any | None = None,
    ) -> None:
        self._stream = stream
        # Sin ejecutor no se le declaran herramientas al modelo. Es lo que
        # permite seguir probando el puente «pelado» sin base de datos, y lo que
        # hace que una sesión mal cableada calle en vez de pedir cosas que nadie
        # va a contestarle.
        self._tools = tool_runner
        self._settings = settings or get_settings()
        # El reloj se inyecta para poder medir la latencia en una prueba sin
        # dormir de verdad. En producción es `time.monotonic`.
        self.metrics = TurnTimer(clock)
        self._prompt_name = _new_id()
        self._audio_content = _new_id()
        self._started = False
        self._closed = False
        self._audio_recibido = False
        self._emitir_texto = True

    # ── ciclo de vida ────────────────────────────────────────────────

    async def start(self, system_prompt: str, *, voice_id: str | None = None) -> None:
        """Abre la sesión y deja el bloque de audio del usuario listo para recibir."""
        if self._stream is None:
            self._stream = await self._open_stream()

        voice = voice_id or self._settings.nova_voice_id
        await self._send(
            protocol.session_start(
                max_tokens=self._settings.max_tokens,
                top_p=self._settings.top_p,
                temperature=self._settings.temperature,
            )
        )
        especificaciones = tool_specs() if self._tools is not None else None
        await self._send(
            protocol.prompt_start(self._prompt_name, voice_id=voice, tools=especificaciones)
        )

        for evento in protocol.text_block(
            self._prompt_name, _new_id(), role="SYSTEM", text=system_prompt
        ):
            await self._send(evento)

        # El bloque de audio queda ABIERTO: los frames del micrófono entran aquí.
        await self._send(protocol.audio_block_start(self._prompt_name, self._audio_content))
        self._started = True
        log.info(
            "bridge.started",
            model=self._settings.nova_model_id,
            voice=voice,
            herramientas=len(especificaciones or []),
        )

    async def close(self) -> None:
        if self._closed or self._stream is None:
            return
        self._closed = True
        with contextlib.suppress(Exception):
            if self._started:
                await self._send(protocol.content_end(self._prompt_name, self._audio_content))
                await self._send(protocol.prompt_end(self._prompt_name))
                await self._send(protocol.session_end())
            # Al cerrar aparece AWS_ERROR_HTTP_STREAM_HAS_COMPLETED: es ruido de
            # limpieza del CRT, no un fallo de la conversación (ADR 0002).
            await self._stream.input_stream.close()
        log.info("bridge.closed")

    # ── entrada ──────────────────────────────────────────────────────

    async def send_audio(self, pcm16_b64: str) -> None:
        """Reenvía un frame del micrófono. Sin cola, sin acumulación."""
        self._audio_recibido = True
        await self._send(protocol.audio_input(self._prompt_name, self._audio_content, pcm16_b64))

    async def send_text(self, text: str) -> None:
        """Entrada de texto en la misma sesión: es el modo de respaldo (ADR 0009).

        Con voz, Nova Sonic detecta solo el fin del turno por las pausas del
        hablante. Con texto no hay pausa que detectar, así que hay que marcarlo:
        se cierra el bloque de audio abierto y se abre uno nuevo. Sin esto el
        modelo recibe el texto y se queda esperando indefinidamente, sin emitir
        ningún evento ni ningún error.
        """
        for evento in protocol.text_block(self._prompt_name, _new_id(), role="USER", text=text):
            await self._send(evento)
        await self._end_user_turn()

    async def _end_user_turn(self) -> None:
        # En modo texto el fin del turno lo marcamos nosotros, así que aquí el
        # TTFA se mide de verdad desde el instante en que el corredor envió.
        self.metrics.user_speech_end()
        # Un bloque de audio que nunca recibió datos no se puede cerrar:
        # «Cannot end content as no content data was received». En un turno de
        # sólo texto hay que rellenarlo con silencio antes de cerrarlo.
        if not self._audio_recibido:
            await self._send(
                protocol.audio_input(self._prompt_name, self._audio_content, _SILENCIO)
            )
        await self._send(protocol.content_end(self._prompt_name, self._audio_content))
        self._audio_content = _new_id()
        self._audio_recibido = False
        await self._send(protocol.audio_block_start(self._prompt_name, self._audio_content))

    # ── salida ───────────────────────────────────────────────────────

    async def events(self) -> AsyncIterator[BridgeEvent]:
        """Traduce los eventos crudos de Bedrock a algo que el navegador entienda."""
        assert self._stream is not None, "hay que llamar a start() primero"
        while not self._closed:
            try:
                salida = await self._stream.await_output()
                resultado = await salida[1].receive()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                yield BridgeEvent("error", {"message": str(exc)})
                return

            if resultado is None or resultado.value is None or resultado.value.bytes_ is None:
                continue

            evento = json.loads(resultado.value.bytes_.decode("utf-8")).get("event", {})
            traducido = self._translate(evento)
            if traducido is not None:
                yield traducido
                # El evento se emite ANTES de ejecutar: la interfaz enseña
                # «consultando el plan…» mientras la consulta ocurre, en vez de
                # después, que es cuando ya no sirve de nada.
                if traducido.kind == "tool_call":
                    await self._responder_herramienta(traducido.payload)

    def _translate(self, evento: dict[str, Any]) -> BridgeEvent | None:
        if "contentStart" in evento:
            inicio = evento["contentStart"]
            rol = inicio.get("role", "ASSISTANT")
            # La deduplicación especulativa/FINAL es del habla del COACH: el
            # modelo emite cada respuesta suya dos veces y hay que quedarse con
            # una. La transcripción de lo que dijo el USUARIO llega una sola vez
            # y viene marcada FINAL, así que aplicarle la misma regla la borra
            # entera — el corredor hablaba y su turno no aparecía nunca.
            self._emitir_texto = rol == "USER" or _debe_emitir(inicio)
            return None

        if "audioOutput" in evento:
            self.metrics.first_audio_out()
            return BridgeEvent("audio", {"audio_b64": evento["audioOutput"]["content"]})

        if "textOutput" in evento:
            salida = evento["textOutput"]
            contenido = salida.get("content", "")
            if _es_payload_de_control(contenido):
                # `{"interrupted": true}` es el acuse de que el modelo dejó de
                # hablar: cierra el cronómetro de la interrupción.
                self.metrics.barge_in_stopped()
                return None
            if not self._emitir_texto:
                return None
            if salida.get("role") == "USER":
                # La transcripción final del usuario es la primera señal que
                # tiene el servidor de que el turno acabó. No es el instante en
                # que dejó de hablar —eso pasa en su micrófono— así que el TTFA
                # real que percibe es algo mayor. Ver la cabecera de metrics.py.
                self.metrics.user_speech_end()
            return BridgeEvent(
                "transcript",
                {"text": contenido, "role": salida.get("role", "ASSISTANT")},
            )

        if "toolUse" in evento:
            return BridgeEvent("tool_call", evento["toolUse"])
        if "completionEnd" in evento:
            return BridgeEvent("turn_end")
        return None  # contentEnd, usageEvent: ruido para el navegador

    async def _responder_herramienta(self, peticion: dict[str, Any]) -> None:
        """Ejecuta lo que pidió el modelo y le devuelve el resultado.

        Sin ejecutor no se hace nada, y es lo correcto: si no hay herramientas
        declaradas, este evento no debería haber llegado nunca.
        """
        if self._tools is None:
            return

        nombre = peticion.get("toolName") or peticion.get("name") or ""
        tool_use_id = peticion.get("toolUseId", "")
        argumentos = _argumentos_de(peticion)

        resultado = await self._tools.run(nombre, argumentos)
        for evento in protocol.tool_result_block(
            self._prompt_name, _new_id(), tool_use_id=tool_use_id, result=resultado
        ):
            await self._send(evento)

    # ── internos ─────────────────────────────────────────────────────

    async def _send(self, evento: dict[str, Any]) -> None:
        assert self._stream is not None
        from aws_sdk_bedrock_runtime.models import (
            BidirectionalInputPayloadPart,
            InvokeModelWithBidirectionalStreamInputChunk,
        )

        await self._stream.input_stream.send(
            InvokeModelWithBidirectionalStreamInputChunk(
                value=BidirectionalInputPayloadPart(bytes_=json.dumps(evento).encode("utf-8"))
            )
        )

    async def _open_stream(self) -> Any:
        # Las credenciales del rol de instancia caducan en horas, y el SDK de
        # smithy sólo lee variables de entorno. Sin esto, la voz funciona toda
        # la tarde y deja de funcionar de madrugada sin que nadie toque nada.
        ensure_fresh_credentials()

        from aws_sdk_bedrock_runtime.client import AsyncBedrockRuntimeClient
        from aws_sdk_bedrock_runtime.config import Config
        from aws_sdk_bedrock_runtime.models import (
            InvokeModelWithBidirectionalStreamOperationInput,
        )
        from smithy_aws_core.identity.environment import EnvironmentCredentialsResolver

        cliente = AsyncBedrockRuntimeClient(
            config=Config(
                endpoint_uri=self._settings.endpoint_uri,
                region=self._settings.aws_region,
                aws_credentials_identity_resolver=EnvironmentCredentialsResolver(),
            )
        )
        return await cliente.invoke_model_with_bidirectional_stream(
            InvokeModelWithBidirectionalStreamOperationInput(model_id=self._settings.nova_model_id)
        )
