"""Sonda: ¿se acabó el bucle del onboarding?

Reproduce el caso reportado, y lo hace en DOS turnos porque el bucle sólo se ve
en el segundo.

  turno 1 · el corredor da cuatro de los cinco datos vitales. Falta a propósito
            los días por semana, así que el coach TIENE que preguntar algo — y
            se comprueba que pregunta UNA cosa nueva, no el cuestionario entero.
  turno 2 · contesta esa pregunta. Si el plan sale aquí, el bucle está roto. Si
            vuelve a preguntar lo del turno 1, no lo está.

Es lo único que no se puede saber sin salir a la red: las pruebas unitarias
demuestran que la herramienta persiste y genera, pero no que el modelo le pase
lo que le contaron.

Uso:
  PYTHONPATH="$PWD;$PWD/packages" uv run python scripts/spike_onboarding.py
"""

from __future__ import annotations

import asyncio
import re
import sys
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ), str(RAIZ / "packages")]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

TURNOS = [
    (
        "Quiero preparar un 10K. Corro 7 kilómetros a la semana, mi tirada más "
        "larga han sido 4 kilómetros, voy a 7 minutos por kilómetro y no tengo "
        "ninguna molestia."
    ),
    "Tres días a la semana.",
]

# Lo que el corredor ya contó en el turno 1. Si el coach lo vuelve a preguntar
# en el turno 2, eso ES el bucle.
YA_CONTESTADO = (
    "kilómetros a la semana",
    "cuánto corres",
    "tirada más larga",
    "distancia más larga",
    "molestia",
    "lesión",
)

# «1.» o «2.» abriendo una frase.
LISTA_NUMERADA = re.compile(r"(^|[\n.!?]\s*)\d\s*[.)]\s")


async def main() -> int:
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from apps.api.bridge import NovaBridge
    from apps.api.credentials import ensure_aws_credentials
    from apps.api.db.models import Base
    from apps.api.db.repo import ProfileRepo
    from apps.api.session_context import build_prompt_for
    from apps.api.tool_runner import ToolRunner

    ensure_aws_credentials()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as c:
        await c.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)

    # Perfil vacío salvo la meta: el punto de partida exacto del bucle.
    async with fabrica() as db:
        await ProfileRepo(db).save("sonda", goal_distance="10k")
        await db.commit()
        prompt = await build_prompt_for(db, "sonda", today=date.today())

    ejecutor = ToolRunner(fabrica, user_id="sonda", today=date.today())
    llamadas: list[tuple[str, dict]] = []
    resultados: list[dict] = []

    class Espia:
        async def run(self, name: str, arguments: dict) -> dict:
            llamadas.append((name, arguments))
            salida = await ejecutor.run(name, arguments)
            resultados.append(salida)
            return salida

    puente = NovaBridge(tool_runner=Espia())
    await puente.start(prompt)

    dichos: list[str] = []

    async def un_turno(frase: str) -> str:
        print(f"\n› corredor: «{frase}»")
        antes = len(dichos)
        await puente.send_text(frase)

        async def leer() -> None:
            async for ev in puente.events():
                if ev.kind == "tool_call":
                    print("  [herramienta]", ev.payload.get("toolName"), ev.payload.get("content"))
                elif ev.kind == "transcript" and ev.payload.get("role") != "USER":
                    dichos.append(ev.payload["text"])
                elif ev.kind == "error":
                    print("  [error]", ev.payload)
                    return
                elif ev.kind == "turn_end" and len(dichos) > antes:
                    return

        try:
            await asyncio.wait_for(leer(), timeout=70)
        except TimeoutError:
            print("  [tiempo agotado]")
        texto = " ".join(dichos[antes:])
        print(f"  coach: {texto[:320]}")
        return texto

    try:
        primero = await un_turno(TURNOS[0])
        segundo = await un_turno(TURNOS[1])
    finally:
        await puente.close()
        await engine.dispose()

    print(f"\n› herramientas: {[n for n, _ in llamadas] or 'ninguna'}")

    fallos: list[str] = []
    planes = [a for n, a in llamadas if n == "create_plan"]
    if not planes:
        fallos.append("nunca llamó a create_plan")
    elif planes[0].get("weekly_volume_km") is None:
        fallos.append(f"no le pasó lo que le contaron: {planes[0]}")

    if not any(r.get("ok") for r in resultados):
        faltas = [r.get("needs_context") for r in resultados]
        fallos.append(f"el plan nunca se generó; faltaba: {faltas}")

    repetidas = [p for p in YA_CONTESTADO if p in segundo.lower()]
    if repetidas:
        fallos.append(f"EL BUCLE: volvió a preguntar lo ya contestado {repetidas}")

    for etiqueta, texto in (("turno 1", primero), ("turno 2", segundo)):
        if LISTA_NUMERADA.search(texto):
            fallos.append(f"lista numerada en el {etiqueta}")

    print()
    if fallos:
        for f in fallos:
            print("FALLA ·", f)
        return 1
    print("OK · el plan sale sin repetir preguntas y sin listas numeradas")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
