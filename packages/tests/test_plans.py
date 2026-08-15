"""Generación de planes.

Aquí se junta todo el motor. La prueba que importa es la última: **ningún plan
que el motor genere puede violar una regla**. Si esa propiedad se sostiene sobre
cientos de perfiles generados, «entrenamiento seguro» deja de ser una promesa
del prompt y pasa a ser una afirmación verificable.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from coach_domain.plans import (
    InsufficientFrequencyError,
    InsufficientTimeError,
    build_plan,
    max_weeks,
    min_weeks,
)
from coach_domain.progression import (
    LONG_RUN_MAX_SHARE,
    previous_reference,
    validate_week,
)
from coach_domain.types import AthleteProfile, Level, RaceDistance
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

HOY = date(2026, 8, 14)


def _perfil(**cambios: object) -> AthleteProfile:
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


# ── R7 · prerrequisito de meta ───────────────────────────────────────


def test_r7_el_maraton_exige_al_menos_dieciseis_semanas() -> None:
    assert min_weeks(RaceDistance.K42) >= 16
    assert min_weeks(RaceDistance.K21) >= 12
    assert min_weeks(RaceDistance.K5) >= 8


def test_r7_rechaza_una_meta_sin_semanas_suficientes() -> None:
    """Tres semanas para un maratón no se negocian con voluntad."""
    with pytest.raises(InsufficientTimeError):
        build_plan(_perfil(), RaceDistance.K42, race_date=date(2026, 9, 1), today=HOY)


def test_r7_el_error_trae_con_que_negociar() -> None:
    """No basta con decir «no». El coach tiene que ofrecer una salida."""
    with pytest.raises(InsufficientTimeError) as exc:
        build_plan(_perfil(), RaceDistance.K42, race_date=date(2026, 10, 1), today=HOY)
    error = exc.value
    assert error.weeks_available < error.weeks_needed
    assert error.alternatives, "tiene que proponer algo, no sólo negar"


def test_r7_propone_una_distancia_que_si_cabe() -> None:
    with pytest.raises(InsufficientTimeError) as exc:
        build_plan(_perfil(), RaceDistance.K42, race_date=date(2026, 11, 20), today=HOY)
    assert RaceDistance.K21 in exc.value.alternatives


def test_r7_con_tiempo_justo_si_construye() -> None:
    carrera = HOY + timedelta(weeks=min_weeks(RaceDistance.K21))
    plan = build_plan(_perfil(), RaceDistance.K21, race_date=carrera, today=HOY)
    assert len(plan.weeks) == min_weeks(RaceDistance.K21)


def test_sin_fecha_de_carrera_usa_la_duracion_minima() -> None:
    """Entrenar sin carrera apuntada es un caso real y válido."""
    plan = build_plan(_perfil(), RaceDistance.K10, race_date=None, today=HOY)
    assert len(plan.weeks) == min_weeks(RaceDistance.K10)
    assert plan.race_date is None


def test_un_plan_larguisimo_se_recorta_al_maximo_util() -> None:
    """Cuarenta semanas para un 5K no es más entrenamiento, es más aburrimiento."""
    carrera = date(2027, 6, 1)
    plan = build_plan(_perfil(), RaceDistance.K5, race_date=carrera, today=HOY)
    assert len(plan.weeks) == max_weeks(RaceDistance.K5)


def test_una_fecha_en_el_pasado_es_un_error() -> None:
    with pytest.raises(InsufficientTimeError):
        build_plan(_perfil(), RaceDistance.K10, race_date=date(2026, 1, 1), today=HOY)


# ── frecuencia mínima ────────────────────────────────────────────────


def test_correr_un_dia_a_la_semana_no_da_para_un_plan() -> None:
    """Con un solo día, la tirada larga sería el 100 % del volumen (R3).

    En vez de fabricar un plan que incumple sus propias reglas, se negocia:
    es el mismo patrón que R7.
    """
    with pytest.raises(InsufficientFrequencyError):
        build_plan(_perfil(days_per_week=1), RaceDistance.K10, None, HOY)


def test_dos_dias_ya_alcanzan() -> None:
    plan = build_plan(_perfil(days_per_week=2), RaceDistance.K10, None, HOY)
    assert all(len(s.sessions) == 2 for s in plan.weeks)


# ── forma del plan ───────────────────────────────────────────────────


def test_el_plan_arranca_en_el_volumen_actual_del_corredor() -> None:
    """Nunca en el volumen que le gustaría tener."""
    plan = build_plan(_perfil(weekly_volume_km=30.0), RaceDistance.K21, None, HOY)
    assert plan.weeks[0].load.total_km == pytest.approx(30.0, abs=0.1)


def test_el_taper_baja_el_volumen_al_final() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    assert plan.weeks[-1].load.total_km < plan.weeks[-4].load.total_km
    assert plan.weeks[-1].phase == "taper"


def test_el_taper_dura_lo_que_dice_la_matriz() -> None:
    plan = build_plan(_perfil(level=Level.AVANZADO), RaceDistance.K42, None, HOY)
    semanas_taper = [s for s in plan.weeks if s.phase == "taper"]
    assert len(semanas_taper) == 3  # 21 días


def test_el_plan_pasa_por_las_cuatro_fases() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    fases = [s.phase for s in plan.weeks]
    assert fases[0] == "base"
    assert "construccion" in fases
    assert "pico" in fases
    assert fases[-1] == "taper"


def test_hay_semanas_de_descarga() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    assert any(s.load.is_deload for s in plan.weeks)


def test_toda_semana_tiene_una_tirada_larga() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    for semana in plan.weeks:
        assert sum(1 for s in semana.sessions if s.kind == "largo") == 1


def test_el_volumen_no_se_pasa_del_pico_de_la_matriz() -> None:
    """Un intermedio motivado no acaba en 90 km porque el interés compuesto sí."""
    plan = build_plan(_perfil(weekly_volume_km=50.0), RaceDistance.K21, None, HOY)
    assert max(s.load.total_km for s in plan.weeks) <= 65.0


def test_las_fechas_de_las_semanas_son_consecutivas() -> None:
    plan = build_plan(_perfil(), RaceDistance.K10, None, HOY)
    for anterior, siguiente in zip(plan.weeks, plan.weeks[1:], strict=False):
        assert (siguiente.start_date - anterior.start_date).days == 7


# ── sesiones ─────────────────────────────────────────────────────────


def test_con_referencia_las_sesiones_traen_ritmo() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    assert all(s.pace is not None for s in plan.weeks[0].sessions)


def test_sin_referencia_no_se_inventa_un_ritmo() -> None:
    """Se prescribe por esfuerzo, no con una cifra sacada de la nada.

    Es la regla de los números aplicada al caso incómodo: cuando falta el
    dato, la respuesta correcta es callarse la cifra, no estimarla.
    """
    perfil = _perfil(reference_distance_km=None, reference_time_sec=None)
    plan = build_plan(perfil, RaceDistance.K10, None, HOY)
    sesiones = plan.weeks[0].sessions
    assert all(s.pace is None for s in sesiones)
    assert all(s.effort_description for s in sesiones)


def test_toda_sesion_explica_para_que_sirve() -> None:
    """«Por qué esta sesión» es la mitad del producto."""
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    for semana in plan.weeks:
        for sesion in semana.sessions:
            assert sesion.notes.strip()


def test_la_tirada_larga_lleva_la_senal_de_tecnica() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    larga = next(s for s in plan.weeks[0].sessions if s.kind == "largo")
    assert larga.technique_cue_id is not None


def test_la_senal_de_tecnica_se_sostiene_dos_semanas() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)

    def cue(i: int) -> str | None:
        return next(s for s in plan.weeks[i].sessions if s.kind == "largo").technique_cue_id

    assert cue(0) == cue(1)
    assert cue(0) != cue(2)


def test_los_kilometros_de_las_sesiones_suman_el_volumen_semanal() -> None:
    plan = build_plan(_perfil(), RaceDistance.K21, None, HOY)
    for semana in plan.weeks:
        suma = sum(s.distance_km for s in semana.sessions)
        assert suma == pytest.approx(semana.load.total_km, abs=0.15)


def test_no_hay_dos_sesiones_el_mismo_dia() -> None:
    plan = build_plan(_perfil(days_per_week=5), RaceDistance.K21, None, HOY)
    for semana in plan.weeks:
        dias = [s.day_of_week for s in semana.sessions]
        assert len(dias) == len(set(dias))


def test_el_plan_es_inmutable() -> None:
    from dataclasses import FrozenInstanceError

    plan = build_plan(_perfil(), RaceDistance.K10, None, HOY)
    with pytest.raises(FrozenInstanceError):
        plan.weeks[0].sessions[0].distance_km = 99.0  # type: ignore[misc]


# ── las propiedades ──────────────────────────────────────────────────

_PERFILES = st.builds(
    AthleteProfile,
    user_id=st.just("u1"),
    level=st.sampled_from(list(Level)),
    weekly_volume_km=st.floats(0.0, 80.0),
    longest_run_km=st.just(0.0),
    days_per_week=st.integers(2, 7),
    reference_distance_km=st.one_of(st.none(), st.floats(3.0, 42.0)),
    reference_time_sec=st.one_of(st.none(), st.integers(600, 20_000)),
)


@given(perfil=_PERFILES, distancia=st.sampled_from(list(RaceDistance)))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propiedad_ningun_plan_generado_viola_las_reglas(
    perfil: AthleteProfile, distancia: RaceDistance
) -> None:
    """La propiedad que hace verificable el sistema entero.

    Si el motor pudiera emitir un plan que sus propias reglas rechazan, toda
    la arquitectura —«el LLM no calcula, consulta al motor»— dejaría de valer
    para nada.
    """
    plan = build_plan(perfil, distancia, race_date=None, today=HOY)
    cargas = [w.load for w in plan.weeks]
    for i, semana in enumerate(plan.weeks):
        anterior = previous_reference(cargas, i)
        problemas = validate_week(semana.load, anterior, distancia, perfil.level)
        assert problemas == [], f"semana {semana.index}: {problemas}"


@given(perfil=_PERFILES, distancia=st.sampled_from(list(RaceDistance)))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propiedad_la_tirada_larga_nunca_pasa_del_tope(
    perfil: AthleteProfile, distancia: RaceDistance
) -> None:
    plan = build_plan(perfil, distancia, race_date=None, today=HOY)
    for semana in plan.weeks:
        if semana.load.total_km > 0:
            proporcion = semana.load.long_run_km / semana.load.total_km
            assert proporcion <= LONG_RUN_MAX_SHARE + 0.005


@given(perfil=_PERFILES, distancia=st.sampled_from(list(RaceDistance)))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propiedad_todo_plan_declara_su_reparto_suave(
    perfil: AthleteProfile, distancia: RaceDistance
) -> None:
    """Sin `easy_km` declarado, R4 se calla — y callarse aquí sería una fuga."""
    plan = build_plan(perfil, distancia, race_date=None, today=HOY)
    assert all(s.load.easy_km is not None for s in plan.weeks)


@given(perfil=_PERFILES, distancia=st.sampled_from(list(RaceDistance)))
@settings(max_examples=60, deadline=None, suppress_health_check=[HealthCheck.too_slow])
def test_propiedad_ninguna_sesion_tiene_distancia_negativa(
    perfil: AthleteProfile, distancia: RaceDistance
) -> None:
    plan = build_plan(perfil, distancia, race_date=None, today=HOY)
    for semana in plan.weeks:
        for sesion in semana.sessions:
            assert sesion.distance_km >= 0
