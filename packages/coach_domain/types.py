"""Vocabulario del dominio.

Todo lo que el motor manipula tiene un tipo con nombre aquí. No hay diccionarios
sueltos ni cadenas mágicas viajando entre módulos: si algo es una distancia de
carrera, es un `RaceDistance`, y el intérprete lo verifica.

Las estructuras son inmutables (`frozen=True`) a propósito. Un plan que se puede
mutar después de validarse es un plan que no está validado.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class RaceDistance(StrEnum):
    """Las cuatro distancias del reto."""

    K5 = "5k"
    K10 = "10k"
    K21 = "21k"
    K42 = "42k"


# Las distancias oficiales, no las redondeadas. Un medio maratón son 21.0975 km:
# usar 21 subestima el tiempo previsto en más de medio minuto, y en maratón la
# diferencia entre 42 y 42.195 pasa de los diez minutos de ritmo acumulado.
DISTANCE_KM: dict[RaceDistance, float] = {
    RaceDistance.K5: 5.0,
    RaceDistance.K10: 10.0,
    RaceDistance.K21: 21.0975,
    RaceDistance.K42: 42.195,
}


class Level(StrEnum):
    """Nivel del corredor. Determina la matriz de progresión (ADR 0003)."""

    PRINCIPIANTE = "principiante"
    INTERMEDIO = "intermedio"
    AVANZADO = "avanzado"


@dataclass(frozen=True)
class PaceRange:
    """Una franja de ritmo, en segundos por kilómetro.

    El nombre de los campos importa: en ritmo, **más rápido es un número más
    chico**. `min_sec_per_km` es el extremo rápido de la franja, no el «mínimo
    esfuerzo». Confundirlos produce planes al revés, así que el constructor lo
    verifica.
    """

    min_sec_per_km: int
    max_sec_per_km: int

    def __post_init__(self) -> None:
        if self.min_sec_per_km <= 0 or self.max_sec_per_km <= 0:
            raise ValueError("un ritmo tiene que ser positivo")
        if self.min_sec_per_km > self.max_sec_per_km:
            raise ValueError(
                f"franja invertida: {self.min_sec_per_km} es más lento que "
                f"{self.max_sec_per_km}; el primer campo es el extremo rápido"
            )

    @property
    def middle_sec_per_km(self) -> int:
        return (self.min_sec_per_km + self.max_sec_per_km) // 2


@dataclass(frozen=True)
class Zones:
    """Las cinco zonas de entrenamiento, de la más suave a la más dura."""

    z1: PaceRange
    z2: PaceRange
    z3: PaceRange
    z4: PaceRange
    z5: PaceRange

    def by_number(self, zone: int) -> PaceRange:
        if not 1 <= zone <= 5:
            raise ValueError("las zonas van de 1 a 5")
        return getattr(self, f"z{zone}")  # type: ignore[no-any-return]


@dataclass(frozen=True)
class AthleteProfile:
    """Lo que el motor necesita saber para prescribir.

    Es deliberadamente pequeño. El perfil completo —edad, peso, motivación,
    problemas prácticos— vive en la base de datos; aquí sólo entra lo que
    cambia un número. Todo lo demás cambia el **tono**, y el tono es asunto del
    prompt, no del motor.
    """

    user_id: str
    level: Level
    weekly_volume_km: float
    longest_run_km: float
    days_per_week: int
    reference_distance_km: float | None = None
    reference_time_sec: int | None = None
    base_cadence_spm: int | None = None
    injuries: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        if self.weekly_volume_km < 0:
            raise ValueError("el volumen semanal no puede ser negativo")
        if self.longest_run_km < 0:
            raise ValueError("la distancia más larga no puede ser negativa")
        if not 1 <= self.days_per_week <= 7:
            raise ValueError("los días por semana van de 1 a 7")
        # Un corredor no puede haber hecho una tirada más larga que su semana
        # entera. Si llega así, el dato está mal capturado y el plan que
        # saldría de él también lo estaría.
        if self.longest_run_km > self.weekly_volume_km and self.weekly_volume_km > 0:
            raise ValueError(
                "la tirada más larga no puede superar el volumen semanal; "
                "revisa el dato antes de planificar"
            )

    @property
    def has_reference(self) -> bool:
        return self.reference_distance_km is not None and self.reference_time_sec is not None
