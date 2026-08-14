"""El paquete de dominio se importa sin arrastrar dependencias externas."""

from __future__ import annotations

import sys


def test_el_dominio_se_importa() -> None:
    import coach_domain

    assert coach_domain.__version__


def test_importar_el_dominio_no_carga_sdk_de_nube() -> None:
    """Refuerza en tiempo de ejecución lo que el script de pureza verifica en estático."""
    for modulo in ("boto3", "sqlalchemy", "fastapi"):
        sys.modules.pop(modulo, None)

    import coach_domain  # noqa: F401

    for modulo in ("boto3", "sqlalchemy", "fastapi"):
        assert modulo not in sys.modules, f"importar el dominio cargó {modulo}"
