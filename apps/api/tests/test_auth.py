"""Cuentas.

Lo que se prueba no es «que se pueda entrar» —eso lo prueba usar la app— sino
las cuatro cosas que si se rompen no se nota hasta que es tarde:

1. **Sin token no se pasa.** Cada ruta del corredor, comprobada una por una. Es
   la clase de fallo que se cuela: se añade un endpoint, se olvida la
   dependencia, y queda abierto meses.
2. **Con MI token no se ven los datos de OTRO.** Ya no hay `user_id` en la URL,
   así que no hay dónde poner el ajeno — y eso también se comprueba.
3. **El login no dice qué correos existen.** Mismo mensaje y mismo trabajo de
   bcrypt exista o no la cuenta.
4. **La contraseña nunca sale.** Ni en la respuesta, ni el hash.
"""

from __future__ import annotations

from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.auth import (
    MIN_PASSWORD_LEN,
    crear_token,
    hash_password,
    normalizar_email,
    verificar_password,
)
from apps.api.db.models import Base
from apps.api.db.session import get_session
from apps.api.main import app

CORREO = "fernando@adivor.com"
CLAVE = "unaClaveLarga123"


@pytest_asyncio.fixture
async def cliente(monkeypatch: pytest.MonkeyPatch) -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)

    async def sesion_de_prueba() -> Any:
        async with fabrica() as s:
            yield s

    # Secreto fijo: si no, cada llamada a _secreto() genera uno de proceso y los
    # tokens de una prueba no valen en la siguiente.
    monkeypatch.setenv("JWT_SECRET", "secreto-de-prueba-suficientemente-largo")
    app.dependency_overrides[get_session] = sesion_de_prueba

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


def _registrar(cliente: Any, correo: str = CORREO, clave: str = CLAVE) -> dict[str, Any]:
    r = cliente.post("/api/auth/register", json={"email": correo, "password": clave})
    assert r.status_code == 201, r.text
    return r.json()


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# ── contraseñas ──────────────────────────────────────────────────────


def test_el_hash_no_se_parece_a_la_contrasena() -> None:
    h = hash_password(CLAVE)
    assert CLAVE not in h
    assert verificar_password(CLAVE, h)
    assert not verificar_password("otra cosa", h)


def test_dos_hashes_de_la_misma_clave_son_distintos() -> None:
    """La sal va dentro. Sin ella, dos personas con la misma contraseña tienen
    el mismo hash y una tabla arcoíris las rompe a las dos de golpe."""
    assert hash_password(CLAVE) != hash_password(CLAVE)


def test_el_correo_se_normaliza() -> None:
    """Si no, «Fernando@x.com» y «fernando@x.com» son dos cuentas y la persona
    jura que su contraseña dejó de funcionar."""
    assert normalizar_email("  Fernando@Adivor.COM ") == "fernando@adivor.com"


def test_una_contrasena_corta_se_rechaza(cliente: Any) -> None:
    r = cliente.post("/api/auth/register", json={"email": CORREO, "password": "corta"})
    assert r.status_code == 422
    assert str(MIN_PASSWORD_LEN) in r.text


def test_una_contrasena_gigante_se_rechaza_en_vez_de_truncarse(cliente: Any) -> None:
    """bcrypt trunca a 72 bytes en silencio, y truncar convierte dos
    contraseñas distintas en la misma."""
    r = cliente.post("/api/auth/register", json={"email": CORREO, "password": "a" * 200})
    assert r.status_code == 422


# ── registro y entrada ───────────────────────────────────────────────


def test_al_registrarse_ya_se_entra(cliente: Any) -> None:
    """Mandar a la pantalla de login a quien acaba de escribir su contraseña es
    fricción sin ninguna seguridad a cambio."""
    cuerpo = _registrar(cliente)
    assert cuerpo["token"]
    assert cuerpo["user"]["email"] == CORREO
    # Recién registrado: al carrusel.
    assert cuerpo["onboarded"] is False


def test_la_respuesta_nunca_lleva_la_contrasena(cliente: Any) -> None:
    texto = cliente.post("/api/auth/register", json={"email": CORREO, "password": CLAVE}).text
    assert CLAVE not in texto
    assert "hashed_password" not in texto
    assert "password" not in texto


def test_el_correo_repetido_no_crea_una_segunda_cuenta(cliente: Any) -> None:
    _registrar(cliente)
    r = cliente.post("/api/auth/register", json={"email": CORREO.upper(), "password": CLAVE})
    assert r.status_code == 409


def test_se_entra_con_las_credenciales_correctas(cliente: Any) -> None:
    _registrar(cliente)
    r = cliente.post("/api/auth/login", json={"email": CORREO, "password": CLAVE})
    assert r.status_code == 200
    assert r.json()["token"]


@pytest.mark.parametrize(
    ("correo", "clave"),
    [
        (CORREO, "la que no es"),
        ("nadie@adivor.com", CLAVE),
    ],
)
def test_el_login_no_dice_que_correos_existen(cliente: Any, correo: str, clave: str) -> None:
    """Mismo mensaje para «no existe» y «contraseña mala».

    Distinguirlos convierte el login en un buscador de correos registrados.
    """
    _registrar(cliente)
    r = cliente.post("/api/auth/login", json={"email": correo, "password": clave})
    assert r.status_code == 401
    assert r.json()["detail"] == "correo o contraseña incorrectos"


# ── la puerta ────────────────────────────────────────────────────────


RUTAS_DEL_CORREDOR = [
    ("GET", "/api/profile"),
    ("POST", "/api/profile"),
    ("GET", "/api/plan/export.csv"),
    ("GET", "/api/today"),
    ("POST", "/api/telegram/link"),
    ("GET", "/api/telegram/status"),
    ("GET", "/api/auth/me"),
]


@pytest.mark.parametrize(("metodo", "ruta"), RUTAS_DEL_CORREDOR)
def test_ninguna_ruta_del_corredor_va_abierta(cliente: Any, metodo: str, ruta: str) -> None:
    """Una por una, a propósito.

    Añadir un endpoint y olvidar la dependencia es el fallo que se queda abierto
    meses. Esta lista tiene que crecer con cada ruta nueva.
    """
    r = cliente.request(metodo, ruta, json={})
    assert r.status_code == 401, f"{metodo} {ruta} contestó {r.status_code}"


def test_un_token_inventado_no_pasa(cliente: Any) -> None:
    r = cliente.get("/api/auth/me", headers=_auth("no.soy.un.token"))
    assert r.status_code == 401


def test_un_token_firmado_con_otro_secreto_no_pasa(
    cliente: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """El caso que importa: no basta con que el token esté bien formado."""
    from apps.api.auth import _secreto

    monkeypatch.setenv("JWT_SECRET", "otro-secreto-completamente-distinto")
    _secreto.__globals__["_SECRETO_DE_PROCESO"] = ""
    ajeno = crear_token("alguien", "alguien@x.com")

    monkeypatch.setenv("JWT_SECRET", "secreto-de-prueba-suficientemente-largo")
    assert cliente.get("/api/auth/me", headers=_auth(ajeno)).status_code == 401


def test_un_token_de_una_cuenta_borrada_no_pasa(cliente: Any) -> None:
    """Un token vive siete días y sigue verificando después de que la cuenta
    desaparezca. Sin comprobar la fila, escribiría registros huérfanos."""
    token = crear_token("no-existe-esta-cuenta", "fantasma@x.com")
    assert cliente.get("/api/auth/me", headers=_auth(token)).status_code == 401


# ── aislamiento entre cuentas ────────────────────────────────────────


def test_cada_quien_ve_lo_suyo(cliente: Any) -> None:
    """No hay `user_id` en la URL, así que no hay dónde poner el ajeno.

    Es la razón de quitarlo en vez de comprobarlo: un parámetro que no existe
    no se puede olvidar de validar.
    """
    uno = _registrar(cliente, "uno@adivor.com")
    otro = _registrar(cliente, "otro@adivor.com")

    cliente.post(
        "/api/profile",
        json={"goal_distance": "42k", "days_per_week": 5},
        headers=_auth(uno["token"]),
    )

    mio = cliente.get("/api/profile", headers=_auth(uno["token"])).json()
    assert mio["profile"]["goal_distance"] == "42k"

    # El otro no tiene perfil: el de nadie más se le pega.
    assert cliente.get("/api/profile", headers=_auth(otro["token"])).status_code == 404


def test_el_onboarding_terminado_viaja_con_la_cuenta(cliente: Any) -> None:
    """Vive en el servidor a propósito: en localStorage, entrar desde otro
    teléfono repetiría el carrusel de alguien que ya lo hizo."""
    cuenta = _registrar(cliente)
    cabeceras = _auth(cuenta["token"])

    cliente.post(
        "/api/profile",
        json={"goal_distance": "42k", "days_per_week": 5, "age": 30},
        headers=cabeceras,
    )

    assert cliente.get("/api/auth/me", headers=cabeceras).json()["onboarded"] is True
    assert (
        cliente.post("/api/auth/login", json={"email": CORREO, "password": CLAVE}).json()[
            "onboarded"
        ]
        is True
    )
