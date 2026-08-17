"""El filtro que decide qué secretos salen de este equipo.

Es la única parte del despliegue que se puede probar sin AWS, y también la que
más caro sale si falla: mandar las credenciales del usuario administrador a un
servidor con el 443 abierto es entregar la cuenta entera junto con la
aplicación.

La prueba que importa es la de la lista blanca. Una lista negra protege de lo
que alguien ya pensó; una lista blanca protege también de la clave que se
añadirá al `.env` dentro de tres semanas sin que nadie se pregunte si debe
viajar.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(RAIZ))

from scripts.deploy_remote import PROHIBIDAS, env_para_el_servidor  # noqa: E402

DOMINIO = "54-80-131-31.sslip.io"


def _claves(texto: str) -> set[str]:
    return {
        ln.split("=", 1)[0]
        for ln in texto.splitlines()
        if "=" in ln and not ln.lstrip().startswith("#")
    }


def test_las_credenciales_de_aws_nunca_viajan() -> None:
    """La instancia usa su rol. Mandarle claves estáticas sería regalar la cuenta."""
    local = "\n".join(
        [
            "AWS_ACCESS_KEY_ID=AKIAEJEMPLO",
            "AWS_SECRET_ACCESS_KEY=secretisimo",
            "AWS_SESSION_TOKEN=temporal",
            "AWS_PROFILE=fernando-admin",
            "DB_PASSWORD=algo",
            "JWT_SECRET=otro",
            "N8N_ENCRYPTION_KEY=mas",
        ]
    )
    salida = env_para_el_servidor(local, DOMINIO)

    for prohibida in PROHIBIDAS:
        assert prohibida not in salida
    assert "AKIAEJEMPLO" not in salida
    assert "secretisimo" not in salida


def test_una_clave_desconocida_no_pasa_por_defecto() -> None:
    """Lista blanca, no lista negra.

    Una lista negra protege de lo que alguien ya pensó. Ésta protege también de
    la variable que se añada mañana — se queda fuera hasta que alguien la
    escriba a propósito en `NECESARIAS`, que es el momento de preguntarse si
    debe estar en un servidor público.
    """
    salida = env_para_el_servidor("SECRETO_NUEVO_DE_MAÑANA=lo-que-sea", DOMINIO)
    assert "SECRETO_NUEVO_DE_MAÑANA" not in salida
    assert "lo-que-sea" not in salida


def test_lo_que_el_servidor_necesita_sí_pasa() -> None:
    local = "\n".join(
        [
            "DB_PASSWORD=p",
            "JWT_SECRET=j",
            "N8N_ENCRYPTION_KEY=n",
            "ANTHROPIC_API_KEY=a",
            "TELEGRAM_BOT_TOKEN=t",
            "TELEGRAM_BOT_USERNAME=RitmoCoachBot",
            "TELEGRAM_WEBHOOK_SECRET=w",
            "AUTOMATION_API_KEY=x",
        ]
    )
    claves = _claves(env_para_el_servidor(local, DOMINIO))

    assert {"DB_PASSWORD", "JWT_SECRET", "N8N_ENCRYPTION_KEY"} <= claves
    assert {"ANTHROPIC_API_KEY", "TELEGRAM_BOT_TOKEN", "AUTOMATION_API_KEY"} <= claves


def test_las_variables_vacias_no_se_copian() -> None:
    """Una clave presente y vacía en el servidor es peor que ausente: `compose`
    la sustituye por cadena vacía en vez de usar su valor por defecto."""
    claves = _claves(env_para_el_servidor("DB_PASSWORD=p\nANTHROPIC_API_KEY=\n", DOMINIO))
    assert "ANTHROPIC_API_KEY" not in claves
    assert "DB_PASSWORD" in claves


def test_la_direccion_publica_se_impone() -> None:
    """Aunque el `.env` local traiga `SITE_ADDRESS=localhost`, que es lo normal.

    Sin esto, Caddy pediría un certificado para «localhost» en un servidor
    público y no habría HTTPS — y sin HTTPS el micrófono no arranca.
    """
    salida = env_para_el_servidor("SITE_ADDRESS=localhost\nDB_PASSWORD=p", DOMINIO)
    assert f"SITE_ADDRESS={DOMINIO}" in salida
    assert "SITE_ADDRESS=localhost" not in salida


@pytest.mark.parametrize("ruido", ["", "   ", "# un comentario", "sin_igual"])
def test_las_lineas_que_no_son_variables_se_ignoran(ruido: str) -> None:
    salida = env_para_el_servidor(f"{ruido}\nDB_PASSWORD=p", DOMINIO)
    assert "DB_PASSWORD=p" in salida
