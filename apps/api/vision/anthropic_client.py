"""Cliente de visión contra la API directa de Anthropic.

**La ruta principal de visión desde el pivote multi-nube** (ADR 0014). No pasa
por Bedrock: llama a `api.anthropic.com` con su propio saldo y sus propias
cuotas, que es justamente el punto — la ruta de visión deja de depender de la
burocracia de una cuenta nueva de AWS.

La voz se queda en Bedrock y no se toca: Anthropic no tiene modelo de streaming
bidireccional de voz, y Nova Sonic sí.

El contrato es idéntico al del cliente de Bedrock —mismo `VisionClient`, mismo
esquema, misma salida— así que el resto del sistema no se entera de por dónde
salió la imagen. Eso es lo que permite cambiar de proveedor con una variable de
entorno en vez de con un refactor.
"""

from __future__ import annotations

import base64
from typing import Any

import structlog

from apps.api.config import get_settings
from apps.api.vision.client import MAX_IMAGE_BYTES, VisionError

log = structlog.get_logger(__name__)

_TOOL_NAME = "registrar_extraccion"

# Formatos que acepta la API de Anthropic para imágenes.
_TIPOS = {
    "image/jpeg": "image/jpeg",
    "image/jpg": "image/jpeg",
    "image/png": "image/png",
    "image/webp": "image/webp",
    "image/gif": "image/gif",
}


class MissingApiKeyError(VisionError):
    """No hay `ANTHROPIC_API_KEY` configurada."""


class AnthropicVisionClient:
    """Extracción estructurada con `tool_choice` forzado.

    Las dos decisiones del cliente de Bedrock se conservan porque son del
    problema, no del proveedor:

    - **`tool_choice` fuerza la herramienta.** La única salida posible es el
      esquema, así que no hay prosa que parsear — y una imagen con texto
      inyectado no tiene ningún campo donde alojar una instrucción.
    - **`temperature = 0`.** Esto es lectura, no redacción: la misma captura
      tiene que dar el mismo número dos veces.
    """

    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        ajustes = get_settings()
        self._model = model or ajustes.vision_models[0]
        self._api_key = api_key or ajustes.anthropic_api_key

    async def extract(
        self,
        images: list[tuple[bytes, str]],
        *,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        if not self._api_key:
            raise MissingApiKeyError(
                "falta ANTHROPIC_API_KEY; la ruta de visión no puede llamar a la API"
            )

        # Importado aquí y no arriba para que el arranque de la API no pague el
        # coste de un SDK que sólo se usa cuando alguien sube una imagen.
        from anthropic import AsyncAnthropic

        contenido: list[dict[str, Any]] = []
        for datos, tipo in images:
            media = _TIPOS.get(tipo)
            if media is None:
                raise VisionError(f"formato no soportado: {tipo}")
            if len(datos) > MAX_IMAGE_BYTES:
                raise VisionError("la imagen supera el tamaño máximo")
            contenido.append(
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media,
                        "data": base64.standard_b64encode(datos).decode("ascii"),
                    },
                }
            )
        contenido.append({"type": "text", "text": prompt})

        cliente = AsyncAnthropic(api_key=self._api_key)
        respuesta = await cliente.messages.create(
            model=self._model,
            max_tokens=1024,
            temperature=0.0,
            tools=[
                {
                    "name": _TOOL_NAME,
                    "description": "Devuelve exactamente lo que se lee en la imagen.",
                    "input_schema": schema,
                }
            ],
            # Fuerza la herramienta: no hay salida posible fuera del esquema.
            tool_choice={"type": "tool", "name": _TOOL_NAME},
            messages=[{"role": "user", "content": contenido}],
        )
        return _primer_tool_use(respuesta)


def _primer_tool_use(respuesta: Any) -> dict[str, Any]:
    for bloque in getattr(respuesta, "content", []) or []:
        if getattr(bloque, "type", None) == "tool_use":
            entrada = getattr(bloque, "input", None)
            if isinstance(entrada, dict):
                return dict(entrada)
    log.warning("vision.anthropic.sin_tool_use", parada=getattr(respuesta, "stop_reason", None))
    raise VisionError("el modelo no invocó la herramienta de extracción")
