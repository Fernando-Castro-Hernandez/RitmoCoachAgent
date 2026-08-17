"""Siembra la cuenta de demostración.

Crea `demo@adivor.com` / `password123` con una historia coherente detrás:
Fernando, semana 7 de 16 hacia un maratón, con una molestia leve en la rodilla
reportada ayer.

## Por qué esos datos y no otros

El estado que se siembra es **ámbar**, no verde y no rojo, y es la decisión que
hace que la demo valga:

- En **verde** el coach se ve como cualquier chatbot que da entrenamientos.
- En **rojo** la pantalla se anula entera y ya no se ve el producto normal.
- En **ámbar** se ve lo único que ningún otro entregable va a enseñar: el motor
  recortando la sesión de hoy por una molestia de 3, con la razón escrita al
  lado. Y basta con reportar un día más de la misma molestia para que escale a
  rojo en vivo, delante de quien mira.

La semana 7 de 16 tampoco es arbitraria: hay historial detrás para que
`get_week_context` y la progresión tengan de dónde salir, y quedan semanas por
delante para que el plan siga teniendo futuro que enseñar.

## Lo que este script NO hace

No inventa el plan. Lo genera `build_plan` como para cualquier otro corredor, y
las sesiones registradas salen de él. Si sembrara un plan a mano, la demo
enseñaría números que el motor nunca produjo — que es exactamente lo que el
producto promete no hacer.

Uso:
    PYTHONPATH="$PWD;$PWD/packages" uv run python scripts/seed_demo.py
    ... --reset   borra la cuenta y la vuelve a crear
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ), str(RAIZ / "packages")]

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

EMAIL = "demo@adivor.com"
PASSWORD = "password123"

SEMANA_ACTUAL = 7
SEMANAS_TOTALES = 16


def _inicio_con_sesion_hoy(inicio: date, hoy: date) -> date:
    """Desplaza el arranque del plan para que hoy toque entrenar.

    Devuelve el primer desplazamiento de 0 a 6 días que lo consigue, o el
    original si ninguno lo hace — un plan sin sesión ningún día de la semana no
    existe, pero no se cuelga por ello.
    """
    from coach_domain.plans import build_plan
    from coach_domain.types import AthleteProfile, Level, RaceDistance

    from apps.api.automation import session_on

    tanteo = AthleteProfile(
        user_id="tanteo",
        level=Level.INTERMEDIO,
        weekly_volume_km=42.0,
        longest_run_km=24.0,
        days_per_week=6,
        reference_distance_km=10.0,
        reference_time_sec=2820,
    )
    for dias in range(7):
        candidato = inicio - timedelta(days=dias)
        plan = build_plan(
            tanteo, RaceDistance.K42, candidato + timedelta(weeks=SEMANAS_TOTALES), candidato
        )
        if session_on(plan, hoy) is not None:
            return candidato
    return inicio


def _sesion_de_hoy(plan: object, hoy: date) -> object:
    from apps.api.automation import session_on

    return session_on(plan, hoy)  # type: ignore[arg-type]


async def sembrar(reset: bool) -> int:
    from coach_domain.plans import build_plan
    from coach_domain.types import AthleteProfile, Level, RaceDistance
    from sqlalchemy import delete, select

    from apps.api.auth import hash_password, normalizar_email, nuevo_user_id
    from apps.api.db.models import (
        AthleteProfileRow,
        CoachDecisionRow,
        ConversationMemoryRow,
        SessionLogRow,
        TrainingStateRow,
        UserRow,
        WellnessLogRow,
    )
    from apps.api.db.repo import LogRepo, ProfileRepo, StateRepo
    from apps.api.db.session import get_sessionmaker

    hoy = date.today()
    # El plan arrancó hace seis semanas para caer en la séptima.
    inicio = hoy - timedelta(weeks=SEMANA_ACTUAL - 1)
    inicio -= timedelta(days=inicio.weekday())

    # Y se busca un arranque con el que HOY caiga en un día de entrenamiento.
    #
    # Ojo con lo que hace y lo que no. Mover el arranque **no cambia qué días de
    # la semana tienen sesión**: `session_on` compara contra el día absoluto, así
    # que el martes es martes se empiece cuando se empiece. Lo que sí cambia es
    # **en qué semana del plan cae hoy**, y las semanas no son iguales entre sí
    # —una de descarga entrena menos días—, así que desplazar sirve para casi
    # todos los días. Escribí este comentario al revés la primera vez y sólo
    # probándolo día a día se vio.
    #
    # Importa porque el ámbar sólo se aprecia con una sesión delante, recortada
    # y con su porqué. Un «hoy descansas» es correcto y no enseña nada.
    inicio = _inicio_con_sesion_hoy(inicio, hoy)
    carrera = inicio + timedelta(weeks=SEMANAS_TOTALES)

    async with get_sessionmaker()() as db:
        existente = (
            (await db.execute(select(UserRow).where(UserRow.email == normalizar_email(EMAIL))))
            .scalars()
            .first()
        )

        if existente and not reset:
            print(f"La cuenta {EMAIL} ya existe. Usa --reset para rehacerla.")
            return 0

        if existente:
            # En orden: lo que referencia primero. La bitácora sólo se anexa
            # desde la API a propósito, así que esto se hace con SQL directo y
            # se queda aquí — un script de siembra no es la aplicación.
            uid = existente.id
            for tabla in (
                TrainingStateRow,
                SessionLogRow,
                WellnessLogRow,
                CoachDecisionRow,
                ConversationMemoryRow,
            ):
                await db.execute(delete(tabla).where(tabla.user_id == uid))
            await db.execute(delete(AthleteProfileRow).where(AthleteProfileRow.user_id == uid))
            await db.execute(delete(UserRow).where(UserRow.id == uid))
            await db.commit()
            print(f"Borrada la cuenta anterior de {EMAIL}.")

        user_id = nuevo_user_id()
        db.add(
            UserRow(
                id=user_id,
                email=normalizar_email(EMAIL),
                hashed_password=hash_password(PASSWORD),
                created_at=datetime.now(UTC),
            )
        )
        await db.flush()

        # ── el perfil, completo: la demo no arranca en el carrusel ──
        await ProfileRepo(db).save(
            user_id,
            level="intermedio",
            goal_distance="42k",
            race_date=carrera,
            days_per_week=6,
            age=27,
            weight_kg=72.0,
            height_cm=178.0,
            reference_distance_km=10.0,
            reference_time_sec=2820,  # 47:00, ritmo de 4:42
            timezone="America/Mexico_City",
            weekly_volume_km=42.0,
            longest_run_km=24.0,
            base_cadence_spm=168,
            injuries=[],
            motivation="Terminar mi primer maratón sin caminar.",
            practical_problems="Corro antes de entrar a trabajar, a las 6.",
        )

        # ── el plan, generado por el motor ──
        perfil = AthleteProfile(
            user_id=user_id,
            level=Level.INTERMEDIO,
            weekly_volume_km=42.0,
            longest_run_km=24.0,
            days_per_week=6,
            reference_distance_km=10.0,
            reference_time_sec=2820,
        )
        plan = build_plan(perfil, RaceDistance.K42, carrera, inicio)
        estado = await StateRepo(db).apply(user_id, plan, reason="plan inicial de maratón")
        estado.current_week = SEMANA_ACTUAL

        # ── seis semanas de bitácora, sacadas del plan ──
        registro = LogRepo(db)
        sesiones = 0
        for semana in plan.weeks[: SEMANA_ACTUAL - 1]:
            for s in sorted(semana.sessions, key=lambda x: x.day_of_week):
                cuando = semana.start_date + timedelta(days=s.day_of_week)
                if cuando >= hoy:
                    continue
                # El ritmo lo calcula el motor a partir de distancia y tiempo:
                # aquí sólo se elige un tiempo plausible para la sesión.
                objetivo = s.pace.min_sec_per_km if s.pace else 330
                await registro.add_session(
                    user_id,
                    occurred_on=cuando,
                    distance_km=s.distance_km,
                    duration_sec=int(s.distance_km * (objetivo + 4)),
                    rpe=6 if s.kind == "largo" else 5,
                    notes="",
                    source="voice",
                )
                sesiones += 1

        # ── la molestia de ayer: ámbar, no rojo ──
        await registro.add_wellness(
            user_id,
            occurred_on=hoy - timedelta(days=1),
            pain_score=3,
            pain_area="rodilla derecha, por fuera",
            flags=[],
            sleep_hours=7.0,
        )
        await registro.add_decision(
            user_id,
            rule="R5",
            rationale=(
                "molestia de 3 en rodilla el primer día: se recorta la sesión y "
                "se pregunta mañana antes de volver a calidad"
            ),
        )

        await db.commit()

    veredicto = None
    async with get_sessionmaker()() as db:
        from apps.api.db.repo import LogRepo as _Log

        veredicto = await _Log(db).current_safety(user_id, hoy)

    print(f"\nCuenta lista: {EMAIL} / {PASSWORD}")
    print(f"  plan          maratón, semana {SEMANA_ACTUAL} de {len(plan.weeks)}")
    print(f"  carrera       {carrera.isoformat()}")
    print(f"  bitácora      {sesiones} sesiones registradas")
    print(f"  puerta        {veredicto.level.value.upper()} — {veredicto.reason}")

    hoy_toca = _sesion_de_hoy(plan, hoy)
    if hoy_toca is None:
        # El lunes es descanso en TODAS las semanas de esta plantilla, y no hay
        # desplazamiento que lo arregle. Se dice en voz alta en vez de dejar que
        # alguien grabe el vídeo y descubra la pantalla de descanso al montarlo.
        print(
            "\n  AVISO: hoy es día de DESCANSO en el plan, así que la hoja NO\n"
            "  enseñará la sesión recortada en ámbar. Es correcto, pero para el\n"
            "  vídeo conviene grabar otro día: el lunes descansa siempre."
        )
    else:
        print(f"  hoy toca      {hoy_toca.kind}, {hoy_toca.distance_km:g} km antes del recorte")

    print(
        "\nPara la demo: reportar la misma molestia dos días más la escala a "
        "ROJO en vivo,\ny la hoja se anula delante de quien esté mirando."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Siembra la cuenta de demostración")
    parser.add_argument("--reset", action="store_true", help="borra la cuenta y la rehace")
    args = parser.parse_args()
    return asyncio.run(sembrar(args.reset))


if __name__ == "__main__":
    sys.exit(main())
