"""Serialización del plan para guardarlo y recuperarlo.

Se escribe a mano en vez de usar `dataclasses.asdict` y confiar en la suerte.
Dos razones: las fechas no son JSON, y —más importante— un plan que se guarda y
se recupera **tiene que volver idéntico**. Si el viaje de ida y vuelta pierde un
campo, el coach empieza a decir números distintos a los que generó el motor, y
eso es exactamente el fallo que toda la arquitectura existe para evitar.

Por eso hay una prueba de ida y vuelta, y por eso `plan_from_json` reconstruye
objetos del dominio y no diccionarios sueltos.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from coach_domain.plans import Plan, Session, Week
from coach_domain.progression import WeekLoad
from coach_domain.types import Level, PaceRange, RaceDistance

SCHEMA_VERSION = 1


def plan_to_json(plan: Plan) -> dict[str, Any]:
    return {
        "schema": SCHEMA_VERSION,
        "distance": plan.distance.value,
        "level": plan.level.value,
        "start_date": plan.start_date.isoformat(),
        "race_date": plan.race_date.isoformat() if plan.race_date else None,
        "weeks": [_week_to_json(w) for w in plan.weeks],
    }


def plan_from_json(data: dict[str, Any]) -> Plan:
    version = data.get("schema")
    if version != SCHEMA_VERSION:
        # Falla ruidosamente en vez de adivinar. Un plan medio interpretado es
        # peor que ningún plan: el corredor no puede notar la diferencia.
        raise ValueError(
            f"el plan guardado usa el esquema {version} y este código lee "
            f"el {SCHEMA_VERSION}; hay que regenerarlo"
        )
    return Plan(
        distance=RaceDistance(data["distance"]),
        level=Level(data["level"]),
        start_date=date.fromisoformat(data["start_date"]),
        race_date=date.fromisoformat(data["race_date"]) if data["race_date"] else None,
        weeks=tuple(_week_from_json(w) for w in data["weeks"]),
    )


def _week_to_json(week: Week) -> dict[str, Any]:
    return {
        "index": week.index,
        "phase": week.phase,
        "start_date": week.start_date.isoformat(),
        "sessions": [_session_to_json(s) for s in week.sessions],
        "load": {
            "index": week.load.index,
            "total_km": week.load.total_km,
            "long_run_km": week.load.long_run_km,
            "quality_sessions": week.load.quality_sessions,
            "is_deload": week.load.is_deload,
            "easy_km": week.load.easy_km,
            "is_taper": week.load.is_taper,
        },
    }


def _week_from_json(data: dict[str, Any]) -> Week:
    return Week(
        index=data["index"],
        phase=data["phase"],
        start_date=date.fromisoformat(data["start_date"]),
        sessions=tuple(_session_from_json(s) for s in data["sessions"]),
        load=WeekLoad(**data["load"]),
    )


def _session_to_json(session: Session) -> dict[str, Any]:
    return {
        "day_of_week": session.day_of_week,
        "kind": session.kind,
        "distance_km": session.distance_km,
        "zone": session.zone,
        "effort_description": session.effort_description,
        "notes": session.notes,
        "pace": (
            None
            if session.pace is None
            else [session.pace.min_sec_per_km, session.pace.max_sec_per_km]
        ),
        "technique_cue_id": session.technique_cue_id,
        "logistics_tip": session.logistics_tip,
    }


def _session_from_json(data: dict[str, Any]) -> Session:
    ritmo = data["pace"]
    return Session(
        day_of_week=data["day_of_week"],
        kind=data["kind"],
        distance_km=data["distance_km"],
        zone=data["zone"],
        effort_description=data["effort_description"],
        notes=data["notes"],
        pace=None if ritmo is None else PaceRange(ritmo[0], ritmo[1]),
        technique_cue_id=data["technique_cue_id"],
        logistics_tip=data["logistics_tip"],
    )
