"""Avisos proactivos: quién, cuándo, y cuándo callarse.

La prueba que da sentido al módulo es `test_cada_quien_a_las_seis_de_su_propia_manana`:
un corredor en Ciudad de México y otro en Toronto, el mismo barrido horario, y
cada uno saliendo en un instante UTC distinto. Es el punto ciego 7 de la Fase 1
convertido en aserción — y la razón de que la hora la decida la API y no el nodo
de horario de n8n, que sólo tiene una zona.

La segunda que importa es que en rojo los cuatro flujos de entrenamiento callan
y sólo habla el escalamiento. La puerta de seguridad no puede tener una puerta
trasera por Telegram.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from coach_domain.plans import build_plan
from coach_domain.types import AthleteProfile, Level, RaceDistance
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.automation import (
    FALLBACK_TZ,
    Nudge,
    due,
    local_now,
    mark_sent,
    session_on,
    weekly_text,
)
from apps.api.db.models import Base, TelegramLinkRow
from apps.api.db.repo import LogRepo, ProfileRepo, StateRepo

# El plan arranca un lunes, para que la semana empiece donde se espera. El lunes
# es día de descanso en un plan de esta frecuencia, así que las pruebas que
# necesitan «hoy toca entrenar» usan el martes.
LUNES = date(2026, 8, 17)
MARTES = LUNES + timedelta(days=1)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as sesion:
        yield sesion
    await engine.dispose()


def _perfil(user_id: str) -> AthleteProfile:
    return AthleteProfile(
        user_id=user_id,
        level=Level.INTERMEDIO,
        weekly_volume_km=30.0,
        longest_run_km=12.0,
        days_per_week=5,
        reference_distance_km=10.0,
        reference_time_sec=3000,
    )


async def _corredor(
    db: AsyncSession,
    user_id: str,
    tz: str,
    *,
    con_plan: bool = True,
    vinculado: bool = True,
    chat_id: int = 100,
) -> None:
    """Un corredor completo: perfil, zona, plan y Telegram vinculado."""
    await ProfileRepo(db).save(user_id, timezone=tz, goal_distance="10k", days_per_week=5)
    if con_plan:
        plan = build_plan(
            profile=_perfil(user_id),
            distance=RaceDistance.K10,
            race_date=LUNES + timedelta(weeks=10),
            today=LUNES,
        )
        await StateRepo(db).apply(user_id, plan, reason="alta")
    if vinculado:
        db.add(
            TelegramLinkRow(
                token=f"tok-{user_id}",
                user_id=user_id,
                chat_id=chat_id,
                expires_at=datetime.now(UTC),
                used_at=datetime.now(UTC),
            )
        )
    await db.commit()


def _utc(dia: date, hora: int, minuto: int = 0) -> datetime:
    return datetime(dia.year, dia.month, dia.day, hora, minuto, tzinfo=UTC)


# ── el reloj ─────────────────────────────────────────────────────────


def test_una_zona_desconocida_no_deja_al_corredor_sin_avisos() -> None:
    """Cae en la zona de reserva y lo dice en el log.

    Que el recordatorio llegue a una hora rara es un defecto visible. Que no
    llegue nunca por un `timezone` mal escrito es un agujero silencioso.
    """
    momento = _utc(LUNES, 12)
    assert local_now("Marte/Olympus_Mons", momento) == local_now(FALLBACK_TZ, momento)


def test_la_hora_local_es_la_del_corredor() -> None:
    # 12:00 UTC en agosto = 06:00 en Ciudad de México (UTC-6).
    assert local_now("America/Mexico_City", _utc(LUNES, 12)).hour == 6
    # …y 08:00 en Toronto (UTC-4 en verano).
    assert local_now("America/Toronto", _utc(LUNES, 12)).hour == 8


@pytest.mark.asyncio
async def test_cada_quien_a_las_seis_de_su_propia_manana(db: AsyncSession) -> None:
    """El punto ciego 7, convertido en aserción.

    Mismo barrido horario, dos corredores, dos instantes UTC distintos. Un nodo
    de horario de n8n no puede hacer esto: tiene una sola zona horaria.
    """
    await _corredor(db, "mx", "America/Mexico_City", chat_id=1)
    await _corredor(db, "ca", "America/Toronto", chat_id=2)

    # 10:00 UTC = 06:00 en Toronto, 04:00 en Ciudad de México.
    a_las_diez = await due(db, "morning", _utc(MARTES, 10))
    assert [n.user_id for n in a_las_diez] == ["ca"]

    # 12:00 UTC = 06:00 en Ciudad de México, 08:00 en Toronto.
    a_las_doce = await due(db, "morning", _utc(MARTES, 12))
    assert [n.user_id for n in a_las_doce] == ["mx"]


@pytest.mark.asyncio
async def test_a_cualquier_otra_hora_no_le_toca_a_nadie(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City")
    assert await due(db, "morning", _utc(LUNES, 15)) == []


# ── el recordatorio de la mañana ─────────────────────────────────────


@pytest.mark.asyncio
async def test_el_recordatorio_lleva_las_cifras_del_plan(db: AsyncSession) -> None:
    """Si es un número, viene del motor. No hay un modelo redactando esto."""
    await _corredor(db, "mx", "America/Mexico_City")
    aviso = (await due(db, "morning", _utc(MARTES, 12)))[0]

    plan = await StateRepo(db).get("mx")
    assert plan is not None
    sesion_de_hoy = session_on(plan, MARTES)
    assert sesion_de_hoy is not None
    assert f"{sesion_de_hoy.distance_km:g} km" in aviso.text
    assert aviso.chat_id == 100


@pytest.mark.asyncio
async def test_sin_plan_no_hay_recordatorio(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City", con_plan=False)
    assert await due(db, "morning", _utc(LUNES, 12)) == []


@pytest.mark.asyncio
async def test_sin_telegram_no_entra_ni_al_calculo(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City", vinculado=False)
    assert await due(db, "morning", _utc(LUNES, 12)) == []


@pytest.mark.asyncio
async def test_un_dia_de_descanso_no_genera_ruido(db: AsyncSession) -> None:
    """El descanso es parte del plan. Avisar de él convierte el aviso en ruido."""
    await _corredor(db, "mx", "America/Mexico_City")
    plan = await StateRepo(db).get("mx")
    assert plan is not None

    descanso = [
        LUNES + timedelta(days=d)
        for d in range(7)
        if session_on(plan, LUNES + timedelta(days=d)) is None
    ]
    assert descanso, "el plan de prueba debería tener al menos un día libre"

    # 12:00 UTC = 06:00 local, la hora del recordatorio, pero en día libre.
    assert await due(db, "morning", _utc(descanso[0], 12)) == []


@pytest.mark.asyncio
async def test_no_se_manda_dos_veces_el_mismo_dia(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City")
    aviso = (await due(db, "morning", _utc(MARTES, 12)))[0]
    await mark_sent(db, aviso)
    await db.commit()

    # El barrido de la hora siguiente ya no lo trae, aunque sigan siendo las 6
    # pasadas en algún sentido: la clave es la fecha local, no el instante.
    assert await due(db, "morning", _utc(MARTES, 12, 59)) == []


# ── la puerta de seguridad ───────────────────────────────────────────


async def _en_rojo(db: AsyncSession, user_id: str, dia: date) -> None:
    """Dolor de 4 tres días seguidos: `assess` lo escala a rojo por persistencia."""
    registro = LogRepo(db)
    for d in range(3):
        await registro.add_wellness(user_id, occurred_on=dia - timedelta(days=d), pain_score=4)
    await db.commit()


@pytest.mark.asyncio
@pytest.mark.parametrize("flujo", ["morning", "checkin", "streak", "weekly"])
async def test_en_rojo_los_flujos_de_entrenamiento_callan(db: AsyncSession, flujo: str) -> None:
    """La puerta de seguridad no puede tener una puerta trasera por Telegram."""
    await _corredor(db, "mx", "America/Mexico_City")
    await _en_rojo(db, "mx", LUNES)

    # Se barre el día entero: ninguna hora local puede sacar un aviso.
    for hora in range(24):
        assert await due(db, flujo, _utc(LUNES, hora)) == []


@pytest.mark.asyncio
async def test_en_rojo_el_escalamiento_es_el_unico_que_habla(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City")
    await _en_rojo(db, "mx", LUNES)

    avisos = await due(db, "escalation", _utc(LUNES, 12))
    assert len(avisos) == 1
    assert avisos[0].user_id == "mx"


@pytest.mark.asyncio
async def test_el_escalamiento_no_prescribe(db: AsyncSession) -> None:
    """El texto lo redactó el dominio, no este módulo.

    Es el mismo mensaje de derivación que oiría hablando, así que el corredor no
    recibe dos versiones distintas de la misma decisión según el canal.
    """
    await _corredor(db, "mx", "America/Mexico_City")
    await _en_rojo(db, "mx", LUNES)

    texto = (await due(db, "escalation", _utc(LUNES, 12)))[0].text
    veredicto = await LogRepo(db).current_safety("mx", LUNES)
    assert texto == veredicto.referral_message
    assert " km" not in texto


@pytest.mark.asyncio
async def test_sin_rojo_no_hay_escalamiento(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City")
    assert await due(db, "escalation", _utc(LUNES, 12)) == []


@pytest.mark.asyncio
async def test_el_escalamiento_sale_a_cualquier_hora(db: AsyncSession) -> None:
    """No espera a las seis de la mañana: el dolor no tiene horario de oficina."""
    await _corredor(db, "mx", "America/Mexico_City")
    await _en_rojo(db, "mx", LUNES)
    assert len(await due(db, "escalation", _utc(LUNES, 3))) == 1


# ── check-in ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_a_quien_ya_registro_no_se_le_pregunta(db: AsyncSession) -> None:
    """Preguntar «¿cómo te fue?» a quien ya lo contó es cómo se silencia un bot."""
    await _corredor(db, "mx", "America/Mexico_City")
    # 02:00 UTC del miércoles = 20:00 del martes en Ciudad de México.
    momento = _utc(MARTES + timedelta(days=1), 2)

    assert len(await due(db, "checkin", momento)) == 1

    await LogRepo(db).add_session(
        "mx", occurred_on=MARTES, distance_km=8.0, duration_sec=2400, source="voice"
    )
    await db.commit()

    assert await due(db, "checkin", momento) == []


# ── racha en riesgo ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_quien_nunca_corrio_no_tiene_racha_que_perder(db: AsyncSession) -> None:
    """No es una pausa, es un inicio. Regañarlo por no volver sería absurdo."""
    await _corredor(db, "mx", "America/Mexico_City")
    # 00:00 UTC del martes = 18:00 del lunes en Ciudad de México.
    assert await due(db, "streak", _utc(LUNES + timedelta(days=1), 0)) == []


@pytest.mark.asyncio
async def test_tres_dias_sin_correr_disparan_el_aviso(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City")
    await LogRepo(db).add_session(
        "mx",
        occurred_on=LUNES - timedelta(days=3),
        distance_km=8.0,
        duration_sec=2400,
        source="voice",
    )
    await db.commit()

    avisos = await due(db, "streak", _utc(LUNES + timedelta(days=1), 0))
    assert len(avisos) == 1
    assert "3 días" in avisos[0].text


@pytest.mark.asyncio
async def test_dos_dias_sin_correr_todavia_no_es_nada(db: AsyncSession) -> None:
    """Un plan de cinco días por semana tiene dos de descanso. Eso no es una racha rota."""
    await _corredor(db, "mx", "America/Mexico_City")
    await LogRepo(db).add_session(
        "mx",
        occurred_on=LUNES - timedelta(days=2),
        distance_km=8.0,
        duration_sec=2400,
        source="voice",
    )
    await db.commit()

    assert await due(db, "streak", _utc(LUNES + timedelta(days=1), 0)) == []


# ── resumen semanal ──────────────────────────────────────────────────


def test_el_resumen_mira_hacia_atras_y_no_prescribe() -> None:
    texto = weekly_text(32.0, 4, 28.0)
    assert "4 sesiones" in texto
    assert "32 km" in texto
    assert "+4.0" in texto


def test_una_semana_en_blanco_no_regana() -> None:
    texto = weekly_text(0.0, 0, 20.0)
    assert "capturas" in texto


@pytest.mark.asyncio
async def test_el_resumen_sale_el_domingo_por_la_tarde(db: AsyncSession) -> None:
    await _corredor(db, "mx", "America/Mexico_City")
    domingo = LUNES + timedelta(days=6)
    # 01:00 UTC del lunes = 19:00 del domingo en Ciudad de México.
    assert len(await due(db, "weekly", _utc(domingo + timedelta(days=1), 1))) == 1
    # Un miércoles a la misma hora local, no.
    miercoles = LUNES + timedelta(days=2)
    assert await due(db, "weekly", _utc(miercoles + timedelta(days=1), 1)) == []


# ── varios ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_un_flujo_inventado_es_un_error(db: AsyncSession) -> None:
    with pytest.raises(ValueError, match="flujo desconocido"):
        await due(db, "inventado", _utc(LUNES, 12))


@pytest.mark.asyncio
async def test_quien_revinculo_recibe_en_el_chat_nuevo(db: AsyncSession) -> None:
    """Cambiar de teléfono no puede mandar el recordatorio al aparato viejo."""
    await _corredor(db, "mx", "America/Mexico_City", chat_id=111)
    db.add(
        TelegramLinkRow(
            token="tok-nuevo",
            user_id="mx",
            chat_id=222,
            expires_at=datetime.now(UTC),
            used_at=datetime.now(UTC) + timedelta(minutes=1),
        )
    )
    await db.commit()

    avisos = await due(db, "morning", _utc(MARTES, 12))
    assert len(avisos) == 1
    assert avisos[0].chat_id == 222


def test_el_aviso_serializa_lo_que_n8n_necesita() -> None:
    aviso = Nudge(
        user_id="u1",
        chat_id=7,
        flow="morning",
        timezone="America/Mexico_City",
        local_time="2026-08-17 06:00",
        local_date=LUNES,
        text="hola",
    )
    d = aviso.as_dict()
    assert d["chat_id"] == 7
    assert d["local_date"] == "2026-08-17"
