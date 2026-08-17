"""Spike: ¿Nova Sonic acepta nuestros toolSpec y llama de verdad?

Lo único que no se puede saber sin salir a la red: que el formato del esquema
sea el correcto, que el modelo elija la herramienta, y que el `toolResult` se
acepte sin romper el turno.

Dos sondas, y la segunda es tan importante como la primera:

  A · perfil completo, «¿qué me toca hoy?»  → DEBE llamar a get_today_session
  B · perfil vacío,   «quiero un maratón»   → NO debe llamar a create_plan,
                                               debe preguntar

La B es el pivote de clarificación autónoma medido contra el modelo real. Un
coach que llama a `create_plan` ahí no está siendo servicial: está armando un
plan de maratón sin saber si la persona corre.

Uso:
  PYTHONPATH="$PWD;$PWD/packages" uv run python scripts/spike_tool_loop.py
"""

from __future__ import annotations

import asyncio
import sys
from datetime import date, timedelta

from coach_domain.plans import build_plan
from coach_domain.types import AthleteProfile, Level, RaceDistance
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.bridge import NovaBridge
from apps.api.credentials import ensure_aws_credentials
from apps.api.db.models import Base
from apps.api.db.repo import ProfileRepo, StateRepo
from apps.api.session_context import build_prompt_for
from apps.api.tool_runner import ToolRunner

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOY = date.today()


async def _fabrica(completo: bool):
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)

    async with fabrica() as db:
        if completo:
            await ProfileRepo(db).save(
                "spike",
                goal_distance="10k",
                days_per_week=4,
                weekly_volume_km=30.0,
                longest_run_km=12.0,
                reference_distance_km=10.0,
                reference_time_sec=3000,
                level="intermedio",
                injuries=[],
            )
            perfil = AthleteProfile(
                user_id="spike",
                level=Level.INTERMEDIO,
                weekly_volume_km=30.0,
                longest_run_km=12.0,
                days_per_week=4,
                reference_distance_km=10.0,
                reference_time_sec=3000,
            )
            # Se planta el plan desde el lunes de esta semana para que «hoy»
            # caiga dentro y la consulta tenga algo que devolver.
            lunes = HOY - timedelta(days=HOY.weekday())
            plan = build_plan(perfil, RaceDistance.K10, lunes + timedelta(weeks=10), lunes)
            await StateRepo(db).apply("spike", plan, reason="spike")
        else:
            await ProfileRepo(db).save("spike", goal_distance="42k")
        await db.commit()
    return engine, fabrica


async def sonda(nombre: str, frase: str, *, completo: bool) -> tuple[list[str], str]:
    engine, fabrica = await _fabrica(completo)
    async with fabrica() as db:
        prompt = await build_prompt_for(db, "spike", today=HOY)
    puente = NovaBridge(tool_runner=ToolRunner(fabrica, user_id="spike", today=HOY))
    await puente.start(prompt)
    print(f"\n── sonda {nombre} ─────────────────────────────────")
    print(f"› «{frase}»")
    await puente.send_text(frase)

    llamadas: list[str] = []
    dijo: list[str] = []

    async def leer() -> None:
        async for evento in puente.events():
            if evento.kind == "tool_call":
                n = evento.payload.get("toolName") or evento.payload.get("name")
                llamadas.append(str(n))
                print(f"  [herramienta] {n}  {evento.payload.get('content')}")
            elif evento.kind == "transcript" and evento.payload.get("role") != "USER":
                dijo.append(evento.payload["text"])
            elif evento.kind == "error":
                print("  [error]", evento.payload)
                return
            elif evento.kind == "turn_end":
                # Tras un toolResult viene otro turno con la respuesta ya
                # informada, así que sólo se corta cuando el coach ha hablado.
                if dijo:
                    return

    try:
        await asyncio.wait_for(leer(), timeout=60)
    except TimeoutError:
        print("  [tiempo agotado]")
    finally:
        await puente.close()
        await engine.dispose()

    texto = " ".join(dijo)
    print(f"› dijo: {texto[:300] or '(nada)'}")
    print(f"› herramientas: {llamadas or 'ninguna'}")
    return llamadas, texto


async def main() -> int:
    ensure_aws_credentials()
    fallos = []

    llamadas, _ = await sonda("A · consulta con contexto", "¿qué me toca hoy?", completo=True)
    if "get_today_session" not in llamadas:
        fallos.append("A: no consultó la sesión de hoy")

    llamadas, texto = await sonda(
        "B · plan sin contexto", "quiero correr un maratón, ármame el plan", completo=False
    )
    if "create_plan" in llamadas:
        fallos.append("B: generó un plan de maratón sin saber si la persona corre")
    if "?" not in texto:
        fallos.append("B: no preguntó nada")

    print("\n" + "=" * 52)
    if fallos:
        for f in fallos:
            print("FALLA ·", f)
        return 1
    print("OK · el bucle funciona y la clarificación autónoma se sostiene")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
