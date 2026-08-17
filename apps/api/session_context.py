"""Arma el prompt de una sesión con lo que ya se sabe del corredor.

`prompts.build_system_prompt` acepta cuatro capas —persona, clarificación,
contexto y seguridad— y **los dos sitios que abrían una sesión lo llamaban sin
argumentos**. El coach salía a hablar sin el perfil, sin la semana, sin el
veredicto de la puerta y sin memoria de la conversación anterior. Las cuatro
capas existían y sólo se usaban dos.

Se notaba de una forma concreta y confusa: el coach preguntaba cosas que ya
estaban en el perfil. Justo lo que el propio prompt le prohíbe —«nunca preguntas
por algo que ya está en el perfil»— y no era desobediencia: no lo tenía.

Este módulo existe para que eso no vuelva a divergir. Los tres sitios que abren
una sesión —el WebSocket, la suite en vivo y la sonda— llaman aquí, así que
añadir una capa se hace una vez.

## Por qué el veredicto va en el prompt si ya está en las herramientas

Redundancia a propósito (ADR 0013). La puerta ya bloquea las herramientas de
prescripción en rojo, así que el modelo *no puede* prescribir aunque quiera.
Ponerlo también en el prompt cambia el **tono**: sin ello el coach intenta
prescribir, se topa con una herramienta que se niega, y contesta algo confuso.
Con ello sabe desde la primera palabra que hoy toca escuchar y derivar.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.repo import LogRepo, MemoryRepo, ProfileRepo
from apps.api.prompts import build_system_prompt
from apps.api.tools import CoachTools

log = structlog.get_logger(__name__)

# Cuántos turnos de la conversación anterior se le recuerdan. Seis son tres
# intercambios: bastante para retomar, poco para que el arranque de cada sesión
# pague el coste de un historial entero.
TURNOS_RECORDADOS = 6


async def build_prompt_for(sesion: AsyncSession, user_id: str, *, today: date | None = None) -> str:
    """El prompt completo de este corredor, en este momento.

    Ningún fallo de lectura deja al coach sin voz: si algo no se puede consultar
    se sigue con las capas que sí se consiguieron. Un coach con menos contexto
    conversa peor; un coach que no arranca no conversa.
    """
    hoy = today or date.today()

    perfil = await _seguro(ProfileRepo(sesion).context(user_id), "perfil")
    veredicto = await _seguro(LogRepo(sesion).current_safety(user_id, hoy), "seguridad")
    turnos = await _seguro(MemoryRepo(sesion).recent(user_id, limit=TURNOS_RECORDADOS), "memoria")

    # La semana sólo se consulta si hay perfil: sin él no hay plan del que
    # hablar, y la herramienta devolvería un error que no aporta nada al prompt.
    semana: dict[str, Any] | None = None
    if perfil:
        semana = await _seguro(CoachTools(sesion, today=hoy).get_week_context(user_id), "semana")
        if semana is not None and semana.get("ok") is False:
            semana = None

    return build_system_prompt(
        profile=perfil,
        week_context=semana,
        safety=veredicto,
        recent_turns=[(t.role, t.text) for t in turnos or []],
    )


async def _seguro(esperable: Any, que: str) -> Any:
    try:
        return await esperable
    except Exception as exc:
        log.warning("prompt.capa_no_disponible", capa=que, error=str(exc))
        return None
