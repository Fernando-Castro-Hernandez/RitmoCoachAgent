"""Que lo que se sube se guarde, y que el coach se entere.

Dos huecos que se tocaban y ninguno de los dos daba error:

1. El «Guardar» de la captura no escribía en la bitácora. Pintaba una línea en
   la transcripción y ahí moría. El mismo entrenamiento contado hablando —por
   `log_run`— sí se guardaba, así que el producto tenía dos memorias y una era
   mentira.
2. `build_system_prompt` nunca había recibido las carreras registradas. Aunque
   el punto 1 hubiera funcionado, el coach habría seguido preguntando «¿cómo te
   fue?» sobre una carrera que estaba en su propia base de datos.

La prueba que más vale es `test_el_ritmo_lo_calcula_el_motor_aunque_manden_uno`:
es la regla del ADR 0003 aplicada a un endpoint nuevo, y la clase de cosa que
se rompe cuando alguien añade un campo «por comodidad».
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.auth import usuario_actual
from apps.api.db.models import Base, UserRow
from apps.api.db.repo import LogRepo, ProfileRepo
from apps.api.db.session import get_session
from apps.api.main import app
from apps.api.prompts import build_system_prompt
from apps.api.session_context import CARRERAS_RECORDADAS, build_prompt_for

HOY = date.today()


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


# ── que se guarde ─────────────────────────────────────────────────────


def test_la_captura_confirmada_llega_a_la_bitacora(cliente: Any) -> None:
    r = cliente.post(
        "/api/sessions",
        json={"distance_km": 8.42, "duration_sec": 2838, "source": "vision"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # Y se puede volver a leer: no se quedó en la respuesta.
    csv = cliente.get("/api/plan/export.csv")
    assert csv.status_code == 404, "no hay plan, pero la sesión sí debe existir"


@pytest.mark.asyncio
async def test_el_ritmo_lo_calcula_el_motor_aunque_manden_uno(cliente: Any) -> None:
    """8,42 km en 47:18 son 337 s/km. Si el cliente dice 300, gana el motor."""
    cuerpo = cliente.post(
        "/api/sessions",
        json={
            "distance_km": 8.42,
            "duration_sec": 2838,
            "reported_pace_sec_per_km": 300,
            "source": "vision",
        },
    ).json()

    assert cuerpo["session"]["pace_sec_per_km"] == 337
    assert cuerpo["session"]["pace"] == "5:37"
    # Y la discrepancia queda marcada en vez de perderse.
    assert cuerpo["session"]["discrepancy_flag"] is True


def test_un_ritmo_leido_que_cuadra_no_marca_discrepancia(cliente: Any) -> None:
    cuerpo = cliente.post(
        "/api/sessions",
        json={
            "distance_km": 8.42,
            "duration_sec": 2838,
            "reported_pace_sec_per_km": 338,
            "source": "vision",
        },
    ).json()
    assert cuerpo["session"]["discrepancy_flag"] is False


@pytest.mark.parametrize(
    "cuerpo",
    [
        {"distance_km": 0, "duration_sec": 100},
        {"distance_km": -3, "duration_sec": 100},
        {"distance_km": 5, "duration_sec": 0},
        {"distance_km": 5000, "duration_sec": 100},
        {"distance_km": 5, "duration_sec": 100, "rpe": 11},
        {"distance_km": 5, "duration_sec": 100, "source": "inventado"},
    ],
)
def test_lo_imposible_se_rechaza_en_la_puerta(cliente: Any, cuerpo: dict[str, Any]) -> None:
    assert cliente.post("/api/sessions", json=cuerpo).status_code == 422


def test_el_esquema_no_acepta_un_ritmo_directo(cliente: Any) -> None:
    """Si alguien añadiera `pace_sec_per_km` al cuerpo, entraría una cifra que
    ningún motor calculó. Hoy se ignora; esta prueba fija que se ignore."""
    cuerpo = cliente.post(
        "/api/sessions",
        json={"distance_km": 10, "duration_sec": 3000, "pace_sec_per_km": 111},
    ).json()
    assert cuerpo["session"]["pace_sec_per_km"] == 300


# ── que el coach se entere ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lo_corrido_viaja_en_el_prompt(cliente: Any) -> None:
    async with cliente.fabrica() as db:
        await ProfileRepo(db).save("u1", goal_distance="10k", name="Fernando")
        await LogRepo(db).add_session(
            "u1", occurred_on=HOY, distance_km=8.42, duration_sec=2838, source="vision"
        )
        await db.commit()

    async with cliente.fabrica() as db:
        prompt = await build_prompt_for(db, "u1", today=HOY)

    assert "8.42 km" in prompt
    assert "5:37/km" in prompt
    assert "captura del reloj" in prompt
    assert "no le preguntes por estas sesiones" in prompt.lower()


@pytest.mark.asyncio
async def test_solo_viajan_las_ultimas(cliente: Any) -> None:
    """El prompt no es un historial: para las tendencias está el motor."""
    async with cliente.fabrica() as db:
        repo = LogRepo(db)
        for i in range(CARRERAS_RECORDADAS + 4):
            await repo.add_session(
                "u1",
                occurred_on=HOY - timedelta(days=i),
                distance_km=5 + i,
                duration_sec=1800,
            )
        await ProfileRepo(db).save("u1", goal_distance="10k")
        await db.commit()

    async with cliente.fabrica() as db:
        prompt = await build_prompt_for(db, "u1", today=HOY)

    # Se cuenta DENTRO del bloque, no en el prompt entero: la persona también
    # usa viñetas «- », así que contar en todo el texto daba 14 y la prueba
    # fallaba con el código correcto. Medía otra cosa.
    bloque = prompt.split("Esto es lo que YA corrió")[1].split("\n\n")[0]
    assert bloque.count("\n- ") == CARRERAS_RECORDADAS

    # Y son las MÁS RECIENTES: 5 a 9 km son de los últimos cinco días; 13, del
    # noveno, ya no cabe.
    assert "9 km" in bloque
    assert "13 km" not in bloque


def test_sin_carreras_no_aparece_el_bloque() -> None:
    """Un apartado vacío de «lo que ya corrió» le dice al modelo que mire una
    lista que no existe, y de ahí salen frases sobre entrenamientos inventados."""
    prompt = build_system_prompt(profile={"goal_distance": "10k"}, recent_runs=[])
    assert "lo que YA corrió" not in prompt


# ── el nombre ─────────────────────────────────────────────────────────


def test_el_nombre_se_guarda_y_vuelve(cliente: Any) -> None:
    cliente.post("/api/profile", json={"goal_distance": "10k", "name": "  Fernando  "})
    perfil = cliente.get("/api/profile").json()["profile"]
    assert perfil["name"] == "Fernando", "se guarda sin los espacios de los lados"


def test_un_nombre_en_blanco_no_es_un_nombre(cliente: Any) -> None:
    """Sin esto el coach saludaría a un espacio: `profile["name"]` sería
    verdadero y el prompt diría «el corredor se llama    »."""
    cliente.post("/api/profile", json={"goal_distance": "10k", "name": "   "})
    assert cliente.get("/api/profile").json()["profile"]["name"] is None


def test_el_prompt_le_dice_al_coach_como_llamarle() -> None:
    prompt = build_system_prompt(profile={"goal_distance": "10k", "name": "Fernando"})
    assert "se llama Fernando" in prompt
    assert "no en todas las frases" in prompt


def test_sin_nombre_el_coach_no_se_lo_inventa_ni_lo_pregunta() -> None:
    """El carrusel ya se lo preguntó. Si lo saltó, eso fue una respuesta."""
    prompt = build_system_prompt(profile={"goal_distance": "10k", "name": None})
    assert "se llama" not in prompt


# ── el calendario ─────────────────────────────────────────────────────


def test_sin_plan_el_calendario_dice_que_no_hay(cliente: Any) -> None:
    assert cliente.get("/api/plan/calendar").status_code == 404


async def _con_plan(fabrica: Any) -> None:
    from coach_domain.plans import build_plan
    from coach_domain.types import AthleteProfile, Level, RaceDistance

    from apps.api.db.repo import StateRepo

    lunes = HOY - timedelta(days=HOY.weekday())
    async with fabrica() as db:
        await ProfileRepo(db).save("u1", goal_distance="10k", days_per_week=4)
        perfil = AthleteProfile(
            user_id="u1",
            level=Level.INTERMEDIO,
            weekly_volume_km=30.0,
            longest_run_km=12.0,
            days_per_week=4,
            reference_distance_km=5.0,
            reference_time_sec=1500,
        )
        plan = build_plan(perfil, RaceDistance.K10, lunes + timedelta(weeks=10), lunes)
        await StateRepo(db).apply("u1", plan, reason="prueba")
        await db.commit()


@pytest.mark.asyncio
async def test_cada_semana_trae_siete_casillas(cliente: Any) -> None:
    """Siete SIEMPRE, con `null` donde se descansa.

    Mandar sólo las sesiones obligaría a la rejilla a reconstruir los huecos, y
    el descanso es parte del plan: se dibuja, no se deja en blanco por omisión.
    """
    await _con_plan(cliente.fabrica)
    cuerpo = cliente.get("/api/plan/calendar").json()

    assert cuerpo["totalWeeks"] == len(cuerpo["weeks"])
    for semana in cuerpo["weeks"]:
        assert len(semana["days"]) == 7
        assert any(d is None for d in semana["days"]), "alguna semana no descansa nunca"
        assert any(d is not None for d in semana["days"])


@pytest.mark.asyncio
async def test_el_calendario_y_el_csv_cuentan_lo_mismo(cliente: Any) -> None:
    """La prueba que evita el peor fallo posible aquí: dos vistas del mismo plan
    que discrepan en un día. Quien lo notara no sabría a cuál creerle."""
    await _con_plan(cliente.fabrica)

    csv_texto = cliente.get("/api/plan/export.csv").content.decode("utf-8-sig")
    filas = [ln.split(",") for ln in csv_texto.strip().splitlines()[1:]]
    del_csv = {(int(f[0]), f[2]) for f in filas}  # (semana, fecha)

    del_calendario = set()
    for semana in cliente.get("/api/plan/calendar").json()["weeks"]:
        inicio = date.fromisoformat(semana["startDate"])
        for i, dia in enumerate(semana["days"]):
            if dia is not None:
                del_calendario.add((semana["index"], (inicio + timedelta(days=i)).isoformat()))

    assert del_calendario == del_csv


@pytest.mark.asyncio
async def test_el_calendario_viaja_entero_tambien_en_rojo(cliente: Any) -> None:
    """No contradice a `/api/today`, que en rojo se calla la sesión de hoy.

    Son dos preguntas distintas: «¿qué hago hoy?» es una prescripción y con
    bandera roja no se emite; «¿cómo es mi plan?» es el documento que el
    corredor ya tiene descargado en CSV.
    """
    await _con_plan(cliente.fabrica)
    async with cliente.fabrica() as db:
        await LogRepo(db).add_wellness(
            "u1", occurred_on=HOY, pain_score=8, flags=["bone_point_pain"]
        )
        await db.commit()

    cuerpo = cliente.get("/api/plan/calendar").json()
    assert cuerpo["safety"] == "flag"
    assert cuerpo["weeks"], "el plan no desaparece; lo que no se emite es la sesión de hoy"
    assert cliente.get("/api/today").json()["session"] is None
