"""Resolución de credenciales de AWS para el cliente de streaming.

El SDK de smithy que usa Nova Sonic **sólo lee variables de entorno**. No tiene
resolvedor de perfiles, y —esto es lo que costó un despliegue— **tampoco lee
IMDS**. El ADR 0008 decía que en EC2 el rol de instancia llegaría solo y que
este módulo no haría falta allí. Era falso, y el error no aparece hasta que
alguien intenta hablar:

    SmithyIdentityError: AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required

La API arranca, `/api/health` contesta 200, la pantalla se pinta entera, y la
voz —que es el producto— no funciona. Lo cazó una prueba que abre un stream de
verdad contra Bedrock desde la instancia, no el despliegue en sí.

## Cómo se resuelve ahora

Se usa **botocore**, que ya viene con `aioboto3` y sí tiene la cadena completa:
variables de entorno, perfil, SSO, rol asumido e IMDS. Lo que encuentre se
exporta al entorno para que smithy lo vea.

Se prueba antes el AWS CLI porque en un portátil con SSO da un mensaje mucho más
claro cuando la sesión ha caducado; si no está instalado —como en el contenedor—
se pasa a botocore sin ruido.

## La renovación no es opcional

Las credenciales de un rol de instancia **caducan**, típicamente en unas horas.
Resolverlas sólo al arrancar significa que la voz funciona toda la tarde y deja
de funcionar de madrugada, sin que nadie toque nada. Por eso el puente llama a
`ensure_fresh_credentials()` antes de abrir cada stream, y aquí se renueva
cuando queda menos que `MARGEN`.

Renovar tiene una trampa que costó dieciséis horas de voz caída: como lo
resuelto se exporta a `os.environ`, y el entorno es lo primero que mira
botocore, volver a recorrer la cadena devuelve lo que uno mismo escribió. Está
contado en `_desde_botocore`.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime, timedelta

import structlog

log = structlog.get_logger(__name__)

# Cuánto margen se deja antes de que caduquen.
#
# Tienen que ser MÁS que los ocho minutos que dura un stream: el puente pregunta
# por las credenciales al abrirlo y no vuelve a preguntar hasta el siguiente, así
# que con cinco minutos un stream abierto justo antes del corte seguía vivo
# pasada la caducidad y se moría a mitad de frase. Quince también es la ventana
# con la que botocore refresca por su cuenta, así que las dos coinciden.
MARGEN = timedelta(minutes=15)

_CADUCAN: datetime | None = None

# El objeto de credenciales de botocore, resuelto UNA vez y conservado.
#
# Conservarlo no es una caché por velocidad: es lo único que hace que la
# renovación funcione. Ver `_desde_botocore`.
_CREDENCIALES: object | None = None


def _exportar(clave: str, secreto: str, token: str | None, expira: datetime | None) -> None:
    global _CADUCAN
    os.environ["AWS_ACCESS_KEY_ID"] = clave
    os.environ["AWS_SECRET_ACCESS_KEY"] = secreto
    if token:
        os.environ["AWS_SESSION_TOKEN"] = token
    else:
        # Unas credenciales permanentes detrás de unas temporales dejarían el
        # token viejo en el entorno, y AWS rechazaría la combinación.
        os.environ.pop("AWS_SESSION_TOKEN", None)
    _CADUCAN = expira


def _desde_el_cli() -> bool:
    """El AWS CLI entiende perfiles y SSO, y explica mejor una sesión caducada."""
    aws = shutil.which("aws")
    if aws is None:
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

    expira = None
    if texto := datos.get("Expiration"):
        with_suppress = texto.replace("Z", "+00:00")
        try:
            expira = datetime.fromisoformat(with_suppress)
        except ValueError:
            expira = None

    _exportar(datos["AccessKeyId"], datos["SecretAccessKey"], datos.get("SessionToken"), expira)
    log.info("credentials.desde_el_cli", expira=datos.get("Expiration"))
    return True


def _desde_botocore() -> bool:
    """La cadena completa, IMDS incluido. Es la que funciona en el contenedor.

    ## Por qué la cadena se recorre una sola vez

    Porque este módulo escribe en `os.environ`, y **el proveedor de variables de
    entorno es el primero de la cadena de botocore**. Recorrerla otra vez
    significa encontrarse con lo que uno mismo dejó escrito la vez anterior.

    Eso fue exactamente lo que pasó en producción. La primera resolución traía
    las del rol, con su caducidad, y las exportaba. La segunda —seis horas más
    tarde, cuando tocaba renovar— leía esas mismas variables y las devolvía como
    `method=env`, ya caducadas y sin fecha de caducidad. Sin fecha, `_CADUCAN`
    quedaba en `None` y se reintentaba en cada stream, encontrándose siempre a
    sí mismo. **El rol no se volvió a consultar nunca**, y Bedrock contestó 403
    `ExpiredTokenException` durante dieciséis horas, en voz y en texto.

    Guardando el objeto, se le pregunta a él. Cuando viene del rol es un
    `RefreshableCredentials`, y `get_frozen_credentials()` es justo el punto
    donde botocore va a IMDS a por unas nuevas si hacen falta. La renovación
    la hace quien sabe hacerla, y aquí sólo se copia el resultado al entorno.
    """
    global _CREDENCIALES

    if _CREDENCIALES is None:
        try:
            import botocore.session
        except ImportError:  # pragma: no cover - botocore viene con aioboto3
            log.warning("credentials.sin_botocore")
            return False
        _CREDENCIALES = botocore.session.get_session().get_credentials()

    credenciales = _CREDENCIALES
    if credenciales is None:
        log.warning("credentials.sin_cadena", hint="ni entorno, ni perfil, ni rol de instancia")
        return False

    congeladas = credenciales.get_frozen_credentials()
    expira = getattr(credenciales, "_expiry_time", None)
    if expira is not None and expira.tzinfo is None:
        expira = expira.replace(tzinfo=UTC)

    _exportar(congeladas.access_key, congeladas.secret_key, congeladas.token, expira)
    log.info("credentials.desde_botocore", metodo=credenciales.method, expira=str(expira))
    return True


def ensure_aws_credentials() -> bool:
    """Deja `AWS_ACCESS_KEY_ID` y compañía en el entorno. Devuelve si las hay.

    No lanza si falla: se registra el motivo y se deja que el error aparezca al
    abrir el stream, donde el mensaje dice mucho más.
    """
    if os.getenv("AWS_ACCESS_KEY_ID") and not os.getenv("AWS_SESSION_TOKEN"):
        # Permanentes puestas a mano: no caducan y no hay nada que renovar.
        log.debug("credentials.ya_en_el_entorno")
        return True

    return _desde_el_cli() or _desde_botocore()


def ensure_fresh_credentials() -> bool:
    """Renueva si están a punto de caducar. Se llama antes de abrir un stream.

    Sin esto, la voz funciona hasta que caducan las credenciales del rol y luego
    deja de funcionar sin que nadie haya tocado nada — de madrugada, y con un
    error que apunta a Bedrock en vez de a la sesión.
    """
    if _CADUCAN is not None and datetime.now(UTC) + MARGEN < _CADUCAN:
        return True
    if _CADUCAN is not None:
        log.info("credentials.renovando", caducaban=str(_CADUCAN))
    return ensure_aws_credentials()


def credentials_expiry() -> datetime | None:
    """Cuándo caducan las actuales, si son temporales. Para `/api/config`."""
    return _CADUCAN
