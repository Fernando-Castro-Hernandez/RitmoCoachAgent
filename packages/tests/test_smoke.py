"""El paquete de dominio se importa sin arrastrar dependencias externas."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[2]

# Módulos que el dominio no puede arrastrar ni indirectamente. Es la misma lista
# que verifica `scripts/check_domain_purity.py` en estático; aquí se comprueba
# en ejecución, que es donde aparecen los arrastres transitivos: un import
# limpio que trae otro import sucio dos capas más abajo.
_PROHIBIDOS = ("boto3", "sqlalchemy", "fastapi", "httpx", "aws_sdk_bedrock_runtime")


def test_el_dominio_se_importa() -> None:
    import coach_domain

    assert coach_domain.__version__


def test_importar_el_dominio_no_carga_sdk_de_nube() -> None:
    """Se comprueba en un intérprete nuevo, no manipulando `sys.modules`.

    La versión que vaciaba `sys.modules` era peor que inútil: dejaba los
    submódulos cargados y el paquete padre fuera, y la siguiente carga perezosa
    de un dialecto de SQLAlchemy reventaba con un `AttributeError` a kilómetros
    de aquí. Una prueba de aislamiento que rompe el proceso no está aislando
    nada. Un subproceso limpio sí.
    """
    guion = (
        "import sys; import coach_domain; "
        f"sucios=[m for m in {_PROHIBIDOS!r} if m in sys.modules]; "
        "print(','.join(sucios))"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", guion],
        capture_output=True,
        text=True,
        cwd=_RAIZ,
        env={"PYTHONPATH": str(_RAIZ / "packages"), "SYSTEMROOT": ""},
        timeout=60,
        check=False,
    )
    assert resultado.returncode == 0, resultado.stderr
    sucios = resultado.stdout.strip()
    assert not sucios, f"importar el dominio cargó: {sucios}"
