"""Endpoints de la ruta de visión (ADR 0014).

**El endpoint no escribe en la bitácora.** Devuelve lo leído y lo que el motor
propone, y el navegador se lo enseña al corredor para que lo confirme o lo
corrija (tarea D6). Sólo después se registra, por la ruta que ya existe.

Ese rodeo es deliberado: una cifra mal leída que entra sola a la bitácora
contamina la progresión, y la progresión es el producto.
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import UsuarioActual
from apps.api.config import get_settings
from apps.api.db.session import get_session
from apps.api.vision.anthropic_client import AnthropicVisionClient
from apps.api.vision.client import (
    MAX_IMAGE_BYTES,
    AllVisionModelsUnavailableError,
    ChainVisionClient,
    VisionClient,
    VisionError,
)
from apps.api.vision.workout import (
    ImplausibleExtractionError,
    extract_workout,
    reconcile,
)

log = structlog.get_logger(__name__)
router = APIRouter(prefix="/api/vision", tags=["visión"])

Sesion = Annotated[AsyncSession, Depends(get_session)]

TIPOS_ACEPTADOS = {"image/jpeg", "image/jpg", "image/png", "image/webp"}


def get_vision_client() -> VisionClient:
    """Dependencia sustituible: las pruebas inyectan un cliente falso."""
    ajustes = get_settings()
    # Sólo Anthropic en esta cadena. Mezclar proveedores en un mismo endpoint
    # haría que un fallo pudiera venir de dos sitios con formatos de error
    # distintos, y depurarlo costaría más de lo que ahorraría.
    return ChainVisionClient(
        [AnthropicVisionClient(m, ajustes.anthropic_api_key) for m in ajustes.vision_models]
    )


ClienteVision = Annotated[VisionClient, Depends(get_vision_client)]


async def _leer_imagen(archivo: UploadFile) -> bytes:
    if archivo.content_type not in TIPOS_ACEPTADOS:
        raise HTTPException(415, f"formato no soportado: {archivo.content_type}")
    datos = await archivo.read()
    if len(datos) > MAX_IMAGE_BYTES:
        raise HTTPException(413, "la imagen supera los 8 MB")
    if not datos:
        raise HTTPException(400, "la imagen viene vacía")
    return datos


@router.post("/workout")
async def leer_captura(
    cliente: ClienteVision,
    usuario: UsuarioActual,
    file: Annotated[UploadFile, File()],
) -> dict[str, Any]:
    """Lee una captura del reloj. **No guarda nada.**

    El `user_id` sale del token y ya no del formulario: mandarlo el cliente
    permitía subirle una captura a la bitácora de otra persona.
    """
    user_id = usuario.id
    datos = await _leer_imagen(file)

    try:
        extraccion = await extract_workout(cliente, datos, file.content_type or "image/jpeg")
    except AllVisionModelsUnavailableError as exc:
        # Se agotó la cadena de modelos. NO es un 502: la respuesta correcta es
        # degradar a captura manual, con los campos vacíos y editables. El
        # corredor teclea cuatro números y sigue con su vida; una pantalla de
        # error le deja el entrenamiento sin registrar.
        log.warning("vision.workout.sin_modelos", user_id=user_id, error=str(exc))
        return {
            "ok": False,
            "mode": "manual",
            "reason": ("Ahorita no puedo leer la imagen. Escribe los números y seguimos igual."),
            "fields": ["distance_km", "duration_sec", "avg_hr"],
            "extraction": None,
            "proposed": None,
        }
    except VisionError as exc:
        log.warning("vision.workout.fallo", user_id=user_id, error=str(exc))
        raise HTTPException(502, f"no pude leer la imagen: {exc}") from exc

    try:
        propuesta = reconcile(extraccion)
    except ImplausibleExtractionError as exc:
        # El motor rechazó lo leído. Se devuelve la extracción cruda igual, para
        # que el corredor vea qué se entendió mal y lo corrija a mano.
        return {
            "ok": False,
            "reason": str(exc),
            "extraction": asdict(extraccion),
            "proposed": None,
        }

    log.info(
        "vision.workout.ok",
        user_id=user_id,
        confidence=extraccion.confidence,
        discrepancy=propuesta.discrepancy_flag,
    )
    return {
        "ok": True,
        "extraction": asdict(extraccion),
        "proposed": asdict(propuesta),
        # Lo dice el endpoint y no el frontend: la regla de que el ritmo sale
        # del motor tiene que viajar con el dato.
        "pace_is_computed": True,
    }
