"""Despliega Ritmo en el EC2, desde aquí, sin SSH.

Todo va por `aws ssm send-command`: el grupo de seguridad no tiene el puerto 22
abierto y no hay ninguna llave privada que custodiar. La instancia lleva el
`AmazonSSMManagedInstanceCore` en su rol, y nada más que eso y el permiso de
Bedrock para el stream de voz.

## Cómo viajan los secretos, y por qué así

El `.env` se manda como el cuerpo de un comando de SSM y se escribe con permisos
600. **No va en el user-data**, que es la forma cómoda y la equivocada: el
user-data se lee desde dentro de la instancia por el servicio de metadatos, así
que cualquier proceso de la caja —y cualquier fallo de SSRF en la aplicación—
podría leerlo entero.

Queda registrado en CloudTrail que se envió un comando, con su identidad y su
hora, pero el contenido no aparece en la consola de EC2 como sí aparecería el
user-data.

Sigue siendo una solución de despliegue pequeño. Lo que tocaría con más tiempo
es Secrets Manager con el rol leyendo al arrancar, y así el secreto no pasa
nunca por esta máquina. Está anotado como deuda, no como olvido.

## Qué NO se copia

`AWS_ACCESS_KEY_ID` y demás credenciales estáticas. La instancia usa su rol, y
mandar claves de un usuario administrador a un servidor público sería regalar
la cuenta entera. El filtro es explícito y está probado abajo.

Uso:
    python scripts/deploy_remote.py            # despliega
    python scripts/deploy_remote.py --solo-env # sólo reescribe el .env remoto
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Lo que NUNCA sale de este equipo. Las credenciales de AWS las da el rol de
# instancia; mandar las de un usuario administrador a un servidor con el 443
# abierto sería entregar la cuenta con la aplicación.
PROHIBIDAS = (
    "AWS_ACCESS_KEY_ID",
    "AWS_SECRET_ACCESS_KEY",
    "AWS_SESSION_TOKEN",
    "AWS_PROFILE",
)

ARTEFACTO = "s3://ritmo-deploy-602440904865/ritmo.tar.gz"

# Lo que sí necesita el servidor, y sólo eso.
NECESARIAS = (
    "DB_PASSWORD",
    "N8N_ENCRYPTION_KEY",
    "JWT_SECRET",
    "ANTHROPIC_API_KEY",
    "VISION_MODEL_CHAIN",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_USERNAME",
    "TELEGRAM_WEBHOOK_SECRET",
    "AUTOMATION_API_KEY",
    "AWS_REGION",
    "NOVA_MODEL_ID",
    "NOVA_VOICE_ID",
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
)


def env_para_el_servidor(texto: str, site_address: str) -> str:
    """Filtra el `.env` local y le pone la dirección pública.

    Devuelve sólo las claves de `NECESARIAS` que tengan valor, más
    `SITE_ADDRESS`. Todo lo demás se queda aquí — incluida cualquier clave que
    alguien añada en el futuro y que nadie haya pensado si debe viajar.
    """
    valores: dict[str, str] = {}
    for linea in texto.splitlines():
        linea = linea.strip()
        if not linea or linea.startswith("#") or "=" not in linea:
            continue
        clave, _, valor = linea.partition("=")
        clave, valor = clave.strip(), valor.strip()
        if clave in PROHIBIDAS:
            continue
        if clave in NECESARIAS and valor:
            valores[clave] = valor

    valores["SITE_ADDRESS"] = site_address
    cabecera = (
        "# Generado por scripts/deploy_remote.py. No editar a mano:\n"
        "# el siguiente despliegue lo sobrescribe.\n"
    )
    return cabecera + "\n".join(f"{k}={v}" for k, v in sorted(valores.items())) + "\n"


def _leer(nombre: str) -> str:
    return (Path(tempfile.gettempdir()) / nombre).read_text().strip()


def ssm(instancia: str, script: str, minutos: int = 25) -> tuple[int, str]:
    """Ejecuta un script en la instancia y espera. Devuelve (código, salida)."""
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump({"commands": script.splitlines()}, f)
        params = f.name

    envio = subprocess.run(
        [
            "aws",
            "ssm",
            "send-command",
            "--instance-ids",
            instancia,
            "--document-name",
            "AWS-RunShellScript",
            "--parameters",
            "file://" + params,
            "--timeout-seconds",
            "3600",
            "--query",
            "Command.CommandId",
            "--output",
            "text",
        ],
        capture_output=True,
        text=True,
    )
    if envio.returncode:
        return 1, envio.stderr

    cid = envio.stdout.strip()
    for _ in range(minutos * 4):
        consulta = subprocess.run(
            [
                "aws",
                "ssm",
                "get-command-invocation",
                "--command-id",
                cid,
                "--instance-id",
                instancia,
                "--output",
                "json",
            ],
            capture_output=True,
            text=True,
        )
        if consulta.returncode == 0:
            d = json.loads(consulta.stdout)
            if d["Status"] in ("Success", "Failed", "Cancelled", "TimedOut"):
                salida = d.get("StandardOutputContent", "")
                error = d.get("StandardErrorContent", "")
                if error.strip():
                    salida += "\n--- stderr ---\n" + error[-4000:]
                return (0 if d["Status"] == "Success" else 1), salida
        time.sleep(15)

    # Se acabó la espera de ESTE script, no la del comando: SSM lo lanzó con
    # una hora de plazo y allá sigue. Decirlo importa — «sin terminar» a secas
    # se lee como «falló», y la reacción correcta no es volver a desplegar
    # encima, es ir a mirar cómo acabó.
    return 1, (
        f"la espera local se agotó a los {minutos} min; el comando {cid} "
        f"SIGUE CORRIENDO en la instancia.\n"
        f"míralo con: aws ssm get-command-invocation --command-id {cid} "
        f"--instance-id {instancia}"
    )


def empaquetar_y_subir() -> tuple[int, str]:
    """Empaqueta el commit actual y lo sube a S3. Devuelve (código, commit).

    **Este paso faltaba, y su ausencia no se notaba: se notaba al revés.** El
    script bajaba a la instancia el artefacto que hubiera en S3, sin comprobar
    de cuándo era, y terminaba anunciando «Desplegado». Un despliegue que en
    realidad reinstalaba código de hace seis horas y decía que había ido bien.
    Lo cacé porque la ruta nueva contestaba 404 en producción con las pruebas
    en verde; sin esa casualidad, la demo del lunes habría corrido sobre un
    commit que nadie eligió.

    Se empaqueta con `git archive` y no con `tar` del directorio: así lo que
    viaja es exactamente un commit —sin `.env`, sin `node_modules`, sin la base
    de datos local— y no «lo que hubiera en el disco». Que el artefacto tenga
    un nombre de commit es lo que hace que la pregunta «¿qué está corriendo
    allá?» tenga respuesta.
    """
    sucio = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, cwd=RAIZ
    ).stdout.strip()
    commit = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, cwd=RAIZ
    ).stdout.strip()

    if sucio:
        # No se aborta: a veces hay que desplegar con algo sin commitear. Pero
        # se dice, porque entonces lo que corre allá no está en ningún sitio.
        print(f"AVISO: hay cambios sin commitear; se despliega {commit} sin ellos.")

    destino = Path(tempfile.gettempdir()) / "ritmo.tar.gz"
    empaque = subprocess.run(
        ["git", "archive", "--format=tar.gz", "-o", str(destino), "HEAD"],
        capture_output=True,
        text=True,
        cwd=RAIZ,
    )
    if empaque.returncode:
        print("no pude empaquetar: " + empaque.stderr)
        return 1, commit

    subida = subprocess.run(
        ["aws", "s3", "cp", str(destino), ARTEFACTO, "--only-show-errors"],
        capture_output=True,
        text=True,
    )
    if subida.returncode:
        print("no pude subir el artefacto: " + subida.stderr)
        return 1, commit

    print(f"artefacto subido · {commit} · {destino.stat().st_size // 1024} KiB")
    return 0, commit


def main() -> int:
    parser = argparse.ArgumentParser(description="Despliega Ritmo en el EC2 por SSM")
    parser.add_argument("--instancia", default="", help="i-...; por defecto se busca por etiqueta")
    parser.add_argument("--solo-env", action="store_true", help="sólo reescribe el .env remoto")
    args = parser.parse_args()

    instancia = (
        args.instancia
        or subprocess.run(
            [
                "aws",
                "ec2",
                "describe-instances",
                "--filters",
                "Name=tag:Name,Values=ritmo",
                "Name=instance-state-name,Values=running",
                "--query",
                "Reservations[0].Instances[0].InstanceId",
                "--output",
                "text",
            ],
            capture_output=True,
            text=True,
        ).stdout.strip()
    )

    if not instancia or instancia == "None":
        print("No encuentro una instancia en marcha con la etiqueta Name=ritmo.")
        return 1

    ip = subprocess.run(
        [
            "aws",
            "ec2",
            "describe-instances",
            "--instance-ids",
            instancia,
            "--query",
            "Reservations[0].Instances[0].PublicIpAddress",
            "--output",
            "text",
        ],
        capture_output=True,
        text=True,
    ).stdout.strip()

    # sslip.io resuelve <ip-con-guiones>.sslip.io a esa IP, así que Let's
    # Encrypt puede emitir un certificado sin comprar dominio. Es lo que hace
    # que el micrófono funcione: `getUserMedia` exige contexto seguro.
    dominio = ip.replace(".", "-") + ".sslip.io"
    print(f"instancia {instancia}  ·  {ip}  ·  https://{dominio}")

    local = RAIZ / ".env"
    if not local.is_file():
        print("Falta el .env local: es de donde salen los secretos.")
        return 1

    remoto = env_para_el_servidor(local.read_text(encoding="utf-8"), dominio)
    claves = [
        ln.split("=")[0] for ln in remoto.splitlines() if "=" in ln and not ln.startswith("#")
    ]
    print("se envían: " + ", ".join(claves))

    # `sh`, no `bash`: SSM ejecuta con el intérprete POSIX y ahí `pipefail` no
    # existe. Lo dijo un «Illegal option -o pipefail» que no señala de dónde
    # sale. Los scripts que sí necesitan bash se invocan con bash explícito.
    escribir = (
        "set -eu\n"
        "install -d -m 755 /opt/ritmo\n"
        "cat > /opt/ritmo/.env <<'FIN_DEL_ENV'\n" + remoto + "FIN_DEL_ENV\n"
        "chmod 600 /opt/ritmo/.env\n"
        "chown root:root /opt/ritmo/.env\n"
        "echo 'env escrito con permisos 600'\n"
    )
    codigo, salida = ssm(instancia, escribir, minutos=3)
    print(salida)
    if codigo:
        return codigo
    if args.solo_env:
        return 0

    # Antes de traer nada: subir lo que se quiere traer.
    codigo, commit = empaquetar_y_subir()
    if codigo:
        return codigo

    # Traer y extraer va aquí y no en `deploy.sh` por un motivo tonto y real:
    # `deploy.sh` viaja DENTRO del artefacto, así que no puede ser quien lo
    # descargue. El `.env` se aparta antes de desempaquetar y se repone después
    # — no viene en el artefacto y desempaquetar encima no debe perderlo.
    traer = "\n".join(
        [
            "set -eu",
            "TMP=$(mktemp -d)",
            "cp -a /opt/ritmo/.env $TMP/.env",
            f"/usr/local/bin/aws s3 cp {ARTEFACTO} $TMP/ritmo.tar.gz",
            "tar -xzf $TMP/ritmo.tar.gz -C /opt/ritmo",
            "cp -a $TMP/.env /opt/ritmo/.env",
            "chmod 600 /opt/ritmo/.env",
            "rm -rf $TMP",
            "echo 'artefacto extraido'",
        ]
    )
    codigo, salida = ssm(instancia, traer, minutos=5)
    print(salida)
    if codigo:
        return codigo

    codigo, salida = ssm(instancia, "bash /opt/ritmo/infra/deploy.sh 2>&1", minutos=25)
    print(salida)
    if codigo == 0:
        print(f"\nDesplegado: https://{dominio}")
    return codigo


if __name__ == "__main__":
    sys.exit(main())
