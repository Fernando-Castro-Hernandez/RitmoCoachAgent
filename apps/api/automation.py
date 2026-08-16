"""Los avisos proactivos: quién toca ahora, y qué se le dice.

## La decisión que estructura todo esto

Un nodo de horario de n8n tiene **una** zona horaria. El producto tiene una por
corredor. Programar «todos los días a las 6:00» en n8n significa elegir la
mañana de alguien y mandarle esa hora a todos los demás — que es exactamente el
punto ciego 7 de la Fase 1.

Así que la responsabilidad se parte por donde debe:

    n8n         corre cada hora en punto, en UTC, y pregunta
    la API      responde quién tiene las 6:00 **en su hora** ahora mismo

La zona horaria vive en el dato, no en el programador de tareas. Añadir un
corredor en Tokio no toca ningún flujo. Y como la decisión quedó en Python, se
puede probar: hay un caso con un corredor en Ciudad de México y otro en Toronto
que verifica que cada uno sale a las 6:00 suyas y en instantes UTC distintos.

## Qué se dice, y quién lo decide

El texto se compone **aquí**, con las cifras que ya calculó el motor —la
distancia de la sesión de hoy, el ritmo objetivo, los kilómetros de la semana—.
No hay un modelo redactando el recordatorio. Es la misma regla de todo el
producto: si es un número, viene del motor.

## En rojo sólo habla una

Cuatro de los cinco flujos son de entrenamiento, y cuando la puerta de seguridad
está en rojo **no salen**. El quinto —el escalamiento— es el único que habla en
rojo, y no prescribe: dice que pares y con quién ir.

Ojo con de quién es el escalamiento: no lo decide este módulo. `assess()` del
dominio ya convierte una molestia de 3 o más que lleva tres días en rojo. Aquí
sólo se detecta que el veredicto **es** rojo y se entrega el mensaje que el
propio dominio redactó (`referral_message`). El motor decide; el flujo reparte.

## El aviso perdido: dos políticas, a propósito

Los cuatro flujos rutinarios se marcan como enviados en el momento de
entregarlos. Si Telegram falla, ese recordatorio se pierde y no se reintenta.

El escalamiento **no**: se marca sólo cuando n8n confirma la entrega
(`POST /api/automation/ack`). Si falla, vuelve a salir a la hora siguiente.

La asimetría es deliberada: un «buenos días» perdido no le cuesta nada a nadie;
un «para de entrenar y que te vea alguien» perdido, sí.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import structlog
from coach_domain.paces import format_pace
from coach_domain.plans import Plan, Session
from coach_domain.safety import SafetyLevel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.models import AthleteProfileRow, NudgeLogRow, SessionLogRow, TelegramLinkRow
from apps.api.db.repo import LogRepo, StateRepo

log = structlog.get_logger(__name__)

# Zona de reserva cuando el perfil trae una que el sistema no conoce. No se
# omite al corredor por un dato malo: se le manda a una hora razonable y queda
# el aviso en el log.
FALLBACK_TZ = "America/Mexico_City"

# Las horas locales de cada flujo. Están aquí arriba y con nombre para que se
# puedan discutir sin leer una función.
MORNING_HOUR = 6
CHECKIN_HOUR = 20
STREAK_HOUR = 18
WEEKLY_HOUR = 19
WEEKLY_WEEKDAY = 6  # domingo

# Días sin correr a partir de los cuales el aviso de racha tiene sentido. Menos
# es ruido: dos días sin correr es un plan de cuatro días por semana.
STREAK_DAYS = 3

FLOWS = ("morning", "checkin", "streak", "weekly", "escalation")


@dataclass(frozen=True)
class Nudge:
    """Un aviso listo para entregar.

    Lleva el `chat_id` resuelto para que n8n no tenga que preguntar dos veces, y
    la hora local para que el flujo sea legible cuando alguien lo audite.
    """

    user_id: str
    chat_id: int
    flow: str
    timezone: str
    local_time: str
    local_date: date
    text: str

    def as_dict(self) -> dict[str, object]:
        return {
            "user_id": self.user_id,
            "chat_id": self.chat_id,
            "flow": self.flow,
            "timezone": self.timezone,
            "local_time": self.local_time,
            "local_date": self.local_date.isoformat(),
            "text": self.text,
        }


# ── el reloj ─────────────────────────────────────────────────────────


def local_now(tz: str, ahora: datetime) -> datetime:
    """El mismo instante, visto desde donde vive el corredor.

    Una zona desconocida no lo deja fuera: cae en `FALLBACK_TZ`. Que el
    recordatorio llegue a una hora rara es un defecto; que no llegue nunca por
    un `timezone` mal escrito hace tres meses es un agujero silencioso.
    """
    try:
        zona = ZoneInfo(tz or FALLBACK_TZ)
    except (ZoneInfoNotFoundError, ValueError):
        log.warning("automation.zona_desconocida", tz=tz)
        zona = ZoneInfo(FALLBACK_TZ)
    return ahora.astimezone(zona)


def is_local_hour(tz: str, ahora: datetime, hora: int) -> bool:
    """Si en la hora local del corredor ya son las `hora` en punto.

    Compara la hora, no el minuto: el flujo corre una vez por hora y llega
    cuando llega. Comparar minutos haría que un arranque con dos minutos de
    retraso se saltara el día entero.
    """
    return local_now(tz, ahora).hour == hora


def is_local_weekday_hour(tz: str, ahora: datetime, dia: int, hora: int) -> bool:
    local = local_now(tz, ahora)
    return local.weekday() == dia and local.hour == hora


# ── la sesión de hoy ─────────────────────────────────────────────────


def session_on(plan: Plan, dia: date) -> Session | None:
    """La sesión que el plan pone ese día, si pone alguna.

    Se busca la semana **por fecha**, no por `current_week`. El contador de
    semana avanza cuando alguien lo avanza; el calendario avanza solo. Si los
    dos se separan —porque el corredor no abrió la aplicación en diez días— el
    recordatorio tiene que hablar del día de hoy, no de donde se quedó el
    contador.
    """
    for semana in plan.weeks:
        if semana.start_date <= dia < semana.start_date + timedelta(days=7):
            for s in semana.sessions:
                if s.day_of_week == dia.weekday():
                    return s
            return None
    return None


def _describe(s: Session) -> str:
    """La sesión en una línea. Todas las cifras salen del plan."""
    trozos = [f"{s.distance_km:g} km"]
    if s.pace is not None:
        trozos.append(
            f"a {format_pace(s.pace.min_sec_per_km)}–{format_pace(s.pace.max_sec_per_km)}/km"
        )
    return " ".join(trozos)


# ── los textos ───────────────────────────────────────────────────────


def morning_text(s: Session) -> str:
    cuerpo = f"Hoy toca {s.kind}: {_describe(s)}."
    if s.notes:
        cuerpo += f"\n{s.notes}"
    if s.logistics_tip:
        cuerpo += f"\n{s.logistics_tip}"
    return f"Buenos días.\n\n{cuerpo}\n\n¿Nos hablamos cuando termines?"


def checkin_text(s: Session) -> str:
    return (
        f"¿Cómo te fue con los {s.distance_km:g} km de hoy?\n\n"
        "Cuéntamelo hablando o mándame la captura del reloj. "
        "Y si algo te molestó, dímelo — eso es lo que más me sirve."
    )


def streak_text(dias: int, s: Session | None) -> str:
    inicio = (
        f"Llevas {dias} días sin correr. No pasa nada — pasa siempre — "
        "pero cuanto antes vuelvas, menos cuesta."
    )
    if s is None:
        return f"{inicio}\n\n¿Retomamos? Dime cuándo puedes y reacomodo la semana."
    return f"{inicio}\n\nHoy tocaba {s.kind}: {_describe(s)}. ¿Le entras?"


def weekly_text(km: float, sesiones: int, semana_previa: float) -> str:
    """El resumen mira hacia atrás, nunca hacia adelante.

    Reporta lo que pasó, con los números de la bitácora. No prescribe, y por eso
    es el único flujo de entrenamiento que puede salir con la puerta en ámbar
    sin pisar la regla de que en rojo la pantalla no prescribe.
    """
    if sesiones == 0:
        return (
            "Semana sin carreras registradas.\n\n"
            "Si corriste y no lo apuntamos, mándame las capturas y lo cuadramos."
        )
    linea = f"Esta semana: {sesiones} sesiones, {km:g} km."
    if semana_previa > 0:
        delta = km - semana_previa
        signo = "+" if delta >= 0 else ""
        linea += f" La anterior fueron {semana_previa:g} km ({signo}{delta:.1f})."
    return f"{linea}\n\nBuen trabajo. ¿Hablamos de la que viene?"


# ── a quién le toca ──────────────────────────────────────────────────


@dataclass(frozen=True)
class _Candidato:
    user_id: str
    chat_id: int
    tz: str


async def _candidatos(sesion: AsyncSession) -> list[_Candidato]:
    """Los corredores que pueden recibir un aviso: los que vincularon Telegram.

    Sin `chat_id` no hay a dónde escribir, así que el resto no entra ni al
    cálculo. Es también lo que mantiene barato el barrido horario.
    """
    consulta = (
        select(
            AthleteProfileRow.user_id,
            AthleteProfileRow.timezone,
            TelegramLinkRow.chat_id,
            TelegramLinkRow.used_at,
        )
        .join(TelegramLinkRow, TelegramLinkRow.user_id == AthleteProfileRow.user_id)
        .where(TelegramLinkRow.used_at.is_not(None))
        .order_by(TelegramLinkRow.used_at.desc())
    )
    filas = (await sesion.execute(consulta)).all()

    # Un corredor puede haber vinculado varias veces (cambió de teléfono). Gana
    # el último, que es el orden en que viene la consulta.
    vistos: dict[str, _Candidato] = {}
    for user_id, tz, chat_id, _ in filas:
        if chat_id is not None and user_id not in vistos:
            vistos[user_id] = _Candidato(user_id, int(chat_id), tz or FALLBACK_TZ)
    return list(vistos.values())


async def _ya_enviado(sesion: AsyncSession, user_id: str, flow: str, dia: date) -> bool:
    consulta = select(NudgeLogRow.id).where(
        NudgeLogRow.user_id == user_id,
        NudgeLogRow.flow == flow,
        NudgeLogRow.sent_on == dia,
    )
    return (await sesion.execute(consulta)).scalars().first() is not None


async def mark_sent(sesion: AsyncSession, aviso: Nudge) -> None:
    """Anota el aviso. No hace commit: lo decide quien maneja la transacción."""
    sesion.add(
        NudgeLogRow(
            user_id=aviso.user_id,
            flow=aviso.flow,
            sent_on=aviso.local_date,
            text=aviso.text,
        )
    )
    await sesion.flush()


async def _corrio_hoy(sesion: AsyncSession, user_id: str, dia: date) -> bool:
    consulta = select(SessionLogRow.id).where(
        SessionLogRow.user_id == user_id,
        SessionLogRow.occurred_on == dia,
    )
    return (await sesion.execute(consulta)).scalars().first() is not None


async def due(sesion: AsyncSession, flow: str, ahora: datetime) -> list[Nudge]:
    """Los avisos de este flujo que toca entregar en este instante.

    No escribe nada: quien decide marcarlos como enviados es el endpoint, y lo
    hace distinto según el flujo (ver la cabecera del módulo).
    """
    if flow not in FLOWS:
        raise ValueError(f"flujo desconocido: {flow}")

    avisos: list[Nudge] = []
    for c in await _candidatos(sesion):
        local = local_now(c.tz, ahora)
        hoy = local.date()

        if await _ya_enviado(sesion, c.user_id, flow, hoy):
            continue

        veredicto = await LogRepo(sesion).current_safety(c.user_id, hoy)
        texto = await _componer(sesion, c, flow, local, veredicto.level, veredicto.referral_message)
        if texto is None:
            continue

        avisos.append(
            Nudge(
                user_id=c.user_id,
                chat_id=c.chat_id,
                flow=flow,
                timezone=c.tz,
                local_time=local.strftime("%Y-%m-%d %H:%M"),
                local_date=hoy,
                text=texto,
            )
        )
    return avisos


async def _componer(
    sesion: AsyncSession,
    c: _Candidato,
    flow: str,
    local: datetime,
    nivel: SafetyLevel,
    referral: str | None,
) -> str | None:
    """El texto del aviso, o `None` si a este corredor no le toca ahora."""
    hoy = local.date()
    en_rojo = nivel is SafetyLevel.RED

    if flow == "escalation":
        # El único que habla en rojo, y sólo en rojo. El mensaje lo redactó el
        # dominio, no este módulo: es el mismo que oiría hablando.
        if not en_rojo:
            return None
        return referral or "Para de entrenar y que te vea un profesional antes de seguir."

    # Los cuatro de entrenamiento callan en rojo. El corredor no se queda sin
    # saber nada: el escalamiento sale por su cuenta.
    if en_rojo:
        return None

    if flow == "weekly":
        # `local` ya viene convertida: aquí se compara la hora del corredor.
        if local.weekday() != WEEKLY_WEEKDAY or local.hour != WEEKLY_HOUR:
            return None
        registro = LogRepo(sesion)
        volumenes = await registro.recent_volumes(c.user_id, hoy, weeks=2)
        corridas = [s for s in await registro.sessions(c.user_id, limit=30) if _en_semana(s, hoy)]
        return weekly_text(volumenes[-1], len(corridas), volumenes[0])

    if flow == "streak":
        if local.hour != STREAK_HOUR:
            return None
        dias = await LogRepo(sesion).days_since_last_run(c.user_id, hoy)
        # `None` es «nunca corrió». Eso no es una racha rota, es un inicio, y
        # regañar a alguien por no volver a algo que no empezó es absurdo.
        if dias is None or dias < STREAK_DAYS:
            return None
        plan = await StateRepo(sesion).get(c.user_id)
        return streak_text(dias, session_on(plan, hoy) if plan else None)

    if flow == "morning" and local.hour != MORNING_HOUR:
        return None
    if flow == "checkin" and local.hour != CHECKIN_HOUR:
        return None

    plan = await StateRepo(sesion).get(c.user_id)
    if plan is None:
        return None
    hoy_toca = session_on(plan, hoy)
    if hoy_toca is None:
        # Día de descanso. El descanso es parte del plan, y avisar de él
        # convierte el recordatorio en ruido.
        return None

    if flow == "morning":
        return morning_text(hoy_toca)

    # checkin: sólo si no registró nada. Preguntarle «¿cómo te fue?» a quien ya
    # nos lo contó es la forma más rápida de que silencie el bot.
    if await _corrio_hoy(sesion, c.user_id, hoy):
        return None
    return checkin_text(hoy_toca)


def _en_semana(fila: SessionLogRow, hoy: date) -> bool:
    return 0 <= (hoy - fila.occurred_on).days < 7
