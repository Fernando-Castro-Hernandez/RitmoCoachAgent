"""Lo que la imagen de la API tiene que llevar dentro.

Estas pruebas leen el `Dockerfile`, no construyen nada. No sustituyen a un
despliegue —la única forma de saber que una imagen funciona es correrla— pero
cazan en un segundo la clase de fallo que cuesta un ciclo entero de
construcción en un ARM pequeño: un archivo que la aplicación necesita y que
nadie copió.

Lo escribo porque me pasó. `alembic.ini` vive en la raíz del repositorio y no
estaba entre los `COPY`, así que el servicio de migraciones murió con 255 y un
mensaje —«No 'script_location' key found»— que no dice que falte un archivo.
Descubrirlo costó construir la imagen, subirla y verla morir.
"""

from __future__ import annotations

from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[3]
DOCKERFILE = (RAIZ / "infra" / "Dockerfile.api").read_text(encoding="utf-8")


@pytest.mark.parametrize(
    ("archivo", "porque"),
    [
        ("alembic.ini", "sin él, `alembic upgrade head` no encuentra las migraciones"),
        ("uv.lock", "sin él, `uv sync` resuelve de cero y la imagen puede no ser la probada"),
        ("pyproject.toml", "es el manifiesto"),
    ],
)
def test_la_imagen_copia_lo_que_hace_falta(archivo: str, porque: str) -> None:
    assert archivo in DOCKERFILE, f"falta COPY de «{archivo}»: {porque}"


def test_las_migraciones_viajan_en_la_imagen() -> None:
    """El directorio de versiones, no sólo el `.ini`."""
    assert "apps/api/" in DOCKERFILE
    assert (RAIZ / "apps" / "api" / "alembic" / "versions").is_dir()


def test_el_arranque_no_pasa_por_uv_run() -> None:
    """`uv run` re-sincroniza el entorno EN CADA ARRANQUE, con el grupo de
    desarrollo incluido.

    El contenedor se descargaba mypy, ruff, hypothesis y pillow cada vez que
    arrancaba. Además de lento, hace que lo que corre dependa de cuándo arrancó
    en vez de de cuándo se construyó — que es justo lo que una imagen existe
    para evitar.
    """
    linea_cmd = next(ln for ln in DOCKERFILE.splitlines() if ln.startswith("CMD"))
    # Se busca el ejecutable `uv`, no la subcadena: «uvicorn» empieza por «uv» y
    # una comprobación ingenua marcaba en rojo el arranque correcto. Lo pillé
    # con mi propia prueba fallando contra el Dockerfile ya arreglado.
    assert '"uv"' not in linea_cmd, f"el CMD vuelve a sincronizar: {linea_cmd}"
    assert "uv run" not in linea_cmd, f"el CMD vuelve a sincronizar: {linea_cmd}"
    assert "uvicorn" in linea_cmd


def test_las_dependencias_se_instalan_sin_el_grupo_de_desarrollo() -> None:
    """mypy y ruff no pintan nada en un servidor, y son 25 MB."""
    assert "--no-dev" in DOCKERFILE
    assert "--frozen" in DOCKERFILE, "sin --frozen, uv ignora el lockfile y resuelve de nuevo"


def test_el_compose_de_produccion_no_monta_credenciales_locales() -> None:
    """`~/.aws` sólo existe en el portátil. En el servidor manda el rol.

    Un volumen que apunta a un directorio inexistente no falla: Docker lo crea
    vacío. El error aparecería después como «no encuentro credenciales» en una
    máquina que sí las tiene.
    """

    def montajes(texto: str) -> str:
        # Sólo las líneas de volumen. El encabezado del archivo EXPLICA por qué
        # `~/.aws` no está aquí, y buscar la cadena a secas encontraba el
        # comentario que documenta la decisión — otro falso positivo mío.
        return "\n".join(
            ln for ln in texto.splitlines() if ln.strip().startswith("-") and ":" in ln
        )

    assert ".aws" not in montajes((RAIZ / "docker-compose.yml").read_text(encoding="utf-8"))
    assert ".aws" in montajes((RAIZ / "docker-compose.override.yml").read_text(encoding="utf-8"))
