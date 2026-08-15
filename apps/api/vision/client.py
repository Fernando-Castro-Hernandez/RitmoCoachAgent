"""Contrato de la ruta de visión, y su implementación sobre Bedrock.

Aquí viven el protocolo `VisionClient`, la cadena de modelos y el cliente de
Bedrock. **El cliente de Bedrock ya no es la ruta por defecto**: desde el pivote
multi-nube la visión va por la API directa de Anthropic
(`apps/api/vision/anthropic_client.py`). Se conserva porque volver a Bedrock es
un cambio de una línea en `get_vision_client`, y porque el ADR 0014 documenta
esa ruta como la alternativa vigente si el saldo de Anthropic se agota.

Nova 2 Sonic sólo acepta `SPEECH` —verificado contra el catálogo de la cuenta—
así que la voz nunca pudo compartir modelo con la visión.

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


class ChainVisionClient:
    """Recorre una lista de modelos hasta que uno responde.

    No es sobreingeniería defensiva: los tres modos de fallo son reales y los
    tres se encontraron verificando contra la cuenta, no imaginando.

    - `ThrottlingException` con «Too many tokens per day». La cuota de tokens
      diarios que el ADR 0002 encontró en 0 **sí** gobierna a los modelos de
      texto y visión, aunque no gobernara al de voz. En esta cuenta está en 0
      para los seis modelos con visión.
    - `ResourceNotFoundException` con «use case details have not been
      submitted». Los modelos de Anthropic exigen un acuerdo aceptado, y el
      estado se consulta con `get-foundation-model-availability`.
    - `AccessDeniedException` cuando el modelo no está habilitado en la región.

    El fallo resultó ser de **disponibilidad de cuenta**, no de capacidad del
    modelo, así que la respuesta correcta es una lista configurable: desbloquear
    cualquiera de ellos hace funcionar la ruta sin tocar código.
    """

    def __init__(self, clients: list[VisionClient]) -> None:
        if not clients:
            raise ValueError("hace falta al menos un modelo de visión")
        self._clients = clients

    async def extract(
        self,
        images: list[tuple[bytes, str]],
        *,
        prompt: str,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        ultimo: Exception | None = None
        for indice, cliente in enumerate(self._clients):
            try:
                return await cliente.extract(images, prompt=prompt, schema=schema)
            except Exception as exc:
                if not _es_recuperable(exc):
                    raise
                ultimo = exc
                log.warning(
                    "vision.modelo_no_disponible",
                    intento=indice + 1,
                    de=len(self._clients),
                    error=type(exc).__name__,
                    detalle=str(exc)[:160],
                )
        raise AllVisionModelsUnavailableError(
            f"ninguno de los {len(self._clients)} modelos de visión respondió"
        ) from ultimo


class AllVisionModelsUnavailableError(VisionError):
    """Se agotó la cadena. La interfaz degrada a captura manual (tarea D6)."""


# Errores que justifican reintentar con el siguiente modelo. Un formato de
# imagen inválido o un esquema mal formado fallarían igual en todos, y
# reintentarlos sólo duplicaría la espera del usuario.
_RECUPERABLES = (
    "ThrottlingException",
    "ResourceNotFoundException",
    "ServiceUnavailableException",
    "ModelNotReadyException",
    "AccessDeniedException",
    "ValidationException",
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
    "on-demand throughput",
)


def _es_recuperable(exc: Exception) -> bool:
    """Si vale la pena seguir con el siguiente modelo de la cadena.

    Se mira por tres vías porque botocore no da una sola fiable: el código de
    error de la respuesta, el nombre de la clase, y el texto.
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
