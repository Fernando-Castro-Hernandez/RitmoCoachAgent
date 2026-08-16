"""Qué se mide, y por qué esas cosas.

Tres familias, y cada una existe porque hay una forma concreta de fallar:

**Latencia.** Una conversación de voz se cae por los milisegundos, no por las
funcionalidades. `ttfa_ms` es la que manda: cuánto tarda el coach en empezar a
sonar después de que el corredor calló. `barge_in_stop_ms` mide lo contrario —
cuánto tarda en callarse cuando lo interrumpen—, que es lo que separa una
conversación de un contestador.

**Dominio.** `invariant_violations_total` cuenta planes emitidos que violan
R1–R8. Debería ser cero siempre, y si deja de serlo el motor tiene un agujero.
`safety_gate_triggers` cuenta las veces que la puerta frenó al coach.

**Alucinación numérica.** La métrica del proyecto: el coach puede redactar,
no calcular. El cálculo **no vive aquí** — es `validate_output` de `prompts.py`,
donde nació y donde está cableado al guardarraíl de salida. Este módulo sólo lo
envuelve para publicar el porcentaje en `/metrics`.

Tener una segunda implementación aquí sería peor que no tener ninguna: las dos
se irían separando, y en algún momento el guardarraíl y la métrica dirían cosas
distintas sobre el mismo turno.

## Lo que todavía no se mide de verdad

`barge_in_stop_ms` está implementado de los dos lados —el navegador manda
`barge_in` y el acuse `{"interrupted": true}` de Nova cierra el cronómetro—
pero **el navegador todavía no lo manda**, así que el histograma está vacío. Se
queda vacío a propósito en vez de rellenarse con una estimación del servidor:
el instante en que alguien empieza a hablar encima pasa en su micrófono, y
cualquier número que el servidor invente para eso sería inventado. Ningún valor
de esta métrica va al README hasta que el circuito esté cerrado.

## TTFA: qué mide exactamente

Se mide desde que llega la transcripción **final del usuario** hasta el primer
`audioOutput`. No desde que el corredor dejó de hablar de verdad: eso pasa en su
micrófono y aquí no se ve. La transcripción es la primera señal que tiene el
servidor de que el turno acabó, así que **el número real que percibe el corredor
es algo mayor** que el que sale de aquí, por el tiempo del reconocimiento. Está
escrito aquí para que nadie lo cite como si fuera latencia de punta a punta.
"""

from __future__ import annotations

import time
from collections.abc import Callable, Sequence
from typing import Any

from prometheus_client import Counter, Gauge, Histogram

# Cubos en milisegundos. Están pensados alrededor de la frontera que importa:
# por debajo de ~800 ms una respuesta de voz se siente conversación; por encima
# de ~1500 ms se siente sistema.
_CUBOS_MS = (100, 200, 400, 600, 800, 1000, 1500, 2000, 3000, 5000, 10000)

ttfa_ms = Histogram(
    "ritmo_ttfa_ms",
    "Del fin de la transcripción del usuario al primer audio del coach",
    buckets=_CUBOS_MS,
)
barge_in_stop_ms = Histogram(
    "ritmo_barge_in_stop_ms",
    "Cuánto tarda el coach en callarse cuando lo interrumpen",
    buckets=_CUBOS_MS,
)
tool_call_ms = Histogram(
    "ritmo_tool_call_ms",
    "Duración de una herramienta de dominio",
    ["tool"],
    buckets=_CUBOS_MS,
)
renewal_gap_ms = Histogram(
    "ritmo_renewal_gap_ms",
    "Hueco audible al renovar la conexión de 8 minutos",
    buckets=(0, 50, 100, 200, 400, 800, 1500, 3000),
)
vision_extraction_ms = Histogram(
    "ritmo_vision_extraction_ms",
    "Lectura de una captura del reloj",
    buckets=(200, 500, 1000, 2000, 4000, 8000, 15000),
)

invariant_violations_total = Counter(
    "ritmo_invariant_violations_total",
    "Planes emitidos que violan una regla del motor. Debería ser siempre 0.",
    ["rule"],
)
safety_gate_triggers = Counter(
    "ritmo_safety_gate_triggers_total",
    "Veces que la puerta de seguridad frenó al coach",
    ["level"],
)
numbers_from_engine = Gauge(
    "ritmo_numbers_from_engine_pct",
    "Porcentaje de cifras con unidad rastreables a una herramienta",
)
vision_extraction_confidence = Counter(
    "ritmo_vision_extraction_confidence_total",
    "Confianza declarada por el modelo al leer una captura",
    ["confidence"],
)
vision_field_correction_rate = Gauge(
    "ritmo_vision_field_correction_rate",
    "Fracción de campos que el corredor corrigió tras la extracción",
)
clarification_turns_before_plan = Histogram(
    "ritmo_clarification_turns_before_plan",
    "Preguntas que hizo el coach antes de poder generar un plan",
    buckets=(0, 1, 2, 3, 4, 5),
)


# ── el reloj de un turno ─────────────────────────────────────────────


def _reloj_monotono() -> float:
    """Milisegundos. Monótono: un ajuste de hora del sistema no puede dar una
    latencia negativa a mitad de una conversación."""
    return time.monotonic() * 1000.0


class TurnTimer:
    """Cronómetro de un turno. Se le puede inyectar el reloj para probarlo.

    Sólo registra la **primera** salida de audio de cada turno: lo que se mide
    es cuándo empezó a sonar el coach, no cuánto duró hablando.
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or _reloj_monotono
        self._inicio_turno: float | None = None
        self._ttfa_ms: float | None = None
        self._inicio_interrupcion: float | None = None
        self._barge_in_stop_ms: float | None = None

    def user_speech_end(self) -> None:
        """El turno del corredor acabó. Arranca la cuenta del TTFA."""
        self._inicio_turno = self._clock()
        self._ttfa_ms = None

    def first_audio_out(self) -> None:
        if self._inicio_turno is None or self._ttfa_ms is not None:
            return
        self._ttfa_ms = self._clock() - self._inicio_turno
        ttfa_ms.observe(self._ttfa_ms)

    def barge_in_start(self) -> None:
        self._inicio_interrupcion = self._clock()
        self._barge_in_stop_ms = None

    def barge_in_stopped(self) -> None:
        if self._inicio_interrupcion is None or self._barge_in_stop_ms is not None:
            return
        self._barge_in_stop_ms = self._clock() - self._inicio_interrupcion
        barge_in_stop_ms.observe(self._barge_in_stop_ms)

    @property
    def ttfa_ms(self) -> float | None:
        return self._ttfa_ms

    @property
    def barge_in_stop_ms(self) -> float | None:
        return self._barge_in_stop_ms


# ── alucinación numérica ─────────────────────────────────────────────


def numbers_from_engine_pct(texto: str, tool_outputs: Sequence[Any]) -> float:
    """Qué porcentaje de las cifras que prescriben salió de una herramienta.

    Delega en `prompts.validate_output`, que es donde vive la definición de qué
    cuenta como cifra que prescribe, y añade lo único que es de este módulo:
    publicarlo como métrica.
    """
    from apps.api.prompts import numbers_from_engine_pct as _calcular

    porcentaje = _calcular(texto, list(tool_outputs))
    numbers_from_engine.set(porcentaje)
    return porcentaje
