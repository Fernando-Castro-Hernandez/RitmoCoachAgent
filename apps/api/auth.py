"""Cuentas: contraseñas, tokens y de quién es cada petición.

Esto sustituye al UUID del navegador. El cambio de fondo no es «ahora hay
login»: es que **`user_id` deja de ser un dato que manda el cliente**. Antes
cualquiera podía pedir `/api/profile/<lo-que-sea>` y el backend contestaba; ese
agujero se cierra aquí, y por eso el cambio toca todas las rutas.

## Contraseñas

bcrypt, con la sal dentro del hash y coste por defecto de la librería. No se
guarda la contraseña en ningún sitio ni se registra en ningún log. El límite de
72 bytes de bcrypt se comprueba y se rechaza con un mensaje claro en vez de
truncarse en silencio — truncar convierte dos contraseñas distintas en la misma.

**Registrar y entrar tardan lo mismo a propósito.** Si «este correo no existe»
respondiera al instante y «contraseña incorrecta» tardara lo que tarda bcrypt,
el tiempo de respuesta diría qué correos están dados de alta. Por eso el login
verifica contra un hash de descarte cuando el correo no existe, y por eso los
dos errores dicen exactamente lo mismo.

## Tokens

JWT firmado con HS256, siete días de vida. Siete y no un año: el token viaja en
la URL del WebSocket (los navegadores no dejan poner cabeceras al abrirlo), así
que acaba en los logs del proxy. Que caduque es lo que acota esa fuga.

El secreto sale de `JWT_SECRET`. **Sin él configurado, la API no arranca en
producción**: un secreto por defecto significa que cualquiera que lea el
repositorio puede firmarse un token de cualquier usuario. En desarrollo se
genera uno al vuelo, con la consecuencia visible de que reiniciar el servidor
invalida las sesiones — mejor eso que un secreto compartido.
"""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

import bcrypt
import jwt
import structlog
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.db.models import UserRow
from apps.api.db.session import get_session

log = structlog.get_logger(__name__)

ALGORITMO = "HS256"
VIDA_DEL_TOKEN = timedelta(days=7)

# bcrypt trunca en silencio a partir de 72 bytes. Se rechaza antes.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LEN = 8

# Un hash real contra el que verificar cuando el correo no existe, para que el
# login tarde lo mismo exista o no. Se calcula una vez al importar.
_HASH_DE_DESCARTE = bcrypt.hashpw(b"contrasena-que-no-es-de-nadie", bcrypt.gensalt()).decode()

_CREDENCIALES_MALAS = "correo o contraseña incorrectos"


class AuthError(HTTPException):
    def __init__(self, detalle: str, codigo: int = status.HTTP_401_UNAUTHORIZED) -> None:
        super().__init__(codigo, detalle, headers={"WWW-Authenticate": "Bearer"})


def _secreto() -> str:
    secreto = os.getenv("JWT_SECRET", "")
    if secreto:
        return secreto
    # Sin secreto no se cae en uno por defecto: se genera uno de proceso. La
    # consecuencia —reiniciar invalida las sesiones— es molesta y visible, que
    # es justo lo contrario de un secreto conocido por todo el que lea el repo.
    global _SECRETO_DE_PROCESO
    if not _SECRETO_DE_PROCESO:
        _SECRETO_DE_PROCESO = secrets.token_urlsafe(48)
        log.warning("auth.sin_jwt_secret", nota="token efímero; configura JWT_SECRET")
    return _SECRETO_DE_PROCESO


_SECRETO_DE_PROCESO = ""


# ── contraseñas ──────────────────────────────────────────────────────


def normalizar_email(email: str) -> str:
    return email.strip().lower()


def validar_password(password: str) -> None:
    """Lanza si la contraseña no sirve. Se comprueba antes de hashear."""
    if len(password) < MIN_PASSWORD_LEN:
        raise HTTPException(422, f"la contraseña necesita al menos {MIN_PASSWORD_LEN} caracteres")
    if len(password.encode()) > MAX_PASSWORD_BYTES:
        # Truncar convertiría dos contraseñas distintas en la misma.
        raise HTTPException(422, "la contraseña es demasiado larga")


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verificar_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        # Un hash corrupto en la base no puede tumbar el login de todos.
        log.error("auth.hash_invalido")
        return False


# ── tokens ───────────────────────────────────────────────────────────


def crear_token(user_id: str, email: str) -> str:
    ahora = datetime.now(UTC)
    carga = {
        "sub": user_id,
        "email": email,
        "iat": int(ahora.timestamp()),
        "exp": int((ahora + VIDA_DEL_TOKEN).timestamp()),
    }
    return jwt.encode(carga, _secreto(), algorithm=ALGORITMO)


def leer_token(token: str) -> dict[str, Any]:
    """Devuelve la carga, o lanza 401. Nunca devuelve una carga sin verificar."""
    try:
        # `algorithms` explícito y en lista blanca: aceptar el algoritmo que
        # venga en la cabecera es como se firma un token con «none».
        return jwt.decode(token, _secreto(), algorithms=[ALGORITMO])
    except jwt.ExpiredSignatureError as e:
        raise AuthError("la sesión venció, vuelve a entrar") from e
    except jwt.InvalidTokenError as e:
        raise AuthError("sesión inválida") from e


def nuevo_user_id() -> str:
    return str(uuid.uuid4())


# ── de quién es esta petición ────────────────────────────────────────


def _token_de(peticion: Request) -> str:
    cabecera = peticion.headers.get("authorization", "")
    if cabecera.lower().startswith("bearer "):
        return cabecera[7:].strip()
    raise AuthError("falta el token")


async def usuario_actual(
    peticion: Request,
    sesion: Annotated[AsyncSession, Depends(get_session)],
) -> UserRow:
    """La cuenta dueña de esta petición. **Es la única fuente de `user_id`.**

    Se comprueba que la fila siga existiendo y no sólo que el token sea válido:
    un token de siete días sigue verificando después de que alguien borre la
    cuenta, y entonces las peticiones escribirían filas huérfanas.
    """
    carga = leer_token(_token_de(peticion))
    usuario = await sesion.get(UserRow, carga.get("sub", ""))
    if usuario is None:
        raise AuthError("la cuenta de esta sesión ya no existe")
    return usuario


UsuarioActual = Annotated[UserRow, Depends(usuario_actual)]


async def usuario_de_token(sesion: AsyncSession, token: str) -> UserRow | None:
    """Para el WebSocket, donde no hay cabeceras que valgan.

    Devuelve `None` en vez de lanzar: quien llama tiene que cerrar el socket con
    su propio código, no dejar que una excepción HTTP se escape por ahí.
    """
    try:
        carga = leer_token(token)
    except HTTPException:
        return None
    return await sesion.get(UserRow, carga.get("sub", ""))


async def buscar_por_email(sesion: AsyncSession, email: str) -> UserRow | None:
    consulta = select(UserRow).where(UserRow.email == normalizar_email(email))
    return (await sesion.execute(consulta)).scalars().first()


async def autenticar(sesion: AsyncSession, email: str, password: str) -> UserRow:
    """Comprueba las credenciales. Tarda lo mismo exista el correo o no."""
    usuario = await buscar_por_email(sesion, email)
    hash_a_comprobar = usuario.hashed_password if usuario else _HASH_DE_DESCARTE

    if not verificar_password(password, hash_a_comprobar) or usuario is None:
        # Mismo mensaje para «no existe» y «contraseña mala»: distinguirlos
        # convierte el login en un buscador de correos registrados.
        log.info("auth.login_fallido")
        raise AuthError(_CREDENCIALES_MALAS)

    return usuario
