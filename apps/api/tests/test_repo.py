"""Persistencia.

Dos invariantes del producto viven aquí y se prueban aquí:

1. **La bitácora sólo se anexa.** Corregir la historia rompe la progresión.
2. **Sólo el motor escribe el plan.** `StateRepo.apply` acepta un `Plan` del
   dominio, y un `Plan` sólo existe si `build_plan` lo validó. Es lo que impide
   que una conversación persuasiva altere el entrenamiento.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from coach_domain.plans import build_plan
from coach_domain.safety import SafetyLevel
from coach_domain.types import AthleteProfile, Level, RaceDistance
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.db.models import Base
from apps.api.db.repo import LogRepo, MemoryRepo, ProfileRepo, StateRepo
from apps.api.db.serialize import plan_from_json, plan_to_json

HOY = date(2026, 8, 15)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    """SQLite en memoria.

    Producción corre sobre PostgreSQL 17; la suite, sobre esto. El esquema usa
    tipos portables a propósito para que la diferencia no muerda. El precio de
    la divergencia se paga con velocidad: la suite entera no necesita un
    contenedor ni espera a que arranque nada.
    """
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as sesion:
        yield sesion
    await engine.dispose()


def _perfil_dominio(**cambios: object) -> AthleteProfile:
    base: dict[str, object] = {
        "user_id": "u1",
        "level": Level.INTERMEDIO,
        "weekly_volume_km": 30.0,
        "longest_run_km": 12.0,
        "days_per_week": 4,
        "reference_distance_km": 10.0,
        "reference_time_sec": 3000,
    }
    return AthleteProfile(**{**base, **cambios})  # type: ignore[arg-type]


# ── perfil ───────────────────────────────────────────────────────────


async def test_un_perfil_que_no_existe_es_none(db: AsyncSession) -> None:
    assert await ProfileRepo(db).get("fantasma") is None


async def test_el_carrusel_y_la_voz_no_se_pisan(db: AsyncSession) -> None:
    """El formulario escribe lo duro, la conversación lo blando, por separado."""
    repo = ProfileRepo(db)
    await repo.save("u1", age=28, days_per_week=4, level="intermedio")
    await repo.save("u1", weekly_volume_km=30.0, injuries=["rodilla_izquierda"])

    fila = await repo.get_row("u1")
    assert fila is not None
    assert fila.age == 28  # no lo borró la segunda escritura
    assert fila.weekly_volume_km == 30.0
    assert fila.injuries == ["rodilla_izquierda"]


async def test_guardar_un_campo_inventado_es_un_error(db: AsyncSession) -> None:
    """El modelo elige el nombre de sus campos, no quien llama."""
    with pytest.raises(ValueError, match="no es un campo del perfil"):
        await ProfileRepo(db).save("u1", vo2max_estimado=55)


async def test_el_perfil_se_traduce_al_dominio(db: AsyncSession) -> None:
    repo = ProfileRepo(db)
    await repo.save(
        "u1",
        level="avanzado",
        weekly_volume_km=60.0,
        longest_run_km=22.0,
        days_per_week=5,
        reference_distance_km=10.0,
        reference_time_sec=2400,
    )
    perfil = await repo.get("u1")
    assert perfil is not None
    assert perfil.level is Level.AVANZADO
    assert perfil.has_reference


async def test_una_contradiccion_en_el_perfil_no_revienta(db: AsyncSession) -> None:
    """«Corro 20 a la semana» y «mi tirada larga son 30» pueden convivir en la
    base: se capturan en momentos distintos. El motor no puede reventar por eso;
    la contradicción la aclara la conversación."""
    repo = ProfileRepo(db)
    await repo.save("u1", weekly_volume_km=20.0, longest_run_km=30.0)
    perfil = await repo.get("u1")
    assert perfil is not None
    assert perfil.longest_run_km == 20.0


# ── estado de entrenamiento ──────────────────────────────────────────


async def test_solo_se_puede_guardar_un_plan_del_motor(db: AsyncSession) -> None:
    """La firma es la defensa: `apply` pide un `Plan`, no un diccionario.

    Un `Plan` sólo existe si `build_plan` lo construyó y lo validó contra
    R1–R8, así que por esta puerta no entra un plan inventado.
    """
    plan = build_plan(_perfil_dominio(), RaceDistance.K21, None, HOY)
    fila = await StateRepo(db).apply("u1", plan, reason="plan inicial")
    assert fila.plan_version == 1

    with pytest.raises(AttributeError):
        await StateRepo(db).apply("u1", {"weeks": []}, reason="a mano")  # type: ignore[arg-type]


async def test_todo_cambio_de_plan_dice_por_que(db: AsyncSession) -> None:
    plan = build_plan(_perfil_dominio(), RaceDistance.K21, None, HOY)
    with pytest.raises(ValueError, match="por qué"):
        await StateRepo(db).apply("u1", plan, reason="   ")


async def test_regenerar_el_plan_sube_la_version(db: AsyncSession) -> None:
    repo = StateRepo(db)
    plan = build_plan(_perfil_dominio(), RaceDistance.K21, None, HOY)
    await repo.apply("u1", plan, reason="plan inicial")
    fila = await repo.apply("u1", plan, reason="molestia en rodilla, R6 al 75 %")
    assert fila.plan_version == 2
    assert "R6" in fila.reason


async def test_el_plan_vuelve_identico_de_la_base(db: AsyncSession) -> None:
    """El viaje de ida y vuelta no puede perder un solo número.

    Si al recuperarlo cambia algo, el coach empieza a decir cifras distintas de
    las que el motor generó — que es exactamente el fallo que toda la
    arquitectura existe para evitar.
    """
    repo = StateRepo(db)
    original = build_plan(_perfil_dominio(), RaceDistance.K21, None, HOY)
    await repo.apply("u1", original, reason="plan inicial")

    recuperado = await repo.get("u1")
    assert recuperado == original


async def test_un_plan_sin_ritmo_tambien_va_y_vuelve(db: AsyncSession) -> None:
    """El caso `None` es el que se rompe en las serializaciones perezosas."""
    perfil = _perfil_dominio(reference_distance_km=None, reference_time_sec=None)
    original = build_plan(perfil, RaceDistance.K10, None, HOY)
    assert original.weeks[0].sessions[0].pace is None
    assert plan_from_json(plan_to_json(original)) == original


async def test_un_esquema_desconocido_falla_ruidosamente() -> None:
    """Un plan medio interpretado es peor que ninguno: nadie nota la diferencia."""
    with pytest.raises(ValueError, match="esquema"):
        plan_from_json({"schema": 99, "distance": "21k"})


async def test_avanzar_de_semana(db: AsyncSession) -> None:
    repo = StateRepo(db)
    plan = build_plan(_perfil_dominio(), RaceDistance.K21, None, HOY)
    await repo.apply("u1", plan, reason="plan inicial")
    assert await repo.advance_week("u1") == 2


# ── bitácora: sólo se anexa ──────────────────────────────────────────


async def test_la_bitacora_no_permite_borrar(db: AsyncSession) -> None:
    repo = LogRepo(db)
    await repo.add_session("u1", occurred_on=HOY, distance_km=8.0, duration_sec=2700)
    with pytest.raises(NotImplementedError, match="sólo se anexa"):
        await repo.delete("u1")


async def test_la_bitacora_no_permite_corregir_en_sitio(db: AsyncSession) -> None:
    with pytest.raises(NotImplementedError, match="sólo se anexa"):
        await LogRepo(db).update_session(1, distance_km=9.0)


async def test_el_ritmo_lo_calcula_el_motor(db: AsyncSession) -> None:
    fila = await LogRepo(db).add_session("u1", occurred_on=HOY, distance_km=8.42, duration_sec=2838)
    assert fila.pace_sec_per_km == 337  # 5:37/km
    assert not fila.discrepancy_flag


async def test_un_ritmo_mal_leido_no_gana_al_motor(db: AsyncSession) -> None:
    """El caso de la captura de pantalla (ADR 0014): gana el motor, y queda marcado."""
    fila = await LogRepo(db).add_session(
        "u1",
        occurred_on=HOY,
        distance_km=8.0,
        duration_sec=2700,
        source="vision",
        reported_pace_sec_per_km=200,  # 3:20/km, imposible aquí
    )
    assert fila.pace_sec_per_km == 338
    assert fila.discrepancy_flag


async def test_una_diferencia_de_redondeo_no_es_discrepancia(db: AsyncSession) -> None:
    fila = await LogRepo(db).add_session(
        "u1",
        occurred_on=HOY,
        distance_km=8.0,
        duration_sec=2700,
        source="vision",
        reported_pace_sec_per_km=337,  # el reloj mostraba 5:37, el motor dice 5:38
    )
    assert not fila.discrepancy_flag


async def test_una_bandera_mal_escrita_falla_al_guardar(db: AsyncSession) -> None:
    """Y no en silencio meses después, cuando alguien la lea."""
    with pytest.raises(ValueError, match="no reconozco"):
        await LogRepo(db).add_wellness("u1", occurred_on=HOY, pain_score=3, flags=["dolor_raro"])


async def test_toda_decision_guarda_su_razon(db: AsyncSession) -> None:
    repo = LogRepo(db)
    await repo.add_decision("u1", rule="R6", rationale="9 días sin correr, volumen al 75 %")
    ultima = (await repo.decisions("u1"))[-1]
    assert ultima.rule == "R6"
    assert "75" in ultima.rationale


async def test_una_decision_sin_razon_es_un_error(db: AsyncSession) -> None:
    with pytest.raises(ValueError, match="auditable"):
        await LogRepo(db).add_decision("u1", rule="R1", rationale="")


# ── lectura de la bitácora ───────────────────────────────────────────


async def test_los_volumenes_recientes_van_de_viejo_a_nuevo(db: AsyncSession) -> None:
    repo = LogRepo(db)
    for semanas_atras, km in [(3, 20.0), (2, 25.0), (1, 30.0), (0, 32.0)]:
        await repo.add_session(
            "u1",
            occurred_on=HOY - timedelta(weeks=semanas_atras),
            distance_km=km,
            duration_sec=int(km * 330),
        )
    volumenes = await repo.recent_volumes("u1", HOY, weeks=4)
    assert volumenes == [20.0, 25.0, 30.0, 32.0]


async def test_los_dias_sin_correr_alimentan_r6(db: AsyncSession) -> None:
    repo = LogRepo(db)
    await repo.add_session(
        "u1", occurred_on=HOY - timedelta(days=9), distance_km=8.0, duration_sec=2700
    )
    assert await repo.days_since_last_run("u1", HOY) == 9


async def test_quien_nunca_corrio_no_esta_de_pausa(db: AsyncSession) -> None:
    """`None` y `0` dicen cosas distintas: empezar no es volver."""
    assert await LogRepo(db).days_since_last_run("u1", HOY) is None


# ── la puerta de seguridad, alimentada por la bitácora ───────────────


async def test_sin_reportes_el_veredicto_es_verde(db: AsyncSession) -> None:
    assert (await LogRepo(db).current_safety("u1", HOY)).level is SafetyLevel.GREEN


async def test_un_dolor_reciente_manda(db: AsyncSession) -> None:
    repo = LogRepo(db)
    await repo.add_wellness("u1", occurred_on=HOY, pain_score=6, pain_area="rodilla")
    veredicto = await repo.current_safety("u1", HOY)
    assert veredicto.level is SafetyLevel.RED
    assert not veredicto.allows_prescription


async def test_un_dolor_de_hace_dos_semanas_ya_no_manda(db: AsyncSession) -> None:
    repo = LogRepo(db)
    await repo.add_wellness("u1", occurred_on=HOY - timedelta(days=14), pain_score=7)
    assert (await repo.current_safety("u1", HOY)).level is SafetyLevel.GREEN


async def test_la_persistencia_se_cuenta_no_se_pregunta(db: AsyncSession) -> None:
    """Tres días seguidos de molestia moderada escalan a rojo solos.

    Preguntarle al corredor «¿cuántos días llevas así?» produce una respuesta
    optimista. Contar los reportes produce el número real, y esa diferencia es
    justo la que convierte un ámbar en un rojo.
    """
    repo = LogRepo(db)
    for atras in (2, 1, 0):
        await repo.add_wellness("u1", occurred_on=HOY - timedelta(days=atras), pain_score=4)

    veredicto = await repo.current_safety("u1", HOY)
    assert veredicto.level is SafetyLevel.RED
    assert "persistente" in veredicto.reason


async def test_una_molestia_de_dos_dias_sigue_siendo_ambar(db: AsyncSession) -> None:
    repo = LogRepo(db)
    for atras in (1, 0):
        await repo.add_wellness("u1", occurred_on=HOY - timedelta(days=atras), pain_score=4)
    assert (await repo.current_safety("u1", HOY)).level is SafetyLevel.AMBER


async def test_un_dia_sin_reporte_corta_la_racha(db: AsyncSession) -> None:
    """Si no reportó ayer, no hay evidencia de que la molestia siguiera."""
    repo = LogRepo(db)
    for atras in (3, 2, 0):  # falta el día 1
        await repo.add_wellness("u1", occurred_on=HOY - timedelta(days=atras), pain_score=4)
    assert (await repo.current_safety("u1", HOY)).level is SafetyLevel.AMBER


# ── memoria conversacional ───────────────────────────────────────────


async def test_la_memoria_vuelve_en_orden_cronologico(db: AsyncSession) -> None:
    repo = MemoryRepo(db)
    await repo.remember("u1", "USER", "entreno para un 21k")
    await repo.remember("u1", "ASSISTANT", "¿cuánto corres a la semana?")
    await repo.remember("u1", "USER", "unos 30")

    turnos = await repo.recent("u1")
    assert [t.text for t in turnos] == [
        "entreno para un 21k",
        "¿cuánto corres a la semana?",
        "unos 30",
    ]


async def test_la_memoria_ignora_lo_vacio(db: AsyncSession) -> None:
    repo = MemoryRepo(db)
    await repo.remember("u1", "USER", "   ")
    assert await repo.recent("u1") == []


async def test_la_memoria_de_un_usuario_no_se_mezcla_con_la_de_otro(db: AsyncSession) -> None:
    repo = MemoryRepo(db)
    await repo.remember("u1", "USER", "lo mío")
    await repo.remember("u2", "USER", "lo suyo")
    assert [t.text for t in await repo.recent("u1")] == ["lo mío"]
