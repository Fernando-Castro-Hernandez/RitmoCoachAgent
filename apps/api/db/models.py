"""Esquema de la base de datos.

Cuatro capas de memoria con dueños distintos (Fase 1). La separación es la
decisión importante, no las tablas:

    perfil                 el corredor lo escribe, por formulario o hablando
    estado de entrenamiento  **sólo el motor determinista escribe aquí**
    bitácora               sólo se anexa; nada se borra ni se corrige en sitio
    memoria conversacional  lo que se dijo, para que la siguiente sesión lo sepa

Que el LLM **lea** memoria pero no escriba el estado de entrenamiento es lo que
impide que una conversación persuasiva altere el plan. Para cambiar el plan hay
que pasar por el motor, y el motor no se deja convencer.

Sobre los tipos: se usan tipos portables (`JSON`, no `JSONB`) a propósito. En
producción esto corre sobre PostgreSQL 17, pero la suite corre sobre SQLite en
memoria — sin contenedor, sin esperas, milisegundos por prueba. El precio es
renunciar a los índices GIN sobre JSON, que a esta escala no hacen falta.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


def _ahora() -> datetime:
    """UTC siempre. La zona horaria del corredor se aplica al presentar, no al
    guardar: guardar en hora local hace imposible comparar dos usuarios."""
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class UserRow(Base):
    """Una cuenta. El dueño de todo lo demás.

    Antes la identidad era un UUID del navegador y el backend confiaba en él;
    ahora hay correo y contraseña. El cambio no es cosmético: significa que
    `user_id` deja de ser un dato que manda el cliente y pasa a salir de un
    token firmado. Ver `auth.py`.

    **La contraseña no está aquí.** Lo que se guarda es el hash de bcrypt, con
    su sal dentro. Nadie —ni con acceso a la base— puede leer la contraseña de
    nadie, que es lo mínimo cuando la misma contraseña se reutiliza en otros
    sitios.

    El correo se guarda normalizado a minúsculas y sin espacios: si no,
    `Fernando@x.com` y `fernando@x.com` acaban siendo dos cuentas distintas y la
    persona jura que su contraseña no funciona.
    """

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class AthleteProfileRow(Base):
    """El perfil. Lo escribe el corredor, en dos capas (tarea C4).

    Los campos duros los captura el carrusel de React; los blandos salen
    hablando, porque un formulario los aplana.
    """

    __tablename__ = "athlete_profile"

    # Referencia a la cuenta. El perfil no existe sin dueño.
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), primary_key=True)

    # ── capa dura · carrusel ─────────────────────────────────────────
    # Cómo quiere que le llamen. Anulable como el resto: nadie está obligado a
    # darlo, y un coach que dice «Fernando» a alguien que no dijo su nombre da
    # más miedo que confianza.
    name: Mapped[str | None] = mapped_column(String(64))
    level: Mapped[str] = mapped_column(String(16), default="principiante")
    goal_distance: Mapped[str | None] = mapped_column(String(8))
    race_date: Mapped[date | None] = mapped_column(Date)
    # Anulables a propósito: `None` significa «todavía no se lo hemos
    # preguntado», y 0 significa «se lo preguntamos y corre cero». La
    # clarificación autónoma (C3) depende de poder distinguirlos: un valor
    # por defecto haría que el coach creyera saber algo que nadie le dijo.
    days_per_week: Mapped[int | None] = mapped_column(Integer)
    age: Mapped[int | None] = mapped_column(Integer)
    weight_kg: Mapped[float | None] = mapped_column(Float)
    height_cm: Mapped[float | None] = mapped_column(Float)
    reference_distance_km: Mapped[float | None] = mapped_column(Float)
    reference_time_sec: Mapped[int | None] = mapped_column(Integer)
    timezone: Mapped[str] = mapped_column(String(64), default="America/Mexico_City")

    # ── capa blanda · voz ────────────────────────────────────────────
    weekly_volume_km: Mapped[float | None] = mapped_column(Float)
    longest_run_km: Mapped[float | None] = mapped_column(Float)
    base_cadence_spm: Mapped[int | None] = mapped_column(Integer)
    injuries: Mapped[list[str] | None] = mapped_column(JSON)
    practical_problems: Mapped[str | None] = mapped_column(Text)
    technique_experience: Mapped[str | None] = mapped_column(Text)
    motivation: Mapped[str | None] = mapped_column(Text)

    # Diagnóstico biomecánico de la tarea C6, para que el módulo de técnica
    # priorice qué señal enseñar en vez de rotar a ciegas.
    gait_findings: Mapped[list[dict[str, Any]] | None] = mapped_column(JSON)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora, onupdate=_ahora
    )


class TrainingStateRow(Base):
    """El plan vigente. **Sólo el motor escribe aquí.**

    El plan se guarda serializado y no normalizado en tablas de semanas y
    sesiones. Es una decisión consciente: el plan se lee entero o no se lee, se
    regenera completo en cada ajuste, y nunca se consulta «todas las sesiones de
    tempo de todos los usuarios». Normalizarlo sería trabajo sin consumidor.

    `plan_version` sube en cada regeneración, y con `reason` queda la traza de
    por qué el plan de hoy no es el de ayer.
    """

    __tablename__ = "training_state"

    user_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("athlete_profile.user_id"), primary_key=True
    )
    plan: Mapped[dict[str, Any]] = mapped_column(JSON)
    plan_version: Mapped[int] = mapped_column(Integer, default=1)
    current_week: Mapped[int] = mapped_column(Integer, default=1)
    reason: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_ahora, onupdate=_ahora
    )


class SessionLogRow(Base):
    """Un entrenamiento registrado. Sólo se anexa.

    `source` distingue de dónde vino el dato —voz, captura de pantalla, texto—
    porque la confianza no es la misma y quien audite el historial merece
    saberlo. `pace_sec_per_km` lo calcula siempre el motor, nunca quien reporta.
    """

    __tablename__ = "session_log"
    __table_args__ = (Index("ix_session_log_user_fecha", "user_id", "occurred_on"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), ForeignKey("users.id"), index=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    distance_km: Mapped[float] = mapped_column(Float)
    duration_sec: Mapped[int] = mapped_column(Integer)
    pace_sec_per_km: Mapped[int] = mapped_column(Integer)
    rpe: Mapped[int | None] = mapped_column(Integer)
    notes: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(16), default="voice")
    # La visión leyó un ritmo distinto del que calcula el motor (ADR 0014).
    # Gana el motor, pero la discrepancia queda registrada.
    discrepancy_flag: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class WellnessLogRow(Base):
    """Dolor, molestias y sueño. Alimenta la puerta de seguridad."""

    __tablename__ = "wellness_log"
    __table_args__ = (Index("ix_wellness_log_user_fecha", "user_id", "occurred_on"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    occurred_on: Mapped[date] = mapped_column(Date)
    pain_score: Mapped[int] = mapped_column(Integer)
    pain_area: Mapped[str] = mapped_column(String(64), default="")
    flags: Mapped[list[str]] = mapped_column(JSON, default=list)
    sleep_hours: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class CoachDecisionRow(Base):
    """Por qué el coach hizo lo que hizo.

    Cada decisión guarda la regla que la produjo y su justificación en texto.
    Sin esto, «el sistema ajustó tu plan» es indistinguible de «el sistema hizo
    algo raro», y un producto de salud que no puede explicarse no es defendible.
    """

    __tablename__ = "coach_decision"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    rule: Mapped[str] = mapped_column(String(16))
    rationale: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class ConversationMemoryRow(Base):
    """Lo que se dijo, para que la próxima sesión arranque sabiéndolo.

    Es la memoria **entre** conversaciones. La memoria *dentro* de una
    conversación vive en `ConversationContext` (tarea A4) y muere con la sesión.
    """

    __tablename__ = "conversation_memory"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    role: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class NudgeLogRow(Base):
    """Cada aviso proactivo que salió. Sólo se anexa (tarea E2).

    Es a la vez el registro de qué se le mandó al corredor y el candado que
    impide mandárselo dos veces. Sin él, un flujo de n8n que se reintenta —o dos
    instancias corriendo a la vez— repiten el mismo recordatorio.

    **`sent_on` es la fecha LOCAL del corredor**, y es la única fecha local que
    se guarda en todo el esquema. La cabecera de este archivo dice «UTC siempre»
    y la regla sigue en pie: aquí la clave de deduplicación *es* «una vez por
    mañana suya», y en UTC eso no se puede expresar — la mañana de un corredor
    en Ciudad de México y la de uno en Toronto caen en instantes distintos y a
    veces en días UTC distintos.
    """

    __tablename__ = "nudge_log"
    __table_args__ = (Index("ix_nudge_log_user_flow", "user_id", "flow", "sent_on"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    flow: Mapped[str] = mapped_column(String(32))
    sent_on: Mapped[date] = mapped_column(Date)
    text: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)


class TelegramLinkRow(Base):
    """Vinculación de la cuenta con un chat de Telegram (tarea E1)."""

    __tablename__ = "telegram_link"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(String(64), index=True)
    chat_id: Mapped[int | None] = mapped_column(Integer)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_ahora)
