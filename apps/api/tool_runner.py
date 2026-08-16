"""Ejecuta lo que el modelo pide y le devuelve el resultado.

Es la pieza que faltaba para cerrar el bucle: el modelo pedía una herramienta,
el puente lo traducía a un evento, y ahí se acababa. Nadie ejecutaba nada y
nadie contestaba, así que el coach se quedaba esperando una respuesta que no
llegaba nunca.

## El `user_id` no se acepta, se impone

El modelo manda un `user_id` en los argumentos porque el esquema se lo pide, y
**se descarta**. El que vale es el de la sesión, que salió del WebSocket. Un
modelo al que se le puede convencer de cambiar de identificador es un modelo al
que se le puede pedir el plan de otra persona, y eso no se arregla con una
instrucción en el prompt: se arregla no usando ese valor.

## Un fallo no tumba la conversación

Si una herramienta revienta, se le devuelve al modelo un `ok: false` con el
motivo en vez de dejar caer la excepción. La alternativa —cerrar el WebSocket—
convierte un error de una consulta en el fin de la conversación, con el corredor
a media frase.

Lo que **no** se hace es inventarle una respuesta plausible. Si `get_today_session`
falla, el modelo recibe que falló, y lo peor que puede pasar es que diga que no
puede consultarlo ahora. Devolverle un valor por defecto sería exactamente la
cifra inventada que todo el sistema existe para evitar.
"""

from __future__ import annotations

import time
from datetime import date
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from apps.api.metrics import safety_gate_triggers, tool_call_ms
from apps.api.tool_specs import TOOL_NAMES
from apps.api.tools import CoachTools

log = structlog.get_logger(__name__)


class ToolRunner:
    """Ejecuta herramientas para una sesión concreta.

    Cada llamada abre su propia sesión de base de datos y hace commit. Es a
    propósito: una conversación de voz dura minutos, y sostener una transacción
    abierta todo ese rato bloquearía filas mientras el corredor piensa qué decir.
    """

    def __init__(
        self,
        sessionmaker: async_sessionmaker[Any],
        *,
        user_id: str,
        today: date | None = None,
    ) -> None:
        self._sessionmaker = sessionmaker
        self._user_id = user_id
        self._today = today

    async def run(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        if name not in TOOL_NAMES:
            # Pasa si el modelo alucina un nombre. Se le dice cuáles hay en vez
            # de callar: con la lista delante suele corregirse en el mismo turno.
            log.warning("tool.desconocida", name=name)
            return {
                "ok": False,
                "error": f"no existe la herramienta «{name}»",
                "available": list(TOOL_NAMES),
            }

        argumentos = dict(arguments)
        # Se impone, no se acepta. Ver la cabecera del módulo.
        argumentos.pop("user_id", None)

        inicio = time.monotonic()
        try:
            async with self._sessionmaker() as sesion:
                herramientas = CoachTools(sesion, today=self._today)
                metodo = getattr(herramientas, name)
                resultado = (
                    await metodo(self._user_id, **argumentos)
                    if _lleva_user_id(name)
                    else await metodo(**argumentos)
                )
                await sesion.commit()
        except TypeError as exc:
            # Argumentos que no encajan con la firma: es el modelo inventando un
            # parámetro. Se le dice, y sigue la conversación.
            log.warning("tool.argumentos_invalidos", name=name, error=str(exc))
            return {"ok": False, "error": f"argumentos inválidos para «{name}»: {exc}"}
        except Exception as exc:
            log.error("tool.falló", name=name, error=str(exc))
            return {"ok": False, "error": f"la herramienta «{name}» falló: {exc}"}
        finally:
            tool_call_ms.labels(tool=name).observe((time.monotonic() - inicio) * 1000)

        _contar_puerta(resultado)
        log.info("tool.ok", name=name)
        return resultado


def _lleva_user_id(name: str) -> bool:
    """`explain_technique_cue` y `environment_check` no son de nadie en concreto."""
    return name not in {"explain_technique_cue", "environment_check"}


def _contar_puerta(resultado: Any) -> None:
    if isinstance(resultado, dict):
        nivel = resultado.get("safety_level")
        if isinstance(nivel, str):
            safety_gate_triggers.labels(level=nivel).inc()
