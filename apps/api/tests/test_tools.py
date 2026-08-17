"""Las herramientas del coach.

Son la única vía por la que una cifra llega a la boca del coach, así que lo que
se prueba aquí no es tanto que devuelvan datos como que **se nieguen cuando
toca**: en rojo no prescriben, sin contexto no generan plan, y con un
identificador inventado no devuelven algo plausible.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from apps.api.clarification import VITAL_FIELDS, missing_vital_context
from apps.api.db.models import Base
from apps.api.tools import CoachTools

HOY = date(2026, 8, 15)


@pytest_asyncio.fixture
async def db() -> AsyncSession:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    async with async_sessionmaker(engine, expire_on_commit=False)() as sesion:
        yield sesion
    await engine.dispose()


@pytest_asyncio.fixture
async def tools(db: AsyncSession) -> CoachTools:
    return CoachTools(db, today=HOY)


async def _con_perfil(tools: CoachTools, **cambios: object) -> None:
    campos: dict[str, object] = {
        "level": "intermedio",
        "weekly_volume_km": 30.0,
        "longest_run_km": 12.0,
        "days_per_week": 4,
        "injuries": [],
        "reference_distance_km": 10.0,
        "reference_time_sec": 3000,
    }
    await tools.profiles.save("u1", **{**campos, **cambios})


# ── el pivote · sin contexto no hay plan ─────────────────────────────


async def test_sin_perfil_no_genera_plan_de_maraton(tools: CoachTools) -> None:
    """⭐ El pivote hecho código.

    Si el prompt falla y el modelo intenta generar el plan igual, la
    herramienta no se lo permite. El prompt le dice que pregunte; esto hace que
    no pueda hacer otra cosa.
    """
    r = await tools.create_plan("u1", distance="42k")
    assert r["ok"] is False
    assert r["needs_context"] == list(VITAL_FIELDS)
    assert "peak_volume_km" not in r
    assert "weeks" not in r


async def test_al_negarse_entrega_la_pregunta_ya_redactada(tools: CoachTools) -> None:
    """No basta con decir «falta contexto»: hay que dar la siguiente frase."""
    r = await tools.create_plan("u1", distance="42k")
    assert r["next_question"] == "¿Cuántos kilómetros corres a la semana ahorita?"
    assert len(r["ask"]) == len(VITAL_FIELDS)


async def test_pregunta_primero_por_lo_mas_importante(tools: CoachTools) -> None:
    await tools.profiles.save("u1", weekly_volume_km=30.0)
    r = await tools.create_plan("u1", distance="42k")
    assert r["needs_context"][0] == "injuries"


async def test_no_vuelve_a_preguntar_lo_que_ya_sabe(tools: CoachTools) -> None:
    await _con_perfil(tools)
    r = await tools.create_plan("u1", distance="21k")
    assert r["ok"] is True
    assert "needs_context" not in r


async def test_correr_cero_es_una_respuesta_no_un_hueco(tools: CoachTools) -> None:
    """`0` y `None` dicen cosas distintas.

    Un principiante absoluto respondió «cero», y eso es contexto completo. Si
    el sistema no supiera distinguirlo de «no se lo preguntamos», le
    preguntaría para siempre.
    """
    await _con_perfil(tools, weekly_volume_km=0.0, longest_run_km=0.0)
    r = await tools.create_plan("u1", distance="5k")
    assert r["ok"] is True


async def test_con_contexto_completo_el_plan_sale_del_motor(tools: CoachTools) -> None:
    await _con_perfil(tools)
    r = await tools.create_plan("u1", distance="21k")
    assert r["source"] == "coach_domain.plans.build_plan"
    assert r["weeks"] == 12
    assert r["first_week_km"] == 30.0


# ── R7 · negociar, no sólo negar ─────────────────────────────────────


async def test_sin_semanas_suficientes_ofrece_alternativas(tools: CoachTools) -> None:
    await _con_perfil(tools)
    r = await tools.create_plan("u1", distance="42k", race_date="2026-11-20")
    assert r["ok"] is False
    assert r["rule"] == "R7"
    assert "21k" in r["alternatives"]
    assert r["weeks_available"] < r["weeks_needed"]


async def test_una_distancia_que_no_preparamos_se_rechaza(tools: CoachTools) -> None:
    await _con_perfil(tools)
    r = await tools.create_plan("u1", distance="100k")
    assert r["ok"] is False
    assert "5k" in r["valid"]


# ── rojo no prescribe ────────────────────────────────────────────────


async def test_en_rojo_la_sesion_de_hoy_no_trae_numeros(tools: CoachTools) -> None:
    await _con_perfil(tools)
    await tools.create_plan("u1", distance="21k")
    await tools.report_wellness("u1", pain_score=7, pain_area="tibia")

    r = await tools.get_today_session("u1")
    assert r["allows_prescription"] is False
    assert "distance_km" not in r
    assert "pace" not in r
    assert r["referral_message"]


async def test_en_rojo_tampoco_se_ajusta_el_plan(tools: CoachTools) -> None:
    await _con_perfil(tools)
    await tools.create_plan("u1", distance="21k")
    await tools.report_wellness("u1", pain_score=0, flags=["chest_pain"])

    r = await tools.adjust_plan("u1", reason="quiero subirle")
    assert r["allows_prescription"] is False
    assert "first_week_km" not in r


async def test_una_bandera_roja_con_dolor_cero_tambien_bloquea(tools: CoachTools) -> None:
    """La bandera describe un mecanismo, no una intensidad."""
    await _con_perfil(tools)
    await tools.create_plan("u1", distance="21k")
    r = await tools.report_wellness("u1", pain_score=0, flags=["altered_gait"])
    assert r["allows_prescription"] is False


async def test_en_ambar_se_entrena_pero_recortado(db: AsyncSession) -> None:
    # Domingo: el día de la tirada larga, que es donde el recorte se nota.
    herramientas = CoachTools(db, today=date(2026, 8, 16))
    await _con_perfil(herramientas)
    await herramientas.create_plan("u1", distance="21k")

    normal = await herramientas.get_today_session("u1")
    assert normal["kind"] == "largo"

    await herramientas.report_wellness("u1", pain_score=4, pain_area="rodilla")
    r = await herramientas.get_today_session("u1")
    assert r["ok"] is True
    assert r["safety_level"] == "amber"
    assert r["kind"] == "suave"  # sin trabajo de calidad
    assert r["distance_km"] < normal["distance_km"]


async def test_el_veredicto_queda_registrado_como_decision(tools: CoachTools) -> None:
    await _con_perfil(tools)
    await tools.report_wellness("u1", pain_score=6)
    decisiones = await tools.logs.decisions("u1")
    assert any(d.rule == "SAFETY" for d in decisiones)


# ── los números salen del motor ──────────────────────────────────────


async def test_log_run_calcula_el_ritmo_con_el_motor(tools: CoachTools) -> None:
    r = await tools.log_run("u1", distance_km=8.42, duration_sec=2838, rpe=5)
    assert r["pace_formatted"] == "5:37"
    assert r["source"] == "coach_domain.paces.pace_from_run"


async def test_toda_herramienta_declara_de_donde_salio_su_cifra(tools: CoachTools) -> None:
    """`source` es lo que hace auditable «esta cifra no la inventó el modelo»."""
    await _con_perfil(tools)
    resultados = [
        await tools.create_plan("u1", distance="21k"),
        await tools.get_week_context("u1"),
        await tools.log_run("u1", distance_km=8.0, duration_sec=2700),
        await tools.report_wellness("u1", pain_score=0),
        await tools.explain_technique_cue("cadencia-incremento"),
        await tools.environment_check(temp_c=33.0),
    ]
    for r in resultados:
        assert r["source"].startswith(("coach_domain.", "apps.api.")), r


async def test_el_contexto_de_semana_trae_los_volumenes_reales(tools: CoachTools) -> None:
    await _con_perfil(tools)
    await tools.create_plan("u1", distance="21k")
    await tools.logs.add_session(
        "u1", occurred_on=HOY - timedelta(days=2), distance_km=10.0, duration_sec=3300
    )
    r = await tools.get_week_context("u1")
    assert r["week_index"] == 1
    assert r["total_weeks"] == 12
    assert r["recent_weekly_km"][-1] == 10.0


# ── técnica ──────────────────────────────────────────────────────────


async def test_explicar_una_senal_inventada_no_devuelve_algo_plausible(
    tools: CoachTools,
) -> None:
    """El identificador lo eligió el modelo. Uno inventado tiene que fallar."""
    r = await tools.explain_technique_cue("respiracion-cuantica")
    assert r["ok"] is False
    assert "no existe" in r["reason"]


async def test_sin_cadencia_base_no_se_inventa_un_objetivo(tools: CoachTools) -> None:
    await _con_perfil(tools)
    r = await tools.get_target_cadence("u1")
    assert r["ok"] is False
    assert r["needs_field"] == "base_cadence_spm"
    assert "target_spm" not in r
    assert "30 segundos" in r["question"]


async def test_con_cadencia_base_el_objetivo_es_relativo(tools: CoachTools) -> None:
    await _con_perfil(tools, base_cadence_spm=160)
    r = await tools.get_target_cadence("u1", weeks_worked=0)
    assert r["target_spm"] == 168
    assert r["target_spm"] != 180


# ── R6 · volver tras una pausa ───────────────────────────────────────


async def test_tras_nueve_dias_parado_el_plan_vuelve_recortado(tools: CoachTools) -> None:
    await _con_perfil(tools)
    await tools.create_plan("u1", distance="21k")
    await tools.logs.add_session(
        "u1", occurred_on=HOY - timedelta(days=9), distance_km=10.0, duration_sec=3300
    )

    r = await tools.adjust_plan("u1", reason="volví de un viaje")
    assert r["ok"] is True
    assert r["return_factor"] == 0.75
    assert r["first_week_km"] < 30.0
    assert "R6" in r["rationale"]


async def test_tras_dos_meses_hay_que_replanificar_desde_cero(tools: CoachTools) -> None:
    await _con_perfil(tools)
    await tools.create_plan("u1", distance="21k")
    await tools.logs.add_session(
        "u1", occurred_on=HOY - timedelta(days=60), distance_km=10.0, duration_sec=3300
    )

    r = await tools.adjust_plan("u1", reason="me reincorporo")
    assert r["ok"] is False
    assert r["needs_replan"] is True
    assert r["rule"] == "R6"


# ── sin plan ─────────────────────────────────────────────────────────


async def test_sin_plan_la_sesion_de_hoy_lo_dice(tools: CoachTools) -> None:
    r = await tools.get_today_session("u1")
    assert r["ok"] is False
    assert r["needs_plan"] is True


async def test_un_dia_de_descanso_se_explica_como_parte_del_plan(db: AsyncSession) -> None:
    """Que el descanso sea parte del plan es doctrina, no relleno."""
    lunes = date(2026, 8, 17)  # con 2 días/semana no hay sesión el lunes
    herramientas = CoachTools(db, today=lunes)
    await _con_perfil(herramientas, days_per_week=2)
    await herramientas.create_plan("u1", distance="10k")

    r = await herramientas.get_today_session("u1")
    assert r["ok"] is True
    assert r["rest_day"] is True
    assert "descanso" in r["message"].lower()


# ── R8 · ambiente ────────────────────────────────────────────────────


async def test_el_calor_afloja_el_ritmo(tools: CoachTools) -> None:
    r = await tools.environment_check(temp_c=33.0)
    assert r["pace_adjustment_sec"] == 35
    assert not r["move_indoors"]


async def test_el_aire_malo_manda_a_interior(tools: CoachTools) -> None:
    r = await tools.environment_check(temp_c=20.0, aqi=180)
    assert r["move_indoors"] is True


@pytest.mark.parametrize("temperatura", [15.0, 22.0, 28.0])
async def test_en_condiciones_normales_no_se_ajusta_nada(
    tools: CoachTools, temperatura: float
) -> None:
    r = await tools.environment_check(temp_c=temperatura)
    assert r["pace_adjustment_sec"] == 0


# ── el bucle infinito del onboarding ─────────────────────────────────
#
# El fallo: el corredor contaba sus siete kilómetros semanales, el modelo lo
# entendía, llamaba a `create_plan`, la base seguía vacía —NINGUNA herramienta
# sabía escribir en el perfil— y la herramienta devolvía las cuatro preguntas.
# Y el modelo las repetía. Para siempre.
#
# Lo que se prueba aquí es que lo dicho en voz alta ES el dato: entra por
# `create_plan` y se persiste ANTES de validar nada.


@pytest.mark.asyncio
async def test_lo_dicho_hablando_genera_el_plan_en_el_mismo_turno(db: AsyncSession) -> None:
    """El caso exacto que reportaba el bucle: 7 km/semana, 4 de tirada, 7:00.

    Se parte de un perfil con SÓLO la meta — ni siquiera los días por semana —
    porque así llega alguien que acaba de registrarse. Los cinco campos vitales
    entran por la conversación, en una llamada.
    """
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save("u1", goal_distance="10k")

    resultado = await herramientas.create_plan(
        "u1",
        distance="10k",
        weekly_volume_km=7.0,
        longest_run_km=4.0,
        reference_pace="7:00",
        injuries=[],
        days_per_week=3,
    )

    assert resultado["ok"] is True, resultado
    assert resultado["weeks"] > 0


@pytest.mark.asyncio
async def test_lo_dicho_queda_guardado_en_el_perfil(db: AsyncSession) -> None:
    """No basta con que funcione este turno: el dato tiene que sobrevivir.

    Si sólo se usara en memoria, la siguiente sesión volvería a preguntar y el
    bucle reaparecería un día después en vez de al instante.
    """
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save("u1", goal_distance="10k", days_per_week=3)

    await herramientas.create_plan(
        "u1",
        distance="10k",
        weekly_volume_km=7.0,
        longest_run_km=4.0,
        reference_pace="7:00",
        injuries=[],
    )

    contexto = await herramientas.profiles.context("u1")
    assert contexto is not None
    assert contexto["weekly_volume_km"] == 7.0
    assert contexto["longest_run_km"] == 4.0
    assert contexto["injuries"] == []
    # Y ya no falta nada: la próxima llamada no vuelve a preguntar.
    assert missing_vital_context(contexto) == []


@pytest.mark.asyncio
async def test_la_lista_vacia_de_molestias_es_una_respuesta(db: AsyncSession) -> None:
    """«No tengo molestias» tiene que contar como contestado.

    Si `[]` se tratara como ausencia, `missing_vital_context` seguiría pidiendo
    `injuries` y el bucle se mantendría por ese único campo.
    """
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save("u1", goal_distance="10k", days_per_week=3)

    await herramientas.create_plan(
        "u1",
        distance="10k",
        weekly_volume_km=7.0,
        longest_run_km=4.0,
        reference_pace="7:00",
        injuries=[],
    )
    contexto = await herramientas.profiles.context("u1")
    assert "injuries" not in missing_vital_context(contexto)


@pytest.mark.asyncio
async def test_el_ritmo_se_ancla_en_la_tirada_mas_larga(db: AsyncSession) -> None:
    """4 km a 7:00 se guardan como una referencia de 4 km en 28 minutos."""
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save("u1", goal_distance="10k", days_per_week=3)

    await herramientas.create_plan(
        "u1",
        distance="10k",
        weekly_volume_km=7.0,
        longest_run_km=4.0,
        reference_pace="7:00",
        injuries=[],
    )
    contexto = await herramientas.profiles.context("u1")
    assert contexto["reference_distance_km"] == 4.0
    assert contexto["reference_time_sec"] == 7 * 60 * 4


@pytest.mark.asyncio
async def test_un_ritmo_ilegible_no_tumba_el_turno(db: AsyncSession) -> None:
    """Se ignora y se vuelve a pedir, en vez de reventar a media conversación."""
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save("u1", goal_distance="10k", days_per_week=3)

    resultado = await herramientas.create_plan(
        "u1",
        distance="10k",
        weekly_volume_km=7.0,
        longest_run_km=4.0,
        reference_pace="siete minutos por kilo",
        injuries=[],
    )

    assert resultado["ok"] is False
    assert "reference_pace" in resultado["needs_context"]


@pytest.mark.asyncio
async def test_lo_que_no_se_menciona_no_borra_lo_que_ya_habia(db: AsyncSession) -> None:
    """`None` es «el modelo no lo mencionó», no «el corredor dijo que no».

    Sobrescribir con nulo borraría lo que el carrusel ya capturó, y el corredor
    vería desaparecer datos que él mismo escribió hace un minuto.
    """
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save(
        "u1", goal_distance="10k", days_per_week=3, longest_run_km=12.0, injuries=["rodilla"]
    )

    await herramientas.create_plan("u1", distance="10k", weekly_volume_km=20.0)

    contexto = await herramientas.profiles.context("u1")
    assert contexto["longest_run_km"] == 12.0
    assert contexto["injuries"] == ["rodilla"]


@pytest.mark.asyncio
async def test_sin_contexto_sigue_negandose(db: AsyncSession) -> None:
    """El canal por el que llega el dato se amplía; el listón no baja."""
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save("u1", goal_distance="42k")

    resultado = await herramientas.create_plan("u1", distance="42k")

    assert resultado["ok"] is False
    assert "weekly_volume_km" in resultado["needs_context"]


@pytest.mark.asyncio
async def test_el_plan_recien_creado_dice_que_toca_hoy(db: AsyncSession) -> None:
    """La respuesta trae `today` resuelto, para que el modelo no lo deduzca.

    Sin esto tenía `first_week_km: 8.0` y tres días por semana, y dividía: dijo
    «2 km» en una corrida y «3 km» en otra con la misma entrada. Una cifra que
    ningún motor produjo — y en un día que además era de descanso.

    No se arregla instruyendo al modelo: se arregla quitándole el motivo.
    """
    herramientas = CoachTools(db, today=HOY)
    await herramientas.profiles.save("u1", goal_distance="10k")

    resultado = await herramientas.create_plan(
        "u1",
        distance="10k",
        weekly_volume_km=7.0,
        longest_run_km=4.0,
        reference_pace="7:00",
        injuries=[],
        days_per_week=3,
    )

    assert resultado["ok"] is True
    hoy = resultado["today"]
    assert hoy is not None
    # O es descanso, o trae la distancia del motor. Nunca «deduzca usted».
    assert hoy.get("rest_day") is True or "distance_km" in hoy
