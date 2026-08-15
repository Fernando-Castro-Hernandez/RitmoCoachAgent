"""Clarificación autónoma: qué necesita saber el coach antes de prescribir.

**El corazón del pivote.** Un generador de planes que acepta lo primero que le
dicen es el fallo que el *Wall Street Journal* documentó sobre Runna: *el
algoritmo toma al corredor por su palabra*. Alguien dice «quiero correr un
maratón» y recibe dieciséis semanas de plan sin que nadie le haya preguntado
cuánto corre hoy.

Que el motor rechace después un plan ilegal está bien, pero llega tarde: para
entonces el corredor ya recibió un número. La defensa tiene que actuar **antes
de que la herramienta se ejecute**.

Y por eso vive en código y no sólo en el prompt. El prompt le dice al modelo que
pregunte; esto hace que no pueda hacer otra cosa. Es la misma defensa en
profundidad que la puerta de seguridad (ADR 0013): si el prompt falla, el código
aguanta.
"""

from __future__ import annotations

from typing import Literal

from coach_domain.types import AthleteProfile

# En orden de importancia. El orden es el guion de la conversación: si falta
# todo, el coach pregunta primero por el volumen semanal, que es el dato que más
# determina el plan y el que un corredor sabe responder sin pensar.
VITAL_FIELDS: tuple[str, ...] = (
    "weekly_volume_km",
    "injuries",
    "longest_run_km",
    "days_per_week",
    "reference_pace",
)

# Cómo preguntar por cada campo. Están aquí y no en el prompt para que el coach
# no reinvente la pregunta cada vez y para que se puedan revisar en el pull
# request como cualquier otro texto de producto.
QUESTIONS: dict[str, str] = {
    "weekly_volume_km": "¿Cuántos kilómetros corres a la semana ahorita?",
    "injuries": "¿Traes alguna molestia o lesión, aunque sea de hace unos meses?",
    "longest_run_km": "¿Cuál es la distancia más larga que ya corriste?",
    "days_per_week": "¿Cuántos días a la semana puedes correr?",
    "reference_pace": "¿Tienes algún tiempo reciente que me sirva de referencia?",
}

# Tres turnos de clarificación y se genera algo conservador diciendo qué se
# asumió. Un coach que pregunta seis cosas seguidas se siente como un
# formulario, y el formulario es justo de lo que huimos.
MAX_CLARIFICATION_TURNS = 3


def clarification_budget(topic: Literal["planning", "safety"]) -> int | None:
    """Cuántas preguntas caben antes de actuar. `None` es «sin límite».

    La seguridad no tiene techo. Si hay una molestia reportada, el coach indaga
    hasta cerrar el asunto cueste los turnos que cueste: una lesión mal
    explorada no se compensa con brevedad.
    """
    return None if topic == "safety" else MAX_CLARIFICATION_TURNS


def missing_vital_context(profile: dict[str, object] | None) -> list[str]:
    """Qué falta por preguntar, en orden de importancia.

    Un campo cuenta como conocido cuando **alguien lo respondió**, no cuando
    tiene un valor. `weekly_volume_km = 0` es una respuesta legítima —hay
    corredores que arrancan de cero— y `None` es «nadie se lo preguntó». Por eso
    las columnas del perfil son anulables: un valor por defecto haría que el
    coach creyera saber algo que nadie le dijo.
    """
    if not profile:
        return list(VITAL_FIELDS)

    faltantes: list[str] = []
    for campo in VITAL_FIELDS:
        if campo == "reference_pace":
            conocido = (
                profile.get("reference_distance_km") is not None
                and profile.get("reference_time_sec") is not None
            )
        else:
            conocido = profile.get(campo) is not None
        if not conocido:
            faltantes.append(campo)
    return faltantes


def next_clarifying_question(profile: dict[str, object] | None) -> str | None:
    """La siguiente pregunta a hacer, o `None` si ya no falta nada vital."""
    faltantes = missing_vital_context(profile)
    return QUESTIONS[faltantes[0]] if faltantes else None


def profile_to_dict(profile: AthleteProfile) -> dict[str, object]:
    """Un perfil del dominio en la forma que espera `missing_vital_context`."""
    return {
        "weekly_volume_km": profile.weekly_volume_km,
        "injuries": list(profile.injuries),
        "longest_run_km": profile.longest_run_km,
        "days_per_week": profile.days_per_week,
        "reference_distance_km": profile.reference_distance_km,
        "reference_time_sec": profile.reference_time_sec,
    }
