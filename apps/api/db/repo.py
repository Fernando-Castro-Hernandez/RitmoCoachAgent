"""Repositorios.

Son la frontera entre la base de datos y el resto de la API, y llevan escritas
dos invariantes del producto:

1. **La bitácora sólo se anexa.** No hay `update` ni `delete` de un
   entrenamiento o de un reporte de dolor. Corregir la historia hace que la
   progresión deje de ser reconstruible, y la progresión es el producto.
2. **Sólo el motor escribe el estado de entrenamiento.** `StateRepo.apply`
   acepta un `Plan` del dominio, no un diccionario. Un plan sólo puede existir
   si `build_plan` lo produjo y lo validó, así que la API no tiene forma de
   escribir un plan inventado ni queriendo.

Los repositorios no hacen commit: eso lo decide quien maneja la transacción.
Una conversación de voz que registra una carrera y ajusta el plan tiene que
guardar las dos cosas o ninguna.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date, timedelta
from typing import Any

from coach_domain.paces import pace_from_run
from coach_domain.plans import Plan
from coach_domain.safety import AMBER_FROM, SafetyVerdict, assess
from coach_domain.types import AthleteProfile, Level
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.models import (
    AthleteProfileRow,
    CoachDecisionRow,
    ConversationMemoryRow,
    SessionLogRow,
    TrainingStateRow,
    WellnessLogRow,
)
from apps.api.db.serialize import plan_from_json, plan_to_json

# Cuánto puede diferir el ritmo que reporta una fuente externa del que calcula
# el motor antes de considerarlo una discrepancia digna de registrar.
PACE_DISCREPANCY_TOLERANCE_SEC = 3

_APPEND_ONLY = (
    "la bitácora sólo se anexa. Corregir la historia rompe la progresión, que "
    "se calcula a partir de ella. Si un registro está mal, se anexa el correcto "
    "y se explica en las notas."
)


class ProfileRepo:
    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get_row(self, user_id: str) -> AthleteProfileRow | None:
        return await self._s.get(AthleteProfileRow, user_id)

    async def get(self, user_id: str) -> AthleteProfile | None:
        """El perfil en la forma que entiende el motor.

        Devuelve `None` si no hay perfil, y también si el perfil existe pero le
        falta lo indispensable para planificar. Es lo que hace que la
        clarificación autónoma (tarea C3) tenga algo concreto que consultar.
        """
        fila = await self.get_row(user_id)
        if fila is None:
            return None

        # Sin volumen semanal ni días disponibles no hay perfil planificable, y
        # devolver uno con ceros por defecto sería mentirle al motor. `None`
        # aquí es la respuesta correcta, y es lo que hace que la clarificación
        # autónoma tenga algo concreto que detectar.
        if fila.weekly_volume_km is None or fila.days_per_week is None:
            return None

        # El perfil se llena en dos momentos distintos —carrusel y voz— así que
        # la base puede sostener a la vez «corro 20 km por semana» y «mi tirada
        # más larga son 30». `AthleteProfile` rechaza esa combinación, y con
        # razón. Aquí se recorta al valor coherente en vez de dejar que reviente:
        # el motor tiene que poder trabajar con lo que hay, y la contradicción es
        # justo lo que la conversación va a aclarar.
        larga = fila.longest_run_km or 0.0
        if fila.weekly_volume_km > 0:
            larga = min(larga, fila.weekly_volume_km)

        return AthleteProfile(
            user_id=fila.user_id,
            level=Level(fila.level),
            weekly_volume_km=fila.weekly_volume_km,
            longest_run_km=larga,
            days_per_week=fila.days_per_week,
            reference_distance_km=fila.reference_distance_km,
            reference_time_sec=fila.reference_time_sec,
            base_cadence_spm=fila.base_cadence_spm,
            injuries=tuple(fila.injuries or ()),
        )

    async def context(self, user_id: str) -> dict[str, Any] | None:
        """El perfil crudo, para saber **qué se le preguntó** y qué no.

        Distinto de `get()`: aquí los `None` importan y se conservan, porque son
        justamente la señal que busca la clarificación autónoma.
        """
        fila = await self.get_row(user_id)
        if fila is None:
            return None
        return {
            "name": fila.name,
            "weekly_volume_km": fila.weekly_volume_km,
            "longest_run_km": fila.longest_run_km,
            "days_per_week": fila.days_per_week,
            "injuries": fila.injuries,
            "reference_distance_km": fila.reference_distance_km,
            "reference_time_sec": fila.reference_time_sec,
            "goal_distance": fila.goal_distance,
            "race_date": fila.race_date,
            "level": fila.level,
            "base_cadence_spm": fila.base_cadence_spm,
        }

    async def save(self, user_id: str, **campos: Any) -> AthleteProfileRow:
        """Alta o actualización parcial. La usan el carrusel y la voz.

        Sólo escribe las columnas que le pasan: el carrusel manda los campos
        duros y la conversación va rellenando los blandos, sin pisarse.
        """
        fila = await self.get_row(user_id)
        if fila is None:
            fila = AthleteProfileRow(user_id=user_id)
            self._s.add(fila)
        for nombre, valor in campos.items():
            if not hasattr(fila, nombre):
                raise ValueError(f"«{nombre}» no es un campo del perfil")
            setattr(fila, nombre, valor)
        await self._s.flush()
        return fila


class StateRepo:
    """El estado de entrenamiento. Sólo el motor escribe aquí."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def get(self, user_id: str) -> Plan | None:
        fila = await self._s.get(TrainingStateRow, user_id)
        return plan_from_json(fila.plan) if fila else None

    async def get_row(self, user_id: str) -> TrainingStateRow | None:
        return await self._s.get(TrainingStateRow, user_id)

    async def apply(self, user_id: str, plan: Plan, reason: str) -> TrainingStateRow:
        """Guarda un plan nuevo.

        Recibe un `Plan`, no un diccionario. Es la parte que importa: un `Plan`
        sólo existe si `build_plan` lo construyó y lo validó contra R1–R8, así
        que por aquí no puede entrar un plan que el motor no haya aprobado.

        `reason` es obligatorio y no vacío. Un plan que cambió sin motivo
        registrado es un plan que nadie puede explicar después.
        """
        if not reason.strip():
            raise ValueError("todo cambio de plan tiene que decir por qué")

        fila = await self.get_row(user_id)
        if fila is None:
            fila = TrainingStateRow(user_id=user_id, plan=plan_to_json(plan), reason=reason)
            self._s.add(fila)
        else:
            fila.plan = plan_to_json(plan)
            fila.plan_version += 1
            fila.current_week = 1
            fila.reason = reason
        await self._s.flush()
        return fila

    async def advance_week(self, user_id: str) -> int:
        fila = await self.get_row(user_id)
        if fila is None:
            raise ValueError("no hay plan que avanzar")
        fila.current_week += 1
        await self._s.flush()
        return fila.current_week


class LogRepo:
    """La bitácora. Sólo se anexa."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    # ── escritura ────────────────────────────────────────────────────

    async def add_session(
        self,
        user_id: str,
        *,
        occurred_on: date,
        distance_km: float,
        duration_sec: int,
        rpe: int | None = None,
        notes: str = "",
        source: str = "voice",
        reported_pace_sec_per_km: int | None = None,
    ) -> SessionLogRow:
        """Registra un entrenamiento.

        El ritmo **lo calcula el motor**, siempre, aunque quien reporta traiga
        uno. Si el reportado difiere en más de 3 s/km —típicamente porque un
        modelo de visión lo leyó mal de una captura— gana el motor y la
        discrepancia queda marcada (ADR 0014).
        """
        ritmo = pace_from_run(distance_km, duration_sec)
        discrepancia = (
            reported_pace_sec_per_km is not None
            and abs(reported_pace_sec_per_km - ritmo) > PACE_DISCREPANCY_TOLERANCE_SEC
        )
        fila = SessionLogRow(
            user_id=user_id,
            occurred_on=occurred_on,
            distance_km=distance_km,
            duration_sec=duration_sec,
            pace_sec_per_km=ritmo,
            rpe=rpe,
            notes=notes,
            source=source,
            discrepancy_flag=discrepancia,
        )
        self._s.add(fila)
        await self._s.flush()
        return fila

    async def add_wellness(
        self,
        user_id: str,
        *,
        occurred_on: date,
        pain_score: int,
        pain_area: str = "",
        flags: Sequence[str] = (),
        sleep_hours: float | None = None,
    ) -> WellnessLogRow:
        # Se evalúa antes de guardar: una bandera con el nombre mal escrito
        # tiene que fallar aquí y no silenciosamente al leerla más tarde.
        assess(pain_score, flags=flags)
        fila = WellnessLogRow(
            user_id=user_id,
            occurred_on=occurred_on,
            pain_score=pain_score,
            pain_area=pain_area,
            flags=list(flags),
            sleep_hours=sleep_hours,
        )
        self._s.add(fila)
        await self._s.flush()
        return fila

    async def add_decision(self, user_id: str, *, rule: str, rationale: str) -> CoachDecisionRow:
        if not rationale.strip():
            raise ValueError("una decisión sin justificación no es auditable")
        fila = CoachDecisionRow(user_id=user_id, rule=rule, rationale=rationale)
        self._s.add(fila)
        await self._s.flush()
        return fila

    async def delete(self, user_id: str) -> None:
        raise NotImplementedError(_APPEND_ONLY)

    async def update_session(self, session_id: int, **campos: Any) -> None:
        raise NotImplementedError(_APPEND_ONLY)

    # ── lectura ──────────────────────────────────────────────────────

    async def sessions(self, user_id: str, limit: int = 20) -> list[SessionLogRow]:
        filas = await self._s.execute(
            select(SessionLogRow)
            .where(SessionLogRow.user_id == user_id)
            .order_by(desc(SessionLogRow.occurred_on), desc(SessionLogRow.id))
            .limit(limit)
        )
        return list(filas.scalars())

    async def decisions(self, user_id: str, limit: int = 20) -> list[CoachDecisionRow]:
        filas = await self._s.execute(
            select(CoachDecisionRow)
            .where(CoachDecisionRow.user_id == user_id)
            .order_by(CoachDecisionRow.id)
            .limit(limit)
        )
        return list(filas.scalars())

    async def recent_volumes(self, user_id: str, today: date, weeks: int = 4) -> list[float]:
        """Kilómetros por semana, de la más antigua a la más reciente.

        Es lo que alimenta R1: sin saber de dónde viene el corredor no se puede
        decidir a dónde puede subir.
        """
        desde = today - timedelta(weeks=weeks)
        filas = await self._s.execute(
            select(SessionLogRow).where(
                SessionLogRow.user_id == user_id,
                SessionLogRow.occurred_on > desde,
            )
        )
        acumulado = [0.0] * weeks
        for fila in filas.scalars():
            # Los cubos se cuentan hacia atrás desde hoy, no hacia adelante
            # desde el corte: el último cubo tiene que ser la semana en curso,
            # que es la que R1 usa como base.
            indice = weeks - 1 - (today - fila.occurred_on).days // 7
            if 0 <= indice < weeks:
                acumulado[indice] += fila.distance_km
        return [round(v, 1) for v in acumulado]

    async def days_since_last_run(self, user_id: str, today: date) -> int | None:
        """Para R6. `None` si nunca corrió: eso no es una pausa, es un inicio."""
        fila = await self._s.execute(
            select(SessionLogRow.occurred_on)
            .where(SessionLogRow.user_id == user_id)
            .order_by(desc(SessionLogRow.occurred_on))
            .limit(1)
        )
        ultima = fila.scalar_one_or_none()
        return None if ultima is None else (today - ultima).days

    async def current_safety(self, user_id: str, today: date) -> SafetyVerdict:
        """El veredicto vigente, calculado a partir de la bitácora.

        La persistencia no se pregunta, se **cuenta**: se recorren hacia atrás
        los reportes con dolor de 3 o más y en días consecutivos. Preguntarle al
        corredor «¿cuántos días llevas así?» produce una respuesta optimista;
        contar los reportes produce el número real, y esa diferencia es
        justamente la que escala un ámbar a rojo.
        """
        filas = await self._s.execute(
            select(WellnessLogRow)
            .where(WellnessLogRow.user_id == user_id)
            .order_by(desc(WellnessLogRow.occurred_on), desc(WellnessLogRow.id))
            .limit(30)
        )
        reportes = list(filas.scalars())
        if not reportes:
            return assess(0)

        ultimo = reportes[0]
        # Sólo cuenta si el reporte es de hoy o de ayer; uno de hace dos
        # semanas no describe el estado actual.
        if (today - ultimo.occurred_on).days > 1:
            return assess(0)

        dias = 0
        esperado = ultimo.occurred_on
        vistos: set[date] = set()
        for reporte in reportes:
            if reporte.occurred_on in vistos:
                continue
            if reporte.occurred_on != esperado or reporte.pain_score < AMBER_FROM:
                break
            vistos.add(reporte.occurred_on)
            dias += 1
            esperado = esperado - timedelta(days=1)

        return assess(
            ultimo.pain_score,
            flags=list(ultimo.flags or ()),
            days_persisting=dias,
        )


class MemoryRepo:
    """Memoria entre conversaciones."""

    def __init__(self, session: AsyncSession) -> None:
        self._s = session

    async def remember(self, user_id: str, role: str, text: str) -> None:
        if not text.strip():
            return
        self._s.add(ConversationMemoryRow(user_id=user_id, role=role, text=text.strip()))
        await self._s.flush()

    async def recent(self, user_id: str, limit: int = 20) -> list[ConversationMemoryRow]:
        """Los últimos turnos, en orden cronológico."""
        filas = await self._s.execute(
            select(ConversationMemoryRow)
            .where(ConversationMemoryRow.user_id == user_id)
            .order_by(desc(ConversationMemoryRow.id))
            .limit(limit)
        )
        return list(reversed(list(filas.scalars())))
