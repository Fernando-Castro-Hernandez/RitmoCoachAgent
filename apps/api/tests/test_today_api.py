"""La hoja, con datos de verdad.

La prueba que justifica el endpoint es `test_en_rojo_la_sesion_no_viaja`. La
regla del producto es que en rojo la pantalla no prescribe, y la forma de
garantizarla no es que el frontend se acuerde de ocultarla: es que **el dato no
salga del servidor**. Una pantalla no puede enseñar lo que no tiene.

Lo segundo que se fija aquí es que el recorte de ámbar venga ya aplicado. Si
viviera en el navegador habría dos sitios donde cambiar la regla y uno se
quedaría atrás.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
import pytest_asyncio
from coach_domain.plans import build_plan
from coach_domain.types import AthleteProfile, Level, RaceDistance
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.auth import usuario_actual
from apps.api.db.models import Base, UserRow
from apps.api.db.repo import LogRepo, ProfileRepo, StateRepo
from apps.api.db.session import get_session
from apps.api.main import app

HOY = date.today()
LUNES = HOY - timedelta(days=HOY.weekday())


@pytest_asyncio.fixture
async def cliente() -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)

    async def sesion_de_prueba() -> Any:
        async with fabrica() as s:
            yield s

    app.dependency_overrides[get_session] = sesion_de_prueba
    app.dependency_overrides[usuario_actual] = lambda: UserRow(
        id="u1", email="u1@ritmo.test", hashed_password=""
    )
    with TestClient(app) as c:
        c.fabrica = fabrica  # type: ignore[attr-defined]
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


async def _con_plan(fabrica: Any, *, dolor: int | None = None, dias: int = 1) -> None:
    async with fabrica() as db:
        await ProfileRepo(db).save("u1", goal_distance="42k", days_per_week=5)
        perfil = AthleteProfile(
            user_id="u1",
            level=Level.INTERMEDIO,
            weekly_volume_km=40.0,
            longest_run_km=20.0,
            days_per_week=5,
            reference_distance_km=10.0,
            reference_time_sec=2820,
        )
        plan = build_plan(perfil, RaceDistance.K42, LUNES + timedelta(weeks=20), LUNES)
        await StateRepo(db).apply("u1", plan, reason="prueba")

        if dolor is not None:
            registro = LogRepo(db)
            for d in range(dias):
                await registro.add_wellness(
                    "u1", occurred_on=HOY - timedelta(days=d), pain_score=dolor
                )
        await db.commit()


# ── sin plan ─────────────────────────────────────────────────────────


def test_sin_plan_lo_dice_en_vez_de_inventarse_una_semana(cliente: Any) -> None:
    cuerpo = cliente.get("/api/today").json()
    assert cuerpo["has_plan"] is False
    assert cuerpo["week"] is None
    assert cuerpo["session"] is None
    assert cuerpo["safety"] == "clear"


# ── verde ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_con_plan_la_hoja_deja_de_ser_muestra(cliente: Any) -> None:
    await _con_plan(cliente.fabrica)
    cuerpo = cliente.get("/api/today").json()

    assert cuerpo["has_plan"] is True
    assert cuerpo["week"]["week"] == 1
    assert cuerpo["week"]["totalWeeks"] == 20
    assert cuerpo["week"]["race"] == "Maratón"
    assert cuerpo["week"]["daysLeft"] is not None
    assert cuerpo["safety"] == "clear"


# ── ámbar ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_en_ambar_el_recorte_ya_viene_hecho(cliente: Any) -> None:
    """El navegador no multiplica nada ni conoce la regla: sólo pinta."""
    await _con_plan(cliente.fabrica)
    completa = cliente.get("/api/today").json()["session"]
    if completa is None:
        pytest.skip("hoy es día de descanso en el plan de prueba")

    await _con_plan(cliente.fabrica, dolor=3)
    recortada = cliente.get("/api/today").json()

    assert recortada["safety"] == "caution"
    assert recortada["session"] is not None
    assert recortada["session"]["distanceKm"] < completa["distanceKm"]
    assert recortada["session"]["kind"] == "suave"
    # Y dice por qué le bajamos: un recorte sin explicación se lee como un error.
    assert recortada["session"]["why"]


# ── rojo ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_en_rojo_la_sesion_no_viaja(cliente: Any) -> None:
    """La regla del producto, hecha protocolo.

    No se manda recortada ni «por si acaso»: no se manda. Una pantalla no puede
    enseñar lo que no tiene, y eso es más fuerte que confiar en que el frontend
    se acuerde de ocultarla.
    """
    await _con_plan(cliente.fabrica, dolor=7)
    cuerpo = cliente.get("/api/today").json()

    assert cuerpo["safety"] == "flag"
    assert cuerpo["session"] is None
    # Pero la semana sí: el corredor no deja de estar en la semana 1 de 20
    # porque le duela algo, y borrarle el contexto sería castigarlo.
    assert cuerpo["week"] is not None
    # Y se le dice con quién ir.
    assert cuerpo["referral"]


@pytest.mark.asyncio
async def test_en_rojo_no_se_filtra_ninguna_distancia(cliente: Any) -> None:
    """Ni en un campo secundario. Se comprueba sobre el JSON entero."""
    await _con_plan(cliente.fabrica, dolor=7)
    crudo = cliente.get("/api/today").text

    assert "distanceKm" not in crudo
    assert "pace" not in crudo


# Que la ruta no vaya abierta se comprueba en `test_auth.py`, con el resto:
# `RUTAS_DEL_CORREDOR` las recorre una por una y ahí es donde tiene que doler
# si alguien añade un endpoint y olvida la dependencia.
