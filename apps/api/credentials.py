"""Resolución de credenciales de AWS para el cliente de streaming.

El SDK de smithy que usa Nova Sonic **no tiene resolvedor de perfiles**: sólo lee
variables de entorno o IMDS. Eso obligaría a exportar las credenciales a mano
antes de arrancar la API, con una sintaxis distinta en bash y en PowerShell.

En vez de eso, si las variables no están puestas se le preguntan al AWS CLI, que
sí entiende perfiles, SSO y roles asumidos. En EC2 no hace falta: el rol de
instancia llega por IMDS y este módulo no toca nada (ADR 0008).
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess

import structlog

log = structlog.get_logger(__name__)


def ensure_aws_credentials() -> bool:
    """Deja `AWS_ACCESS_KEY_ID` y compañía en el entorno. Devuelve si hay credenciales.

    No lanza excepción si falla: se registra el motivo y se deja que el error
    aparezca al abrir el stream, donde el mensaje es más útil.
    """
    if os.getenv("AWS_ACCESS_KEY_ID"):
        log.debug("credentials.already_in_env")
        return True

    aws = shutil.which("aws")
    if aws is None:
        log.warning("credentials.no_cli", hint="instala el AWS CLI o exporta las variables")
        return False

    try:
        proceso = subprocess.run(
            [aws, "configure", "export-credentials", "--format", "process"],
            capture_output=True,
            text=True,
            timeout=30,
            check=True,
        )
        datos = json.loads(proceso.stdout)
    except subprocess.CalledProcessError as exc:
        log.warning("credentials.cli_failed", stderr=exc.stderr.strip()[:200])
        return False
    except (OSError, subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
        log.warning("credentials.unreadable", error=str(exc))
        return False

    os.environ["AWS_ACCESS_KEY_ID"] = datos["AccessKeyId"]
    os.environ["AWS_SECRET_ACCESS_KEY"] = datos["SecretAccessKey"]
    if token := datos.get("SessionToken"):
        os.environ["AWS_SESSION_TOKEN"] = token

    log.info("credentials.loaded_from_cli", expires=datos.get("Expiration"))
    return True
