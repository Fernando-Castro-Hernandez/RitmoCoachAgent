"""Módulo de técnica de carrera.

La característica que salió de la investigación de usuario: nadie cubre la base
de la pirámide (ADR 0011). Dos cosas se prueban aquí y son distintas:

1. Que la **fórmula** de cadencia sea la del ADR y no el mito de los 180 spm.
2. Que la **biblioteca** de señales sea dictable, esté curada y no se emita
   nunca por encima de la puerta de seguridad.
"""

from __future__ import annotations

import pytest
from coach_domain.safety import assess
from coach_domain.technique import (
    CUE_ROTATION_WEEKS,
    UnknownCueError,
    get_cue,
    load_cues,
    select_cue,
    target_cadence,
)

VERDE = assess(0)

# ── cadencia objetivo ────────────────────────────────────────────────


def test_la_cadencia_objetivo_arranca_cinco_por_ciento_arriba() -> None:
    assert target_cadence(160, weeks_worked=0) == 168


def test_la_cadencia_objetivo_sube_un_punto_por_semana() -> None:
    assert target_cadence(160, weeks_worked=1) == 170  # +6 %
    assert target_cadence(160, weeks_worked=2) == 171  # +7 %


def test_la_cadencia_objetivo_topa_en_diez_por_ciento() -> None:
    """El tope es lo que impide que el objetivo se vuelva absurdo con el tiempo."""
    assert target_cadence(160, weeks_worked=5) == 176
    assert target_cadence(160, weeks_worked=50) == 176
    assert target_cadence(160, weeks_worked=500) == 176


def test_la_cadencia_es_relativa_y_no_un_numero_universal() -> None:
    """El objetivo de 180 spm para todo el mundo es un mito (ADR 0011).

    Dos corredores con bases distintas tienen que recibir objetivos distintos.
    Si esta prueba falla, alguien metió el número mágico en el motor.
    """
    lento = target_cadence(150, weeks_worked=0)
    rapido = target_cadence(178, weeks_worked=0)
    assert lento != rapido
    assert lento < 180 < rapido


def test_no_se_inventa_una_cadencia_sin_base() -> None:
    """Sin el dato, no hay objetivo. Se le pide al corredor que la cuente."""
    with pytest.raises(ValueError, match="mayor que cero"):
        target_cadence(0, weeks_worked=1)
    with pytest.raises(ValueError, match="mayor que cero"):
        target_cadence(-160, weeks_worked=1)


def test_rechaza_semanas_negativas() -> None:
    with pytest.raises(ValueError):
        target_cadence(160, weeks_worked=-1)


# ── la biblioteca ────────────────────────────────────────────────────


def test_la_biblioteca_cubre_las_ocho_categorias_del_adr() -> None:
    categorias = {c.category for c in load_cues()}
    assert categorias >= {
        "cadencia",
        "sobrezancada",
        "postura",
        "brazos",
        "manos",
        "mirada",
        "hombros",
        "respiracion",
    }


def test_toda_senal_es_dictable_en_voz() -> None:
    """Más de dos frases habladas y el corredor ya se perdió."""
    for cue in load_cues():
        assert cue.voice_text.strip()
        assert len(cue.voice_text) <= 220, f"«{cue.id}» es demasiado largo para decirse"


def test_ninguna_senal_es_una_lista() -> None:
    """Nadie puede seguir una enumeración corriendo."""
    for cue in load_cues():
        assert "\n-" not in cue.voice_text
        assert cue.voice_text.count(";") <= 1


def test_los_identificadores_son_unicos() -> None:
    ids = [c.id for c in load_cues()]
    assert len(ids) == len(set(ids))


def test_toda_senal_tiene_explicacion_larga_y_nivel() -> None:
    for cue in load_cues():
        assert len(cue.long_explanation) > len(cue.voice_text)
        assert cue.levels, f"«{cue.id}» no declara para qué nivel sirve"


def test_toda_senal_se_contraindica_con_dolor_agudo() -> None:
    """La seguridad es transversal: ninguna señal se salta esa regla."""
    for cue in load_cues():
        assert "dolor_agudo_activo" in cue.contraindications


def test_se_puede_pedir_una_senal_por_id() -> None:
    cue = get_cue("cadencia-incremento")
    assert cue.category == "cadencia"
    assert "más cortos" in cue.voice_text


def test_pedir_una_senal_que_no_existe_es_un_error() -> None:
    with pytest.raises(UnknownCueError):
        get_cue("señal-inventada-por-el-modelo")


def test_la_biblioteca_se_carga_una_sola_vez() -> None:
    """Leer YAML del disco en cada turno de voz sería un desperdicio."""
    assert load_cues() is load_cues()


# ── selección ────────────────────────────────────────────────────────


def test_la_seguridad_manda_sobre_la_tecnica() -> None:
    """Con dolor activo no se enseña técnica. Ni en ámbar (ADR 0011)."""
    assert select_cue("principiante", 1, assess(7)) is None
    assert select_cue("principiante", 1, assess(4)) is None
    assert select_cue("principiante", 1, assess(0, flags=["swelling"])) is None


def test_en_verde_si_hay_senal() -> None:
    assert select_cue("principiante", 1, VERDE) is not None


def test_la_misma_senal_se_repite_dos_semanas() -> None:
    """Una señal a la vez, sostenida hasta que se automatiza."""
    assert select_cue("principiante", 1, VERDE) == select_cue("principiante", 2, VERDE)
    assert select_cue("principiante", 1, VERDE) != select_cue("principiante", 3, VERDE)
    assert CUE_ROTATION_WEEKS == 2


def test_la_rotacion_da_la_vuelta_sin_romperse() -> None:
    principiante = [c for c in load_cues() if "principiante" in c.levels]
    vuelta = 2 * len(principiante)
    assert select_cue("principiante", 1, VERDE) == select_cue("principiante", 1 + vuelta, VERDE)


def test_solo_ofrece_senales_del_nivel_del_corredor() -> None:
    for semana in range(1, 30):
        cue = select_cue("avanzado", semana, VERDE)
        assert cue is not None
        assert "avanzado" in cue.levels


def test_un_nivel_desconocido_no_devuelve_cualquier_cosa() -> None:
    assert select_cue("semidios", 1, VERDE) is None


def test_se_pueden_excluir_senales_contraindicadas() -> None:
    """Una molestia de rodilla ya superada sigue vetando su señal."""
    for semana in range(1, 30):
        cue = select_cue("intermedio", semana, VERDE, exclude=frozenset({"molestia_rodilla"}))
        if cue is not None:
            assert "molestia_rodilla" not in cue.contraindications


def test_excluirlo_todo_devuelve_nada_en_vez_de_reventar() -> None:
    todas = frozenset({"dolor_agudo_activo"})
    assert select_cue("principiante", 1, VERDE, exclude=todas) is None


def test_la_seleccion_es_determinista() -> None:
    """Mismas entradas, misma señal. El coach no improvisa."""
    for semana in range(1, 20):
        assert select_cue("intermedio", semana, VERDE) == select_cue("intermedio", semana, VERDE)
