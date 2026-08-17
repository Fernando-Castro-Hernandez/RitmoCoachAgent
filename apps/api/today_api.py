"""Lo que la hoja necesita para dejar de ser una muestra.

Hasta aquí la pantalla principal pintaba datos de ejemplo con el sello MUESTRA,
porque no había de dónde sacar los de verdad: el plan vivía en la base y la
única forma de llegar a él era hablando. Esto lo expone.

## Una petición, no tres

Devuelve la semana, la sesión de hoy y el veredicto de la puerta juntos. No es
por ahorrar viajes: es porque **los tres tienen que ser del mismo instante**.
Con tres peticiones sueltas, un reporte de dolor entre la primera y la tercera
deja la pantalla enseñando la sesión completa con el semáforo ya en ámbar — que
es exactamente la incoherencia que este producto no se puede permitir.

## El recorte de ámbar ya viene aplicado

La distancia que sale de aquí es la que el motor decidió, recortada si hay
molestia. La pantalla no multiplica nada ni conoce la regla: sólo pinta. Si el
recorte viviera en el frontend habría dos sitios donde cambiarlo y uno se
quedaría atrás.

## En rojo no se manda la sesión

No se manda recortada ni «por si acaso»: **no se manda**. La regla del producto
es que en rojo la pantalla no prescribe, y la forma de garantizarla es que el
dato no llegue al navegador. Una pantalla no puede enseñar lo que no tiene.
"""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import UsuarioActual
from apps.api.db.repo import LogRepo, StateRepo
from apps.api.db.session import get_session
from apps.api.tools import CoachTools

router = APIRouter(prefix="/api", tags=["hoja"])

Sesion = Annotated[AsyncSession, Depends(get_session)]

# Del nivel de la puerta al vocabulario de la hoja. La interfaz no habla de
# «red» y «amber»: habla de tinta de alarma y de precaución.
_SEMAFORO = {"green": "clear", "amber": "caution", "red": "flag"}


@router.get("/today")
async def hoja_de_hoy(sesion: Sesion, usuario: UsuarioActual) -> dict[str, Any]:
    """El estado completo de la hoja, en un solo instante."""
    hoy = date.today()
    herramientas = CoachTools(sesion, today=hoy)

    veredicto = await LogRepo(sesion).current_safety(usuario.id, hoy)
    semana = await herramientas.get_week_context(usuario.id)
    plan = await StateRepo(sesion).get(usuario.id)

    respuesta: dict[str, Any] = {
        "safety": _SEMAFORO.get(veredicto.level.value, "clear"),
        "safety_reason": veredicto.reason,
        "referral": veredicto.referral_message,
        "has_plan": bool(semana.get("ok")),
        "week": None,
        "session": None,
        "rest_day": False,
    }

    if not semana.get("ok"):
        # Sin plan todavía. La hoja lo sabe y enseña el estado de «aún no hay
        # nada que prescribir» en vez de inventarse una semana.
        return respuesta

    respuesta["week"] = {
        "week": semana["week_index"],
        "totalWeeks": semana["total_weeks"],
        "phase": semana["phase"],
        "race": _nombre_de_carrera(semana["distance"]),
        "daysLeft": _dias_hasta(semana.get("race_date"), hoy),
    }

    if not veredicto.allows_prescription:
        # Rojo: la sesión no viaja. Ver la cabecera del módulo.
        return respuesta

    hoy_toca = await herramientas.get_today_session(usuario.id)
    if hoy_toca.get("rest_day"):
        respuesta["rest_day"] = True
        return respuesta
    if not hoy_toca.get("ok"):
        return respuesta

    respuesta["session"] = {
        "kind": hoy_toca["kind"],
        "distanceKm": hoy_toca["distance_km"],
        "pace": hoy_toca.get("pace"),
        "effort": hoy_toca.get("effort", ""),
        "zone": hoy_toca.get("zone", 2),
        "durationLabel": _duracion(hoy_toca["distance_km"], hoy_toca.get("pace"), plan),
        "why": hoy_toca.get("why", ""),
    }
    return respuesta


def _nombre_de_carrera(distancia: str) -> str:
    return {"5k": "5K", "10k": "10K", "21k": "Medio maratón", "42k": "Maratón"}.get(
        distancia, distancia
    )


def _dias_hasta(iso: str | None, hoy: date) -> int | None:
    if not iso:
        return None
    return max(0, (date.fromisoformat(iso) - hoy).days)


def _duracion(km: float, ritmo: str | None, plan: Any) -> str:
    """Una estimación honesta del tiempo en pie, a partir del ritmo objetivo.

    Se calcula del rango que dio el motor, no de un número inventado: si no hay
    ritmo objetivo —una sesión de intervalos, por ejemplo— se devuelve vacío en
    vez de estimar. Es preferible un hueco a una cifra que nadie calculó.
    """
    if not ritmo:
        return ""
    try:
        lento = ritmo.split("–")[-1]
        minutos, segundos = (int(x) for x in lento.split(":"))
    except (ValueError, IndexError):
        return ""

    total = int(km * (minutos * 60 + segundos))
    h, m = divmod(total // 60, 60)
    return f"{h} h {m} min" if h else f"{m} min"
