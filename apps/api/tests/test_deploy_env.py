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


# ── que se despliegue lo que se cree que se despliega ─────────────────


def test_el_artefacto_se_sube_antes_de_traerlo() -> None:
    """El fallo que costó un despliegue entero: nadie subía el artefacto.

    El script bajaba a la instancia lo que hubiera en S3 —seis horas viejo— y
    anunciaba «Desplegado». Las pruebas en verde, el commit en `main`, y
    producción corriendo otra cosa. Se descubrió por casualidad: una ruta nueva
    contestando 404 en un servidor que decía estar recién desplegado.

    Esta prueba fija el ORDEN, que es lo único que hace que el artefacto sea el
    de este commit y no el de cualquier otro.
    """
    fuente = (RAIZ / "scripts" / "deploy_remote.py").read_text(encoding="utf-8")
    cuerpo = fuente.split("def main(")[1]

    # Se ancla en las DOS asignaciones, no en las palabras. Buscar «traer» a
    # secas encontraba mi propio comentario «antes de traer nada», que está
    # justo encima de la subida: la prueba fallaba con el código correcto.
    # Es el mismo falso positivo que «uvicorn» conteniendo «uv».
    subida = cuerpo.find("= empaquetar_y_subir()")
    descarga = cuerpo.find('traer = "\\n".join(')
    assert subida != -1, "main() ya no sube el artefacto: se desplegaría código viejo"
    assert descarga != -1, "cambió cómo se arma el paso de descarga; revisa esta prueba"
    assert subida < descarga, "se baja el artefacto antes de subirlo: llegaría el anterior"


def test_el_artefacto_sale_de_un_commit_y_no_del_disco() -> None:
    """`git archive` y no `tar` del directorio.

    Con `tar` viajaría «lo que hubiera en el disco»: el `.env` local, la base de
    datos de pruebas, `node_modules`. Con `git archive` viaja un commit, que
    además es la única forma de poder responder qué está corriendo allá.
    """
    fuente = (RAIZ / "scripts" / "deploy_remote.py").read_text(encoding="utf-8")
    assert '"git", "archive"' in fuente


def test_agotar_la_espera_no_se_confunde_con_un_fallo() -> None:
    """El comando sigue vivo en la instancia cuando el script deja de mirar.

    «sin terminar» a secas se leía como «falló», y la reacción a eso es volver
    a desplegar encima de un despliegue en curso.
    """
    fuente = (RAIZ / "scripts" / "deploy_remote.py").read_text(encoding="utf-8")
    assert "SIGUE CORRIENDO" in fuente
    assert "get-command-invocation" in fuente
