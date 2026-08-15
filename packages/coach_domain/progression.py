"""Las ocho reglas de progresión.

Invariantes deterministas que el LLM no puede sobreescribir. El motor las valida
**antes** de emitir cualquier sesión, así que un plan ilegal no llega a existir.

    R1  Incremento gradual      el volumen sube como mucho el tope de la matriz
    R2  Descarga obligatoria    cada 4ª semana (3ª en maratón), −30 %
    R3  Tope de tirada larga    nunca más del 30 % del volumen semanal
    R4  Distribución 80/20      mínimo 80 % del volumen en zona conversacional
    R5  Una variable a la vez   no sube volumen e intensidad la misma semana
    R6  Regreso tras pausa      escalones de recuperación por días parado
    R7  Prerrequisito de meta   → vive en `plans/`, donde se genera el plan
    R8  Ambiente                calor o mala calidad de aire aflojan el ritmo

Sobre la fuente de los números: salen de la matriz de niveles de la Fase 1, que
a su vez recoge la práctica establecida en entrenamiento de resistencia. No son
verdades fisiológicas exactas, son topes conservadores; y su valor está tanto en
ser conservadores como en ser **explícitos, versionados y discutibles**.
"""

from __future__ import annotations

from dataclasses import dataclass

from coach_domain.types import Level, RaceDistance

# Incremento semanal máximo, tal como está en la matriz de la Fase 1. La matriz
# indexa por distancia porque asume el «perfil típico» de cada meta.
MAX_INCREASE_BY_DISTANCE: dict[RaceDistance, float] = {
    RaceDistance.K5: 0.05,
    RaceDistance.K10: 0.08,
    RaceDistance.K21: 0.10,
    RaceDistance.K42: 0.10,
}

# Pero ese supuesto se rompe con el corredor más frecuente y más expuesto: el
# principiante que se apunta a un maratón. Heredaría el 10 % del avanzado. Por
# eso el tope real es el mínimo de los dos, y el nivel puede frenar la distancia.
MAX_INCREASE_BY_LEVEL: dict[Level, float] = {
    Level.PRINCIPIANTE: 0.05,
    Level.INTERMEDIO: 0.08,
    Level.AVANZADO: 0.10,
}

DELOAD_PCT = 0.30
LONG_RUN_MAX_SHARE = 0.30
EASY_MIN_SHARE = 0.80

# Tolerancias de coma flotante. Sin ellas, una semana calculada por el propio
# motor puede fallar su propia validación por 1e-14, que es la clase de bug que
# aparece sólo en producción y sólo a veces.
_KM_EPS = 0.05
_SHARE_EPS = 0.005

# R8 · umbrales ambientales
HEAT_FROM_C = 28.0
HEAT_INDOOR_FROM_C = 35.0
AQI_UNHEALTHY_FROM = 150
MAX_PACE_ADJUSTMENT_SEC = 40


@dataclass(frozen=True)
class WeekLoad:
    """La carga de una semana, en la forma en que las reglas la miran."""

    index: int
    total_km: float
    long_run_km: float
    quality_sessions: int
    is_deload: bool
    # Kilómetros en zona conversacional. Es opcional porque una semana escrita a
    # mano puede no declararlo, y sin el dato R4 se calla en vez de inventar un
    # veredicto. `build_plan` siempre lo declara.
    easy_km: float | None = None
    # Semana de afinamiento previa a la carrera. El taper baja el volumen por
    # diseño y con su propia curva, así que sustituye a la cadencia de descargas
    # de R2 en lugar de convivir con ella.
    is_taper: bool = False


@dataclass(frozen=True)
class Violation:
    """Una regla incumplida, con el número que la incumple.

    El mensaje lleva la cifra concreta a propósito: «sube a 48 km, el tope es
    43.2» es accionable; «incremento excesivo» obliga a ir al código.
    """

    rule: str
    message: str


@dataclass(frozen=True)
class EnvironmentAdvice:
    """R8. Ajustar el **ritmo**, no el esfuerzo: con calor, el mismo esfuerzo
    produce un ritmo más lento, y exigir el ritmo de siempre es exigir más."""

    pace_adjustment_sec: int
    move_indoors: bool
    reason: str


# ── R1 ───────────────────────────────────────────────────────────────


def max_increase(distance: RaceDistance, level: Level) -> float:
    """Tope de incremento semanal. Manda el más conservador de los dos."""
    return min(MAX_INCREASE_BY_DISTANCE[distance], MAX_INCREASE_BY_LEVEL[level])


# ── R2 ───────────────────────────────────────────────────────────────


def deload_every(distance: RaceDistance) -> int:
    """Cada cuántas semanas toca descarga."""
    return 3 if distance is RaceDistance.K42 else 4


def is_deload_week(index: int, distance: RaceDistance) -> bool:
    return index > 0 and index % deload_every(distance) == 0


def next_week_volume(
    previous_km: float,
    index: int,
    distance: RaceDistance,
    level: Level,
) -> float:
    """Volumen de la semana `index`, dada la anterior. R1 y R2 combinadas."""
    if previous_km < 0:
        raise ValueError("el volumen previo no puede ser negativo")
    if is_deload_week(index, distance):
        return round(previous_km * (1 - DELOAD_PCT), 1)
    return round(previous_km * (1 + max_increase(distance, level)), 1)


# ── R6 ───────────────────────────────────────────────────────────────


def return_factor(days_off: int) -> float:
    """Qué fracción del volumen previo se retoma tras una pausa.

    El 0.0 no significa «no corras»: significa que el plan dejó de ser válido y
    hay que rehacerlo desde la base actual, no desde la que había hace un mes.
    """
    if days_off < 0:
        raise ValueError("los días sin correr no pueden ser negativos")
    if days_off <= 3:
        return 1.00
    if days_off <= 7:
        return 0.90
    if days_off <= 14:
        return 0.75
    if days_off <= 28:
        return 0.50
    return 0.0


# ── R8 ───────────────────────────────────────────────────────────────


def environment_advice(temp_c: float, aqi: int | None = None) -> EnvironmentAdvice:
    """Ajuste de ritmo por calor o calidad del aire."""
    ajuste = 0
    razones: list[str] = []
    interior = False

    if temp_c > HEAT_FROM_C:
        # +20 s/km al cruzar el umbral, +3 por cada grado extra, tope +40.
        ajuste = min(20 + round((temp_c - HEAT_FROM_C) * 3), MAX_PACE_ADJUSTMENT_SEC)
        razones.append(f"{temp_c:.0f} °C")
    if temp_c >= HEAT_INDOOR_FROM_C:
        interior = True
        razones.append("calor extremo")

    if aqi is not None and aqi >= AQI_UNHEALTHY_FROM:
        ajuste = min(max(ajuste, 20), MAX_PACE_ADJUSTMENT_SEC)
        interior = True
        razones.append(f"calidad del aire {aqi}")

    if not razones:
        return EnvironmentAdvice(0, False, "condiciones normales")
    return EnvironmentAdvice(ajuste, interior, ", ".join(razones))


# ── validación de una semana ─────────────────────────────────────────


def previous_reference(weeks: list[WeekLoad], index: int) -> WeekLoad | None:
    """La semana contra la que se compara la que está en `index`.

    No es simplemente la anterior. Una semana de descarga o de taper baja el
    volumen a propósito, así que medir la progresión contra ella daría dos
    lecturas falsas seguidas: primero un salto enorme al recuperar el nivel, y
    después un techo artificialmente bajo. La referencia correcta es la última
    semana de carga normal.

    Con esto R1 conserva su sentido —«no subas más del tope respecto a donde
    venías»— en vez de castigar el funcionamiento normal del plan.
    """
    for anterior in reversed(weeks[:index]):
        if not anterior.is_deload and not anterior.is_taper:
            return anterior
    return None


def validate_week(
    week: WeekLoad,
    previous: WeekLoad | None,
    distance: RaceDistance,
    level: Level,
) -> list[Violation]:
    """Devuelve todas las reglas que la semana incumple. Vacío es legal.

    `previous` es la **semana de referencia**, no necesariamente la inmediata
    anterior: ver `previous_reference`.

    Devuelve la lista completa y no la primera violación: si una semana rompe
    dos reglas, arreglar una y volver a fallar es una pérdida de tiempo para
    quien la corrige, sea una persona o el generador de planes.
    """
    problemas: list[Violation] = []
    tope_pct = max_increase(distance, level)

    # R2 · la descarga no es negociable, ni siquiera a petición del usuario.
    # El taper es la excepción: ya está bajando el volumen con su propia curva,
    # y exigirle además el −30 % de una descarga lo convertiría en reposo.
    toca_descarga = is_deload_week(week.index, distance) and not week.is_taper
    if toca_descarga and not week.is_deload:
        problemas.append(
            Violation("R2", f"la semana {week.index} tiene que ser de descarga y no lo es")
        )
    if week.is_deload and not week.is_taper and previous is not None:
        techo_descarga = previous.total_km * (1 - DELOAD_PCT) + _KM_EPS
        if week.total_km > techo_descarga:
            problemas.append(
                Violation(
                    "R2",
                    f"descarga insuficiente: {week.total_km} km, "
                    f"debería bajar a {techo_descarga - _KM_EPS:.1f}",
                )
            )

    # R1 · sólo aplica cuando se sube, y no durante una descarga.
    if previous is not None and not week.is_deload:
        techo = previous.total_km * (1 + tope_pct)
        if week.total_km > techo + _KM_EPS:
            problemas.append(
                Violation(
                    "R1",
                    f"sube a {week.total_km} km desde {previous.total_km}; "
                    f"el tope es {techo:.1f} ({tope_pct:.0%})",
                )
            )

    # R3 · la tirada larga es la sesión que más lesiona cuando se desmadra.
    if week.total_km > 0:
        proporcion = week.long_run_km / week.total_km
        if proporcion > LONG_RUN_MAX_SHARE + _SHARE_EPS:
            problemas.append(
                Violation(
                    "R3",
                    f"la tirada larga es el {proporcion:.0%} del volumen; "
                    f"el tope es {LONG_RUN_MAX_SHARE:.0%}",
                )
            )

    # R4 · sin el reparto declarado no se afirma nada.
    if week.easy_km is not None and week.total_km > 0:
        suave = week.easy_km / week.total_km
        if suave < EASY_MIN_SHARE - _SHARE_EPS:
            problemas.append(
                Violation(
                    "R4",
                    f"sólo el {suave:.0%} del volumen es suave; el mínimo es {EASY_MIN_SHARE:.0%}",
                )
            )

    # R5 · dos estímulos nuevos a la vez es cómo se acumula fatiga sin notarlo.
    #
    # No aplica después de una descarga. La semana de descarga baja el volumen y
    # retira la calidad, así que la siguiente sube las dos cosas por definición;
    # comparar contra esa base artificialmente baja marcaría como infracción lo
    # que en realidad es volver al punto de partida, no un estímulo nuevo. Quien
    # sí controla que ese regreso sea moderado es R1, que mide contra la semana
    # de descarga y por tanto es más conservador todavía.
    if previous is not None and not week.is_deload and not previous.is_deload:
        sube_volumen = week.total_km > previous.total_km + _KM_EPS
        sube_calidad = week.quality_sessions > previous.quality_sessions
        if sube_volumen and sube_calidad:
            problemas.append(Violation("R5", "sube volumen e intensidad en la misma semana"))

    return problemas
