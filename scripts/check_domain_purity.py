"""Verifica que el motor de dominio no tenga dependencias de entrada/salida.

`packages/coach_domain/` debe ser código puro: sin red, sin base de datos, sin
SDK de nube y sin framework web. Esa restricción es lo que hace que el motor sea
testeable con pruebas por propiedades y auditable de un vistazo.

CI ejecuta este script. Si alguien contamina el dominio, el build falla — la
arquitectura queda protegida por el pipeline y no por disciplina.

Uso:  uv run poe purity
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

# La consola de Windows usa cp1252 por defecto y no puede imprimir «✓» ni «✗».
# CI corre en Linux con UTF-8, así que sin esto el script sólo falla en local.
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

DOMAIN = Path(__file__).resolve().parent.parent / "packages" / "coach_domain"

FORBIDDEN = {
    # Nube y SDK
    "boto3",
    "botocore",
    "aws_sdk_bedrock_runtime",
    "langfuse",
    # Red
    "httpx",
    "requests",
    "aiohttp",
    "urllib",
    "urllib3",
    "socket",
    "http",
    # Web
    "fastapi",
    "starlette",
    "uvicorn",
    "flask",
    "django",
    # Persistencia
    "sqlalchemy",
    "alembic",
    "psycopg",
    "psycopg2",
    "redis",
    "pymongo",
}


def imported_roots(tree: ast.AST) -> set[str]:
    """Devuelve los módulos raíz importados por un árbol sintáctico."""
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        # level > 0 es un import relativo: siempre interno, se ignora.
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            roots.add(node.module.split(".")[0])
    return roots


def main() -> int:
    if not DOMAIN.is_dir():
        print(f"aviso: {DOMAIN} todavía no existe, nada que verificar")
        return 0

    violations: list[str] = []
    checked = 0

    for path in sorted(DOMAIN.rglob("*.py")):
        checked += 1
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as exc:
            violations.append(f"{path}: no se pudo analizar — {exc}")
            continue

        for module in sorted(imported_roots(tree) & FORBIDDEN):
            rel = path.relative_to(DOMAIN.parent.parent)
            violations.append(f"{rel} importa «{module}»")

    if violations:
        print("PUREZA DEL DOMINIO VIOLADA\n")
        for v in violations:
            print(f"  ✗ {v}")
        print(
            "\nEl motor de dominio no puede depender de red, base de datos ni LLM."
            "\nMueve esa lógica a apps/api/ y deja que el dominio reciba datos ya resueltos."
        )
        return 1

    print(f"dominio puro ✓  ({checked} archivos verificados)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
