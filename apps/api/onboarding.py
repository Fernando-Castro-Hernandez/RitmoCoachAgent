"""Onboarding híbrido: qué captura el formulario y qué captura la voz.

**El reparto es la decisión, no el formulario.** El carrusel de React captura lo
duro; la conversación captura lo blando. En una frase: *el formulario captura lo
que el corredor **afirma**; la conversación captura lo que **revela**.*

Preguntar la edad por voz es lento y propenso a error de transcripción, y el
dato es trivial. Preguntar «¿alguna molestia?» por formulario produce una
casilla sin marcar; preguntarlo hablando produce «bueno, la rodilla a veces,
pero nada grave» — que es exactamente el dato que importa y el que un formulario
no puede capturar.

Y hay un efecto de producto: con el perfil duro ya cargado, el primer turno del
coach deja de ser «¿cómo te llamas?» y pasa a ser algo que demuestra que ya sabe
con quién habla.
"""

from __future__ import annotations

from typing import Any

from apps.api.clarification import QUESTIONS as VITAL_QUESTIONS

# ── el reparto ───────────────────────────────────────────────────────

#: Datos discretos y verificables. Un formulario los captura mejor, más rápido y
#: sin error de transcripción.
HARD_FIELDS: tuple[str, ...] = (
    "goal_distance",
    "race_date",
    "days_per_week",
    "age",
    "weight_kg",
    "height_cm",
    "reference_distance_km",
    "reference_time_sec",
    "timezone",
)

#: Necesitan matiz, repregunta y detección de contradicciones. Un formulario los
#: aplana: nadie escribe «me molesta la rodilla pero sólo en bajadas» en un
#: campo de texto, y sí lo dice hablando.
SOFT_FIELDS: tuple[str, ...] = (
    "weekly_volume_km",
    "longest_run_km",
    "injuries",
    "practical_problems",
    "technique_experience",
    "base_cadence_spm",
    "motivation",
)

REQUIRED_FIELDS: tuple[str, ...] = HARD_FIELDS + SOFT_FIELDS

#: Lo único sin lo que el carrusel no puede terminar. Todo lo demás se salta:
#: un onboarding que exige nueve respuestas antes de dejarte entrar es un
#: onboarding que la gente abandona.
CAROUSEL_REQUIRED: tuple[str, ...] = ("goal_distance",)

# Preguntas de la capa blanda que no son campos vitales de planificación. Las
# vitales ya están redactadas en `clarification.QUESTIONS`, y se reutilizan para
# que el corredor no oiga dos versiones distintas de la misma pregunta.
_SOFT_QUESTIONS: dict[str, str] = {
    "practical_problems": (
        "¿Qué se te complica más cuando sales a correr? Cualquier cosa: "
        "la hora, la ruta, el calor, lo que sea."
    ),
    "technique_experience": "¿Alguien te ha dado indicaciones de técnica al correr?",
    "base_cadence_spm": ("¿Sabes más o menos tu cadencia, o tu reloj la mide?"),
    "motivation": "¿Y por qué esta carrera? ¿Qué te movió a apuntarte?",
}

QUESTIONS: dict[str, str] = {**VITAL_QUESTIONS, **_SOFT_QUESTIONS}

# El orden de la conversación. Lo vital primero: si el corredor se aburre y se
# va al tercer turno, mejor que se haya ido habiendo contestado lo que hace
# falta para planificar.
_SOFT_ORDER: tuple[str, ...] = (
    "weekly_volume_km",
    "injuries",
    "longest_run_km",
    "practical_problems",
    "technique_experience",
    "base_cadence_spm",
    "motivation",
)


def can_finish_carousel(answers: dict[str, Any] | None) -> bool:
    """Si el carrusel puede cerrarse con lo que lleva.

    Acepta `None`, que es lo que devuelve el perfil de una cuenta recién creada.
    Antes reventaba: con la identidad en el navegador nunca llegaba un `None`
    aquí, porque el perfil se creaba antes de preguntar nada. Con cuentas, el
    primer sitio que consulta esto es la respuesta del registro.
    """
    if not answers:
        return False
    return all(answers.get(c) is not None for c in CAROUSEL_REQUIRED)


def next_question(profile: dict[str, Any] | None) -> str | None:
    """La siguiente pregunta que le toca hacer a la voz, o `None` si ya está.

    Sólo pregunta por la capa blanda: lo que el carrusel ya capturó no se
    vuelve a preguntar, y ésa es la mitad del valor del reparto. Un coach que
    te pregunta la edad después de que la escribiste se siente roto.
    """
    campo = next_field(profile)
    return QUESTIONS[campo] if campo else None


def next_field(profile: dict[str, Any] | None) -> str | None:
    datos = profile or {}
    for campo in _SOFT_ORDER:
        if datos.get(campo) is None:
            return campo
    return None


def profile_completeness(profile: dict[str, Any] | None) -> float:
    """De 0 a 1. Alimenta la barra de progreso y las métricas."""
    datos = profile or {}
    conocidos = sum(1 for c in REQUIRED_FIELDS if datos.get(c) is not None)
    return round(conocidos / len(REQUIRED_FIELDS), 3)


def field_layer(field: str) -> str:
    """A qué capa pertenece un campo. Lo usa la interfaz para saber si un dato
    lo pide en pantalla o lo deja para la conversación."""
    if field in HARD_FIELDS:
        return "hard"
    if field in SOFT_FIELDS:
        return "soft"
    raise ValueError(f"«{field}» no es un campo del onboarding")
