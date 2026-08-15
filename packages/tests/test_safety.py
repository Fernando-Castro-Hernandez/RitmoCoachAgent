"""La puerta de seguridad.

Es la función más importante del repositorio. Decide si el coach puede prescribir
entrenamiento, y su veredicto se evalúa **antes** de que el modelo redacte una
sola palabra (ADR 0013). Todo lo demás del motor produce números; esto produce la
única respuesta que puede evitar una lesión.

Por eso se prueba con más casos que ningún otro módulo, y por eso las propiedades
son afirmaciones absolutas: «rojo nunca permite prescribir» no admite excepción.
"""

from __future__ import annotations

import pytest
from coach_domain.safety import (
    EMERGENCY_FLAGS,
    RED_FLAGS,
    SafetyLevel,
    assess,
)
from hypothesis import given
from hypothesis import strategies as st

# ── el semáforo por puntaje de dolor ─────────────────────────────────


def test_sin_dolor_es_verde() -> None:
    v = assess(0)
    assert v.level is SafetyLevel.GREEN
    assert v.allows_prescription
    assert v.referral_message is None


def test_dolor_leve_sigue_siendo_verde() -> None:
    assert assess(1).level is SafetyLevel.GREEN
    assert assess(2).level is SafetyLevel.GREEN


def test_dolor_moderado_es_ambar() -> None:
    v = assess(4)
    assert v.level is SafetyLevel.AMBER
    assert v.allows_prescription, "en ámbar se entrena, pero ajustado"


def test_el_ambar_empieza_en_tres() -> None:
    """La frontera exacta, porque es la que se discute."""
    assert assess(2).level is SafetyLevel.GREEN
    assert assess(3).level is SafetyLevel.AMBER


def test_dolor_de_cinco_o_mas_es_rojo() -> None:
    v = assess(5)
    assert v.level is SafetyLevel.RED
    assert not v.allows_prescription
    assert v.referral_message is not None


def test_el_rojo_empieza_en_cinco() -> None:
    assert assess(4).level is SafetyLevel.AMBER
    assert assess(5).level is SafetyLevel.RED


@pytest.mark.parametrize("puntaje", [-1, 11, 100])
def test_rechaza_un_puntaje_fuera_de_escala(puntaje: int) -> None:
    with pytest.raises(ValueError, match="de 0 a 10"):
        assess(puntaje)


# ── persistencia: el ámbar que no se va ──────────────────────────────


def test_el_ambar_persistente_escala_a_rojo() -> None:
    """Tres días de molestia moderada dejan de ser molestia.

    Es la regla que más lesiones evita en la práctica: el dolor que no cede
    solo no es fatiga, y seguir entrenando encima es cómo una molestia se
    convierte en una baja de seis semanas.
    """
    v = assess(4, days_persisting=3)
    assert v.level is SafetyLevel.RED
    assert not v.allows_prescription


def test_el_ambar_de_ayer_todavia_es_ambar() -> None:
    assert assess(4, days_persisting=2).level is SafetyLevel.AMBER


def test_la_persistencia_no_convierte_el_verde_en_rojo() -> None:
    """Estar treinta días sin dolor no es una alarma."""
    assert assess(0, days_persisting=30).level is SafetyLevel.GREEN
    assert assess(2, days_persisting=30).level is SafetyLevel.GREEN


# ── banderas rojas ───────────────────────────────────────────────────


@pytest.mark.parametrize("bandera", sorted(RED_FLAGS))
def test_toda_bandera_roja_fuerza_rojo_sin_importar_el_puntaje(bandera: str) -> None:
    """Una bandera roja gana sobre cualquier puntaje, incluido el cero.

    Alguien puede reportar dolor 0 y aterrizaje alterado a la vez. La bandera
    manda: describe un mecanismo, no una intensidad.
    """
    v = assess(0, flags=[bandera])
    assert v.level is SafetyLevel.RED
    assert not v.allows_prescription
    assert v.referral_message


@pytest.mark.parametrize("bandera", sorted(EMERGENCY_FLAGS))
def test_las_banderas_de_urgencia_piden_atencion_inmediata(bandera: str) -> None:
    v = assess(1, flags=[bandera])
    assert v.referral_message is not None
    assert "inmediata" in v.referral_message.lower()


def test_la_urgencia_gana_sobre_una_bandera_roja_comun() -> None:
    """Si concurren las dos, el mensaje tiene que ser el de urgencia."""
    v = assess(3, flags=["swelling", "chest_pain"])
    assert v.referral_message is not None
    assert "inmediata" in v.referral_message.lower()


def test_las_banderas_de_urgencia_son_un_subconjunto_de_las_rojas() -> None:
    assert EMERGENCY_FLAGS <= RED_FLAGS


def test_una_bandera_desconocida_no_se_ignora_en_silencio() -> None:
    """Un typo en el nombre de una bandera no puede volverse un permiso."""
    with pytest.raises(ValueError, match="no reconozco"):
        assess(0, flags=["dolor_raro_inventado"])


def test_sin_banderas_es_el_caso_normal() -> None:
    assert assess(1, flags=[]).level is SafetyLevel.GREEN


# ── el veredicto es explicable ───────────────────────────────────────


def test_todo_veredicto_dice_por_que() -> None:
    """Sin la razón no hay auditoría, y la decisión queda sin defensa."""
    for v in (assess(0), assess(4), assess(7), assess(0, flags=["swelling"])):
        assert v.reason.strip()


def test_el_rojo_nunca_nombra_una_lesion() -> None:
    """El coach no diagnostica. Ni siquiera cuando está seguro."""
    prohibidas = {"fascitis", "tendinitis", "esguince", "fractura", "síndrome"}
    for bandera in sorted(RED_FLAGS):
        mensaje = assess(9, flags=[bandera]).referral_message or ""
        assert not prohibidas & set(mensaje.lower().split())


# ── propiedades ──────────────────────────────────────────────────────


_BANDERAS = st.lists(st.sampled_from(sorted(RED_FLAGS)), max_size=3)


@given(puntaje=st.integers(0, 10), dias=st.integers(0, 60), banderas=_BANDERAS)
def test_propiedad_el_rojo_nunca_permite_prescribir(
    puntaje: int, dias: int, banderas: list[str]
) -> None:
    """La invariante que sostiene todo el producto."""
    v = assess(puntaje, flags=banderas, days_persisting=dias)
    if v.level is SafetyLevel.RED:
        assert not v.allows_prescription


@given(puntaje=st.integers(0, 10), dias=st.integers(0, 60), banderas=_BANDERAS)
def test_propiedad_el_rojo_siempre_deriva(puntaje: int, dias: int, banderas: list[str]) -> None:
    """Bloquear sin decir a dónde ir sería abandonar al corredor."""
    v = assess(puntaje, flags=banderas, days_persisting=dias)
    if v.level is SafetyLevel.RED:
        assert v.referral_message
    else:
        assert v.referral_message is None


@given(puntaje=st.integers(0, 10), dias=st.integers(0, 60), banderas=_BANDERAS)
def test_propiedad_mas_dolor_nunca_afloja_la_puerta(
    puntaje: int, dias: int, banderas: list[str]
) -> None:
    """Monotonía: subir el dolor no puede relajar el veredicto."""
    orden = {SafetyLevel.GREEN: 0, SafetyLevel.AMBER: 1, SafetyLevel.RED: 2}
    actual = assess(puntaje, flags=banderas, days_persisting=dias)
    if puntaje < 10:
        peor = assess(puntaje + 1, flags=banderas, days_persisting=dias)
        assert orden[peor.level] >= orden[actual.level]


@given(puntaje=st.integers(0, 10), dias=st.integers(0, 60), banderas=_BANDERAS)
def test_propiedad_mas_dias_nunca_afloja_la_puerta(
    puntaje: int, dias: int, banderas: list[str]
) -> None:
    orden = {SafetyLevel.GREEN: 0, SafetyLevel.AMBER: 1, SafetyLevel.RED: 2}
    actual = assess(puntaje, flags=banderas, days_persisting=dias)
    manana = assess(puntaje, flags=banderas, days_persisting=dias + 1)
    assert orden[manana.level] >= orden[actual.level]


@given(puntaje=st.integers(0, 10), dias=st.integers(0, 60), banderas=_BANDERAS)
def test_propiedad_agregar_una_bandera_nunca_afloja_la_puerta(
    puntaje: int, dias: int, banderas: list[str]
) -> None:
    orden = {SafetyLevel.GREEN: 0, SafetyLevel.AMBER: 1, SafetyLevel.RED: 2}
    actual = assess(puntaje, flags=banderas, days_persisting=dias)
    con_mas = assess(puntaje, flags=[*banderas, "swelling"], days_persisting=dias)
    assert orden[con_mas.level] >= orden[actual.level]


@given(puntaje=st.integers(0, 10), dias=st.integers(0, 60), banderas=_BANDERAS)
def test_propiedad_el_veredicto_es_determinista(
    puntaje: int, dias: int, banderas: list[str]
) -> None:
    """Las mismas entradas dan el mismo veredicto, siempre.

    Es lo que distingue esta puerta de un clasificador probabilístico, y la
    razón por la que la seguridad no vive en el prompt.
    """
    a = assess(puntaje, flags=banderas, days_persisting=dias)
    b = assess(puntaje, flags=list(reversed(banderas)), days_persisting=dias)
    assert a == b
