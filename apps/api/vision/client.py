"""Cliente de visión: `Converse` sobre Bedrock, con salida estructurada.

La otra mitad de la arquitectura multimodelo del ADR 0014. Nova 2 Sonic sólo
acepta `SPEECH` —verificado contra el catálogo de la cuenta— así que las
imágenes van por una ruta distinta, con otro modelo y otro protocolo.

Dos decisiones que no son cosméticas:

- **`toolChoice` fuerza la herramienta.** El modelo no puede responder con prosa
  que después haya que parsear: la única salida posible es el esquema. Y de
  paso, una imagen con texto inyectado no tiene dónde alojar una instrucción.
- **`temperature = 0`.** Esto es lectura, no redacción. La misma captura tiene
  que dar el mismo número dos veces, o la bitácora deja de ser reproducible.
"""

from __future__ import annotations

import json
from typing import Any, Protocol

import structlog

from apps.api.config import get_settings

log = structlog.get_logger(__name__)

# Bedrock nombra los formatos sin el «image/».
_FORMATOS = {
    "image/jpeg": "jpeg",
    "image/jpg": "jpeg",
    "image/png": "png",
    "image/webp": "webp",
    "image/gif": "gif",
}

MAX_IMAGE_BYTES = 8 * 1024 * 1024
_TOOL_NAME = "registrar_extraccion"


class VisionError(RuntimeError):
    """El modelo no devolvió algo utilizable."""


class VisionClient(Protocol):
    """Lo mínimo que necesita la ruta de visión.

    Es un protocolo y no la clase concreta para que las pruebas puedan sustituir
    el modelo sin red, sin credenciales y sin gastar un token.
    """

    async def extract(
        self,
        images: list[tuple[bytes, str]],
        *,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]: ...


class BedrockVisionClient:
    """Implementación real contra `Converse`."""

    def __init__(self, model_id: str | None = None) -> None:
        self._model_id = model_id or get_settings().vision_model_id

    async def extract(
        self,
        images: list[tuple[bytes, str]],
        *,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        # Importado aquí y no arriba: arrastra botocore entero, y el arranque
        # de la API no debería pagar ese coste por una ruta que sólo se usa
        # cuando alguien sube una imagen.
        import aioboto3

        contenido: list[dict[str, Any]] = []
        for datos, tipo in images:
            formato = _FORMATOS.get(tipo)
            if formato is None:
                raise VisionError(f"formato no soportado: {tipo}")
            if len(datos) > MAX_IMAGE_BYTES:
                raise VisionError("la imagen supera el tamaño máximo")
            contenido.append({"image": {"format": formato, "source": {"bytes": datos}}})
        contenido.append({"text": prompt})

        sesion = aioboto3.Session()
        async with sesion.client(
            "bedrock-runtime", region_name=get_settings().aws_region
        ) as cliente:
            respuesta = await cliente.converse(
                modelId=self._model_id,
                messages=[{"role": "user", "content": contenido}],
                toolConfig={
                    "tools": [
                        {
                            "toolSpec": {
                                "name": _TOOL_NAME,
                                "description": "Devuelve exactamente lo que se lee en la imagen.",
                                "inputSchema": {"json": schema},
                            }
                        }
                    ],
                    # Fuerza la herramienta: no hay salida posible fuera del esquema.
                    "toolChoice": {"tool": {"name": _TOOL_NAME}},
                },
                # Esto es lectura, no redacción: la misma captura, el mismo número.
                inferenceConfig={"temperature": 0.0, "maxTokens": 1024},
            )

        return _primer_tool_use(respuesta)


def _primer_tool_use(respuesta: dict[str, Any]) -> dict[str, Any]:
    bloques = respuesta.get("output", {}).get("message", {}).get("content", [])
    for bloque in bloques:
        if "toolUse" in bloque:
            entrada = bloque["toolUse"].get("input", {})
            # Algunos modelos devuelven el JSON como cadena aunque se les fuerce
            # el esquema. Aceptar las dos formas cuesta tres líneas.
            if isinstance(entrada, str):
                try:
                    return dict(json.loads(entrada))
                except json.JSONDecodeError as exc:
                    raise VisionError(f"la salida no es JSON válido: {entrada[:120]}") from exc
            return dict(entrada)
    log.warning("vision.sin_tool_use", bloques=len(bloques))
    raise VisionError("el modelo no invocó la herramienta de extracción")


class FallbackVisionClient:
    """Intenta con el modelo principal y cae al de respaldo si falla.

    No es sobreingeniería: los dos modos de fallo son reales y los dos se
    encontraron verificando contra la cuenta de verdad.

    - `ThrottlingException` con «Too many tokens per day». La cuota de tokens
      diarios que el ADR 0002 encontró en 0 **sí** gobierna a los modelos de
      texto y visión, aunque no gobernara al de voz. Es el mismo número, y por
      fin se ve el efecto que allá no se vio.
    - `ResourceNotFoundException` con «use case details have not been
      submitted». Los modelos de Anthropic exigen rellenar un formulario en la
      consola antes del primer uso.

    Que la ruta de visión sobreviva a cualquiera de los dos es la diferencia
    entre una demo que se cae y una que se degrada.
    """

    def __init__(self, primary: VisionClient, fallback: VisionClient) -> None:
        self._primary = primary
        self._fallback = fallback

    async def extract(
        self,
        images: list[tuple[bytes, str]],
        *,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        try:
            return await self._primary.extract(images, prompt=prompt, schema=schema)
        except Exception as exc:
            if not _es_recuperable(exc):
                raise
            log.warning("vision.fallback", error=type(exc).__name__, detalle=str(exc)[:160])
            return await self._fallback.extract(images, prompt=prompt, schema=schema)


# Errores que justifican reintentar con el otro modelo. Un formato de imagen
# inválido o un esquema mal formado fallarían igual en los dos, y reintentarlos
# sólo duplicaría la espera del usuario.
_RECUPERABLES = (
    "ThrottlingException",
    "ResourceNotFoundException",
    "ServiceUnavailableException",
    "ModelNotReadyException",
    "AccessDeniedException",
)


# Frases que identifican el fallo aunque el tipo de excepción no ayude. Las dos
# primeras son literales de lo que devolvió Bedrock al verificar contra la
# cuenta real, y por eso están aquí y no inventadas.
_FRASES_RECUPERABLES = (
    "too many tokens",
    "use case details",
    "throttl",
    "not ready",
    "try again",
)


def _es_recuperable(exc: Exception) -> bool:
    """Si vale la pena reintentar con el otro modelo.

    Se mira por tres vías porque botocore no da una sola fiable: el código de
    error de la respuesta, el nombre de la clase, y el texto. Un formato de
    imagen inválido fallaría igual en los dos modelos, así que ése no entra.
    """
    respuesta = getattr(exc, "response", None)
    if isinstance(respuesta, dict):
        codigo = respuesta.get("Error", {}).get("Code", "")
        if codigo in _RECUPERABLES:
            return True
    if type(exc).__name__ in _RECUPERABLES:
        return True
    texto = str(exc).lower()
    return any(frase in texto for frase in _FRASES_RECUPERABLES)
