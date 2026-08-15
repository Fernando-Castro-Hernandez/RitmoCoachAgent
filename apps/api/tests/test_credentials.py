"""Resolución de credenciales sin depender de la máquina donde corren las pruebas."""

from __future__ import annotations

import json
import subprocess
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


def test_sin_cli_no_revienta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(credentials.shutil, "which", lambda _: None)
    assert credentials.ensure_aws_credentials() is False


def test_si_el_cli_falla_no_revienta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(credentials.shutil, "which", lambda _: "/usr/bin/aws")

    def falla(*a: Any, **k: Any) -> None:
        raise subprocess.CalledProcessError(1, "aws", stderr="perfil inexistente")

    monkeypatch.setattr(subprocess, "run", falla)
    assert credentials.ensure_aws_credentials() is False
