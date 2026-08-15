"""La puerta de seguridad.

Decide si el coach puede prescribir entrenamiento. Su veredicto se evalúa
**antes** de que el modelo redacte una sola palabra, y cuando sale rojo las
herramientas de prescripción dejan de estar disponibles: el prompt y el código
dicen lo mismo, y si el prompt falla, el código aguanta (ADR 0013).

Es deliberadamente aburrida. Sin modelos, sin umbrales aprendidos, sin
probabilidad: una tabla de reglas que cabe en una pantalla y que cualquiera
—incluido un fisioterapeuta que no programa— puede leer y discutir. Esa
auditabilidad *es* la característica.

**Lo que esto no es.** No es un diagnóstico ni un triaje clínico. Es un filtro
conservador que decide cuándo un coach automático debe callarse y mandar con
alguien. Prefiere equivocarse mandando de más.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum


class SafetyLevel(StrEnum):
    GREEN = "green"
    AMBER = "amber"
    RED = "red"


# Banderas que exigen atención médica **ahora**, no una cita la semana que
# viene. No son lesiones de carrera: son señales de que algo puede estar mal
# más allá del aparato locomotor.
EMERGENCY_FLAGS: frozenset[str] = frozenset(
    {
        "chest_pain",
        "dizziness_syncope",
        "disproportionate_dyspnea",
    }
)

# El resto de banderas rojas. Cada una describe un **mecanismo**, no una
# intensidad, y por eso ganan sobre cualquier puntaje de dolor: alguien puede
# reportar un 2 de dolor y estar cojeando.
_MUSCULOSKELETAL_FLAGS: frozenset[str] = frozenset(
    {
        "altered_gait",  # cojea o cambia la forma de correr para evitar el dolor
        "bone_point_pain",  # duele un punto exacto del hueso — sospecha de estrés
        "worsens_during_run",  # empeora mientras corre, en vez de aflojar
        "night_or_rest_pain",  # duele en reposo o de noche
        "swelling",  # hinchazón visible
        "numbness_tingling",  # adormecimiento u hormigueo
    }
)

# Condiciones que no son una lesión pero que sacan la prescripción del alcance
# de un coach automático.
_CONDITION_FLAGS: frozenset[str] = frozenset(
    {
        "pregnancy",
        "known_cardiac_condition",
    }
)

RED_FLAGS: frozenset[str] = EMERGENCY_FLAGS | _MUSCULOSKELETAL_FLAGS | _CONDITION_FLAGS

# Umbrales del semáforo. Están aquí arriba y con nombre para que se puedan
# discutir sin leer la función.
AMBER_FROM = 3
RED_FROM = 5
PERSISTENCE_DAYS = 3

_EMERGENCY_MSG = (
    "Lo que me describes necesita atención médica inmediata. "
    "Por favor deja de entrenar y busca ayuda ahora mismo."
)
_REFERRAL_MSG = (
    "Eso que sientes merece que lo revise un profesional antes de que sigamos. "
    "No voy a darte entrenamiento hasta que lo veas."
)


@dataclass(frozen=True)
class SafetyVerdict:
    """El resultado de la puerta.

    `reason` no es decorativo: se guarda en `coach_decision` junto a cada
    decisión, y es lo que permite reconstruir después por qué el coach frenó.
    """

    level: SafetyLevel
    reason: str
    allows_prescription: bool
    referral_message: str | None


def assess(
    pain_score: int,
    flags: Sequence[str] = (),
    days_persisting: int = 0,
) -> SafetyVerdict:
    """Evalúa si se puede prescribir entrenamiento.

    Args:
        pain_score: dolor reportado de 0 a 10.
        flags: banderas presentes, de `RED_FLAGS`.
        days_persisting: días seguidos con la misma molestia.

    Raises:
        ValueError: si el puntaje sale de la escala o una bandera no se
            reconoce. Un nombre mal escrito no puede degradarse a «sin
            bandera»: eso convertiría un typo en un permiso para entrenar.
    """
    if not 0 <= pain_score <= 10:
        raise ValueError("el dolor se reporta de 0 a 10")
    if days_persisting < 0:
        raise ValueError("los días de persistencia no pueden ser negativos")

    presentes = set(flags)
    if desconocidas := presentes - RED_FLAGS:
        raise ValueError(f"no reconozco estas banderas: {sorted(desconocidas)}")

    # El orden importa: se evalúa de lo más grave a lo menos grave, y la
    # primera regla que dispara es la que manda.
    if presentes & EMERGENCY_FLAGS:
        return SafetyVerdict(
            SafetyLevel.RED,
            f"bandera de urgencia: {sorted(presentes & EMERGENCY_FLAGS)}",
            allows_prescription=False,
            referral_message=_EMERGENCY_MSG,
        )

    if presentes:
        return SafetyVerdict(
            SafetyLevel.RED,
            f"bandera roja presente: {sorted(presentes)}",
            allows_prescription=False,
            referral_message=_REFERRAL_MSG,
        )

    if pain_score >= RED_FROM:
        return SafetyVerdict(
            SafetyLevel.RED,
            f"dolor de {pain_score}, umbral {RED_FROM}",
            allows_prescription=False,
            referral_message=_REFERRAL_MSG,
        )

    if pain_score >= AMBER_FROM:
        # El dolor que no cede solo dejó de ser fatiga. Es la regla que más
        # lesiones evita: seguir entrenando encima de una molestia persistente
        # es cómo tres días de incomodidad se vuelven seis semanas de baja.
        if days_persisting >= PERSISTENCE_DAYS:
            return SafetyVerdict(
                SafetyLevel.RED,
                f"molestia de {pain_score} persistente {days_persisting} días",
                allows_prescription=False,
                referral_message=_REFERRAL_MSG,
            )
        return SafetyVerdict(
            SafetyLevel.AMBER,
            f"molestia moderada de {pain_score}, {days_persisting} días",
            allows_prescription=True,
            referral_message=None,
        )

    return SafetyVerdict(
        SafetyLevel.GREEN,
        f"sin dolor relevante ({pain_score})",
        allows_prescription=True,
        referral_message=None,
    )
