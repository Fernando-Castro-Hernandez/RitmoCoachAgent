"""Onboarding híbrido y los endpoints REST del pivote.

El reparto duro/blando es la decisión que se prueba aquí: el formulario captura
lo que el corredor **afirma**, la conversación captura lo que **revela**. Y una
vez que el carrusel escribió, el coach no puede volver a preguntar por la edad:
eso es lo que hace que se sienta un coach y no un formulario con voz.
"""

from __future__ import annotations

import csv
import io
from collections.abc import AsyncIterator, Iterator
from datetime import date
from typing import Any

import pytest
import pytest_asyncio
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.auth import usuario_actual
from apps.api.db.models import Base, UserRow
from apps.api.db.session import get_session
from apps.api.main import app
from apps.api.onboarding import (
    HARD_FIELDS,
    REQUIRED_FIELDS,
    SOFT_FIELDS,
    can_finish_carousel,
    field_layer,
    next_field,
    next_question,
    profile_completeness,
)
from apps.api.tools import CoachTools
from apps.api.vision_api import get_vision_client

HOY = date(2026, 8, 15)


# ── el reparto ───────────────────────────────────────────────────────


def test_los_datos_duros_no_se_preguntan_por_voz() -> None:
    """Si el carrusel ya los capturó, la voz no los vuelve a pedir."""
    perfil = dict.fromkeys(HARD_FIELDS, "algo")
    pregunta = next_question(perfil)
    assert pregunta is not None  # aún faltan los blandos
    assert "edad" not in pregunta.lower()
    assert "peso" not in pregunta.lower()


def test_las_molestias_siempre_se_preguntan_hablando() -> None:
    """Un formulario produce una casilla sin marcar; hablar produce «bueno, la
    rodilla a veces, pero nada grave», que es el dato que importa."""
    assert "injuries" in SOFT_FIELDS
    assert "injuries" not in HARD_FIELDS


def test_la_edad_y_el_peso_se_capturan_en_pantalla() -> None:
    """Dictarlos por voz es lento y propenso a error de transcripción."""
    for campo in ("age", "weight_kg", "height_cm", "race_date"):
        assert field_layer(campo) == "hard"


def test_cada_campo_pertenece_a_una_sola_capa() -> None:
    assert set(HARD_FIELDS).isdisjoint(SOFT_FIELDS)
    assert set(REQUIRED_FIELDS) == set(HARD_FIELDS) | set(SOFT_FIELDS)


def test_un_campo_que_no_existe_no_tiene_capa() -> None:
    with pytest.raises(ValueError, match="no es un campo"):
        field_layer("vo2max")


# ── el carrusel ──────────────────────────────────────────────────────


def test_solo_la_meta_es_obligatoria_en_el_carrusel() -> None:
    """Un onboarding que exige nueve respuestas es uno que la gente abandona."""
    assert can_finish_carousel({"goal_distance": "21k"})
    assert not can_finish_carousel({"age": 30, "weight_kg": 72.0})


def test_el_carrusel_solo_deja_el_perfil_a_medias() -> None:
    perfil = dict.fromkeys(HARD_FIELDS, "algo")
    assert 0.0 < profile_completeness(perfil) < 1.0


def test_un_perfil_vacio_no_tiene_avance() -> None:
    assert profile_completeness(None) == 0.0
    assert profile_completeness({}) == 0.0


# ── el orden de la conversación ──────────────────────────────────────


def test_pregunta_primero_lo_que_hace_falta_para_planificar() -> None:
    """Si se aburre y se va al tercer turno, que se haya ido habiendo
    contestado lo que hace falta para armar el plan."""
    assert next_field({}) == "weekly_volume_km"
    assert next_field({"weekly_volume_km": 30.0}) == "injuries"


def test_los_problemas_practicos_se_preguntan_pero_despues() -> None:
    """Salieron de la entrevista de la Fase 2, y son valiosos — pero no
    bloquean el plan."""
    assert "practical_problems" in SOFT_FIELDS
    parcial = {"weekly_volume_km": 30.0, "injuries": [], "longest_run_km": 12.0}
    assert next_field(parcial) == "practical_problems"


def test_pregunta_hasta_completar_y_luego_se_calla() -> None:
    perfil: dict[str, Any] = {}
    for _ in range(20):
        campo = next_field(perfil)
        if campo is None:
            break
        perfil[campo] = "respuesta"
    assert next_question(perfil) is None


def test_no_hay_dos_versiones_de_la_misma_pregunta() -> None:
    """La pregunta del volumen es la misma en el onboarding y en la
    clarificación autónoma. Duplicarla sería garantizar que se desincronicen."""
    from apps.api.clarification import QUESTIONS as VITALES
    from apps.api.onboarding import QUESTIONS as TODAS

    assert TODAS["weekly_volume_km"] == VITALES["weekly_volume_km"]


# ── endpoints ────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def sesion_factory() -> AsyncIterator[Any]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest.fixture
def cliente(sesion_factory: Any) -> Iterator[TestClient]:
    """Cliente ya autenticado como «u1».

    Se sustituye la dependencia de identidad en vez de registrar una cuenta de
    verdad, por dos razones: el `user_id` queda fijo y legible en el resto del
    archivo, y estas pruebas son de perfil, plan y visión — no de autenticación.
    Que la puerta cierre se prueba una por una en `test_auth.py`, que es donde
    tiene que doler si alguien la deja abierta.
    """

    async def _sesion() -> AsyncIterator[Any]:
        async with sesion_factory() as s:
            yield s

    app.dependency_overrides[get_session] = _sesion
    app.dependency_overrides[usuario_actual] = lambda: UserRow(
        id="u1", email="u1@ritmo.test", hashed_password=""
    )
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


def test_el_carrusel_guarda_y_dice_que_falta_por_voz(cliente: TestClient) -> None:
    r = cliente.post(
        "/api/profile",
        json={"goal_distance": "21k", "age": 28, "days_per_week": 4},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ok"] is True
    assert "age" in cuerpo["saved"]
    # El coach abre por aquí en vez de por «¿cómo te llamas?».
    assert "kilómetros" in cuerpo["next_voice_question"]


def test_el_carrusel_rechaza_una_meta_que_no_preparamos(cliente: TestClient) -> None:
    r = cliente.post("/api/profile", json={"goal_distance": "100k"})
    assert r.status_code == 422


def test_el_carrusel_rechaza_un_peso_imposible(cliente: TestClient) -> None:
    r = cliente.post("/api/profile", json={"goal_distance": "5k", "weight_kg": 5})
    assert r.status_code == 422


def test_consultar_un_perfil_que_no_existe(cliente: TestClient) -> None:
    assert cliente.get("/api/profile").status_code == 404


def test_el_perfil_devuelve_su_avance(cliente: TestClient) -> None:
    cliente.post("/api/profile", json={"goal_distance": "21k", "age": 30})
    cuerpo = cliente.get("/api/profile").json()
    assert cuerpo["carousel_done"] is True
    assert 0.0 < cuerpo["completeness"] < 1.0


# ── exportar a CSV ───────────────────────────────────────────────────


async def _con_plan(sesion_factory: Any) -> None:
    async with sesion_factory() as s:
        herramientas = CoachTools(s, today=HOY)
        await herramientas.profiles.save(
            "u1",
            level="intermedio",
            weekly_volume_km=30.0,
            longest_run_km=12.0,
            days_per_week=4,
            injuries=[],
            reference_distance_km=10.0,
            reference_time_sec=3000,
        )
        await herramientas.create_plan("u1", distance="21k")
        await s.commit()


def test_sin_plan_no_hay_csv(cliente: TestClient) -> None:
    assert cliente.get("/api/plan/export.csv").status_code == 404


def test_el_csv_trae_una_fila_por_sesion(
    cliente: TestClient, sesion_factory: Any, anyio_backend: Any = None
) -> None:
    import asyncio

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_con_plan(sesion_factory))
    r = cliente.get("/api/plan/export.csv")
    assert r.status_code == 200

    texto = r.content.decode("utf-8")
    # BOM UTF-8: sin él, Excel en Windows destroza los acentos.
    assert texto.startswith("﻿")

    filas = list(csv.DictReader(io.StringIO(texto.lstrip("﻿"))))
    assert len(filas) == 12 * 4  # 12 semanas × 4 sesiones
    assert filas[0]["dia"] == "martes"
    # El ritmo va formateado, no en segundos.
    assert ":" in filas[0]["ritmo_objetivo"]


def test_el_csv_no_filtra_datos_personales(cliente: TestClient, sesion_factory: Any) -> None:
    import asyncio

    asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_con_plan(sesion_factory))
    texto = cliente.get("/api/plan/export.csv").content.decode("utf-8")
    assert "peso" not in texto.lower()
    assert "@" not in texto


# ── endpoint de visión ───────────────────────────────────────────────


class ClienteVisionFalso:
    def __init__(self, salida: dict[str, Any]) -> None:
        self.salida = salida

    async def extract(self, images: Any, *, prompt: str, schema: Any) -> dict[str, Any]:
        return self.salida


@pytest.fixture
def con_vision(cliente: TestClient) -> Iterator[TestClient]:
    app.dependency_overrides[get_vision_client] = lambda: ClienteVisionFalso(
        {
            "distance_km": 8.42,
            "duration_sec": 2838,
            "avg_pace_sec_per_km": 350,
            "avg_hr": 152,
            "confidence": "high",
            "unreadable_fields": [],
        }
    )
    yield cliente
    app.dependency_overrides.pop(get_vision_client, None)


def test_subir_una_captura_devuelve_lo_leido_y_lo_propuesto(
    con_vision: TestClient,
) -> None:
    r = con_vision.post(
        "/api/vision/workout",
        files={"file": ("reloj.jpg", b"jpegfalso", "image/jpeg")},
    )
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["ok"] is True
    # El modelo leyó 5:50 y el motor calcula 5:37. Gana el motor.
    assert cuerpo["extraction"]["avg_pace_sec_per_km"] == 350
    assert cuerpo["proposed"]["pace_sec_per_km"] == 337
    assert cuerpo["proposed"]["discrepancy_flag"] is True
    assert cuerpo["pace_is_computed"] is True


def test_el_endpoint_no_escribe_en_la_bitacora(con_vision: TestClient, sesion_factory: Any) -> None:
    """Nada se guarda hasta que el corredor lo confirme (tarea D6)."""
    import asyncio

    con_vision.post(
        "/api/vision/workout",
        files={"file": ("reloj.jpg", b"jpegfalso", "image/jpeg")},
    )

    async def _contar() -> int:
        async with sesion_factory() as s:
            return len(await CoachTools(s, today=HOY).logs.sessions("u1"))

    assert asyncio.get_event_loop_policy().new_event_loop().run_until_complete(_contar()) == 0


def test_un_formato_que_no_es_imagen_se_rechaza(con_vision: TestClient) -> None:
    r = con_vision.post(
        "/api/vision/workout",
        files={"file": ("plan.pdf", b"%PDF-1.4", "application/pdf")},
    )
    assert r.status_code == 415


def test_una_imagen_vacia_se_rechaza(con_vision: TestClient) -> None:
    r = con_vision.post(
        "/api/vision/workout",
        files={"file": ("vacia.jpg", b"", "image/jpeg")},
    )
    assert r.status_code == 400


def test_una_lectura_imposible_se_devuelve_para_corregir(cliente: TestClient) -> None:
    """El motor rechaza, pero se enseña lo leído para que el corredor lo arregle
    a mano en vez de dejarle una pantalla vacía."""
    app.dependency_overrides[get_vision_client] = lambda: ClienteVisionFalso(
        {
            "distance_km": 42.0,
            "duration_sec": 3600,  # 1:25/km, imposible
            "confidence": "high",
            "unreadable_fields": [],
        }
    )
    r = cliente.post(
        "/api/vision/workout",
        files={"file": ("reloj.jpg", b"x", "image/jpeg")},
    )
    app.dependency_overrides.pop(get_vision_client, None)

    cuerpo = r.json()
    assert cuerpo["ok"] is False
    assert cuerpo["proposed"] is None
    assert cuerpo["extraction"]["distance_km"] == 42.0


def test_la_cadena_de_vision_aparece_en_la_configuracion(cliente: TestClient) -> None:
    """La que se usa de verdad, no la que había hace dos ADRs.

    Esta prueba afirmaba que la visión usaba `nova-2-lite`. Y pasaba — porque
    `/api/config` leía `os.getenv("VISION_MODEL_ID", "us.amazon.nova-2-lite…")`
    y nadie define esa variable, así que informaba un modelo que el sistema
    dejó de usar en el ADR 0014. La prueba fijaba la ficción en vez de cazarla.

    Ahora la configuración sale de `Settings`, que es de donde sale la cadena
    real que recorre `ChainVisionClient`.
    """
    cuerpo = cliente.get("/api/config").json()

    cadena = cuerpo["vision_model_chain"]
    assert cadena, "la cadena de visión no puede venir vacía"
    # Voz y visión son modelos distintos y de nubes distintas (ADR 0014): Nova
    # Sonic sólo acepta SPEECH, así que no puede leer una imagen.
    assert cuerpo["model_id"] not in cadena
    assert all("3-5-haiku" not in m for m in cadena), "Claude 3.5 Haiku no acepta imágenes"


class ClienteVisionCaido:
    async def extract(self, images: Any, *, prompt: str, schema: Any) -> dict[str, Any]:
        from apps.api.vision.client import AllVisionModelsUnavailableError

        raise AllVisionModelsUnavailableError("ninguno de los 2 modelos respondió")


def test_sin_modelos_disponibles_se_degrada_a_captura_manual(cliente: TestClient) -> None:
    """No es un 502.

    Si Bedrock no responde, el corredor teclea cuatro números y sigue con su
    vida. Una pantalla de error le deja el entrenamiento sin registrar, y el
    entrenamiento sin registrar contamina la progresión igual que una cifra mal
    leída. La ruta de visión es una comodidad, no un requisito.
    """
    app.dependency_overrides[get_vision_client] = ClienteVisionCaido
    r = cliente.post(
        "/api/vision/workout",
        files={"file": ("reloj.jpg", b"x", "image/jpeg")},
    )
    app.dependency_overrides.pop(get_vision_client, None)

    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["mode"] == "manual"
    assert "distance_km" in cuerpo["fields"]
    assert "Escribe los números" in cuerpo["reason"]
