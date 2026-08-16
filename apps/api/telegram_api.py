"""La superficie HTTP de la vinculación con Telegram.

Tres endpoints y una regla que los separa en dos mundos:

- `/api/telegram/link/{user_id}` y `/api/telegram/status/{user_id}` los llama la
  interfaz. Son del corredor.
- `/api/telegram/webhook` lo llama Telegram. **Es público**, escribe
  vinculaciones, y por eso es el único sitio de la API que valida un secreto
  compartido antes de mirar el cuerpo.

Sobre el webhook, dos decisiones que no son cosméticas:

**Sin secreto configurado, cierra.** Si `TELEGRAM_WEBHOOK_SECRET` está vacío, el
endpoint responde 503 en lugar de aceptar a cualquiera. Un endpoint público que
vincula chats no puede caer abierto por una variable que se olvidó de poner: el
fallo hay que verlo al configurarlo, no cuando alguien lo encuentre.

**Siempre 200 a Telegram.** Un token malo no es un error del servidor: es un
enlace viejo. Si respondiéramos 4xx, Telegram reintentaría el mismo `update` y
acabaría desactivando el webhook. El corredor se entera por el mensaje que
recibe, que es donde está mirando.
"""

from __future__ import annotations

import hmac
from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from apps.api.db.session import get_session
from apps.api.telegram import (
    InvalidLinkTokenError,
    bind,
    chat_id_for,
    deep_link,
    issue_link_token,
    parse_start_command,
    send_message,
)

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["telegram"])

Sesion = Annotated[AsyncSession, Depends(get_session)]

VINCULADO = (
    "Listo. Soy Ritmo y te escribo por aquí.\n\n"
    "Te voy a mandar la sesión del día por la mañana y un check-in después de "
    "que corras. Si algo te duele, dímelo — aquí o hablando."
)

ENLACE_INVALIDO = (
    "Ese enlace ya no sirve: los de vinculación duran quince minutos y se usan "
    "una sola vez. Pide uno nuevo desde la aplicación y lo intentamos otra vez."
)


@router.post("/link/{user_id}")
async def crear_enlace(user_id: str, sesion: Sesion) -> dict[str, Any]:
    """Emite el enlace profundo de vinculación.

    Devuelve `deep_link: null` cuando no hay bot configurado, para que la
    pantalla pueda decir «Telegram no está disponible» en vez de ofrecer un
    enlace roto.
    """
    token = await issue_link_token(sesion, user_id)
    enlace = deep_link(token)
    return {
        "deep_link": enlace,
        "expires_in_s": 900,
        "configured": enlace is not None,
    }


@router.get("/status/{user_id}")
async def estado(user_id: str, sesion: Sesion) -> dict[str, Any]:
    """Si este corredor recibe avisos por Telegram.

    No devuelve el `chat_id`. La pantalla sólo necesita saber si está vinculado
    o no, y un identificador que no se usa es un identificador que se filtra.
    """
    return {
        "linked": await chat_id_for(sesion, user_id) is not None,
        "bot_configured": bool(get_settings().telegram_bot_username),
    }


@router.post("/webhook")
async def webhook(
    peticion: Request,
    sesion: Sesion,
    x_telegram_bot_api_secret_token: Annotated[str | None, Header()] = None,
) -> dict[str, Any]:
    """Recibe los `update` de Telegram. Sólo actúa sobre `/start <token>`."""
    esperado = get_settings().telegram_webhook_secret
    if not esperado:
        log.error("telegram.webhook.sin_secreto")
        raise HTTPException(503, "el webhook de telegram no está configurado")

    # Comparación en tiempo constante: el secreto llega en cada petición de un
    # endpoint público, y eso es justo lo que hace medible un `==`.
    if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", esperado):
        log.warning("telegram.webhook.secreto_invalido")
        raise HTTPException(403, "secreto inválido")

    cuerpo = await peticion.json()
    mensaje = (cuerpo or {}).get("message") or {}
    chat_id = (mensaje.get("chat") or {}).get("id")
    token = parse_start_command(mensaje.get("text"))

    if chat_id is None or token is None:
        # Cualquier otro mensaje se ignora en silencio. Este bot no conversa:
        # la conversación es por voz, y contestar aquí invitaría a usar el texto
        # de un desconocido como entrada del modelo.
        return {"ok": True, "handled": False}

    try:
        user_id = await bind(sesion, token, int(chat_id))
    except InvalidLinkTokenError:
        await send_message(int(chat_id), ENLACE_INVALIDO)
        # 200 a propósito: ver la cabecera del módulo.
        return {"ok": True, "handled": False, "reason": "invalid_token"}

    await send_message(int(chat_id), VINCULADO)
    log.info("telegram.webhook.vinculado", user_id=user_id)
    return {"ok": True, "handled": True}
