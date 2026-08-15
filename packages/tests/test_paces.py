"""Aritmética de ritmos, zonas y predicción.

Es la capa más baja del motor: todo lo demás calcula encima de esto. Un error
aquí se propaga a cada sesión de cada plan, así que se prueba con casos
concretos **y** con propiedades sobre cientos de entradas generadas.
"""

from __future__ import annotations

import itertools

import pytest
from coach_domain.paces import (
    format_pace,
    pace_from_run,
    parse_pace,
    riegel_predict,
    zones_from_effort,
)
from coach_domain.types import DISTANCE_KM, PaceRange, RaceDistance
from hypothesis import given
from hypothesis import strategies as st

# ── ritmo ────────────────────────────────────────────────────────────


def test_ritmo_de_una_carrera_conocida() -> None:
    assert pace_from_run(8.42, 2838) == 337  # 5:37/km
    assert pace_from_run(10.0, 3000) == 300  # 5:00/km clavados


def test_el_medio_siempre_sube() -> None:
    """`round()` de Python redondea al par: 337.5→338 pero 336.5→336.

    Dos carreras equivalentes tienen que redondear igual. La regla es media
    hacia arriba, siempre.
    """
    assert pace_from_run(8.0, 2700) == 338  # 337.5 exacto
    assert pace_from_run(8.0, 2692) == 337  # 336.5 exacto


def test_ritmo_rechaza_distancia_cero() -> None:
    with pytest.raises(ValueError):
        pace_from_run(0.0, 1800)


def test_ritmo_rechaza_duracion_cero() -> None:
    with pytest.raises(ValueError):
        pace_from_run(8.0, 0)


@given(km=st.floats(1.0, 50.0), sec=st.integers(240, 30_000))
def test_propiedad_el_ritmo_siempre_es_positivo(km: float, sec: int) -> None:
    assert pace_from_run(km, sec) > 0


# ── Riegel ───────────────────────────────────────────────────────────


def test_riegel_predice_mas_lento_en_distancias_mayores() -> None:
    """El exponente 1.06 es lo que hace la curva no lineal."""
    t10 = 50 * 60
    t21 = riegel_predict(10.0, t10, 21.0975)
    assert t21 > t10 * 2.1


def test_riegel_a_la_misma_distancia_devuelve_el_mismo_tiempo() -> None:
    assert riegel_predict(10.0, 3000, 10.0) == 3000


def test_riegel_rechaza_distancias_invalidas() -> None:
    with pytest.raises(ValueError):
        riegel_predict(0.0, 3000, 21.0975)
    with pytest.raises(ValueError):
        riegel_predict(10.0, 3000, -1.0)


@given(
    conocida=st.floats(3.0, 42.2),
    seg=st.integers(600, 25_000),
    objetivo=st.floats(3.0, 42.2),
)
def test_propiedad_riegel_es_monotono(conocida: float, seg: int, objetivo: float) -> None:
    """Más distancia nunca puede predecir menos tiempo."""
    t1 = riegel_predict(conocida, seg, objetivo)
    t2 = riegel_predict(conocida, seg, objetivo + 1.0)
    assert t2 > t1


# ── zonas ────────────────────────────────────────────────────────────


def test_las_zonas_van_de_lenta_a_rapida() -> None:
    z = zones_from_effort(10.0, 50 * 60)
    assert z.z5.min_sec_per_km < z.z4.min_sec_per_km < z.z2.min_sec_per_km


def test_cada_zona_tiene_el_rapido_antes_que_el_lento() -> None:
    z = zones_from_effort(10.0, 50 * 60)
    for franja in (z.z1, z.z2, z.z3, z.z4, z.z5):
        assert franja.min_sec_per_km <= franja.max_sec_per_km


def test_las_zonas_son_contiguas() -> None:
    """Sin huecos entre zonas: todo ritmo cae en alguna."""
    z = zones_from_effort(10.0, 50 * 60)
    escalera = [z.z5, z.z4, z.z3, z.z2, z.z1]
    for rapida, lenta in itertools.pairwise(escalera):
        assert rapida.max_sec_per_km == lenta.min_sec_per_km


@given(km=st.floats(3.0, 42.2), seg=st.integers(600, 25_000))
def test_propiedad_las_zonas_nunca_se_invierten(km: float, seg: int) -> None:
    z = zones_from_effort(km, seg)
    assert z.z5.min_sec_per_km < z.z1.max_sec_per_km


# ── formato ──────────────────────────────────────────────────────────


def test_formato_de_ritmo() -> None:
    assert format_pace(337) == "5:37"
    assert format_pace(300) == "5:00"
    assert format_pace(605) == "10:05"


def test_formatear_y_leer_son_inversos() -> None:
    assert parse_pace(format_pace(337)) == 337


@given(seg=st.integers(150, 1200))
def test_propiedad_formatear_y_leer_son_inversos(seg: int) -> None:
    assert parse_pace(format_pace(seg)) == seg


def test_leer_ritmo_acepta_espacios_y_apostrofe() -> None:
    assert parse_pace("  5:37  ") == 337
    assert parse_pace("5'37\"") == 337


def test_leer_ritmo_rechaza_basura() -> None:
    with pytest.raises(ValueError):
        parse_pace("rapidito")
    with pytest.raises(ValueError):
        parse_pace("5:99")  # 99 segundos no existen


# ── tipos ────────────────────────────────────────────────────────────


def test_toda_distancia_de_carrera_tiene_kilometraje() -> None:
    for distancia in RaceDistance:
        assert DISTANCE_KM[distancia] > 0


def test_las_distancias_oficiales_son_las_exactas() -> None:
    """21.0975 y 42.195, no 21 y 42. En maratón son casi 12 minutos."""
    assert DISTANCE_KM[RaceDistance.K21] == 21.0975
    assert DISTANCE_KM[RaceDistance.K42] == 42.195


def test_una_franja_invertida_es_un_error() -> None:
    with pytest.raises(ValueError):
        PaceRange(min_sec_per_km=400, max_sec_per_km=300)
