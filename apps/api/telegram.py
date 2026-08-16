"""Vinculación de la cuenta con un chat de Telegram.

Telegram es el canal de salida del coach proactivo: el recordatorio de la mañana,
el check-in después de la sesión, el aviso de racha en riesgo y —el que importa—
el escalamiento de ámbar a rojo cuando el dolor lleva tres días. Los flujos de
n8n (tarea E2) necesitan un `chat_id`, y este módulo es el único sitio donde ese
`chat_id` se puede llegar a escribir.

**Por qué Telegram y no WhatsApp:** la API de negocio de Meta exige verificación
de empresa, y el reto dura un fin de semana. Telegram da un bot en dos minutos y
el canal es intercambiable — lo que se guarda es «a dónde escribirle a este
corredor», no «Telegram».

## El enlace profundo y su riesgo

Vincular se hace con `t.me/<bot>?start=<token>`. Es cómodo porque el corredor
toca un enlace y ya, pero significa que **el secreto viaja en una URL**: queda en
el historial del navegador, se pega en un chat, se manda por captura. El modelo
de amenaza es que otra persona lo vea antes que el dueño.

Tres cosas lo acotan, y las tres están probadas:

1. **Un solo uso.** El primer `bind` marca `used_at`; el segundo falla. Un token
   filtrado después de usarse ya no vale nada.
2. **Quince minutos.** Se emite en el momento de tocar «vincular», no antes.
3. **Se marca antes de escribir.** El `UPDATE` condicional (`WHERE used_at IS
   NULL`) es lo que decide, así que dos peticiones simultáneas con el mismo
   token no pueden ganar las dos — la base de datos arbitra, no el proceso.

## Lo que llega de Telegram es dato

`parse_start_command` lee **sólo** el argumento de `/start` y descarta el resto
del mensaje. Un `update` de Telegram es entrada de un desconocido: nadie
autenticó a quien escribe, y el texto puede contener lo que sea, incluidas
instrucciones dirigidas al modelo. Aquí nunca se pasa a un prompt.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.config import get_settings
from apps.api.db.models import TelegramLinkRow

log = structlog.get_logger(__name__)

# Vida del token de vinculación. Corto a propósito: se emite cuando el corredor
# toca el botón y se gasta en el mismo minuto. Si caduca, pedir otro cuesta un
# toque; si dura horas, una URL filtrada sigue viva.
LINK_TOKEN_TTL = timedelta(minutes=15)

TELEGRAM_API = "https://api.telegram.org"
TELEGRAM_LINK_BASE = "https://t.me"


class InvalidLinkTokenError(Exception):
    """El token no existe, ya se usó o caducó.

    Es un solo error para los tres casos **a propósito**: distinguirlos en la
    respuesta le diría a quien prueba tokens cuáles existen.
    """


def make_link_token() -> str:
    """Token opaco, de `secrets`.

    No deriva del `user_id` ni de un contador: un token derivable convierte el
    enlace profundo en «apunta a cualquier corredor».
    """
    return secrets.token_urlsafe(32)


def deep_link(token: str, bot_username: str | None = None) -> str | None:
    """El enlace que abre el bot con el token puesto.

    Devuelve `None` si no hay bot configurado, en vez de una URL sin usuario:
    `https://t.me/?start=…` parece un enlace y no lleva a ninguna parte, y ese
    fallo aparecería en la mano del corredor y no en el log.
    """
    usuario = bot_username if bot_username is not None else get_settings().telegram_bot_username
    usuario = usuario.lstrip("@").strip()
    if not usuario:
        return None
    return f"{TELEGRAM_LINK_BASE}/{usuario}?start={token}"


async def issue_link_token(sesion: AsyncSession, user_id: str) -> str:
    """Emite un token nuevo. No toca el vínculo vigente.

    Pedir un enlace y no usarlo es lo más normal del mundo —se abre la pantalla,
    se cierra— y no puede dejar mudo al corredor que ya tenía Telegram puesto.
    """
    ahora = datetime.now(UTC)
    token = make_link_token()
    sesion.add(
        TelegramLinkRow(
            token=token,
            user_id=user_id,
            chat_id=None,
            created_at=ahora,
            expires_at=ahora + LINK_TOKEN_TTL,
            used_at=None,
        )
    )
    await sesion.commit()
    log.info("telegram.token_emitido", user_id=user_id)
    return token


async def bind(sesion: AsyncSession, token: str, chat_id: int) -> str:
    """Consume el token y deja el chat vinculado. Devuelve el `user_id`.

    El `UPDATE ... WHERE used_at IS NULL` es la parte que importa: quien gane esa
    fila es quien vincula, y lo decide la base de datos. Comprobar en Python y
    escribir después deja una ventana en la que dos peticiones con el mismo token
    pasan las dos.
    """
    ahora = datetime.now(UTC)

    fila = await sesion.get(TelegramLinkRow, token)
    if fila is None or _vencido(fila, ahora):
        # Mismo error para «no existe» y «caducó»: ver `InvalidLinkTokenError`.
        log.warning("telegram.token_rechazado", motivo="inexistente_o_vencido")
        raise InvalidLinkTokenError("el enlace de vinculación no es válido o ya venció")

    resultado = await sesion.execute(
        update(TelegramLinkRow)
        .where(TelegramLinkRow.token == token, TelegramLinkRow.used_at.is_(None))
        .values(chat_id=chat_id, used_at=ahora)
    )
    if resultado.rowcount == 0:
        # Alguien —o el propio corredor dos veces— ya lo gastó. Nada se escribió.
        await sesion.rollback()
        log.warning("telegram.token_rechazado", motivo="ya_usado")
        raise InvalidLinkTokenError("el enlace de vinculación no es válido o ya venció")

    await sesion.commit()
    log.info("telegram.vinculado", user_id=fila.user_id)
    return fila.user_id


async def chat_id_for(sesion: AsyncSession, user_id: str) -> int | None:
    """A dónde escribirle. `None` si nunca vinculó.

    El más reciente gana: cambiar de teléfono es normal, y el recordatorio tiene
    que llegar al que trae encima.
    """
    consulta = (
        select(TelegramLinkRow.chat_id)
        .where(TelegramLinkRow.user_id == user_id, TelegramLinkRow.used_at.is_not(None))
        .order_by(TelegramLinkRow.used_at.desc())
        .limit(1)
    )
    return (await sesion.execute(consulta)).scalars().first()


async def user_id_for(sesion: AsyncSession, chat_id: int) -> str | None:
    """El camino inverso: quién es el que escribe desde este chat."""
    consulta = (
        select(TelegramLinkRow.user_id)
        .where(TelegramLinkRow.chat_id == chat_id, TelegramLinkRow.used_at.is_not(None))
        .order_by(TelegramLinkRow.used_at.desc())
        .limit(1)
    )
    return (await sesion.execute(consulta)).scalars().first()


def parse_start_command(texto: str | None) -> str | None:
    """El token de un `/start <token>`, o `None`.

    Se lee **sólo** el primer argumento. Todo lo demás del mensaje se descarta:
    es texto de un desconocido y no tiene por qué llegar a ningún prompt.
    """
    if not texto:
        return None
    partes = texto.strip().split()
    if not partes:
        return None
    # Telegram manda `/start@mi_bot` cuando el bot está en un grupo.
    comando = partes[0].split("@", 1)[0]
    if comando != "/start" or len(partes) < 2:
        return None
    return partes[1]


async def send_message(chat_id: int, text: str) -> bool:
    """Manda un mensaje. `False` si no hay bot configurado.

    No revienta sin token: el resto del producto funciona sin Telegram, y una
    excepción aquí tumbaría el webhook o un flujo de n8n por un canal que es un
    extra. El fallo queda en el log, que es donde se busca.
    """
    ajustes = get_settings()
    if not ajustes.telegram_bot_token:
        log.warning("telegram.sin_token", accion="send_message")
        return False

    import httpx

    async with httpx.AsyncClient(timeout=10.0) as cliente:
        respuesta = await cliente.post(
            f"{TELEGRAM_API}/bot{ajustes.telegram_bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
        )
    if respuesta.status_code != 200:
        log.warning("telegram.envio_falló", status=respuesta.status_code)
        return False
    return True


def _vencido(fila: TelegramLinkRow, ahora: datetime) -> bool:
    """SQLite devuelve fechas sin zona aunque la columna la declare.

    Producción corre sobre PostgreSQL, que sí la conserva. Normalizar aquí evita
    que la comparación reviente en la suite y sólo en la suite.
    """
    if fila.used_at is not None:
        return True
    limite = fila.expires_at
    if limite.tzinfo is None:
        limite = limite.replace(tzinfo=UTC)
    return limite <= ahora
