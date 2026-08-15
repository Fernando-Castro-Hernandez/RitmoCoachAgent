"""Generación de planes de entrenamiento.

Donde se junta todo el motor: la matriz de la Fase 1, las reglas R1–R8, la
puerta de seguridad y la biblioteca de técnica. **Éste es el módulo que el LLM
no puede sustituir.** Cuando el coach dice «hoy te tocan 14 kilómetros», el 14
sale de aquí.

La garantía dura: `build_plan` valida el plan completo contra `validate_week`
antes de devolverlo, y lanza si encuentra una sola violación. El motor no puede
emitir un plan ilegal ni por error de programación. Esa comprobación es
redundante con la construcción —y precisamente por eso vale: convierte un bug
futuro en una excepción ruidosa en vez de en un plan que alguien va a correr.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, timedelta

from coach_domain.paces import zones_from_effort
from coach_domain.plans.templates import (
    LONG_RUN_SHARE,
    QUALITY_SHARE,
    START_FLOOR_KM,
    TEMPLATES,
    DistanceTemplate,
)
from coach_domain.progression import (
    WeekLoad,
    is_deload_week,
    next_week_volume,
    previous_reference,
    validate_week,
)
from coach_domain.safety import assess
from coach_domain.technique import select_cue
from coach_domain.types import AthleteProfile, Level, PaceRange, RaceDistance

# Días de la semana, lunes = 0. La tirada larga va en domingo por defecto: es
# cuando la mayoría tiene tiempo, y así el lunes queda libre para descansar.
LONG_RUN_DAY = 6
_QUALITY_DAYS = (2, 4)  # miércoles, viernes
# Orden de preferencia para las sesiones suaves. Incluye los días de calidad al
# final porque en descarga y en taper la calidad se retira, y esos huecos pasan
# a estar libres: con seis días de carrera a la semana hacen falta más de cuatro
# ranuras suaves.
_EASY_DAY_ORDER = (1, 3, 5, 0, 2, 4)  # martes, jueves, sábado, lunes, miércoles, viernes

_ZONE_EFFORT = {
    2: "conversacional — deberías poder hablar en frases completas",
    3: "cómodamente duro — te salen frases cortas, no párrafos",
    4: "duro — sólo palabras sueltas",
}

# El «por qué esta sesión» es la mitad del producto: un plan que sólo dice
# cuántos kilómetros es una hoja de cálculo, no un entrenador.
_NOTES = {
    "largo": (
        "Construye la base aeróbica. Va lento a propósito: "
        "el objetivo es el tiempo de pie, no el ritmo."
    ),
    "suave": ("Volumen fácil que suma sin cobrar factura. Si dudas si vas muy lento, vas bien."),
    "tempo": (
        "Trabajo continuo al filo de lo cómodo. Sube el umbral "
        "sin dejarte roto para el resto de la semana."
    ),
    "intervalos": (
        "Tramos duros con descanso entre ellos. Mejora la economía de carrera y la velocidad punta."
    ),
}

# Consejos prácticos: salieron de la entrevista de la Fase 2, donde los
# problemas reales no eran de fisiología sino de logística.
_LOGISTICS = (
    "Si pasas de la hora, lleva agua o planea una ruta con bebedero.",
    "Deja la ropa lista la noche anterior. Suena tonto y funciona.",
    "Ruta circular en vueltas cortas: si algo va mal, nunca estás lejos de casa.",
    "Come algo ligero 90 minutos antes, no justo antes de salir.",
    "Si hace calor, sal temprano y afloja el ritmo sin culpa.",
)


class InsufficientTimeError(Exception):
    """R7. No hay semanas suficientes para preparar la meta con seguridad.

    Lleva material para negociar, no sólo la negativa: el coach tiene que poder
    ofrecer una distancia que sí quepa o un plan de llegar sano.
    """

    def __init__(
        self,
        weeks_available: int,
        weeks_needed: int,
        distance: RaceDistance,
        alternatives: tuple[str, ...],
    ) -> None:
        self.weeks_available = weeks_available
        self.weeks_needed = weeks_needed
        self.distance = distance
        self.alternatives = alternatives
        super().__init__(
            f"faltan semanas para {distance}: hay {weeks_available}, se necesitan {weeks_needed}"
        )


class InsufficientFrequencyError(Exception):
    """Menos de dos días por semana no da para un plan legal.

    Con un solo día, la tirada larga sería el 100 % del volumen y violaría R3.
    Fabricar un plan que incumple las propias reglas sería peor que negarse, así
    que se negocia igual que en R7.
    """


@dataclass(frozen=True)
class Session:
    day_of_week: int
    kind: str
    distance_km: float
    zone: int
    effort_description: str
    notes: str
    pace: PaceRange | None = None
    technique_cue_id: str | None = None
    logistics_tip: str | None = None


@dataclass(frozen=True)
class Week:
    index: int
    phase: str
    start_date: date
    sessions: tuple[Session, ...]
    load: WeekLoad


@dataclass(frozen=True)
class Plan:
    distance: RaceDistance
    level: Level
    start_date: date
    race_date: date | None
    weeks: tuple[Week, ...]

    @property
    def peak_volume_km(self) -> float:
        return max(w.load.total_km for w in self.weeks)


def min_weeks(distance: RaceDistance) -> int:
    return TEMPLATES[distance].min_weeks


def max_weeks(distance: RaceDistance) -> int:
    return TEMPLATES[distance].max_weeks


def build_plan(
    profile: AthleteProfile,
    distance: RaceDistance,
    race_date: date | None,
    today: date,
) -> Plan:
    """Construye el plan completo, o lanza explicando qué hay que negociar."""
    plantilla = TEMPLATES[distance]

    if profile.days_per_week < 2:
        raise InsufficientFrequencyError(
            "con un solo día a la semana la tirada larga sería todo el volumen; "
            "hacen falta al menos dos días"
        )

    semanas = _resolve_weeks(distance, plantilla, race_date, today)
    volumenes = _build_volumes(profile, distance, plantilla, semanas)
    zonas = _zones_or_none(profile)

    inicio = today - timedelta(days=today.weekday())  # lunes de esta semana
    semanas_taper = _taper_weeks(plantilla)
    de_construccion = semanas - semanas_taper

    weeks: list[Week] = []
    for indice, total in enumerate(volumenes, start=1):
        es_taper = indice > de_construccion
        es_descarga = not es_taper and is_deload_week(indice, distance)
        weeks.append(
            _build_week(
                index=indice,
                total_km=total,
                phase=_phase(indice, de_construccion, es_taper),
                start_date=inicio + timedelta(weeks=indice - 1),
                profile=profile,
                plantilla=plantilla,
                zonas=zonas,
                is_deload=es_descarga,
                is_taper=es_taper,
            )
        )

    plan = Plan(distance, profile.level, inicio, race_date, tuple(weeks))
    _assert_legal(plan)
    return plan


# ── resolución de la duración ────────────────────────────────────────


def _resolve_weeks(
    distance: RaceDistance,
    plantilla: DistanceTemplate,
    race_date: date | None,
    today: date,
) -> int:
    if race_date is None:
        # Entrenar sin carrera apuntada es un caso real: se usa la duración
        # mínima, que ya es un bloque de entrenamiento completo.
        return plantilla.min_weeks

    disponibles = (race_date - today).days // 7
    if disponibles < plantilla.min_weeks:
        raise InsufficientTimeError(
            weeks_available=max(disponibles, 0),
            weeks_needed=plantilla.min_weeks,
            distance=distance,
            alternatives=_alternatives(disponibles),
        )
    # Más semanas de las que la distancia aprovecha no es más entrenamiento,
    # es más tiempo para aburrirse y abandonar.
    return min(disponibles, plantilla.max_weeks)


def _alternatives(weeks_available: int) -> tuple[str, ...]:
    """Con qué puede negociar el coach. Nunca vuelve vacío.

    Los valores son cadenas porque incluyen una opción que no es una distancia.
    `RaceDistance` es un `StrEnum`, así que `RaceDistance.K21 in alternatives`
    sigue funcionando para quien consulte por distancia.
    """
    caben = tuple(d.value for d in RaceDistance if TEMPLATES[d].min_weeks <= weeks_available)
    # Si no cabe ninguna distancia, todavía queda la salida honesta: preparar
    # para terminar sin marca, o mover la fecha.
    return (*caben, "llegar-sano")


def _taper_weeks(plantilla: DistanceTemplate) -> int:
    return max(1, round(plantilla.taper_days / 7))


def _phase(index: int, build_weeks: int, is_taper: bool) -> str:
    if is_taper:
        return "taper"
    if index <= math.ceil(build_weeks / 3):
        return "base"
    if index <= math.ceil(2 * build_weeks / 3):
        return "construccion"
    return "pico"


# ── volúmenes ────────────────────────────────────────────────────────


def _build_volumes(
    profile: AthleteProfile,
    distance: RaceDistance,
    plantilla: DistanceTemplate,
    semanas: int,
) -> list[float]:
    semanas_taper = _taper_weeks(plantilla)
    de_construccion = max(1, semanas - semanas_taper)

    # La semana 1 arranca donde está el corredor hoy, nunca donde le gustaría
    # estar. Si viene de cero se usa un suelo de correr–caminar; eso es un punto
    # de partida, no un incremento, así que R1 no lo gobierna.
    actual = min(max(profile.weekly_volume_km, START_FLOOR_KM), plantilla.peak_volume_km)
    volumenes = [round(actual, 1)]

    # Cada semana progresa desde la última de **carga normal**, saltándose las
    # descargas. Encadenarlas haría que el plan encogiera: con descarga cada
    # cuatro semanas y un tope del 5 %, un ciclo completo es 1.05³ × 0.70 = 0.81
    # del volumen inicial. Un plan que baja de volumen cada mes no es un plan de
    # entrenamiento. La descarga interrumpe la progresión; no la reinicia.
    ultima_de_carga = volumenes[0]

    for indice in range(2, de_construccion + 1):
        siguiente = next_week_volume(ultima_de_carga, indice, distance, profile.level)
        volumen = round(min(siguiente, plantilla.peak_volume_km), 1)
        volumenes.append(volumen)
        if not is_deload_week(indice, distance):
            ultima_de_carga = volumen

    pico = ultima_de_carga
    for j in range(1, semanas - de_construccion + 1):
        # Descenso lineal hasta la reducción total de la matriz.
        recorte = plantilla.taper_reduction * j / semanas_taper
        volumenes.append(round(pico * (1 - recorte), 1))

    return volumenes


def _zones_or_none(profile: AthleteProfile):  # type: ignore[no-untyped-def]
    if not profile.has_reference:
        return None
    assert profile.reference_distance_km is not None
    assert profile.reference_time_sec is not None
    return zones_from_effort(profile.reference_distance_km, profile.reference_time_sec)


# ── una semana ───────────────────────────────────────────────────────


def _build_week(
    *,
    index: int,
    total_km: float,
    phase: str,
    start_date: date,
    profile: AthleteProfile,
    plantilla: DistanceTemplate,
    zonas: object,
    is_deload: bool,
    is_taper: bool,
) -> Week:
    dias = min(profile.days_per_week, plantilla.max_days)

    # En descarga y en taper se retira el trabajo de calidad: el objetivo de esas
    # semanas es absorber lo entrenado, no añadir estímulo. Y `dias - 2` deja
    # siempre al menos una sesión suave, sin la cual R4 sería imposible de
    # cumplir con la tirada larga sola.
    calidad = 0 if (is_deload or is_taper) else min(plantilla.quality_sessions, dias - 2)
    calidad = max(calidad, 0)

    # Truncar y no redondear. Redondear hacia arriba puede empujar la tirada
    # larga por encima del 30 % del volumen cuando la semana es corta —0.364 km
    # se convertiría en 0.4, que sobre 1.3 km ya es el 31 %— y el motor acabaría
    # rechazando su propio plan. Truncar sólo puede dejarla por debajo.
    larga_km = _truncar(min(total_km * LONG_RUN_SHARE, plantilla.peak_long_run_km))
    calidad_km = _truncar(total_km * QUALITY_SHARE)
    suaves = dias - 1 - calidad
    resto = max(total_km - larga_km - calidad * calidad_km, 0.0)
    suaves_km = _repartir(resto, suaves)

    cue = select_cue(profile.level.value, index, assess(0))

    sesiones: list[Session] = [
        Session(
            day_of_week=LONG_RUN_DAY,
            kind="largo",
            distance_km=larga_km,
            zone=2,
            effort_description=_ZONE_EFFORT[2],
            notes=_NOTES["largo"],
            pace=_pace(zonas, 2),
            technique_cue_id=cue.id if cue else None,
            logistics_tip=_LOGISTICS[(index - 1) % len(_LOGISTICS)],
        )
    ]

    dias_calidad = _QUALITY_DAYS[:calidad]
    dias_suaves = [d for d in _EASY_DAY_ORDER if d not in dias_calidad][:suaves]

    for n in range(calidad):
        tipo = "tempo" if n == 0 else "intervalos"
        zona = 3 if n == 0 else 4
        sesiones.append(
            Session(
                day_of_week=dias_calidad[n],
                kind=tipo,
                distance_km=calidad_km,
                zone=zona,
                effort_description=_ZONE_EFFORT[zona],
                notes=_NOTES[tipo],
                pace=_pace(zonas, zona),
            )
        )

    for n in range(suaves):
        sesiones.append(
            Session(
                day_of_week=dias_suaves[n],
                kind="suave",
                distance_km=suaves_km[n],
                zone=2,
                effort_description=_ZONE_EFFORT[2],
                notes=_NOTES["suave"],
                pace=_pace(zonas, 2),
            )
        )

    carga = WeekLoad(
        index=index,
        total_km=total_km,
        long_run_km=larga_km,
        quality_sessions=calidad,
        is_deload=is_deload,
        easy_km=round(total_km - calidad * calidad_km, 1),
        is_taper=is_taper,
    )
    return Week(index, phase, start_date, tuple(sesiones), carga)


def _truncar(km: float) -> float:
    """A un decimal, siempre hacia abajo."""
    return math.floor(km * 10) / 10


def _repartir(total: float, partes: int) -> list[float]:
    """Reparte kilómetros entre sesiones sumando exactamente el total.

    Redondear cada parte por separado deja una deriva de hasta 0.05 km por
    sesión, y entonces las sesiones de la semana no suman el volumen semanal.
    La última sesión absorbe el residuo.
    """
    if partes <= 0:
        return []
    cada = _truncar(total / partes)
    trozos = [cada] * (partes - 1)
    return [*trozos, round(total - sum(trozos), 1)]


def _pace(zonas: object, zone: int) -> PaceRange | None:
    """Sin esfuerzo de referencia no hay ritmo, y no se inventa uno.

    Es la regla de los números aplicada al caso incómodo: cuando falta el dato,
    la respuesta correcta es prescribir por esfuerzo y callarse la cifra.
    """
    if zonas is None:
        return None
    return zonas.by_number(zone)  # type: ignore[attr-defined,no-any-return]


# ── la garantía ──────────────────────────────────────────────────────


def _assert_legal(plan: Plan) -> None:
    """Ningún plan sale de aquí violando una regla.

    Es redundante con la construcción a propósito. Si mañana alguien toca la
    generación y rompe R3 sin darse cuenta, esto lo convierte en una excepción
    ruidosa en vez de en un plan que un corredor se va a creer.
    """
    cargas = [w.load for w in plan.weeks]
    for i, semana in enumerate(plan.weeks):
        anterior = previous_reference(cargas, i)
        problemas = validate_week(semana.load, anterior, plan.distance, plan.level)
        if problemas:
            detalle = "; ".join(f"{p.rule}: {p.message}" for p in problemas)
            raise AssertionError(f"el motor generó una semana ilegal ({semana.index}) — {detalle}")
