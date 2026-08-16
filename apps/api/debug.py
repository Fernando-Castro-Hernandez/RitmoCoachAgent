"""`/metrics` y el reproductor de sesión.

Dos superficies de observabilidad con públicos distintos:

- **`GET /metrics`** — formato Prometheus, para una máquina. Es lo que se
  raspa cada quince segundos.
- **`GET /debug/sessions/{user_id}`** — para una persona. Reconstruye una
  conversación desde la bitácora: qué se dijo, qué decidió el motor y con qué
  justificación, y qué avisos salieron por Telegram.

El reproductor existe por una razón concreta: cuando alguien pregunta «¿por qué
el sistema me dijo esto?», la respuesta tiene que ser una traza y no una
conjetura. Un producto de salud que no puede explicarse no es defendible, y esa
es la misma razón por la que `coach_decision` guarda la regla y el porqué.

**Sin llave, cerrado.** El reproductor devuelve la conversación completa de una
persona. Reutiliza la llave de automatización en vez de inventar una segunda:
son el mismo perímetro —lo que se le enseña a un operador— y dos secretos para
lo mismo es un secreto que alguien no rota.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, Response
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from apps.api.db.models import NudgeLogRow
from apps.api.db.repo import LogRepo, MemoryRepo, StateRepo
from apps.api.db.session import get_session

router = APIRouter(tags=["observabilidad"])

Sesion = Annotated[AsyncSession, Depends(get_session)]

LIMITE_TURNOS = 100


@router.get("/metrics")
def metricas() -> Response:
    """Exposición Prometheus. Sin llave: no lleva datos de nadie.

    Son contadores e histogramas agregados —latencias, violaciones, disparos de
    la puerta—. Ni un identificador de corredor sale por aquí, que es lo que
    permite raspar este endpoint desde la red interna sin más ceremonia.
    """
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/debug/sessions/{user_id}")
async def reproducir(
    user_id: str,
    sesion: Sesion,
    x_ritmo_automation_key: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """La conversación de un corredor, reconstruida desde la bitácora."""
    esperada = get_settings().automation_api_key
    if not esperada:
        raise HTTPException(503, "el reproductor de sesión no está configurado")
    if not hmac.compare_digest(x_ritmo_automation_key or "", esperada):
        raise HTTPException(403, "llave inválida")

    memoria = MemoryRepo(sesion)
    registro = LogRepo(sesion)
    estado = await StateRepo(sesion).get_row(user_id)

    turnos = await memoria.recent(user_id, limit=LIMITE_TURNOS)
    decisiones = await registro.decisions(user_id, limit=LIMITE_TURNOS)
    sesiones = await registro.sessions(user_id, limit=30)
    avisos = (
        (
            await sesion.execute(
                select(NudgeLogRow)
                .where(NudgeLogRow.user_id == user_id)
                .order_by(NudgeLogRow.id.desc())
                .limit(30)
            )
        )
        .scalars()
        .all()
    )

    return {
        "user_id": user_id,
        "turns": [{"role": t.role, "text": t.text, "at": t.created_at.isoformat()} for t in turnos],
        # La traza que contesta «¿por qué me dijo esto?». Cada decisión trae la
        # regla que la produjo, no sólo el resultado.
        "decisions": [
            {"rule": d.rule, "rationale": d.rationale, "at": d.created_at.isoformat()}
            for d in decisiones
        ],
        "sessions": [
            {
                "on": s.occurred_on.isoformat(),
                "distance_km": s.distance_km,
                "pace_sec_per_km": s.pace_sec_per_km,
                "source": s.source,
                "discrepancy_flag": s.discrepancy_flag,
            }
            for s in sesiones
        ],
        "nudges": [
            {"flow": n.flow, "sent_on": n.sent_on.isoformat(), "text": n.text} for n in avisos
        ],
        "plan": (
            None
            if estado is None
            else {
                "version": estado.plan_version,
                "current_week": estado.current_week,
                "reason": estado.reason,
            }
        ),
    }
