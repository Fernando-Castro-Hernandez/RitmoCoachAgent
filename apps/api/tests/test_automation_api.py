"""Lo que n8n le pregunta a la API.

Dos cosas se prueban aquí y las dos son de política, no de plomería:

1. **La llave.** Estos endpoints devuelven datos de salud de gente con nombre.
   Sin llave configurada cierran; con llave equivocada, 403.
2. **Las dos políticas de entrega.** Los flujos rutinarios se marcan al
   entregarlos, así que el segundo barrido ya no los trae. El escalamiento
   **no**: vuelve a salir hasta que n8n confirme. Un «buenos días» perdido no
   cuesta nada; un «para de entrenar» perdido, sí.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from coach_domain.plans import build_plan
from coach_domain.types import AthleteProfile, Level, RaceDistance
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import get_settings
from apps.api.db.models import Base, TelegramLinkRow
from apps.api.db.repo import LogRepo, ProfileRepo, StateRepo
from apps.api.db.session import get_session
from apps.api.main import app

LLAVE = "llave-de-prueba"
LUNES = date(2026, 8, 17)
MARTES = LUNES + timedelta(days=1)
# 12:00 UTC = 06:00 en Ciudad de México: la hora del recordatorio matutino.
SEIS_LOCAL = "2026-08-18T12:00:00+00:00"


@pytest_asyncio.fixture
async def cliente(monkeypatch: pytest.MonkeyPatch) -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)

    async def sesion_de_prueba() -> Any:
        async with fabrica() as s:
            yield s

    app.dependency_overrides[get_session] = sesion_de_prueba
    monkeypatch.setenv("AUTOMATION_API_KEY", LLAVE)
    get_settings.cache_clear()

    with TestClient(app) as c:
        c.fabrica = fabrica  # type: ignore[attr-defined]
        yield c

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    await engine.dispose()


async def _corredor(fabrica: Any, user_id: str = "mx", *, dolor: bool = False) -> None:
    async with fabrica() as db:
        await ProfileRepo(db).save(user_id, timezone="America/Mexico_City", goal_distance="10k")
        plan = build_plan(
            profile=AthleteProfile(
                user_id=user_id,
                level=Level.INTERMEDIO,
                weekly_volume_km=30.0,
                longest_run_km=12.0,
                days_per_week=5,
                reference_distance_km=10.0,
                reference_time_sec=3000,
            ),
            distance=RaceDistance.K10,
            race_date=LUNES + timedelta(weeks=10),
            today=LUNES,
        )
        await StateRepo(db).apply(user_id, plan, reason="alta")
        db.add(
            TelegramLinkRow(
                token=f"tok-{user_id}",
                user_id=user_id,
                chat_id=42,
                expires_at=datetime.now(UTC),
                used_at=datetime.now(UTC),
            )
        )
        if dolor:
            registro = LogRepo(db)
            for d in range(3):
                await registro.add_wellness(
                    user_id, occurred_on=MARTES - timedelta(days=d), pain_score=4
                )
        await db.commit()


def _due(cliente: Any, flujo: str, at: str = SEIS_LOCAL, llave: str | None = LLAVE) -> Any:
    cabeceras = {} if llave is None else {"X-Ritmo-Automation-Key": llave}
    return cliente.get(f"/api/automation/due/{flujo}", params={"at": at}, headers=cabeceras)


# ── la llave ─────────────────────────────────────────────────────────


def test_sin_llave_configurada_cierra(cliente: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_API_KEY", "")
    get_settings.cache_clear()
    assert _due(cliente, "morning").status_code == 503


def test_llave_equivocada_no_pasa(cliente: Any) -> None:
    assert _due(cliente, "morning", llave="otra").status_code == 403


def test_sin_cabecera_no_pasa(cliente: Any) -> None:
    assert _due(cliente, "morning", llave=None).status_code == 403


def test_un_flujo_inventado_es_404(cliente: Any) -> None:
    assert _due(cliente, "inventado").status_code == 404


def test_un_instante_ilegible_es_422(cliente: Any) -> None:
    assert _due(cliente, "morning", at="mañana por la mañana").status_code == 422


# ── las dos políticas de entrega ─────────────────────────────────────


@pytest.mark.asyncio
async def test_el_recordatorio_se_marca_al_entregarlo(cliente: Any) -> None:
    """El segundo barrido de la misma mañana ya no lo trae."""
    await _corredor(cliente.fabrica)

    primero = _due(cliente, "morning").json()
    assert primero["count"] == 1
    assert primero["nudges"][0]["chat_id"] == 42
    assert primero["nudges"][0]["timezone"] == "America/Mexico_City"

    assert _due(cliente, "morning").json()["count"] == 0


@pytest.mark.asyncio
async def test_el_escalamiento_insiste_hasta_que_se_confirma(cliente: Any) -> None:
    """La asimetría deliberada: este no se pierde por un fallo de Telegram."""
    await _corredor(cliente.fabrica, dolor=True)

    primero = _due(cliente, "escalation").json()
    assert primero["count"] == 1

    # Sin confirmar, vuelve a salir.
    assert _due(cliente, "escalation").json()["count"] == 1

    aviso = primero["nudges"][0]
    ack = cliente.post(
        "/api/automation/ack",
        json={
            "user_id": aviso["user_id"],
            "flow": "escalation",
            "local_date": aviso["local_date"],
            "text": aviso["text"],
        },
        headers={"X-Ritmo-Automation-Key": LLAVE},
    )
    assert ack.status_code == 200

    assert _due(cliente, "escalation").json()["count"] == 0


def test_confirmar_tambien_pide_llave(cliente: Any) -> None:
    r = cliente.post(
        "/api/automation/ack",
        json={"user_id": "mx", "flow": "escalation", "local_date": "2026-08-18"},
    )
    assert r.status_code == 403


def test_una_fecha_ilegible_al_confirmar_es_422(cliente: Any) -> None:
    r = cliente.post(
        "/api/automation/ack",
        json={"user_id": "mx", "flow": "escalation", "local_date": "el martes"},
        headers={"X-Ritmo-Automation-Key": LLAVE},
    )
    assert r.status_code == 422


@pytest.mark.asyncio
async def test_confirmar_dos_veces_no_rompe_nada(cliente: Any) -> None:
    """Idempotente por construcción: el filtro es «existe alguna fila», no «una»."""
    await _corredor(cliente.fabrica, dolor=True)
    cuerpo = {
        "user_id": "mx",
        "flow": "escalation",
        "local_date": "2026-08-18",
        "text": "x",
    }
    cabeceras = {"X-Ritmo-Automation-Key": LLAVE}
    assert cliente.post("/api/automation/ack", json=cuerpo, headers=cabeceras).status_code == 200
    assert cliente.post("/api/automation/ack", json=cuerpo, headers=cabeceras).status_code == 200
    assert _due(cliente, "escalation").json()["count"] == 0
