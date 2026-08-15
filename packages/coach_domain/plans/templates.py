"""La matriz de niveles de la Fase 1, codificada.

Un solo lugar con todos los parámetros por distancia. Está aislado a propósito:
son los números que un entrenador humano querría revisar y discutir, y tenerlos
dispersos por el generador los volvería imposibles de auditar.

Fuente: sección «Matriz de niveles» de `docs/fases/fase-1-alcance-y-viabilidad.html`.
"""

from __future__ import annotations

from dataclasses import dataclass

from coach_domain.types import RaceDistance


@dataclass(frozen=True)
class DistanceTemplate:
    """Los parámetros de una distancia. Los rangos de la matriz se guardan
    completos; el generador usa el tope superior como techo y el inferior
    como referencia de lo razonable."""

    min_weeks: int
    max_weeks: int
    min_days: int
    max_days: int
    peak_volume_km: float
    peak_long_run_km: float
    quality_sessions: int
    taper_days: int
    taper_reduction: float
    method: str
    required_base: str


TEMPLATES: dict[RaceDistance, DistanceTemplate] = {
    RaceDistance.K5: DistanceTemplate(
        min_weeks=8,
        max_weeks=10,
        min_days=3,
        max_days=3,
        peak_volume_km=25.0,
        peak_long_run_km=10.0,
        quality_sessions=1,
        taper_days=7,
        taper_reduction=0.40,
        method="correr-caminar",
        required_base="caminar 30 minutos seguidos",
    ),
    RaceDistance.K10: DistanceTemplate(
        min_weeks=10,
        max_weeks=12,
        min_days=3,
        max_days=4,
        peak_volume_km=40.0,
        peak_long_run_km=16.0,
        quality_sessions=1,
        taper_days=10,
        taper_reduction=0.45,
        method="continuo + fartlek",
        required_base="correr 5 K continuos",
    ),
    RaceDistance.K21: DistanceTemplate(
        min_weeks=12,
        max_weeks=16,
        min_days=4,
        max_days=5,
        peak_volume_km=65.0,
        peak_long_run_km=21.0,
        quality_sessions=2,
        taper_days=14,
        taper_reduction=0.50,
        method="continuo + tempo",
        required_base="25–30 km por semana durante 4 semanas",
    ),
    RaceDistance.K42: DistanceTemplate(
        min_weeks=16,
        max_weeks=20,
        min_days=5,
        max_days=6,
        peak_volume_km=90.0,
        peak_long_run_km=35.0,
        quality_sessions=2,
        taper_days=21,
        taper_reduction=0.55,
        method="polarizado 80/20",
        required_base="40–50 km por semana durante 6–8 semanas y un 21 K",
    ),
}

# Volumen de arranque para quien viene de cero. No es un incremento —es el punto
# de partida— y por eso no lo gobierna R1. Corresponde a un esquema de
# correr–caminar de tres días.
START_FLOOR_KM = 8.0

# Cuánto ocupa la tirada larga del volumen semanal. Deliberadamente por debajo
# del tope de R3 (30 %): dejar margen evita que un redondeo convierta un plan
# legal en uno que el propio motor rechaza.
LONG_RUN_SHARE = 0.28

# Fracción del volumen semanal que se lleva cada sesión de calidad. Con un
# máximo de dos sesiones, el trabajo duro se queda en el 18 % y R4 (mínimo 80 %
# suave) se cumple por construcción.
QUALITY_SHARE = 0.09
