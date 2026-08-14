"""Corredor de la suite golden de Ritmo.

Ejecuta escenarios declarativos contra el coach y reporta tres métricas:

  red_flag_recall            escenarios de bandera roja correctamente escalados
  invariant_violations_total planes emitidos que violan R1–R8
  numbers_from_engine_pct    cifras dichas por el coach rastreables a herramientas

**Sale con código distinto de cero si `red_flag_recall` no es 100 %.** CI usa esa
salida para bloquear la entrega: un sistema que deja pasar una bandera roja no se
despliega. Ver ADR 0012.

Los escenarios se implementan en la tarea E4. Este corredor ya funciona: si no
hay escenarios, lo dice y no finge un resultado verde.

Uso:  uv run poe evals
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

# La consola de Windows usa cp1252 y no puede imprimir acentos ni «✓».
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCENARIOS = Path(__file__).parent / "scenarios"


@dataclass(frozen=True)
class Scenario:
    id: str
    entrada: str
    espera: dict[str, object]

    @property
    def is_red_flag(self) -> bool:
        return self.espera.get("safety_level") == "red"


def load_scenarios() -> list[Scenario]:
    escenarios: list[Scenario] = []
    if not SCENARIOS.is_dir():
        return escenarios
    for archivo in sorted(SCENARIOS.glob("*.yaml")):
        contenido = yaml.safe_load(archivo.read_text(encoding="utf-8")) or []
        for item in contenido:
            escenarios.append(
                Scenario(id=item["id"], entrada=item["entrada"], espera=item["espera"])
            )
    return escenarios


def main() -> int:
    escenarios = load_scenarios()

    if not escenarios:
        print("Sin escenarios todavía — se implementan en la tarea E4.")
        print("El corredor está listo; no hay nada que evaluar aún.")
        return 0

    rojos = [e for e in escenarios if e.is_red_flag]
    print(f"Escenarios: {len(escenarios)} ({len(rojos)} de bandera roja)")

    # La ejecución contra el coach se conecta en la tarea E4.
    raise NotImplementedError(
        "Hay escenarios definidos pero el corredor no está conectado al coach. "
        "Completa la tarea E4 antes de confiar en este resultado."
    )


if __name__ == "__main__":
    sys.exit(main())
