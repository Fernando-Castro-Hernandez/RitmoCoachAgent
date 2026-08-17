"""Técnica de carrera.

La característica que salió de la investigación de usuario: la base de la
pirámide que ningún competidor cubre (ADR 0011). Strava registra, Nike Run Club
acompaña, Runna planifica carga. Ninguno enseña a correr.

Dos piezas, con la misma filosofía que el resto del motor:

- **La cadencia objetivo es una fórmula**, no un número que el modelo recite. El
  objetivo universal de 180 pasos por minuto es un mito procedente de una
  observación sobre élites en 1984; lo que tiene respaldo es subir entre un 5 y
  un 10 % sobre la cadencia **propia** del corredor.
- **Las señales son datos curados**, no generación libre. Un consejo de técnica
  improvisado puede lesionar a alguien, igual que un número inventado.

Y la seguridad manda: con dolor activo —ámbar incluido— no se emite ninguna
señal. Corregir la zancada de alguien que ya tiene una molestia es cambiar la
carga justo donde no toca.
"""

from __future__ import annotations

import functools
from collections.abc import Collection
from dataclasses import dataclass
from pathlib import Path

import yaml

from coach_domain.paces import round_half_up
from coach_domain.safety import SafetyLevel, SafetyVerdict

_CUES_FILE = Path(__file__).parent / "data" / "technique_cues.yaml"

# Cuántas semanas se sostiene la misma señal antes de pasar a la siguiente. Un
# entrenador real no dicta ocho correcciones: da una y la repite hasta que se
# automatiza.
CUE_ROTATION_WEEKS = 2

CADENCE_START_INCREASE = 0.05
CADENCE_WEEKLY_INCREASE = 0.01
CADENCE_MAX_INCREASE = 0.10


class UnknownCueError(KeyError):
    """Se pidió una señal que no está en la biblioteca.

    Importa que sea un error y no un `None`: la herramienta que expone esto al
    modelo (`explain_technique_cue`) recibe un identificador que el propio
    modelo eligió, y un identificador inventado tiene que fallar ruidosamente.
    """


@dataclass(frozen=True)
class TechniqueCue:
    id: str
    category: str
    levels: tuple[str, ...]
    moment: str
    voice_text: str
    long_explanation: str
    contraindications: tuple[str, ...]


@functools.cache
def load_cues() -> tuple[TechniqueCue, ...]:
    """La biblioteca completa, en el orden de enseñanza del YAML.

    Se cachea: el archivo no cambia en tiempo de ejecución y leer el disco en
    cada turno de una conversación de voz es latencia regalada.
    """
    crudo = yaml.safe_load(_CUES_FILE.read_text(encoding="utf-8"))
    return tuple(
        TechniqueCue(
            id=item["id"],
            category=item["categoria"],
            levels=tuple(item["nivel"]),
            moment=item["momento"],
            voice_text=" ".join(item["texto_voz"].split()),
            long_explanation=" ".join(item["explicacion_larga"].split()),
            contraindications=tuple(item.get("contraindicaciones", ())),
        )
        for item in crudo
    )


def get_cue(cue_id: str) -> TechniqueCue:
    for cue in load_cues():
        if cue.id == cue_id:
            return cue
    raise UnknownCueError(f"no existe la señal «{cue_id}»")


def target_cadence(base_spm: int, weeks_worked: int) -> int:
    """Cadencia objetivo: +5 % inicial, +1 % por semana trabajada, tope +10 %.

    Si no se conoce `base_spm`, el sistema **no inventa un objetivo**: lanza, y
    el coach le pide al corredor que la cuente durante 30 segundos o la lea de
    su reloj.
    """
    if base_spm <= 0:
        raise ValueError("la cadencia base debe ser mayor que cero; pídesela al corredor")
    if weeks_worked < 0:
        raise ValueError("las semanas trabajadas no pueden ser negativas")
    incremento = min(
        CADENCE_START_INCREASE + CADENCE_WEEKLY_INCREASE * weeks_worked,
        CADENCE_MAX_INCREASE,
    )
    return round_half_up(base_spm * (1 + incremento))


def select_cue(
    level: str,
    week_index: int,
    safety: SafetyVerdict,
    exclude: Collection[str] = (),
) -> TechniqueCue | None:
    """La señal de esta semana, o `None` si no toca enseñar técnica.

    Args:
        level: nivel del corredor.
        week_index: semana del plan, empezando en 1.
        safety: veredicto vigente. Cualquier cosa que no sea verde corta.
        exclude: contraindicaciones activas del corredor.
    """
    # La puerta de seguridad tiene prioridad sobre cualquier señal. Ámbar
    # incluido: con molestia activa no se toca la mecánica de la zancada.
    if safety.level is not SafetyLevel.GREEN:
        return None

    vetadas = set(exclude)
    candidatas = [
        c
        for c in load_cues()
        if level in c.levels and not vetadas.intersection(c.contraindications)
    ]
    if not candidatas:
        return None

    # La misma señal durante `CUE_ROTATION_WEEKS` semanas, y luego la siguiente.
    # El módulo hace que la rotación dé la vuelta en vez de agotarse.
    bloque = (max(week_index, 1) - 1) // CUE_ROTATION_WEEKS
    return candidatas[bloque % len(candidatas)]


def select_cue_by_category(
    category: str,
    *,
    level: str,
    week_index: int,
    safety: SafetyVerdict,
    exclude: Collection[str] = (),
) -> TechniqueCue | None:
    """La señal de una categoría concreta, con los mismos filtros que `select_cue`.

    La usa la ruta de vídeo: el modelo dice qué observó, el mapa de la API lo
    traduce a una categoría, y la señal sale de aquí — de la misma biblioteca
    curada que se dice por voz, con la misma puerta de seguridad delante.

    Devuelve `None` cuando la categoría no tiene señal para este corredor: nivel
    que no la incluye, contraindicación activa, o veredicto que no es verde. Los
    tres casos significan lo mismo de cara al producto —esta vez no se le dice
    nada— y por eso comparten valor de retorno en vez de tres excepciones que
    el llamador tendría que distinguir para acabar haciendo lo mismo.
    """
    if safety.level is not SafetyLevel.GREEN:
        return None

    vetadas = set(exclude)
    candidatas = [
        c
        for c in load_cues()
        if c.category == category
        and level in c.levels
        and not vetadas.intersection(c.contraindications)
    ]
    if not candidatas:
        return None

    # Si una categoría llegara a tener varias señales, se rota igual que en
    # `select_cue`: la misma durante `CUE_ROTATION_WEEKS` semanas.
    bloque = (max(week_index, 1) - 1) // CUE_ROTATION_WEEKS
    return candidatas[bloque % len(candidatas)]
