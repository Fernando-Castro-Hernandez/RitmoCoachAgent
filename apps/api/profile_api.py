"""Endpoints del perfil y del plan.

Los usa el carrusel de onboarding (capa dura) y la descarga en CSV. La capa
blanda no pasa por aquí: sale hablando, por el WebSocket de voz.

**El `user_id` ya no viaja en la URL.** Sale del token, y sólo de ahí. Cuando la
identidad era un UUID del navegador, `GET /api/profile/<cualquier-cosa>`
contestaba con el perfil de cualquiera; quitar el parámetro es lo que hace que
ese agujero no pueda volver por descuido. Un parámetro que no existe no se
puede olvidar de comprobar.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Annotated, Any

from coach_domain.paces import format_pace
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import UsuarioActual
from apps.api.db.repo import ProfileRepo, StateRepo
from apps.api.db.session import get_session
from apps.api.onboarding import (
    HARD_FIELDS,
    can_finish_carousel,
    next_question,
    profile_completeness,
)

router = APIRouter(prefix="/api", tags=["perfil"])

Sesion = Annotated[AsyncSession, Depends(get_session)]

CSV_COLUMNS = [
    "semana",
    "fase",
    "fecha",
    "dia",
    "tipo",
    "distancia_km",
    "ritmo_objetivo",
    "zona",
    "notas",
    "senal_de_tecnica",
]

_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


class HardProfile(BaseModel):
    """Lo que captura el carrusel. Todo opcional menos la meta.

    Un onboarding que exige nueve respuestas antes de dejarte entrar es un
    onboarding que la gente abandona: el resto se salta y la conversación lo
    recoge después.
    """

    goal_distance: str = Field(..., pattern="^(5k|10k|21k|42k)$")
    race_date: date | None = None
    days_per_week: int | None = Field(None, ge=1, le=7)
    age: int | None = Field(None, ge=10, le=100)
    weight_kg: float | None = Field(None, gt=20, lt=250)
    height_cm: float | None = Field(None, gt=100, lt=250)
    reference_distance_km: float | None = Field(None, gt=0, le=100)
    reference_time_sec: int | None = Field(None, gt=0)
    timezone: str | None = None
    level: str | None = Field(None, pattern="^(principiante|intermedio|avanzado)$")


@router.post("/profile")
async def save_hard_profile(
    cuerpo: HardProfile, sesion: Sesion, usuario: UsuarioActual
) -> dict[str, Any]:
    """Guarda la capa dura y dice qué le queda por preguntar a la voz."""
    user_id = usuario.id
    campos = {k: v for k, v in cuerpo.model_dump().items() if v is not None}
    repo = ProfileRepo(sesion)
    await repo.save(user_id, **campos)
    await sesion.commit()

    contexto = await repo.context(user_id)
    return {
        "ok": True,
        "saved": sorted(campos),
        "completeness": profile_completeness(contexto),
        # Lo que la conversación tiene que recoger. El coach abre por aquí en
        # vez de por «¿cómo te llamas?».
        "next_voice_question": next_question(contexto),
    }


@router.get("/profile")
async def get_profile(sesion: Sesion, usuario: UsuarioActual) -> dict[str, Any]:
    contexto = await ProfileRepo(sesion).context(usuario.id)
    if contexto is None:
        raise HTTPException(404, "no hay perfil todavía")
    return {
        "profile": contexto,
        "completeness": profile_completeness(contexto),
        "carousel_done": can_finish_carousel(contexto),
        "hard_fields": list(HARD_FIELDS),
        "next_voice_question": next_question(contexto),
    }


@router.get("/plan/export.csv")
async def export_plan_csv(sesion: Sesion, usuario: UsuarioActual) -> Response:
    """El plan activo en CSV.

    Responde a algo que la entrevista de la Fase 2 dejó claro: el corredor
    experimentado ya lleva su hoja de cálculo. No se le pide que la abandone; se
    le llena.
    """
    user_id = usuario.id
    plan = await StateRepo(sesion).get(user_id)
    if plan is None:
        raise HTTPException(404, "no hay plan que exportar")

    buffer = io.StringIO()
    escritor = csv.DictWriter(buffer, fieldnames=CSV_COLUMNS)
    escritor.writeheader()
    for semana in plan.weeks:
        for s in sorted(semana.sessions, key=lambda x: x.day_of_week):
            escritor.writerow(
                {
                    "semana": semana.index,
                    "fase": semana.phase,
                    "fecha": (
                        semana.start_date.fromordinal(
                            semana.start_date.toordinal() + s.day_of_week
                        ).isoformat()
                    ),
                    "dia": _DIAS[s.day_of_week],
                    "tipo": s.kind,
                    "distancia_km": s.distance_km,
                    "ritmo_objetivo": (
                        ""
                        if s.pace is None
                        else f"{format_pace(s.pace.min_sec_per_km)}-"
                        f"{format_pace(s.pace.max_sec_per_km)}"
                    ),
                    "zona": s.zone,
                    "notas": s.notes,
                    "senal_de_tecnica": s.technique_cue_id or "",
                }
            )

    # BOM UTF-8: sin él, Excel en Windows destroza los acentos, y el archivo
    # llega a alguien que sólo quería ver su plan.
    contenido = "﻿" + buffer.getvalue()
    return Response(
        content=contenido,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="plan-{user_id}.csv"'},
    )
