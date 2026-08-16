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

**Alucinación numérica.** `numbers_from_engine_pct` es la métrica del proyecto.
El coach puede redactar; no puede calcular. Esta función coge lo que dijo, saca
las cifras **que llevan unidad** y comprueba que cada una salió de una
herramienta. Si el modelo dice «corre 22 km» y el motor había dicho 18, el
porcentaje baja y se ve.

## Por qué sólo las cifras con unidad

Un texto de coaching está lleno de números que no prescriben nada: «de 1 a 10»,
«los tres primeros kilómetros», «la semana 4». Exigir que todos vengan del motor
llenaría la métrica de falsos positivos hasta volverla inútil, y una métrica que
nadie mira no protege de nada.

Las que sí prescriben llevan unidad: km, minutos, ppm, un ritmo `m:ss`, un
porcentaje. Ésas son las que pueden lesionar a alguien, y son las que se cuentan.

## El sesgo que tiene, dicho de frente

Es **conservadora**: si el motor dice 18 km y el coach dice «9 de ida y 9 de
vuelta», los dos nueves cuentan como inventados aunque la aritmética esté bien.
Prefiero que la métrica avise de más. Un falso positivo se mira y se descarta en
diez segundos; una cifra inventada que pasa desapercibida se la lleva alguien a
la calle.

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

import re
import time
from collections.abc import Callable, Iterable, Sequence
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

# Un ritmo: 5:30, 4:45. Se busca primero, porque si no el «5» y el «30» se
# leerían como dos cifras sueltas.
_RITMO = re.compile(r"\b(\d{1,2}):([0-5]\d)\b")

# Una cifra seguida de su unidad. Sólo estas prescriben algo.
_CON_UNIDAD = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*(km|kms|kilómetros?|kilometros?|m|minutos?|min|ppm|bpm|%)\b",
    re.IGNORECASE,
)

# Tolerancia al comparar kilómetros: el motor redondea a la décima y el coach
# puede decir «unos 18» de un 18.0. Un desvío mayor ya es otra prescripción.
_TOLERANCIA_KM = 0.051


def _valores_del_motor(salidas: Iterable[Any]) -> set[float]:
    """Todo número que apareció en una salida de herramienta, a cualquier hondura.

    Se recorre el árbol entero en vez de leer campos concretos porque las
    herramientas evolucionan, y una métrica que hay que actualizar cada vez que
    se añade un campo acaba desactualizada y mintiendo en verde.
    """
    encontrados: set[float] = set()

    def recorrer(nodo: Any) -> None:
        if isinstance(nodo, bool):
            return
        if isinstance(nodo, int | float):
            encontrados.add(float(nodo))
            return
        if isinstance(nodo, str):
            # Un ritmo serializado como «5:30» también es una cifra del motor.
            for m, s in _RITMO.findall(nodo):
                encontrados.add(float(int(m) * 60 + int(s)))
            return
        if isinstance(nodo, dict):
            for v in nodo.values():
                recorrer(v)
            return
        if isinstance(nodo, list | tuple):
            for v in nodo:
                recorrer(v)

    for salida in salidas:
        recorrer(salida)
    return encontrados


def _cifras_que_prescriben(texto: str) -> list[tuple[float, str]]:
    """Las cifras con unidad, normalizadas a (valor, unidad)."""
    cifras: list[tuple[float, str]] = []
    for minutos, segundos in _RITMO.findall(texto):
        cifras.append((float(int(minutos) * 60 + int(segundos)), "pace"))
    # Los ritmos se quitan antes de buscar unidades: si no, el «30» de «5:30»
    # se leería otra vez como un número suelto seguido de lo que venga.
    resto = _RITMO.sub(" ", texto)
    for valor, unidad in _CON_UNIDAD.findall(resto):
        cifras.append((float(valor.replace(",", ".")), unidad.lower()))
    return cifras


def _rastreable(valor: float, unidad: str, motor: set[float]) -> bool:
    if unidad == "pace":
        # El ritmo puede venir del motor en segundos o formateado; ambas formas
        # se normalizaron a segundos, así que basta con comparar.
        return any(abs(valor - v) < 1.0 for v in motor)
    if unidad.startswith(("km", "kil")):
        return any(abs(valor - v) <= _TOLERANCIA_KM for v in motor)
    return any(abs(valor - v) < 0.001 for v in motor)


def numbers_from_engine_pct(texto: str, tool_outputs: Sequence[Any]) -> float:
    """Qué porcentaje de las cifras que prescriben salió de una herramienta.

    Un texto sin cifras con unidad devuelve 100: no prescribió nada, así que no
    hay nada que pueda haber inventado. Devolver 0 ahí castigaría a las
    respuestas conversacionales, que son la mayoría.
    """
    cifras = _cifras_que_prescriben(texto)
    if not cifras:
        return 100.0

    motor = _valores_del_motor(tool_outputs)
    buenas = sum(1 for valor, unidad in cifras if _rastreable(valor, unidad, motor))
    porcentaje = 100.0 * buenas / len(cifras)
    numbers_from_engine.set(porcentaje)
    return porcentaje
