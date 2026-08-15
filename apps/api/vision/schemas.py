"""Lo que la ruta de visión puede devolver, y nada más.

El esquema no es documentación: se le pasa a Bedrock como `toolConfig`, y el
modelo queda obligado a rellenarlo. Esa obligación es también la defensa contra
inyección: **una imagen con texto que parezca una orden no tiene ningún campo
donde alojarla** (ADR 0014).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

Confidence = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class WorkoutExtraction:
    """Lo que se leyó en la captura. Sólo lectura: aquí no se calcula nada."""

    distance_km: float | None
    duration_sec: int | None
    avg_pace_sec_per_km: int | None
    avg_hr: int | None
    confidence: Confidence
    unreadable_fields: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ProposedSession:
    """Lo que se le propone al corredor para que lo confirme.

    **No se guarda nada hasta que lo vea.** Una cifra mal leída que entra a la
    bitácora contamina la progresión, y la progresión es el producto.
    """

    distance_km: float
    duration_sec: int
    pace_sec_per_km: int
    avg_hr: int | None
    needs_confirmation: bool
    discrepancy_flag: bool
    source: str
    notes: str = ""


WORKOUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "distance_km": {
            "type": ["number", "null"],
            "description": "Distancia total. Si la pantalla dice millas, conviértelas a km.",
        },
        "duration_sec": {
            "type": ["integer", "null"],
            "description": "Duración total en segundos.",
        },
        "avg_pace_sec_per_km": {
            "type": ["integer", "null"],
            "description": "Ritmo medio en segundos por kilómetro, tal como aparece.",
        },
        "avg_hr": {
            "type": ["integer", "null"],
            "description": "Frecuencia cardiaca media en pulsaciones por minuto.",
        },
        "confidence": {
            "type": "string",
            "enum": ["high", "medium", "low"],
            "description": (
                "high si los números se leen limpios; medium si alguno es dudoso; "
                "low si la imagen está borrosa, cortada o no es un entrenamiento."
            ),
        },
        "unreadable_fields": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Campos que no se pudieron leer.",
        },
    },
    "required": ["confidence", "unreadable_fields"],
}


GAIT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "observable": {
                        "type": "string",
                        "enum": [
                            "foot_strike_position",
                            "hip_drop",
                            "arm_crossover",
                            "trunk_lean",
                            "cadence_impression",
                        ],
                    },
                    "assessment": {"type": "string", "enum": ["ok", "watch", "flag"]},
                    "note": {
                        "type": "string",
                        "description": (
                            "Una frase, escrita para decirse en voz alta. Sin ángulos, "
                            "sin grados y sin nombres de lesiones."
                        ),
                    },
                },
                "required": ["observable", "assessment", "note"],
            },
        }
    },
    "required": ["findings"],
}
