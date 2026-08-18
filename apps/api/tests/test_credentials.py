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
    # El módulo conserva el objeto de botocore entre llamadas, que es justo lo
    # que arregla la renovación. Entre pruebas hay que soltarlo, o la primera
    # que resuelva le deja las credenciales puestas a todas las demás.
    monkeypatch.setattr(credentials, "_CREDENCIALES", None)
    monkeypatch.setattr(credentials, "_CADUCAN", None)


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


# ── la renovación que no renovaba ────────────────────────────────────


class _DelRol:
    """Las del rol de instancia: temporales, y se refrescan solas.

    Es lo que devuelve botocore por IMDS. `get_frozen_credentials()` es el
    punto donde botocore decide si tiene que ir a por unas nuevas.
    """

    method = "iam-role"

    def __init__(self, cadena: _CadenaRealista) -> None:
        self._cadena = cadena
        self._refrescar()

    def _refrescar(self) -> None:
        self._cadena.refrescos += 1
        self.access_key = f"AKIADELROL-{self._cadena.refrescos}"
        self.secret_key = "secreta-del-rol"
        self.token = f"token-del-rol-{self._cadena.refrescos}"
        self._expiry_time = datetime.now(UTC) + timedelta(hours=6)

    def envejecer(self) -> None:
        """Pasan las horas. Botocore no lo sabe hasta que se le pregunta."""
        self._expiry_time = datetime.now(UTC) + timedelta(minutes=1)

    def get_frozen_credentials(self) -> _DelRol:
        # Lo que hace `RefreshableCredentials`: si están por caducar, va a por
        # unas nuevas antes de entregarlas.
        if datetime.now(UTC) + timedelta(minutes=15) > self._expiry_time:
            self._refrescar()
        return self


class _DelEntorno:
    """Las que encuentra en las variables de entorno: sin caducidad conocida."""

    method = "env"

    def __init__(self) -> None:
        import os as _os

        self.access_key = _os.environ["AWS_ACCESS_KEY_ID"]
        self.secret_key = _os.environ.get("AWS_SECRET_ACCESS_KEY", "")
        self.token = _os.environ.get("AWS_SESSION_TOKEN")

    def get_frozen_credentials(self) -> _DelEntorno:
        return self


class _CadenaRealista:
    """Un botocore de mentira que se comporta como el de verdad en LO QUE IMPORTA.

    Y lo que importa es una sola cosa: **el proveedor de variables de entorno va
    primero en la cadena**. Las demás pruebas de este archivo sustituyen
    `get_credentials` por una función que siempre devuelve lo mismo, así que no
    pueden ver el fallo — la cadena nunca mira el entorno.
    """

    def __init__(self) -> None:
        self.refrescos = 0
        self.resoluciones = 0
        self._del_rol = _DelRol(self)

    def get_credentials(self) -> object:
        import os as _os

        self.resoluciones += 1
        if _os.environ.get("AWS_ACCESS_KEY_ID"):
            return _DelEntorno()
        return self._del_rol


def test_lo_exportado_no_envenena_la_siguiente_renovacion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """El fallo que dejó la voz muerta en producción durante dieciséis horas.

    `_exportar` escribe las credenciales en `os.environ` para que las vea el SDK
    de smithy, que no sabe leer de ningún otro sitio. Pero el proveedor de
    variables de entorno es el PRIMERO de la cadena de botocore: en la siguiente
    resolución, botocore encontraba lo que este módulo acababa de escribir y lo
    devolvía tal cual, con `method=env` y sin caducidad.

    A partir de ahí ya no había vuelta atrás. `_CADUCAN` quedaba en `None`, así
    que `ensure_fresh_credentials` reintentaba en cada stream, y en cada intento
    volvía a leerse a sí mismo. **El rol nunca se consultaba de nuevo.** Bedrock
    contestaba 403 `ExpiredTokenException` y el corredor veía «algo falló», en
    voz y en texto, que comparten puente.

    En los logs se lee entero:

        20:27 credentials.desde_botocore  expira='...02:41:45+00:00' metodo=iam-role
        18:33 credentials.renovando       caducaban='...02:41:45+00:00'
        18:33 credentials.desde_botocore  expira=None metodo=env      ← aquí
        ...   credentials.desde_botocore  expira=None metodo=env      ← y ya siempre
    """
    cadena = _CadenaRealista()
    monkeypatch.setattr(credentials.shutil, "which", lambda _: None)
    monkeypatch.setattr(credentials, "_CADUCAN", None)
    monkeypatch.setattr(credentials, "_CREDENCIALES", None, raising=False)

    import botocore.session

    monkeypatch.setattr(botocore.session, "get_session", lambda: cadena)

    assert credentials.ensure_aws_credentials() is True
    primera = credentials.os.environ["AWS_ACCESS_KEY_ID"]
    assert credentials.credentials_expiry() is not None

    # Pasan las horas: las del rol están por caducar y toca renovar.
    cadena._del_rol.envejecer()
    monkeypatch.setattr(credentials, "_CADUCAN", datetime.now(UTC) + timedelta(minutes=1))
    assert credentials.ensure_fresh_credentials() is True

    assert credentials.credentials_expiry() is not None, (
        "se perdió la caducidad: se resolvió desde el entorno que este módulo "
        "escribió, no desde el rol. Es el fallo de producción."
    )
    assert credentials.os.environ["AWS_ACCESS_KEY_ID"] != primera, (
        "las credenciales no cambiaron: se renovó contra sí mismo"
    )


def test_el_margen_cubre_un_stream_entero(monkeypatch: pytest.MonkeyPatch) -> None:
    """El puente renueva su stream cada ocho minutos, y no vuelve a preguntar
    por las credenciales hasta el siguiente. Con un margen menor, un stream
    abierto justo antes del corte sigue vivo pasada la caducidad y muere a
    mitad de frase."""
    assert timedelta(minutes=10) <= credentials.MARGEN
