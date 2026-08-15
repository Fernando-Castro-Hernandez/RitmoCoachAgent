"""Ritmos, zonas y predicción de rendimiento.

La capa más baja del motor. Todo lo demás calcula encima de estas funciones, y
**cada cifra que el coach pronuncia sale de aquí o de un módulo que llama aquí**
(ADR 0003). El modelo de lenguaje no hace aritmética.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal

from coach_domain.types import PaceRange, Zones

# Exponente de la fórmula de Riegel (1981). Refleja que el ritmo sostenible se
# degrada al alargar la distancia: correr el doble cuesta algo más del doble.
RIEGEL_EXPONENT = 1.06

# El umbral funcional se aproxima como el ritmo de 10 K un 3 % más lento. Es una
# aproximación de campo, no una medición de lactato: sirve para anclar zonas de
# entrenamiento, no para fisiología. Queda documentado para que nadie lo lea
# como más de lo que es.
THRESHOLD_FROM_10K = 1.03

# Fronteras de zona como múltiplos del ritmo umbral. Se declaran como una sola
# escalera y no como pares independientes: así las zonas quedan contiguas por
# construcción y no puede aparecer un hueco por un redondeo distinto en cada
# lado de la frontera.
_ZONE_EDGES: tuple[float, float, float, float, float, float] = (
    0.90,  # extremo rápido de Z5
    0.97,  # Z5 │ Z4
    1.06,  # Z4 │ Z3
    1.15,  # Z3 │ Z2
    1.29,  # Z2 │ Z1
    1.40,  # extremo lento de Z1
)

_PACE_PATTERN = re.compile(r"^(\d{1,3})\s*[:'′]\s*(\d{1,2})\s*[\"″]?$")


def _round_half_up(value: float) -> int:
    """Redondeo como lo espera una persona: el medio siempre sube.

    `round()` de Python usa redondeo bancario —al par más cercano— así que
    `round(337.5)` da 338 pero `round(336.5)` da 336. Para una cifra que el
    coach dice en voz alta eso es inaceptable: dos carreras equivalentes
    tendrían que redondear igual, y explicar el redondeo bancario a un corredor
    no es una conversación que nadie quiera tener.
    """
    return int(Decimal(str(value)).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def pace_from_run(distance_km: float, duration_sec: int) -> int:
    """Ritmo medio de una carrera, en segundos por kilómetro."""
    if distance_km <= 0:
        raise ValueError("la distancia debe ser mayor que cero")
    if duration_sec <= 0:
        raise ValueError("la duración debe ser mayor que cero")
    return _round_half_up(duration_sec / distance_km)


def riegel_predict(known_km: float, known_sec: int, target_km: float) -> int:
    """Predice el tiempo en otra distancia: `T2 = T1 · (D2/D1)^1.06`.

    Es la fórmula que permite decirle a alguien que corrió 10 K en 50 minutos
    qué le tocaría en un medio maratón. Pierde precisión en los extremos —muy
    corto o mucho más largo que la referencia— y por eso el motor sólo la usa
    para anclar zonas y proyecciones, nunca para prometer una marca.
    """
    if known_km <= 0 or target_km <= 0:
        raise ValueError("las distancias deben ser mayores que cero")
    if known_sec <= 0:
        raise ValueError("el tiempo de referencia debe ser mayor que cero")
    return _round_half_up(known_sec * (target_km / known_km) ** RIEGEL_EXPONENT)


def threshold_pace(known_km: float, known_sec: int) -> int:
    """Ritmo umbral aproximado, ancla de todas las zonas."""
    t10 = riegel_predict(known_km, known_sec, 10.0)
    return _round_half_up(t10 / 10.0 * THRESHOLD_FROM_10K)


def zones_from_effort(known_km: float, known_sec: int) -> Zones:
    """Las cinco zonas de ritmo derivadas de un esfuerzo conocido."""
    umbral = threshold_pace(known_km, known_sec)
    bordes = [_round_half_up(umbral * factor) for factor in _ZONE_EDGES]
    # bordes va de rápido a lento; las zonas se numeran al revés.
    return Zones(
        z5=PaceRange(bordes[0], bordes[1]),
        z4=PaceRange(bordes[1], bordes[2]),
        z3=PaceRange(bordes[2], bordes[3]),
        z2=PaceRange(bordes[3], bordes[4]),
        z1=PaceRange(bordes[4], bordes[5]),
    )


def format_pace(sec_per_km: int) -> str:
    """337 → «5:37». Es la forma en que un corredor lee un ritmo."""
    if sec_per_km <= 0:
        raise ValueError("un ritmo tiene que ser positivo")
    return f"{sec_per_km // 60}:{sec_per_km % 60:02d}"


def parse_pace(text: str) -> int:
    """«5:37» → 337. Acepta también «5'37"», que es como lo escriben muchos."""
    coincidencia = _PACE_PATTERN.match(text.strip())
    if coincidencia is None:
        raise ValueError(f"no reconozco «{text}» como un ritmo; se espera «5:37»")
    minutos, segundos = int(coincidencia.group(1)), int(coincidencia.group(2))
    if segundos >= 60:
        raise ValueError(f"«{text}» tiene más de 59 segundos en el campo de segundos")
    return minutos * 60 + segundos
