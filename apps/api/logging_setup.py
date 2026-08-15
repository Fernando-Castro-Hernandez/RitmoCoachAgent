"""Configuración de structlog.

Sin esto las llamadas a `log.info(...)` no salen a ningún lado, y un sistema de
voz en streaming es prácticamente imposible de depurar a ciegas: cuando algo
llega tarde o el coach dice algo raro, sin trazas no hay forma de saber si fue la
red, el modelo, una herramienta lenta o el prompt (ADR 0012).

En desarrollo la salida es coloreada y legible; en producción, JSON de una línea
por evento, que es lo que un agregador de logs sabe consumir.
"""

from __future__ import annotations

import logging
import os
import sys

import structlog


def configure_logging() -> None:
    nivel = os.getenv("LOG_LEVEL", "INFO").upper()
    en_produccion = os.getenv("ENV", "dev").lower() in {"prod", "production"}

    # `force=True` no es opcional: uvicorn ya instaló sus handlers en el logger
    # raíz antes de que corra el lifespan, y sin esto basicConfig es un no-op
    # silencioso. Síntoma: ni una línea de traza y horas depurando a ciegas.
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, nivel, logging.INFO),
        force=True,
    )

    procesadores: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="%H:%M:%S" if not en_produccion else "iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    procesadores.append(
        structlog.processors.JSONRenderer()
        if en_produccion
        else structlog.dev.ConsoleRenderer(colors=False)
    )

    structlog.configure(
        processors=procesadores,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(logging, nivel, logging.INFO)),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
