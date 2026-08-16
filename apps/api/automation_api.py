"""Lo que n8n le pregunta a la API.

Dos endpoints y una llave. Los flujos no saben nada del producto: preguntan
«¿a quién le toca el recordatorio de la mañana ahora mismo?», reciben una lista
con el `chat_id` y el texto ya redactado, y la reparten por Telegram.

Que el texto venga hecho no es comodidad: es lo que impide que la lógica del
producto —qué se dice, con qué números, y cuándo callarse porque la puerta de
seguridad está en rojo— acabe repartida entre cinco JSON de n8n donde no hay
pruebas que la cubran.

**La llave.** Estos endpoints devuelven datos de salud de personas con nombre y
apellido, así que van detrás de un secreto compartido, y —igual que el webhook
de Telegram— **cierran si no está configurado** en vez de caer abiertos.
"""

from __future__ import annotations

import hmac
from datetime import UTC, datetime
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.automation import FLOWS, Nudge, due, mark_sent
from apps.api.config import get_settings
from apps.api.db.session import get_session

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/automation", tags=["automatización"])

Sesion = Annotated[AsyncSession, Depends(get_session)]

# El escalamiento no se marca al entregarlo: se marca cuando n8n confirma que
# Telegram lo aceptó. Un «buenos días» perdido no le cuesta nada a nadie; un
# «para de entrenar y que te vea alguien» perdido, sí.
CONFIRMA_ENTREGA = frozenset({"escalation"})


def _autorizar(llave: str | None) -> None:
    esperada = get_settings().automation_api_key
    if not esperada:
        log.error("automation.sin_llave")
        raise HTTPException(503, "la automatización no está configurada")
    # Tiempo constante: la llave viaja en cada petición horaria de cinco flujos.
    if not hmac.compare_digest(llave or "", esperada):
        log.warning("automation.llave_invalida")
        raise HTTPException(403, "llave inválida")


class Ack(BaseModel):
    """Lo que n8n devuelve cuando Telegram aceptó el mensaje."""

    user_id: str
    flow: str
    local_date: str
    text: str = ""


@router.get("/due/{flow}")
async def pendientes(
    flow: str,
    sesion: Sesion,
    x_ritmo_automation_key: Annotated[str | None, Header()] = None,
    at: str | None = None,
) -> dict[str, Any]:
    """A quién le toca este flujo ahora mismo, cada uno en su hora local.

    `at` (ISO 8601, UTC) permite fijar el instante para demostrar el
    comportamiento por zona horaria sin esperar a las seis de la mañana. Es
    lectura pura y no cambia a quién se le marca nada.
    """
    _autorizar(x_ritmo_automation_key)
    if flow not in FLOWS:
        raise HTTPException(404, f"flujo desconocido: {flow}")

    ahora = _instante(at)
    avisos = await due(sesion, flow, ahora)

    if flow not in CONFIRMA_ENTREGA:
        for aviso in avisos:
            await mark_sent(sesion, aviso)
        await sesion.commit()

    log.info("automation.due", flow=flow, cuantos=len(avisos))
    return {
        "flow": flow,
        "at": ahora.isoformat(),
        "count": len(avisos),
        "nudges": [a.as_dict() for a in avisos],
    }


@router.post("/ack")
async def confirmar(
    cuerpo: Ack, sesion: Sesion, x_ritmo_automation_key: Annotated[str | None, Header()] = None
) -> dict[str, Any]:
    """Marca un aviso como entregado. Sólo lo necesita el escalamiento.

    Es idempotente por construcción: `mark_sent` anexa, y el filtro de
    `due` es «existe alguna fila de este flujo en esta fecha local», así que
    confirmar dos veces no cambia el resultado.
    """
    _autorizar(x_ritmo_automation_key)
    if cuerpo.flow not in FLOWS:
        raise HTTPException(404, f"flujo desconocido: {cuerpo.flow}")

    try:
        dia = datetime.fromisoformat(cuerpo.local_date).date()
    except ValueError as e:
        raise HTTPException(422, "local_date tiene que ser una fecha ISO") from e

    await mark_sent(
        sesion,
        Nudge(
            user_id=cuerpo.user_id,
            chat_id=0,
            flow=cuerpo.flow,
            timezone="",
            local_time="",
            local_date=dia,
            text=cuerpo.text,
        ),
    )
    await sesion.commit()
    log.info("automation.ack", flow=cuerpo.flow, user_id=cuerpo.user_id)
    return {"ok": True}


def _instante(at: str | None) -> datetime:
    if at is None:
        return datetime.now(UTC)
    try:
        momento = datetime.fromisoformat(at)
    except ValueError as e:
        raise HTTPException(422, "«at» tiene que ser una marca de tiempo ISO 8601") from e
    # Sin zona explícita se asume UTC: es lo que manda n8n y lo que evita que un
    # `at` ambiguo se interprete con la zona del servidor, que no es la de nadie.
    return momento if momento.tzinfo else momento.replace(tzinfo=UTC)
