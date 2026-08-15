"""Los tipos del dominio se defienden solos.

Un dato imposible tiene que morir en el constructor y no seis capas más abajo,
cuando ya se convirtió en un plan que alguien va a correr. Estas pruebas fijan
qué es imposible.
"""

from __future__ import annotations

import pytest
from coach_domain.paces import zones_from_effort
from coach_domain.types import AthleteProfile, Level, PaceRange, RaceDistance

# ── franjas de ritmo ─────────────────────────────────────────────────


def test_una_franja_rechaza_ritmos_no_positivos() -> None:
    with pytest.raises(ValueError, match="positivo"):
        PaceRange(min_sec_per_km=0, max_sec_per_km=300)
    with pytest.raises(ValueError, match="positivo"):
        PaceRange(min_sec_per_km=300, max_sec_per_km=-1)


def test_el_mensaje_de_franja_invertida_explica_el_orden() -> None:
    """Confundir los campos es el error probable; el mensaje tiene que enseñar."""
    with pytest.raises(ValueError, match="extremo rápido"):
        PaceRange(min_sec_per_km=400, max_sec_per_km=300)


def test_el_medio_de_una_franja() -> None:
    assert PaceRange(300, 340).middle_sec_per_km == 320


def test_una_franja_de_un_solo_ritmo_es_valida() -> None:
    assert PaceRange(330, 330).middle_sec_per_km == 330


# ── zonas ────────────────────────────────────────────────────────────


def test_se_puede_pedir_una_zona_por_numero() -> None:
    z = zones_from_effort(10.0, 50 * 60)
    assert z.by_number(3) == z.z3
    assert z.by_number(1) == z.z1
    assert z.by_number(5) == z.z5


def test_no_existe_la_zona_seis() -> None:
    z = zones_from_effort(10.0, 50 * 60)
    for invalida in (0, 6, -1):
        with pytest.raises(ValueError, match="de 1 a 5"):
            z.by_number(invalida)


# ── perfil del atleta ────────────────────────────────────────────────


def _perfil(**cambios: object) -> AthleteProfile:
    base: dict[str, object] = {
        "user_id": "u1",
        "level": Level.INTERMEDIO,
        "weekly_volume_km": 30.0,
        "longest_run_km": 12.0,
        "days_per_week": 4,
    }
    return AthleteProfile(**{**base, **cambios})  # type: ignore[arg-type]


def test_un_perfil_razonable_se_construye() -> None:
    p = _perfil()
    assert p.level is Level.INTERMEDIO
    assert p.injuries == ()


def test_rechaza_volumen_negativo() -> None:
    with pytest.raises(ValueError, match="volumen semanal"):
        _perfil(weekly_volume_km=-1.0)


def test_rechaza_tirada_negativa() -> None:
    with pytest.raises(ValueError, match="más larga"):
        _perfil(longest_run_km=-5.0)


@pytest.mark.parametrize("dias", [0, 8, -2])
def test_rechaza_dias_por_semana_imposibles(dias: int) -> None:
    with pytest.raises(ValueError, match="días por semana"):
        _perfil(days_per_week=dias)


def test_rechaza_una_tirada_mas_larga_que_la_semana_entera() -> None:
    """Es el error de captura más común y el más dañino.

    Si alguien dice que corre 20 km a la semana y que su tirada larga es de
    30, uno de los dos datos está mal. Planificar sobre eso produce una
    progresión inventada, así que el perfil no llega a existir.
    """
    with pytest.raises(ValueError, match="tirada más larga"):
        _perfil(weekly_volume_km=20.0, longest_run_km=30.0)


def test_un_corredor_que_arranca_de_cero_es_valido() -> None:
    """Volumen cero no es un error: es un principiante absoluto."""
    p = _perfil(weekly_volume_km=0.0, longest_run_km=0.0, level=Level.PRINCIPIANTE)
    assert p.weekly_volume_km == 0.0


def test_sabe_si_tiene_una_referencia_de_ritmo() -> None:
    assert not _perfil().has_reference
    assert not _perfil(reference_distance_km=10.0).has_reference
    assert _perfil(reference_distance_km=10.0, reference_time_sec=3000).has_reference


def test_las_lesiones_son_inmutables() -> None:
    p = _perfil(injuries=("rodilla_derecha",))
    assert isinstance(p.injuries, tuple)


def test_el_perfil_es_inmutable() -> None:
    from dataclasses import FrozenInstanceError

    p = _perfil()
    with pytest.raises(FrozenInstanceError):
        p.weekly_volume_km = 99.0  # type: ignore[misc]


# ── enumeraciones ────────────────────────────────────────────────────


def test_las_distancias_se_comparan_como_texto() -> None:
    """`StrEnum` permite que el valor viaje a JSON sin conversión manual."""
    assert RaceDistance.K21.value == "21k"
    assert Level.PRINCIPIANTE.value == "principiante"
    assert f"{RaceDistance.K42}" == "42k"  # interpolación directa, sin .value
