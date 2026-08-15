"""Las ocho reglas de progresión.

Son los invariantes que el LLM no puede sobreescribir. El motor los valida antes
de emitir cualquier sesión, y la propiedad final —«ninguna semana generada por
el motor viola una regla»— es lo que convierte «entrenamiento seguro» en algo
verificable y no en una promesa del prompt.

R7 (prerrequisito de meta) se prueba en `test_plans.py`, donde vive la
generación; aquí sólo están las reglas que se evalúan sobre una semana suelta.
"""

from __future__ import annotations

import pytest
from coach_domain.progression import (
    DELOAD_PCT,
    LONG_RUN_MAX_SHARE,
    WeekLoad,
    deload_every,
    environment_advice,
    is_deload_week,
    max_increase,
    next_week_volume,
    return_factor,
    validate_week,
)
from coach_domain.types import Level, RaceDistance
from hypothesis import given
from hypothesis import strategies as st


def _semana(**cambios: object) -> WeekLoad:
    base: dict[str, object] = {
        "index": 2,
        "total_km": 40.0,
        "long_run_km": 11.0,
        "quality_sessions": 1,
        "is_deload": False,
    }
    return WeekLoad(**{**base, **cambios})  # type: ignore[arg-type]


# ── R1 · incremento gradual ──────────────────────────────────────────


def test_r1_el_tope_sale_de_la_matriz_de_la_fase_1() -> None:
    assert max_increase(RaceDistance.K5, Level.PRINCIPIANTE) == 0.05
    assert max_increase(RaceDistance.K10, Level.INTERMEDIO) == 0.08
    assert max_increase(RaceDistance.K21, Level.INTERMEDIO) == 0.08
    assert max_increase(RaceDistance.K42, Level.AVANZADO) == 0.10


def test_r1_un_principiante_que_va_a_maraton_no_hereda_el_diez_por_ciento() -> None:
    """El caso que la matriz de la Fase 1 no cubría.

    La matriz indexa el incremento por distancia, asumiendo que quien corre un
    maratón es avanzado. Pero el principiante que se apunta a un maratón existe,
    y es exactamente el corredor que más se lesiona. Manda el más conservador de
    los dos topes.
    """
    assert max_increase(RaceDistance.K42, Level.PRINCIPIANTE) == 0.05
    assert max_increase(RaceDistance.K21, Level.PRINCIPIANTE) == 0.05


def test_r1_un_avanzado_en_5k_tampoco_sube_al_diez() -> None:
    """Y al revés: la distancia corta tampoco tolera saltos grandes."""
    assert max_increase(RaceDistance.K5, Level.AVANZADO) == 0.05


def test_r1_el_volumen_sube_como_mucho_el_tope() -> None:
    assert next_week_volume(20.0, 1, RaceDistance.K5, Level.PRINCIPIANTE) == 21.0
    assert next_week_volume(50.0, 1, RaceDistance.K42, Level.AVANZADO) == 55.0


def test_r1_pasarse_del_tope_es_una_violacion() -> None:
    previa = _semana(index=1, total_km=40.0)
    semana = _semana(index=2, total_km=48.0)  # +20 %
    problemas = validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
    assert any(p.rule == "R1" for p in problemas)


def test_r1_el_mensaje_dice_el_tope_concreto() -> None:
    previa = _semana(index=1, total_km=40.0)
    semana = _semana(index=2, total_km=48.0)
    problema = next(
        p
        for p in validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
        if p.rule == "R1"
    )
    assert "43.2" in problema.message


def test_r1_no_aplica_a_la_primera_semana() -> None:
    assert validate_week(_semana(index=1), None, RaceDistance.K21, Level.INTERMEDIO) == []


def test_r1_bajar_el_volumen_nunca_es_violacion() -> None:
    previa = _semana(index=1, total_km=40.0)
    semana = _semana(index=2, total_km=30.0, long_run_km=8.0)
    assert validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO) == []


# ── R2 · descarga obligatoria ────────────────────────────────────────


def test_r2_la_descarga_es_cada_cuarta_semana() -> None:
    assert is_deload_week(4, RaceDistance.K21)
    assert is_deload_week(8, RaceDistance.K21)
    assert not is_deload_week(3, RaceDistance.K21)


def test_r2_el_maraton_descarga_cada_tres() -> None:
    """Más volumen absoluto, menos margen antes de acumular fatiga."""
    assert deload_every(RaceDistance.K42) == 3
    assert is_deload_week(3, RaceDistance.K42)
    assert is_deload_week(6, RaceDistance.K42)


def test_r2_la_semana_cero_no_es_descarga() -> None:
    assert not is_deload_week(0, RaceDistance.K21)


def test_r2_la_descarga_recorta_el_treinta_por_ciento() -> None:
    assert next_week_volume(40.0, 4, RaceDistance.K21, Level.INTERMEDIO) == 28.0


def test_r2_saltarse_la_descarga_es_una_violacion() -> None:
    """«No es negociable ni por petición del usuario» (Fase 1)."""
    previa = _semana(index=3, total_km=40.0)
    semana = _semana(index=4, total_km=42.0, is_deload=False)
    problemas = validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
    assert any(p.rule == "R2" for p in problemas)


def test_r2_una_descarga_que_no_descarga_lo_suficiente_es_violacion() -> None:
    previa = _semana(index=3, total_km=40.0)
    semana = _semana(index=4, total_km=38.0, is_deload=True)  # sólo -5 %
    problemas = validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
    assert any(p.rule == "R2" for p in problemas)


# ── R3 · tope de tirada larga ────────────────────────────────────────


def test_r3_la_tirada_larga_no_pasa_del_treinta_por_ciento() -> None:
    semana = _semana(total_km=40.0, long_run_km=15.0)  # 37.5 %
    problemas = validate_week(semana, None, RaceDistance.K21, Level.INTERMEDIO)
    assert any(p.rule == "R3" for p in problemas)


def test_r3_justo_en_el_treinta_por_ciento_es_valido() -> None:
    semana = _semana(total_km=40.0, long_run_km=40.0 * LONG_RUN_MAX_SHARE)
    assert not any(
        p.rule == "R3" for p in validate_week(semana, None, RaceDistance.K21, Level.INTERMEDIO)
    )


def test_r3_una_semana_sin_kilometros_no_revienta() -> None:
    semana = _semana(total_km=0.0, long_run_km=0.0)
    validate_week(semana, None, RaceDistance.K21, Level.INTERMEDIO)  # no lanza


# ── R4 · distribución 80/20 ──────────────────────────────────────────


def test_r4_al_menos_el_ochenta_por_ciento_es_suave() -> None:
    semana = _semana(total_km=40.0, easy_km=28.0)  # 70 %
    problemas = validate_week(semana, None, RaceDistance.K42, Level.AVANZADO)
    assert any(p.rule == "R4" for p in problemas)


def test_r4_el_ochenta_exacto_pasa() -> None:
    semana = _semana(total_km=40.0, easy_km=32.0)
    assert not any(
        p.rule == "R4" for p in validate_week(semana, None, RaceDistance.K42, Level.AVANZADO)
    )


def test_r4_no_se_evalua_si_no_se_declara_el_reparto() -> None:
    """Sin el dato no se inventa un veredicto.

    `build_plan` siempre lo declara; una semana construida a mano puede no
    hacerlo, y afirmar que cumple sin saberlo sería peor que callarse.
    """
    semana = _semana(total_km=40.0, easy_km=None)
    assert not any(
        p.rule == "R4" for p in validate_week(semana, None, RaceDistance.K42, Level.AVANZADO)
    )


# ── R5 · una variable a la vez ───────────────────────────────────────


def test_r5_no_sube_volumen_e_intensidad_la_misma_semana() -> None:
    previa = _semana(index=1, total_km=40.0, quality_sessions=1)
    semana = _semana(index=2, total_km=43.0, quality_sessions=2)
    problemas = validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
    assert any(p.rule == "R5" for p in problemas)


def test_r5_subir_solo_el_volumen_esta_bien() -> None:
    previa = _semana(index=1, total_km=40.0, quality_sessions=1)
    semana = _semana(index=2, total_km=43.0, quality_sessions=1)
    assert not any(
        p.rule == "R5" for p in validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
    )


def test_r5_subir_solo_la_intensidad_esta_bien() -> None:
    previa = _semana(index=1, total_km=40.0, quality_sessions=1)
    semana = _semana(index=2, total_km=40.0, quality_sessions=2)
    assert not any(
        p.rule == "R5" for p in validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
    )


def test_r5_no_aplica_en_semana_de_descarga() -> None:
    """En descarga el volumen baja, así que no hay dos variables subiendo."""
    previa = _semana(index=3, total_km=40.0, quality_sessions=1)
    semana = _semana(index=4, total_km=28.0, quality_sessions=2, is_deload=True)
    assert not any(
        p.rule == "R5" for p in validate_week(semana, previa, RaceDistance.K21, Level.INTERMEDIO)
    )


# ── R6 · regreso tras pausa ──────────────────────────────────────────


@pytest.mark.parametrize(
    ("dias", "factor"),
    [(0, 1.00), (3, 1.00), (4, 0.90), (7, 0.90), (8, 0.75), (14, 0.75), (15, 0.50), (28, 0.50)],
)
def test_r6_los_escalones_de_regreso(dias: int, factor: float) -> None:
    assert return_factor(dias) == factor


def test_r6_mas_de_un_mes_obliga_a_replanificar() -> None:
    """Cero no es «no corras»: es «este plan ya no sirve, hay que rehacerlo»."""
    assert return_factor(29) == 0.0
    assert return_factor(90) == 0.0


def test_r6_rechaza_dias_negativos() -> None:
    with pytest.raises(ValueError):
        return_factor(-1)


@given(dias=st.integers(0, 400))
def test_propiedad_r6_nunca_devuelve_mas_de_uno(dias: int) -> None:
    assert 0.0 <= return_factor(dias) <= 1.0


@given(dias=st.integers(0, 200))
def test_propiedad_r6_es_monotono_decreciente(dias: int) -> None:
    assert return_factor(dias + 1) <= return_factor(dias)


# ── R8 · ambiente ────────────────────────────────────────────────────


def test_r8_por_debajo_de_veintiocho_no_se_ajusta_nada() -> None:
    consejo = environment_advice(temp_c=22.0)
    assert consejo.pace_adjustment_sec == 0
    assert not consejo.move_indoors


def test_r8_el_calor_afloja_el_ritmo() -> None:
    """+20 a +40 s/km según la Fase 1. Ajustar el ritmo, no el esfuerzo."""
    assert environment_advice(temp_c=28.0).pace_adjustment_sec == 0  # el umbral no dispara
    assert environment_advice(temp_c=28.1).pace_adjustment_sec == 20  # arranca en 20
    assert environment_advice(temp_c=32.0).pace_adjustment_sec == 32  # +3 por grado
    assert environment_advice(temp_c=29.0).pace_adjustment_sec == 23


def test_r8_el_ajuste_topa_en_cuarenta() -> None:
    assert environment_advice(temp_c=45.0).pace_adjustment_sec == 40


def test_r8_el_calor_extremo_manda_a_interior() -> None:
    assert environment_advice(temp_c=36.0).move_indoors


def test_r8_el_aire_malo_tambien_ajusta() -> None:
    consejo = environment_advice(temp_c=20.0, aqi=160)
    assert consejo.pace_adjustment_sec > 0
    assert consejo.move_indoors


def test_r8_todo_ajuste_explica_por_que() -> None:
    for consejo in (
        environment_advice(temp_c=33.0),
        environment_advice(temp_c=20.0, aqi=200),
        environment_advice(temp_c=15.0),
    ):
        assert consejo.reason.strip()


@given(temp=st.floats(-10.0, 50.0), aqi=st.one_of(st.none(), st.integers(0, 500)))
def test_propiedad_r8_el_ajuste_siempre_es_razonable(temp: float, aqi: int | None) -> None:
    consejo = environment_advice(temp_c=temp, aqi=aqi)
    assert 0 <= consejo.pace_adjustment_sec <= 60


# ── la propiedad global ──────────────────────────────────────────────


@given(
    previo=st.floats(min_value=5.0, max_value=120.0),
    indice=st.integers(min_value=1, max_value=20),
    distancia=st.sampled_from(list(RaceDistance)),
    nivel=st.sampled_from(list(Level)),
)
def test_propiedad_el_motor_no_puede_producir_una_semana_ilegal(
    previo: float, indice: int, distancia: RaceDistance, nivel: Level
) -> None:
    """Lo que hace verificable el sistema entero.

    Si `next_week_volume` pudiera generar una semana que `validate_week` rechaza,
    el motor se estaría contradiciendo a sí mismo — y ese es exactamente el
    fallo que la arquitectura promete que no puede ocurrir.
    """
    total = next_week_volume(previo, indice, distancia, nivel)
    es_descarga = is_deload_week(indice, distancia)
    semana = WeekLoad(
        index=indice,
        total_km=total,
        long_run_km=total * 0.29,
        quality_sessions=1,
        is_deload=es_descarga,
        easy_km=total * 0.82,
    )
    anterior = WeekLoad(indice - 1, previo, previo * 0.29, 1, False, previo * 0.82)
    assert validate_week(semana, anterior, distancia, nivel) == []


@given(
    previo=st.floats(min_value=5.0, max_value=120.0),
    indice=st.integers(min_value=1, max_value=20),
    distancia=st.sampled_from(list(RaceDistance)),
    nivel=st.sampled_from(list(Level)),
)
def test_propiedad_la_descarga_siempre_baja_el_volumen(
    previo: float, indice: int, distancia: RaceDistance, nivel: Level
) -> None:
    total = next_week_volume(previo, indice, distancia, nivel)
    if is_deload_week(indice, distancia):
        assert total < previo
    else:
        assert total >= previo


@given(
    previo=st.floats(min_value=5.0, max_value=120.0),
    indice=st.integers(min_value=1, max_value=20),
    distancia=st.sampled_from(list(RaceDistance)),
    nivel=st.sampled_from(list(Level)),
)
def test_propiedad_nunca_sube_mas_del_tope(
    previo: float, indice: int, distancia: RaceDistance, nivel: Level
) -> None:
    total = next_week_volume(previo, indice, distancia, nivel)
    assert total <= previo * (1 + max_increase(distancia, nivel)) + 0.05


def test_la_constante_de_descarga_es_la_de_la_fase_1() -> None:
    assert DELOAD_PCT == 0.30
    assert LONG_RUN_MAX_SHARE == 0.30
