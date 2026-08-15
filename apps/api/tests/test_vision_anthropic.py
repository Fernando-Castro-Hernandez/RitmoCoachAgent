"""Cliente de visión contra la API directa de Anthropic.

Ruta principal desde el pivote multi-nube (ADR 0014). Se prueba con la respuesta
del SDK simulada: sin red, sin clave y sin gastar saldo.

Lo que se verifica es que el contrato no cambió al cambiar de proveedor. El
resto del sistema —`extract_workout`, `reconcile`, el endpoint— no puede
enterarse de por dónde salió la imagen, porque eso es lo que permite mover la
ruta con una variable de entorno en vez de con un refactor.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass
from typing import Any

import pytest

from apps.api.vision.anthropic_client import (
    AnthropicVisionClient,
    MissingApiKeyError,
    _primer_tool_use,
)
from apps.api.vision.client import VisionError
from apps.api.vision.schemas import WORKOUT_SCHEMA
from apps.api.vision.workout import extract_workout, reconcile


@dataclass
class BloqueFalso:
    type: str
    input: dict[str, Any] | None = None
    text: str | None = None


@dataclass
class RespuestaFalsa:
    content: list[BloqueFalso]
    stop_reason: str = "tool_use"


class MensajesFalsos:
    def __init__(self, respuesta: Any, error: Exception | None = None) -> None:
        self.respuesta = respuesta
        self.error = error
        self.kwargs: dict[str, Any] = {}

    async def create(self, **kwargs: Any) -> Any:
        self.kwargs = kwargs
        if self.error is not None:
            raise self.error
        return self.respuesta


class SdkFalso:
    """Sustituye a `AsyncAnthropic` sin tocar la red."""

    ultima: MensajesFalsos

    def __init__(self, respuesta: Any, error: Exception | None = None) -> None:
        self._respuesta = respuesta
        self._error = error

    def __call__(self, **_: Any) -> SdkFalso:
        self.messages = MensajesFalsos(self._respuesta, self._error)
        SdkFalso.ultima = self.messages
        return self


@pytest.fixture
def sdk(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Inyecta el doble en el punto de importación perezosa del cliente."""

    def _instalar(respuesta: Any, error: Exception | None = None) -> SdkFalso:
        import anthropic

        doble = SdkFalso(respuesta, error)
        monkeypatch.setattr(anthropic, "AsyncAnthropic", doble)
        return doble

    return _instalar


_LECTURA = {
    "distance_km": 8.42,
    "duration_sec": 2838,
    "avg_pace_sec_per_km": 350,
    "avg_hr": 152,
    "confidence": "high",
    "unreadable_fields": [],
}


def _respuesta_ok() -> RespuestaFalsa:
    return RespuestaFalsa([BloqueFalso(type="tool_use", input=dict(_LECTURA))])


# ── el contrato no cambió al cambiar de proveedor ────────────────────


async def test_extrae_igual_que_el_cliente_de_bedrock(sdk: Any) -> None:
    sdk(_respuesta_ok())
    cliente = AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="sk-ant-falsa")

    extraccion = await extract_workout(cliente, b"pngfalso", "image/png")
    assert extraccion.distance_km == 8.42
    assert extraccion.confidence == "high"


async def test_el_motor_sigue_mandando_sobre_el_modelo(sdk: Any) -> None:
    """La regla del ADR 0003 no depende del proveedor.

    El modelo leyó 5:50; 8.42 km en 47:18 son 5:37. Gana el motor, y la
    discrepancia queda marcada igual que en la ruta de Bedrock.
    """
    sdk(_respuesta_ok())
    cliente = AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="sk-ant-falsa")

    propuesta = reconcile(await extract_workout(cliente, b"x", "image/png"))
    assert propuesta.pace_sec_per_km == 337
    assert propuesta.discrepancy_flag is True
    assert propuesta.source == "coach_domain.paces.pace_from_run"


# ── cómo se llama a la API ───────────────────────────────────────────


async def test_fuerza_la_herramienta_y_pone_temperatura_cero(sdk: Any) -> None:
    """Las dos decisiones son del problema, no del proveedor.

    `tool_choice` deja el esquema como única salida posible —y de paso, una
    imagen con texto inyectado no tiene dónde alojar una instrucción—. La
    temperatura en cero es porque esto es lectura, no redacción.
    """
    sdk(_respuesta_ok())
    cliente = AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="sk-ant-falsa")
    await cliente.extract([(b"x", "image/png")], prompt="lee esto", schema=WORKOUT_SCHEMA)

    kwargs = SdkFalso.ultima.kwargs
    assert kwargs["tool_choice"] == {"type": "tool", "name": "registrar_extraccion"}
    assert kwargs["temperature"] == 0.0
    assert kwargs["tools"][0]["input_schema"] is WORKOUT_SCHEMA


async def test_la_imagen_viaja_en_base64_con_su_tipo(sdk: Any) -> None:
    sdk(_respuesta_ok())
    cliente = AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="sk-ant-falsa")
    await cliente.extract([(b"bytes-crudos", "image/jpeg")], prompt="p", schema={})

    contenido = SdkFalso.ultima.kwargs["messages"][0]["content"]
    imagen = contenido[0]
    assert imagen["type"] == "image"
    assert imagen["source"]["media_type"] == "image/jpeg"
    assert base64.standard_b64decode(imagen["source"]["data"]) == b"bytes-crudos"
    assert contenido[-1] == {"type": "text", "text": "p"}


async def test_el_modelo_se_puede_cambiar_por_configuracion(sdk: Any) -> None:
    sdk(_respuesta_ok())
    cliente = AnthropicVisionClient("claude-sonnet-4-5-20250929", api_key="sk-ant-falsa")
    await cliente.extract([(b"x", "image/png")], prompt="p", schema={})
    assert SdkFalso.ultima.kwargs["model"] == "claude-sonnet-4-5-20250929"


# ── fallos ───────────────────────────────────────────────────────────


async def test_sin_clave_falla_claro_y_pronto() -> None:
    """Y no con un 401 críptico a mitad de una subida."""
    cliente = AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="")
    with pytest.raises(MissingApiKeyError, match="ANTHROPIC_API_KEY"):
        await cliente.extract([(b"x", "image/png")], prompt="p", schema={})


async def test_un_formato_que_no_acepta_la_api_se_rechaza_antes_de_salir(sdk: Any) -> None:
    sdk(_respuesta_ok())
    cliente = AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="sk-ant-falsa")
    with pytest.raises(VisionError, match="formato no soportado"):
        await cliente.extract([(b"x", "image/bmp")], prompt="p", schema={})


async def test_una_imagen_gigante_no_se_manda(sdk: Any) -> None:
    sdk(_respuesta_ok())
    cliente = AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="sk-ant-falsa")
    with pytest.raises(VisionError, match="tamaño máximo"):
        await cliente.extract([(b"x" * (9 * 1024 * 1024), "image/png")], prompt="p", schema={})


def test_si_responde_con_prosa_falla_ruidosamente() -> None:
    respuesta = RespuestaFalsa(
        [BloqueFalso(type="text", text="creo que son unos 8 km")], stop_reason="end_turn"
    )
    with pytest.raises(VisionError, match="no invocó la herramienta"):
        _primer_tool_use(respuesta)


# ── la cadena y la degradación siguen funcionando ────────────────────


async def test_un_error_de_la_api_cae_a_captura_manual(sdk: Any) -> None:
    """Sin saldo o con la API caída, la cadena se agota y la interfaz degrada
    a que el corredor escriba los números (tarea D6)."""
    from apps.api.vision.client import AllVisionModelsUnavailableError, ChainVisionClient

    class OverloadedError(Exception):
        pass

    sdk(None, error=OverloadedError("Overloaded, please try again"))
    cadena = ChainVisionClient(
        [AnthropicVisionClient("claude-haiku-4-5-20251001", api_key="sk-ant-falsa")]
    )
    with pytest.raises(AllVisionModelsUnavailableError):
        await cadena.extract([(b"x", "image/png")], prompt="p", schema={})


def test_el_modelo_por_defecto_acepta_imagenes() -> None:
    """Claude 3.5 Haiku NO acepta imágenes; el 4.5 sí.

    Es el error fácil de cometer al elegir «el Haiku barato», y rompería la
    ruta entera en producción con un mensaje poco obvio.
    """
    from apps.api.config import Settings

    modelos = Settings().vision_models
    assert modelos
    assert not any("3-5-haiku" in m for m in modelos), (
        "Claude 3.5 Haiku no soporta entrada de imágenes"
    )
