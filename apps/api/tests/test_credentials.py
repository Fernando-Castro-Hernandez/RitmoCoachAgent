"""Resolución de credenciales sin depender de la máquina donde corren las pruebas.

Lo que estas pruebas protegen ahora es más que «no revienta»: es que **haya
cadena**. El SDK de smithy que usa Nova Sonic sólo lee variables de entorno —ni
perfiles, ni IMDS— así que si nadie las pone, la voz no funciona. La API
arranca igual, `/api/health` contesta 200, y el fallo no se ve hasta que alguien
intenta hablar.

En el contenedor no hay AWS CLI, y ahí es donde entra botocore. Por eso ahora
`test_sin_cli_cae_a_botocore` es la prueba que importa: cuando lo escribí,
faltaba ese respaldo y el despliegue quedó con la voz muerta.
"""

from __future__ import annotations

import json
import subprocess
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from typing import Any

import pytest

from apps.api import credentials


@pytest.fixture(autouse=True)
def entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> None:
    for clave in ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN"):
        monkeypatch.delenv(clave, raising=False)


def test_respeta_las_variables_ya_definidas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "ya-estaba")

    def explota(*_: Any, **__: Any) -> None:
        raise AssertionError("no debe invocar al CLI si ya hay credenciales")

    monkeypatch.setattr(subprocess, "run", explota)
    assert credentials.ensure_aws_credentials() is True


def test_carga_desde_el_cli(monkeypatch: pytest.MonkeyPatch) -> None:
    salida = json.dumps(
        {
            "Version": 1,
            "AccessKeyId": "AKIAFALSA",
            "SecretAccessKey": "secreta",
            "SessionToken": "temporal",
        }
    )
    monkeypatch.setattr(credentials.shutil, "which", lambda _: "/usr/bin/aws")
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=salida, stderr=""),
    )

    assert credentials.ensure_aws_credentials() is True
    assert credentials.os.environ["AWS_ACCESS_KEY_ID"] == "AKIAFALSA"
    assert credentials.os.environ["AWS_SESSION_TOKEN"] == "temporal"


class _Credenciales:
    """Lo que devuelve botocore, con lo justo que se le pide."""

    method = "iam-role"
    access_key = "AKIADELROL"
    secret_key = "secreta-del-rol"
    token = "token-del-rol"

    def get_frozen_credentials(self) -> _Credenciales:
        return self


def _botocore_devuelve(monkeypatch: pytest.MonkeyPatch, credenciales: object) -> None:
    import botocore.session

    monkeypatch.setattr(
        botocore.session,
        "get_session",
        lambda: SimpleNamespace(get_credentials=lambda: credenciales),
    )


def test_sin_cli_cae_a_botocore(monkeypatch: pytest.MonkeyPatch) -> None:
    """El caso del contenedor, y el que costó un despliegue.

    En la imagen no hay AWS CLI. Sin este respaldo, `ensure_aws_credentials`
    devolvía False, nadie ponía las variables, y Nova Sonic contestaba
    «AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required» — pero sólo
    cuando alguien intentaba hablar.
    """
    monkeypatch.setattr(credentials.shutil, "which", lambda _: None)
    _botocore_devuelve(monkeypatch, _Credenciales())

    assert credentials.ensure_aws_credentials() is True
    assert credentials.os.environ["AWS_ACCESS_KEY_ID"] == "AKIADELROL"
    assert credentials.os.environ["AWS_SESSION_TOKEN"] == "token-del-rol"


def test_si_el_cli_falla_se_intenta_botocore(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(credentials.shutil, "which", lambda _: "/usr/bin/aws")

    def falla(*a: Any, **k: Any) -> None:
        raise subprocess.CalledProcessError(1, "aws", stderr="perfil inexistente")

    monkeypatch.setattr(subprocess, "run", falla)
    _botocore_devuelve(monkeypatch, _Credenciales())

    assert credentials.ensure_aws_credentials() is True


def test_sin_nada_devuelve_false_y_no_revienta(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ni CLI ni cadena. No lanza: el error se ve al abrir el stream, donde el
    mensaje dice mucho más que aquí."""
    monkeypatch.setattr(credentials.shutil, "which", lambda _: None)
    _botocore_devuelve(monkeypatch, None)

    assert credentials.ensure_aws_credentials() is False


def test_unas_permanentes_borran_el_token_viejo(monkeypatch: pytest.MonkeyPatch) -> None:
    """Un token de sesión que sobrevive a unas credenciales permanentes hace que
    AWS rechace la combinación entera."""
    monkeypatch.setenv("AWS_SESSION_TOKEN", "de-antes")
    monkeypatch.setattr(credentials.shutil, "which", lambda _: None)

    permanentes = _Credenciales()
    permanentes.token = None  # type: ignore[assignment]
    _botocore_devuelve(monkeypatch, permanentes)

    assert credentials.ensure_aws_credentials() is True
    assert "AWS_SESSION_TOKEN" not in credentials.os.environ


# ── renovación ───────────────────────────────────────────────────────


def test_no_renueva_si_todavia_faltan_horas(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(credentials, "_CADUCAN", datetime.now(UTC) + timedelta(hours=3))
    monkeypatch.setattr(
        credentials, "ensure_aws_credentials", lambda: pytest.fail("no debía renovar")
    )
    assert credentials.ensure_fresh_credentials() is True


def test_renueva_cuando_estan_por_caducar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sin esto, la voz funciona toda la tarde y muere de madrugada sin que
    nadie haya tocado nada."""
    monkeypatch.setattr(credentials, "_CADUCAN", datetime.now(UTC) + timedelta(minutes=1))
    llamadas: list[int] = []
    monkeypatch.setattr(
        credentials, "ensure_aws_credentials", lambda: (llamadas.append(1), True)[1]
    )

    assert credentials.ensure_fresh_credentials() is True
    assert llamadas == [1]
