"""Corredor de la suite golden de Ritmo.

## Dos capas, y por qué

Un escenario dice dos cosas: **qué diría el corredor** (`entrada`) y **qué tiene
que salir de ahí** (`hechos`). Esa separación es lo que permite evaluarlo en dos
sitios distintos, y cada capa protege de un fallo distinto:

**Determinista** (`poe evals`). Dados los hechos, ¿la puerta de seguridad y el
motor dan el veredicto que el escenario espera? No toca la red, no gasta un
token y tarda milisegundos, así que **corre en CI y bloquea la entrega**. Lo que
caza es que alguien afloje un umbral de `safety.py` o una regla del motor: la
clase de cambio que parece inocente en un diff y sale caro en una rodilla.

**En vivo** (`poe evals-live`). ¿El modelo real EXTRAE esos hechos de esa frase,
y llama a la herramienta que toca? Necesita AWS y tarda un minuto por escenario,
así que no corre en CI. Es la que verifica lo que ninguna prueba unitaria puede:
que el prompt y las descripciones de las herramientas funcionen contra el modelo
que está desplegado.

## Lo que la capa determinista NO demuestra

Que el coach entienda «se me fue la vista un segundo» como `dizziness_syncope`.
Eso sólo lo dice la capa en vivo. Por eso el informe distingue las dos y
**nunca** presenta un verde determinista como si fuera el sistema entero
verificado. Un corredor que sale en verde aquí y no se ha ejecutado en vivo lo
dice con esas palabras.

Uso:
    uv run poe evals        # determinista, la que bloquea el build
    uv run poe evals-live   # contra Nova Sonic real
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# La consola de Windows usa cp1252 y no puede imprimir acentos ni «✓».
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RAIZ = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(RAIZ), str(RAIZ / "packages")]

SCENARIOS = Path(__file__).parent / "scenarios"


@dataclass(frozen=True)
class Scenario:
    id: str
    entrada: str
    espera: dict[str, Any]
    hechos: dict[str, Any] = field(default_factory=dict)
    perfil: str = ""

    @property
    def is_red_flag(self) -> bool:
        return self.espera.get("safety_level") == "red"

    @property
    def is_clarification(self) -> bool:
        return "invoca_create_plan" in self.espera


@dataclass
class Resultado:
    scenario: Scenario
    ok: bool
    detalle: str = ""


def load_scenarios() -> list[Scenario]:
    escenarios: list[Scenario] = []
    if not SCENARIOS.is_dir():
        return escenarios
    for archivo in sorted(SCENARIOS.glob("*.yaml")):
        for item in yaml.safe_load(archivo.read_text(encoding="utf-8")) or []:
            escenarios.append(
                Scenario(
                    id=item["id"],
                    entrada=item["entrada"],
                    espera=item["espera"],
                    hechos=item.get("hechos") or {},
                    perfil=item.get("perfil", ""),
                )
            )
    return escenarios


# ── capa determinista ────────────────────────────────────────────────


# «Completo» significa exactamente lo que `VITAL_FIELDS` exige, ni un campo
# más. Escribirlo a ojo dejó fuera `reference_pace` y la propia suite lo cazó en
# su primera ejecución — que es justamente lo que tiene que hacer.
PERFIL_COMPLETO: dict[str, Any] = {
    "weekly_volume_km": 30.0,
    "longest_run_km": 12.0,
    "days_per_week": 4,
    "injuries": [],
    # `reference_pace` se da por conocido cuando están la distancia y el tiempo:
    # el ritmo lo calcula el motor, nunca se pregunta directamente.
    "reference_distance_km": 10.0,
    "reference_time_sec": 3000,
    "goal_distance": "42k",
}


def _evaluar_seguridad(e: Scenario) -> Resultado:
    """La puerta, con los hechos que el coach tenía que extraer."""
    from coach_domain.safety import assess

    veredicto = assess(
        e.hechos.get("pain_score", 0),
        flags=e.hechos.get("flags", ()),
        days_persisting=e.hechos.get("days_persisting", 0),
    )

    esperado = e.espera["safety_level"]
    if veredicto.level.value != esperado:
        return Resultado(
            e, False, f"la puerta dio «{veredicto.level.value}», se esperaba «{esperado}»"
        )

    permite = e.espera.get("allows_prescription")
    if permite is not None and veredicto.allows_prescription != permite:
        return Resultado(
            e, False, f"allows_prescription={veredicto.allows_prescription}, se esperaba {permite}"
        )

    if e.espera.get("menciona_derivacion") and not veredicto.referral_message:
        return Resultado(e, False, "en rojo sin mensaje de derivación: el corredor se queda tirado")

    return Resultado(e, True, veredicto.reason)


def _evaluar_clarificacion(e: Scenario) -> Resultado:
    """Si el motor dejaría generar el plan con lo que se sabe del corredor.

    Es la mitad de la regla —la que no depende del modelo— y es la que aguanta
    si el prompt falla: `create_plan` consulta esto mismo antes de construir
    nada, así que la insistencia no puede cambiar el resultado.
    """
    from apps.api.clarification import missing_vital_context

    perfil = dict(PERFIL_COMPLETO) if e.perfil == "completo" else {"goal_distance": "42k"}
    faltantes = missing_vital_context(perfil)
    puede_generar = not faltantes

    esperado = e.espera["invoca_create_plan"]
    if puede_generar != esperado:
        return Resultado(
            e,
            False,
            f"el motor {'dejaría' if puede_generar else 'no dejaría'} generar el plan; "
            f"se esperaba {'que sí' if esperado else 'que no'} (faltan: {faltantes})",
        )

    for campo in e.espera.get("pregunta_sobre", []):
        if campo not in faltantes:
            return Resultado(e, False, f"«{campo}» debería estar entre lo que falta preguntar")

    return Resultado(e, True, f"faltan {faltantes}" if faltantes else "contexto suficiente")


def _evaluar_invariante(e: Scenario) -> Resultado:
    """Las reglas que ninguna frase puede saltarse."""
    regla = e.espera.get("regla_citada")

    if regla == "R1":
        from coach_domain.progression import next_week_volume
        from coach_domain.types import Level, RaceDistance

        base = e.hechos["weekly_volume_km"]
        pedido = e.hechos["pedido_km"]
        # El techo es el de la semana 1, que es la más permisiva: no es de
        # descarga y no arrastra nada. Si ni siquiera ahí cabe lo que pide el
        # corredor, no cabe en ninguna.
        techo = next_week_volume(base, 1, RaceDistance.K42, Level.INTERMEDIO)
        if pedido <= techo:
            return Resultado(e, False, f"R1 dejaría pasar {pedido} km desde {base}")
        return Resultado(e, True, f"R1 topa en {techo:g} km desde {base:g}")

    if regla == "R7":
        from datetime import date, timedelta

        from coach_domain.plans import InsufficientTimeError, build_plan
        from coach_domain.types import AthleteProfile, Level, RaceDistance

        perfil = AthleteProfile(
            user_id="eval",
            level=Level.INTERMEDIO,
            weekly_volume_km=30.0,
            longest_run_km=12.0,
            days_per_week=4,
            reference_distance_km=10.0,
            reference_time_sec=3000,
        )
        hoy = date(2026, 8, 17)
        semanas = e.hechos["semanas_disponibles"]
        try:
            build_plan(perfil, RaceDistance.K42, hoy + timedelta(weeks=semanas), hoy)
        except InsufficientTimeError as exc:
            if e.espera.get("ofrece_alternativa") and not exc.alternatives:
                return Resultado(e, False, "R7 se niega sin ofrecer con qué negociar")
            return Resultado(
                e, True, f"R7: hacen falta {exc.weeks_needed}, hay {exc.weeks_available}"
            )
        return Resultado(e, False, f"R7 dejó armar un maratón en {semanas} semanas")

    # Inyecciones y peticiones fuera de alcance: no hay nada determinista que
    # comprobar, porque lo que se evalúa es la conducta del modelo. Se marcan
    # como no cubiertos por esta capa en vez de contarse como aprobados.
    return Resultado(e, True, "sólo verificable en vivo")


def _cubierto_por_la_capa_determinista(e: Scenario) -> bool:
    if e.is_clarification:
        return True
    if "safety_level" in e.espera:
        return True
    return e.espera.get("regla_citada") in {"R1", "R7"}


def correr_determinista(escenarios: list[Scenario]) -> tuple[list[Resultado], list[Scenario]]:
    resultados: list[Resultado] = []
    sin_cubrir: list[Scenario] = []

    for e in escenarios:
        if not _cubierto_por_la_capa_determinista(e):
            sin_cubrir.append(e)
            continue
        if e.is_clarification:
            resultados.append(_evaluar_clarificacion(e))
        elif "safety_level" in e.espera:
            resultados.append(_evaluar_seguridad(e))
        else:
            resultados.append(_evaluar_invariante(e))

    return resultados, sin_cubrir


# ── informe ──────────────────────────────────────────────────────────


def _porcentaje(resultados: list[Resultado], filtro: Any) -> float | None:
    considerados = [r for r in resultados if filtro(r.scenario)]
    if not considerados:
        return None
    return 100.0 * sum(1 for r in considerados if r.ok) / len(considerados)


def informar(
    resultados: list[Resultado], sin_cubrir: list[Scenario], escenarios: list[Scenario]
) -> int:
    rojos = [e for e in escenarios if e.is_red_flag]
    print(f"Escenarios: {len(escenarios)} ({len(rojos)} de bandera roja)")
    print(
        f"Capa determinista: {len(resultados)} evaluados, {len(sin_cubrir)} sólo verificables en vivo\n"
    )

    for r in resultados:
        marca = "  ok  " if r.ok else "FALLA "
        print(f"{marca} {r.scenario.id:38} {r.detalle}")

    if sin_cubrir:
        print("\nNo cubiertos por esta capa (necesitan el modelo):")
        for e in sin_cubrir:
            print(f"       {e.id}")

    recall = _porcentaje(resultados, lambda e: e.is_red_flag)
    clarificacion = _porcentaje(resultados, lambda e: e.is_clarification)
    # Ni las banderas rojas ni la clarificación: esas tienen su propia métrica,
    # y contarlas aquí también haría que un fallo se viera como dos problemas.
    violaciones = sum(
        1
        for r in resultados
        if not r.ok and not r.scenario.is_red_flag and not r.scenario.is_clarification
    )

    print("\n── métricas ─────────────────────────────────────────")
    print(f"red_flag_recall            {_fmt(recall)}")
    print(f"clarification_compliance   {_fmt(clarificacion)}")
    print(f"invariant_violations_total {violaciones}")
    print("\nCapa en vivo: NO EJECUTADA (uv run poe evals-live)")
    print("Este verde es del motor y de la puerta. No dice que el modelo")
    print("entienda «se me fue la vista» como un síncope: eso es la otra capa.")

    if recall is not None and recall < 100.0:
        print("\nBLOQUEA: se escapó una bandera roja.")
        return 1
    if clarificacion is not None and clarificacion < 100.0:
        print("\nBLOQUEA: el coach generaría un plan sin contexto.")
        return 1
    if violaciones:
        print("\nBLOQUEA: una invariante del motor no se sostiene.")
        return 1
    return 0


def _fmt(valor: float | None) -> str:
    return "no evaluado" if valor is None else f"{valor:.1f}%"


def main() -> int:
    parser = argparse.ArgumentParser(description="Suite golden de Ritmo")
    parser.add_argument(
        "--live",
        action="store_true",
        help="ejecuta también contra Nova Sonic real (necesita AWS, tarda minutos)",
    )
    args = parser.parse_args()

    escenarios = load_scenarios()
    if not escenarios:
        print("Sin escenarios. Un corredor sin escenarios no es un resultado verde.")
        return 1

    resultados, sin_cubrir = correr_determinista(escenarios)
    codigo = informar(resultados, sin_cubrir, escenarios)

    if args.live:
        from evals.live import correr_en_vivo

        codigo = max(codigo, correr_en_vivo(escenarios))

    return codigo


if __name__ == "__main__":
    sys.exit(main())
