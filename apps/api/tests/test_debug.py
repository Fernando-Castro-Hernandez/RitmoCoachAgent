"""Las dos superficies de observabilidad, y la línea que las separa.

`/metrics` es agregado y no lleva a nadie dentro, así que va abierto: se raspa
cada quince segundos desde la red interna y pedirle una llave sería ceremonia.

`/debug/sessions/{id}` devuelve la conversación entera de una persona, así que
va cerrado. Que esa diferencia esté probada es el punto de este archivo — es
exactamente el tipo de endpoint que se añade «para depurar» y se queda abierto.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.config import get_settings
from apps.api.db.models import Base
from apps.api.db.repo import LogRepo, MemoryRepo
from apps.api.db.session import get_session
from apps.api.main import app

LLAVE = "llave-de-prueba"


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


# ── /metrics ─────────────────────────────────────────────────────────


def test_metrics_va_abierto_y_habla_prometheus(cliente: Any) -> None:
    r = cliente.get("/metrics")
    assert r.status_code == 200
    assert "text/plain" in r.headers["content-type"]
    assert "ritmo_ttfa_ms" in r.text


def test_metrics_no_lleva_a_nadie_dentro(cliente: Any) -> None:
    """Sólo agregados. Es lo que permite raspar esto sin ceremonia."""
    assert "user_id" not in cliente.get("/metrics").text


# ── el reproductor ───────────────────────────────────────────────────


def test_el_reproductor_no_va_abierto(cliente: Any) -> None:
    assert cliente.get("/debug/sessions/u1").status_code == 403


def test_sin_llave_configurada_cierra(cliente: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AUTOMATION_API_KEY", "")
    get_settings.cache_clear()
    r = cliente.get("/debug/sessions/u1", headers={"X-Ritmo-Automation-Key": LLAVE})
    assert r.status_code == 503


@pytest.mark.asyncio
async def test_reconstruye_lo_que_se_dijo_y_por_que(cliente: Any) -> None:
    """La respuesta a «¿por qué el sistema me dijo esto?» tiene que ser una
    traza, no una conjetura."""
    async with cliente.fabrica() as db:
        await MemoryRepo(db).remember("u1", "USER", "me duele la tibia")
        await LogRepo(db).add_decision(
            "u1", rule="R8", rationale="dolor de 7 en punto óseo: no se prescribe"
        )
        await db.commit()

    cuerpo = cliente.get("/debug/sessions/u1", headers={"X-Ritmo-Automation-Key": LLAVE}).json()

    assert cuerpo["turns"][0]["text"] == "me duele la tibia"
    assert cuerpo["decisions"][0]["rule"] == "R8"
    assert "punto óseo" in cuerpo["decisions"][0]["rationale"]


def test_un_corredor_sin_historia_no_es_un_error(cliente: Any) -> None:
    cuerpo = cliente.get("/debug/sessions/nadie", headers={"X-Ritmo-Automation-Key": LLAVE}).json()
    assert cuerpo["turns"] == []
    assert cuerpo["plan"] is None
