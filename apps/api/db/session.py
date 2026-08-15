"""Motor y sesiones de base de datos.

`expire_on_commit=False` no es cosmético: sin él, tocar un atributo después del
commit dispara una recarga perezosa, y en código asíncrono eso revienta con un
`MissingGreenlet` a mitad de una conversación de voz. Es un fallo que sólo
aparece bajo carga, así que se desactiva desde el principio.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from apps.api.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """Dependencia de FastAPI: una sesión por petición."""
    async with get_sessionmaker()() as sesion:
        yield sesion
