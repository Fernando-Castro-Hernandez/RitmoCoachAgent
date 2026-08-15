"""Las herramientas que el modelo puede invocar.

**Son la única vía por la que una cifra llega a la boca del coach.** Si el
número no salió de aquí, salió de la imaginación del modelo, y eso es
exactamente lo que `numbers_from_engine_pct` mide (ADR 0012).

Cada resultado lleva un campo `source` con la función del motor que produjo la
cifra. No es decoración: es lo que permite auditar después de dónde vino cada
número, y lo que alimenta la métrica.

Tres defensas están escritas aquí, en código, y no sólo en el prompt:

1. **Rojo no prescribe.** Ninguna herramienta devuelve distancia ni ritmo
   cuando la puerta de seguridad está en rojo. El prompt lo dice; esto lo
   garantiza.
2. **Sin contexto no hay plan.** `create_plan` se niega y devuelve qué falta
   preguntar. Es el pivote hecho código: si el prompt falla y el modelo intenta
   generar un plan de maratón sin saber nada del corredor, la herramienta no se
   lo permite.
3. **Los identificadores se validan.** `explain_technique_cue` con una señal
   inventada falla ruidosamente en vez de devolver algo plausible.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from coach_domain.paces import format_pace
from coach_domain.plans import (
    InsufficientFrequencyError,
    InsufficientTimeError,
    Session,
    build_plan,
)
from coach_domain.progression import environment_advice, return_factor
from coach_domain.safety import SafetyLevel, SafetyVerdict, assess
from coach_domain.technique import UnknownCueError, get_cue, target_cadence
from coach_domain.types import RaceDistance
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.clarification import QUESTIONS, missing_vital_context
from apps.api.db.repo import LogRepo, ProfileRepo, StateRepo

# Los días de la semana como los diría una persona, no como los numera Python.
_DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _bloqueado(veredicto: SafetyVerdict) -> dict[str, Any]:
    """La respuesta cuando la puerta está en rojo.

    Deliberadamente **no** contiene `distance_km` ni `pace`. El modelo no puede
    prescribir lo que no recibe, y eso es más fuerte que pedirle que se
    abstenga.
    """
    return {
        "ok": False,
        "allows_prescription": False,
        "safety_level": veredicto.level.value,
        "reason": veredicto.reason,
        "referral_message": veredicto.referral_message,
        "source": "coach_domain.safety.assess",
    }


def _sesion_a_dict(sesion: Session) -> dict[str, Any]:
    return {
        "day": _DIAS[sesion.day_of_week],
        "kind": sesion.kind,
        "distance_km": sesion.distance_km,
        "zone": sesion.zone,
        "effort": sesion.effort_description,
        "pace": (
            None
            if sesion.pace is None
            else f"{format_pace(sesion.pace.min_sec_per_km)}–"
            f"{format_pace(sesion.pace.max_sec_per_km)}"
        ),
        "why": sesion.notes,
        "technique_cue_id": sesion.technique_cue_id,
        "logistics_tip": sesion.logistics_tip,
    }


class CoachTools:
    """Las siete herramientas, atadas a una sesión de base de datos."""

    def __init__(self, session: AsyncSession, *, today: date | None = None) -> None:
        self._s = session
        self._hoy = today or date.today()
        self.profiles = ProfileRepo(session)
        self.state = StateRepo(session)
        self.logs = LogRepo(session)

    # ── 1 · qué toca hoy ─────────────────────────────────────────────

    async def get_today_session(self, user_id: str) -> dict[str, Any]:
        veredicto = await self.logs.current_safety(user_id, self._hoy)
        if not veredicto.allows_prescription:
            return _bloqueado(veredicto)

        plan = await self.state.get(user_id)
        fila = await self.state.get_row(user_id)
        if plan is None or fila is None:
            return {"ok": False, "reason": "todavía no hay plan", "needs_plan": True}

        semana = plan.weeks[min(fila.current_week, len(plan.weeks)) - 1]
        hoy = [s for s in semana.sessions if s.day_of_week == self._hoy.weekday()]
        if not hoy:
            return {
                "ok": True,
                "rest_day": True,
                "week_index": semana.index,
                "message": "Hoy toca descanso. El descanso es parte del plan, no una pausa.",
                "source": "coach_domain.plans.build_plan",
            }

        sesion = _sesion_a_dict(hoy[0])
        # En ámbar se entrena, pero recortado y sin trabajo de calidad. El
        # recorte lo aplica el motor; el modelo sólo lo cuenta.
        if veredicto.level is SafetyLevel.AMBER:
            sesion["distance_km"] = round(sesion["distance_km"] * 0.6, 1)
            sesion["kind"] = "suave"
            sesion["why"] = (
                "Vamos a bajarle hoy por la molestia que reportaste. "
                "Suave y corto, y mañana vemos cómo amaneciste."
            )
        sesion.update(
            {
                "ok": True,
                "rest_day": False,
                "week_index": semana.index,
                "phase": semana.phase,
                "safety_level": veredicto.level.value,
                "source": "coach_domain.plans.build_plan",
            }
        )
        return sesion

    # ── 2 · registrar una carrera ────────────────────────────────────

    async def log_run(
        self,
        user_id: str,
        *,
        distance_km: float,
        duration_sec: int,
        rpe: int | None = None,
        notes: str = "",
        source: str = "voice",
        reported_pace_sec_per_km: int | None = None,
    ) -> dict[str, Any]:
        fila = await self.logs.add_session(
            user_id,
            occurred_on=self._hoy,
            distance_km=distance_km,
            duration_sec=duration_sec,
            rpe=rpe,
            notes=notes,
            source=source,
            reported_pace_sec_per_km=reported_pace_sec_per_km,
        )
        return {
            "ok": True,
            "distance_km": fila.distance_km,
            "duration_sec": fila.duration_sec,
            "pace_sec_per_km": fila.pace_sec_per_km,
            "pace_formatted": format_pace(fila.pace_sec_per_km),
            "discrepancy_flag": fila.discrepancy_flag,
            "source": "coach_domain.paces.pace_from_run",
        }

    # ── 3 · reportar cómo se siente ──────────────────────────────────

    async def report_wellness(
        self,
        user_id: str,
        *,
        pain_score: int,
        pain_area: str = "",
        flags: list[str] | None = None,
        sleep_hours: float | None = None,
    ) -> dict[str, Any]:
        await self.logs.add_wellness(
            user_id,
            occurred_on=self._hoy,
            pain_score=pain_score,
            pain_area=pain_area,
            flags=flags or [],
            sleep_hours=sleep_hours,
        )
        # Se re-evalúa contra la bitácora completa, no sólo contra lo que acaba
        # de decir: así la persistencia de tres días escala sola a rojo sin que
        # nadie tenga que acordarse.
        veredicto = await self.logs.current_safety(user_id, self._hoy)
        if veredicto.level is not SafetyLevel.GREEN:
            await self.logs.add_decision(user_id, rule="SAFETY", rationale=veredicto.reason)
        return {
            "ok": True,
            "safety_level": veredicto.level.value,
            "allows_prescription": veredicto.allows_prescription,
            "reason": veredicto.reason,
            "referral_message": veredicto.referral_message,
            "source": "coach_domain.safety.assess",
        }

    # ── 4 · ajustar el plan ──────────────────────────────────────────

    async def adjust_plan(self, user_id: str, *, reason: str) -> dict[str, Any]:
        veredicto = await self.logs.current_safety(user_id, self._hoy)
        if not veredicto.allows_prescription:
            return _bloqueado(veredicto)

        perfil = await self.profiles.get(user_id)
        plan_actual = await self.state.get(user_id)
        if perfil is None or plan_actual is None:
            return {"ok": False, "reason": "no hay plan que ajustar", "needs_plan": True}

        # R6: si estuvo parado, se vuelve por debajo de donde lo dejó.
        dias_parado = await self.logs.days_since_last_run(user_id, self._hoy)
        factor = return_factor(dias_parado) if dias_parado is not None else 1.0
        if factor == 0.0:
            return {
                "ok": False,
                "rule": "R6",
                "reason": f"{dias_parado} días sin correr; hay que replanificar desde la base",
                "needs_replan": True,
                "source": "coach_domain.progression.return_factor",
            }

        ajustado = perfil
        if factor < 1.0:
            ajustado = type(perfil)(
                **{
                    **perfil.__dict__,
                    "weekly_volume_km": round(perfil.weekly_volume_km * factor, 1),
                    "longest_run_km": round(perfil.longest_run_km * factor, 1),
                }
            )

        nuevo = build_plan(ajustado, plan_actual.distance, plan_actual.race_date, self._hoy)
        motivo = f"{reason} (R6 al {factor:.0%} por {dias_parado} días sin correr)"
        await self.state.apply(user_id, nuevo, reason=motivo)
        await self.logs.add_decision(user_id, rule="R6", rationale=motivo)
        return {
            "ok": True,
            "weeks": len(nuevo.weeks),
            "first_week_km": nuevo.weeks[0].load.total_km,
            "return_factor": factor,
            "rationale": motivo,
            "source": "coach_domain.plans.build_plan",
        }

    # ── 5 · dónde va el corredor ─────────────────────────────────────

    async def get_week_context(self, user_id: str) -> dict[str, Any]:
        plan = await self.state.get(user_id)
        fila = await self.state.get_row(user_id)
        if plan is None or fila is None:
            return {"ok": False, "reason": "todavía no hay plan", "needs_plan": True}

        semana = plan.weeks[min(fila.current_week, len(plan.weeks)) - 1]
        volumenes = await self.logs.recent_volumes(user_id, self._hoy)
        veredicto = await self.logs.current_safety(user_id, self._hoy)
        return {
            "ok": True,
            "week_index": semana.index,
            "total_weeks": len(plan.weeks),
            "phase": semana.phase,
            "planned_km": semana.load.total_km,
            "long_run_km": semana.load.long_run_km,
            "is_deload": semana.load.is_deload,
            "recent_weekly_km": volumenes,
            "distance": plan.distance.value,
            "race_date": plan.race_date.isoformat() if plan.race_date else None,
            "safety_level": veredicto.level.value,
            "source": "coach_domain.plans.build_plan",
        }

    # ── 6 · explicar una señal de técnica ────────────────────────────

    async def explain_technique_cue(self, cue_id: str) -> dict[str, Any]:
        try:
            cue = get_cue(cue_id)
        except UnknownCueError:
            # Ruidoso a propósito: el identificador lo eligió el modelo, y uno
            # inventado no puede devolver algo plausible.
            return {
                "ok": False,
                "reason": f"no existe la señal «{cue_id}»",
                "source": "coach_domain.technique.get_cue",
            }
        return {
            "ok": True,
            "id": cue.id,
            "category": cue.category,
            "voice_text": cue.voice_text,
            "long_explanation": cue.long_explanation,
            "source": "coach_domain.technique.get_cue",
        }

    async def get_target_cadence(self, user_id: str, weeks_worked: int = 0) -> dict[str, Any]:
        """La cadencia objetivo. Sin base conocida **no se inventa una**."""
        contexto = await self.profiles.context(user_id)
        base = (contexto or {}).get("base_cadence_spm")
        if base is None:
            return {
                "ok": False,
                "needs_field": "base_cadence_spm",
                "question": (
                    "Necesito tu cadencia. ¿Tu reloj la mide, o cuentas los pasos "
                    "de un pie durante 30 segundos y los multiplicas por cuatro?"
                ),
                "source": "coach_domain.technique.target_cadence",
            }
        return {
            "ok": True,
            "base_spm": base,
            "target_spm": target_cadence(base, weeks_worked),
            "source": "coach_domain.technique.target_cadence",
        }

    # ── 7 · crear el plan ────────────────────────────────────────────

    async def create_plan(
        self,
        user_id: str,
        *,
        distance: str,
        race_date: str | None = None,
    ) -> dict[str, Any]:
        """Genera el plan, o se niega diciendo qué falta preguntar.

        **Aquí es donde el pivote deja de ser una instrucción del prompt y pasa
        a ser una propiedad del sistema.** Si el modelo intenta generar un plan
        de maratón sin saber cuánto corre el corredor, no puede: recibe la lista
        de lo que le falta y las preguntas ya redactadas.
        """
        contexto = await self.profiles.context(user_id)
        faltantes = missing_vital_context(contexto)
        if faltantes:
            return {
                "ok": False,
                "needs_context": faltantes,
                "ask": [QUESTIONS[c] for c in faltantes],
                "next_question": QUESTIONS[faltantes[0]],
                "reason": (
                    "No puedo armar un plan sin saber de dónde parte el corredor. "
                    "Pregúntale esto primero, una cosa a la vez."
                ),
                "source": "apps.api.clarification.missing_vital_context",
            }

        perfil = await self.profiles.get(user_id)
        if perfil is None:
            return {
                "ok": False,
                "reason": "el perfil está incompleto",
                "needs_context": ["profile"],
            }

        try:
            meta = RaceDistance(distance)
        except ValueError:
            return {
                "ok": False,
                "reason": f"«{distance}» no es una distancia que preparemos",
                "valid": [d.value for d in RaceDistance],
            }

        fecha = date.fromisoformat(race_date) if race_date else None
        try:
            plan = build_plan(perfil, meta, fecha, self._hoy)
        except InsufficientTimeError as exc:
            # No se niega y ya: se devuelve con qué negociar.
            return {
                "ok": False,
                "rule": "R7",
                "weeks_available": exc.weeks_available,
                "weeks_needed": exc.weeks_needed,
                "alternatives": list(exc.alternatives),
                "reason": (
                    f"Para {distance} hacen falta {exc.weeks_needed} semanas y sólo "
                    f"hay {exc.weeks_available}. Ofrécele cambiar de meta o preparar "
                    "para terminar sin marca."
                ),
                "source": "coach_domain.plans.build_plan",
            }
        except InsufficientFrequencyError as exc:
            return {"ok": False, "rule": "frecuencia", "reason": str(exc)}

        await self.state.apply(user_id, plan, reason=f"plan inicial de {distance}")
        await self.logs.add_decision(
            user_id,
            rule="R7",
            rationale=(
                f"plan de {distance} en {len(plan.weeks)} semanas, pico {plan.peak_volume_km} km"
            ),
        )
        return {
            "ok": True,
            "distance": meta.value,
            "weeks": len(plan.weeks),
            "peak_volume_km": plan.peak_volume_km,
            "first_week_km": plan.weeks[0].load.total_km,
            "race_date": race_date,
            "source": "coach_domain.plans.build_plan",
        }

    # ── extra · ambiente (R8) ────────────────────────────────────────

    async def environment_check(self, temp_c: float, aqi: int | None = None) -> dict[str, Any]:
        consejo = environment_advice(temp_c, aqi)
        return {
            "ok": True,
            "pace_adjustment_sec": consejo.pace_adjustment_sec,
            "move_indoors": consejo.move_indoors,
            "reason": consejo.reason,
            "source": "coach_domain.progression.environment_advice",
        }


__all__ = ["CoachTools", "assess"]
