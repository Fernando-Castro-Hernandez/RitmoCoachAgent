"""Métricas.

La que importa es `numbers_from_engine_pct`. El coach puede redactar; no puede
calcular. Esta función es lo que convierte esa regla en un número que se mira,
y la mitad de las pruebas de aquí son sobre dónde está su frontera: qué cifras
cuenta, cuáles ignora, y qué se le escapa.

Lo demás es el cronómetro del turno, probado con un reloj falso para que no
haya que dormir de verdad para medir 640 ms.
"""

from __future__ import annotations

import pytest

from apps.api.bridge import NovaBridge
from apps.api.metrics import TurnTimer, numbers_from_engine_pct


class RelojFalso:
    """Un reloj que sólo avanza cuando la prueba se lo dice."""

    def __init__(self) -> None:
        self.ms = 0.0

    def at(self, ms: float) -> None:
        self.ms = ms

    def __call__(self) -> float:
        return self.ms


# ── el cronómetro ────────────────────────────────────────────────────


def test_ttfa_se_mide_desde_el_fin_del_habla() -> None:
    reloj = RelojFalso()
    t = TurnTimer(reloj)

    reloj.at(1000)
    t.user_speech_end()
    reloj.at(1640)
    t.first_audio_out()

    assert t.ttfa_ms == 640


def test_solo_cuenta_el_primer_audio_del_turno() -> None:
    """Lo que se mide es cuándo EMPEZÓ a sonar, no cuánto habló."""
    reloj = RelojFalso()
    t = TurnTimer(reloj)

    reloj.at(0)
    t.user_speech_end()
    reloj.at(500)
    t.first_audio_out()
    reloj.at(3000)
    t.first_audio_out()

    assert t.ttfa_ms == 500


def test_audio_sin_turno_abierto_no_inventa_una_latencia() -> None:
    """Si nadie habló, no hay desde dónde medir. Mejor `None` que un cero falso."""
    t = TurnTimer(RelojFalso())
    t.first_audio_out()
    assert t.ttfa_ms is None


def test_el_turno_siguiente_reinicia_la_cuenta() -> None:
    reloj = RelojFalso()
    t = TurnTimer(reloj)

    reloj.at(0)
    t.user_speech_end()
    reloj.at(400)
    t.first_audio_out()

    reloj.at(10_000)
    t.user_speech_end()
    reloj.at(10_900)
    t.first_audio_out()

    assert t.ttfa_ms == 900


def test_la_interrupcion_se_mide_hasta_que_el_coach_calla() -> None:
    reloj = RelojFalso()
    t = TurnTimer(reloj)

    reloj.at(2000)
    t.barge_in_start()
    reloj.at(2180)
    t.barge_in_stopped()

    assert t.barge_in_stop_ms == 180


# ── el puente lo cablea ──────────────────────────────────────────────


def test_el_puente_mide_de_la_transcripcion_del_usuario_al_audio() -> None:
    """El cableado real, sin red.

    Se mide desde la transcripción FINAL del usuario porque es la primera señal
    que tiene el servidor de que el turno acabó. El TTFA que percibe el corredor
    es algo mayor: el reconocimiento tarda, y eso pasa antes de este punto.
    """
    reloj = RelojFalso()
    puente = NovaBridge(stream=object(), clock=reloj)

    reloj.at(5000)
    puente._translate({"textOutput": {"content": "hola coach", "role": "USER"}})
    reloj.at(5720)
    puente._translate({"audioOutput": {"content": "AAAA"}})

    assert puente.metrics.ttfa_ms == 720


def test_el_acuse_de_interrupcion_cierra_el_cronometro() -> None:
    reloj = RelojFalso()
    puente = NovaBridge(stream=object(), clock=reloj)

    reloj.at(0)
    puente.metrics.barge_in_start()
    reloj.at(140)
    # Nova manda el acuse como un textOutput con un JSON dentro.
    assert puente._translate({"textOutput": {"content": '{"interrupted": true}'}}) is None

    assert puente.metrics.barge_in_stop_ms == 140


# ── alucinación numérica ─────────────────────────────────────────────


def test_numbers_from_engine_detecta_cifra_inventada() -> None:
    p = numbers_from_engine_pct("corre 22 km", [{"distance_km": 18.0}])
    assert p < 100.0


def test_la_cifra_que_dio_el_motor_pasa() -> None:
    p = numbers_from_engine_pct("corre 18 km hoy", [{"distance_km": 18.0}])
    assert p == 100.0


def test_una_respuesta_sin_cifras_no_puede_haber_inventado_nada() -> None:
    """Devolver 0 aquí castigaría a las respuestas conversacionales, que son
    la mayoría, y llenaría la métrica de ruido hasta volverla inútil."""
    assert numbers_from_engine_pct("¿cómo te sentiste ayer?", []) == 100.0


def test_los_numeros_sin_unidad_no_cuentan() -> None:
    """«De 1 a 10» y «la semana 4» no prescriben nada.

    Exigir que todo número venga del motor llenaría la métrica de falsos
    positivos, y una métrica que nadie mira no protege de nada.
    """
    texto = "en una escala de 1 a 10, ¿cómo va? Vamos por la semana 4 de 12."
    assert numbers_from_engine_pct(texto, []) == 100.0


def test_un_ritmo_inventado_se_detecta() -> None:
    p = numbers_from_engine_pct("ve a 4:30 por kilómetro", [{"pace_sec_per_km": 330}])
    assert p == 0.0


def test_un_ritmo_del_motor_pasa_venga_como_venga() -> None:
    """El motor puede devolverlo en segundos o ya formateado; las dos formas valen."""
    assert numbers_from_engine_pct("ve a 5:30", [{"pace_sec_per_km": 330}]) == 100.0
    assert numbers_from_engine_pct("ve a 5:30", [{"pace": "5:30"}]) == 100.0


def test_el_redondeo_del_motor_no_cuenta_como_invención() -> None:
    """El motor redondea a la décima; el coach dice «unos 18»."""
    assert numbers_from_engine_pct("son unos 18 km", [{"distance_km": 18.0}]) == 100.0


def test_una_cifra_de_verdad_distinta_si_cuenta() -> None:
    assert numbers_from_engine_pct("son 18.4 km", [{"distance_km": 18.0}]) == 0.0


def test_se_buscan_las_cifras_a_cualquier_hondura() -> None:
    """Las herramientas evolucionan. Leer campos concretos obliga a actualizar
    esto cada vez que se añade uno, y una métrica desactualizada miente en verde."""
    salida = {"plan": {"weeks": [{"sessions": [{"distance_km": 12.0}]}]}}
    assert numbers_from_engine_pct("hoy son 12 km", [salida]) == 100.0


def test_una_mezcla_da_un_porcentaje_intermedio() -> None:
    p = numbers_from_engine_pct("12 km a 5:30", [{"distance_km": 12.0}])
    assert p == 50.0


def test_el_sesgo_conservador_esta_documentado_y_probado() -> None:
    """Si el motor dice 18 y el coach dice «9 de ida y 9 de vuelta», los dos
    nueves cuentan como inventados aunque la aritmética esté bien.

    Es a propósito. Un falso positivo se descarta en diez segundos; una cifra
    inventada que pasa desapercibida se la lleva alguien a la calle.
    """
    p = numbers_from_engine_pct("9 km de ida y 9 km de vuelta", [{"distance_km": 18.0}])
    assert p == 0.0


@pytest.mark.parametrize(
    "texto",
    ["corre 10 kilómetros", "corre 10 km", "corre 10km", "corre 10 kms"],
)
def test_la_unidad_se_reconoce_como_la_escriba_el_modelo(texto: str) -> None:
    assert numbers_from_engine_pct(texto, [{"distance_km": 10.0}]) == 100.0


def test_la_coma_decimal_tambien(texto: str = "corre 10,5 km") -> None:
    """El modelo habla español y escribe «10,5»."""
    assert numbers_from_engine_pct(texto, [{"distance_km": 10.5}]) == 100.0
