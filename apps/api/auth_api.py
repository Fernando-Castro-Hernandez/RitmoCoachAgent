"""Registro, entrada, y quién soy.

Tres rutas. La forma de la respuesta es la misma en registro y en login —token
más usuario— para que el frontend tenga un solo camino después de cualquiera de
los dos.

`onboarded` es lo que decide a dónde va el frontend al entrar. Sale de si el
carrusel está completo, no de una bandera en `localStorage`: si viviera en el
navegador, entrar desde otro teléfono repetiría el onboarding de alguien que ya
lo hizo.
"""

from __future__ import annotations

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.auth import (
    UsuarioActual,
    autenticar,
    buscar_por_email,
    crear_token,
    hash_password,
    normalizar_email,
    nuevo_user_id,
    validar_password,
)
from apps.api.db.models import UserRow
from apps.api.db.repo import ProfileRepo
from apps.api.db.session import get_session
from apps.api.onboarding import can_finish_carousel

log = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/auth", tags=["cuentas"])

Sesion = Annotated[AsyncSession, Depends(get_session)]


class Credenciales(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=1)


async def _respuesta(sesion: AsyncSession, usuario: UserRow) -> dict[str, Any]:
    contexto = await ProfileRepo(sesion).context(usuario.id)
    return {
        "token": crear_token(usuario.id, usuario.email),
        "user": {"id": usuario.id, "email": usuario.email},
        # Decide la pantalla de destino. Vive en el servidor a propósito: en el
        # navegador, entrar desde otro teléfono repetiría el carrusel.
        "onboarded": can_finish_carousel(contexto),
    }


@router.post("/register", status_code=201)
async def registrar(cuerpo: Credenciales, sesion: Sesion) -> dict[str, Any]:
    """Crea la cuenta y devuelve el token ya listo.

    No se pide confirmar el correo ni entrar otra vez: quien acaba de escribir
    su contraseña ya demostró lo que hay que demostrar, y mandarlo a una
    pantalla de login después de registrarse es fricción sin ninguna seguridad
    a cambio.
    """
    validar_password(cuerpo.password)
    email = normalizar_email(cuerpo.email)

    if await buscar_por_email(sesion, email) is not None:
        # Aquí sí se dice que existe: en el registro es inevitable —el correo o
        # se puede usar o no— y ocultarlo sólo produce cuentas que nadie
        # entiende por qué no se crean. El login, que es donde se prueban
        # contraseñas, sigue sin distinguir.
        raise HTTPException(409, "ya hay una cuenta con ese correo")

    usuario = UserRow(
        id=nuevo_user_id(),
        email=email,
        hashed_password=hash_password(cuerpo.password),
    )
    sesion.add(usuario)
    await sesion.commit()

    log.info("auth.registro", user_id=usuario.id)
    return await _respuesta(sesion, usuario)


@router.post("/login")
async def entrar(cuerpo: Credenciales, sesion: Sesion) -> dict[str, Any]:
    usuario = await autenticar(sesion, cuerpo.email, cuerpo.password)
    log.info("auth.login", user_id=usuario.id)
    return await _respuesta(sesion, usuario)


@router.get("/me")
async def yo(usuario: UsuarioActual, sesion: Sesion) -> dict[str, Any]:
    """Para que el frontend confirme al arrancar que el token guardado sigue
    valiendo, en vez de descubrirlo al fallar la primera petición de verdad."""
    contexto = await ProfileRepo(sesion).context(usuario.id)
    return {
        "user": {"id": usuario.id, "email": usuario.email},
        "onboarded": can_finish_carousel(contexto),
    }
