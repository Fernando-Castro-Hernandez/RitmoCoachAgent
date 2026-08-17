"""Ruta de vídeo: de una zancada a una señal de técnica.

Lo que se fija aquí no es que el modelo mire bien —eso se verifica a mano con
clips reales— sino la frontera que hace segura la característica: **el modelo
describe y el motor prescribe**. Tres pruebas la sostienen:

- con molestia activa no sale ninguna señal, aunque el modelo marque algo;
- una señal la elige la biblioteca curada, nunca el texto del modelo;
- un observable que no está en el esquema se descarta en vez de propagarse.

La tercera parece paranoia hasta que se piensa qué pasaría sin ella: un
`observable` inventado no encuentra categoría, y sin el filtro acabaría
eligiendo la señal equivocada o reventando aguas abajo.
"""

from __future__ import annotations

from datetime import date
from typing import Any

import pytest
import pytest_asyncio
from coach_domain.safety import SafetyLevel, assess
from coach_domain.technique import select_cue_by_category
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api.auth import usuario_actual
from apps.api.db.models import Base, UserRow
from apps.api.db.repo import LogRepo, ProfileRepo
from apps.api.db.session import get_session
from apps.api.main import app
from apps.api.vision.client import VisionError
from apps.api.vision.gait import (
    GAIT_PROMPT,
    MAX_FRAMES,
    NoFramesError,
    analyze_gait,
    suggest_cue,
)
from apps.api.vision.schemas import GAIT_SCHEMA, GaitFinding
from apps.api.vision_api import _contraindicaciones, get_vision_client

VERDE = assess(0)
ROJO = assess(9, flags=["chest_pain"])
AMBAR = assess(4)


class ClienteFalso:
    """Un modelo de visión sin red, sin credenciales y sin gastar un token."""

    def __init__(self, salida: dict[str, Any] | Exception) -> None:
        self.salida = salida
        self.llamadas: list[dict[str, Any]] = []

    async def extract(
        self, images: list[tuple[bytes, str]], *, prompt: str, schema: dict[str, Any]
    ) -> dict[str, Any]:
        self.llamadas.append({"images": images, "prompt": prompt, "schema": schema})
        if isinstance(self.salida, Exception):
            raise self.salida
        return self.salida


def _hallazgo(observable: str, assessment: str = "watch", note: str = "n") -> dict[str, str]:
    return {"observable": observable, "assessment": assessment, "note": note}


# ── la lectura ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_los_fotogramas_viajan_como_una_secuencia() -> None:
    """Los diez van en la MISMA llamada, no en diez llamadas sueltas.

    Es lo que hace que la pregunta tenga sentido: la cadencia y el cruce de
    brazos sólo se ven comparando cuadros consecutivos. Diez llamadas de un
    fotograma serían diez fotos independientes y diez veces el coste.
    """
    cliente = ClienteFalso({"findings": []})
    await analyze_gait(cliente, [(b"x", "image/jpeg")] * 6)

    assert len(cliente.llamadas) == 1
    assert len(cliente.llamadas[0]["images"]) == 6
    assert cliente.llamadas[0]["schema"] is GAIT_SCHEMA


@pytest.mark.asyncio
async def test_sin_fotogramas_falla_en_vez_de_preguntarle_al_modelo() -> None:
    cliente = ClienteFalso({"findings": []})
    with pytest.raises(NoFramesError):
        await analyze_gait(cliente, [])
    assert cliente.llamadas == []


@pytest.mark.asyncio
async def test_hay_un_techo_de_fotogramas() -> None:
    cliente = ClienteFalso({"findings": []})
    with pytest.raises(NoFramesError):
        await analyze_gait(cliente, [(b"x", "image/jpeg")] * (MAX_FRAMES + 1))
    assert cliente.llamadas == []


@pytest.mark.asyncio
async def test_un_observable_inventado_se_descarta() -> None:
    salida = {
        "findings": [
            _hallazgo("trunk_lean"),
            _hallazgo("pronacion_severa"),  # no está en el enum
            {"observable": "arm_crossover", "assessment": "excelente", "note": "n"},
        ]
    }
    hallazgos = await analyze_gait(ClienteFalso(salida), [(b"x", "image/jpeg")])
    assert [h.observable for h in hallazgos] == ["trunk_lean"]


@pytest.mark.asyncio
async def test_una_salida_sin_hallazgos_es_un_error_del_modelo() -> None:
    with pytest.raises(VisionError):
        await analyze_gait(ClienteFalso({"otra_cosa": []}), [(b"x", "image/jpeg")])


def test_el_prompt_prohibe_medir_y_diagnosticar() -> None:
    """Un vídeo de teléfono sin calibrar no mide nada, y «12 grados de
    pronación» suena a diagnóstico justamente porque lleva una cifra."""
    texto = GAIT_PROMPT.lower()
    assert "grados" in texto
    assert "lesiones" in texto
    assert "instrucciones" in texto, "falta la defensa contra inyección por imagen"


def test_el_esquema_no_tiene_donde_poner_un_consejo() -> None:
    """La defensa estructural: si no hay campo, no hay consejo improvisado."""
    propiedades = GAIT_SCHEMA["properties"]["findings"]["items"]["properties"]
    assert set(propiedades) == {"observable", "assessment", "note"}


# ── la señal ──────────────────────────────────────────────────────────


def test_con_dolor_activo_no_sale_ninguna_senal() -> None:
    """Ámbar incluido. Corregir la zancada de quien ya tiene una molestia es
    cambiar la carga justo donde no toca."""
    hallazgos = [GaitFinding("foot_strike_position", "flag", "n")]
    assert AMBAR.level is not SafetyLevel.GREEN
    assert suggest_cue(hallazgos, level="principiante", week_index=1, safety=AMBAR) is None
    assert suggest_cue(hallazgos, level="principiante", week_index=1, safety=ROJO) is None


def test_la_senal_sale_de_la_biblioteca_y_no_del_modelo() -> None:
    hallazgos = [GaitFinding("foot_strike_position", "flag", "te veo alcanzando con el pie")]
    cue = suggest_cue(hallazgos, level="principiante", week_index=1, safety=VERDE)
    assert cue is not None
    assert cue.category == "sobrezancada"
    # El texto es el curado, no la nota del modelo.
    assert cue.voice_text != hallazgos[0].note
    assert cue.voice_text


def test_lo_evidente_manda_sobre_lo_dudoso() -> None:
    hallazgos = [
        GaitFinding("trunk_lean", "watch", "n"),
        GaitFinding("arm_crossover", "flag", "n"),
    ]
    cue = suggest_cue(hallazgos, level="principiante", week_index=1, safety=VERDE)
    assert cue is not None and cue.category == "brazos"


def test_si_nada_destaca_no_se_inventa_una_correccion() -> None:
    """Un coach que siempre encuentra algo que corregir deja de ser creíble."""
    hallazgos = [GaitFinding("trunk_lean", "ok", "n"), GaitFinding("arm_crossover", "ok", "n")]
    assert suggest_cue(hallazgos, level="principiante", week_index=1, safety=VERDE) is None


def test_la_cadera_se_observa_pero_no_se_convierte_en_senal() -> None:
    """No hay señal curada para la cadera. Decir «no dejes caer la cadera» sin
    poder enseñar el ejercicio que lo entrena es un consejo que no sirve."""
    hallazgos = [GaitFinding("hip_drop", "flag", "n")]
    assert suggest_cue(hallazgos, level="principiante", week_index=1, safety=VERDE) is None


def test_una_contraindicacion_activa_veta_su_senal() -> None:
    hallazgos = [GaitFinding("foot_strike_position", "flag", "n")]
    cue = suggest_cue(
        hallazgos,
        level="principiante",
        week_index=1,
        safety=VERDE,
        exclude=("molestia_rodilla",),
    )
    assert cue is None


def test_la_categoria_pedida_es_la_que_vuelve() -> None:
    for categoria in ("cadencia", "postura", "brazos", "sobrezancada"):
        cue = select_cue_by_category(categoria, level="principiante", week_index=1, safety=VERDE)
        assert cue is not None and cue.category == categoria


def test_una_categoria_que_no_existe_devuelve_nada() -> None:
    assert (
        select_cue_by_category("respiracion", level="avanzado", week_index=1, safety=VERDE) is None
    ), "respiración sólo está para principiantes"


@pytest.mark.parametrize(
    ("dichas", "esperadas"),
    [
        (["me molesta la rodilla derecha"], ("molestia_rodilla",)),
        (["dolor lumbar de vez en cuando"], ("molestia_lumbar",)),
        (["knee pain"], ("molestia_rodilla",)),
        ([], ()),
        (None, ()),
        (["nada"], ()),
    ],
)
def test_las_molestias_dichas_se_traducen_a_contraindicaciones(
    dichas: Any, esperadas: tuple[str, ...]
) -> None:
    assert _contraindicaciones(dichas) == esperadas


# ── el endpoint ───────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def cliente() -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    fabrica = async_sessionmaker(engine, expire_on_commit=False)

    async def sesion_de_prueba() -> Any:
        async with fabrica() as s:
            yield s

    app.dependency_overrides[get_session] = sesion_de_prueba
    app.dependency_overrides[usuario_actual] = lambda: UserRow(
        id="u1", email="u1@ritmo.test", hashed_password=""
    )
    with TestClient(app) as c:
        c.fabrica = fabrica  # type: ignore[attr-defined]
        yield c

    app.dependency_overrides.clear()
    await engine.dispose()


def _con_modelo(salida: dict[str, Any] | Exception) -> ClienteFalso:
    falso = ClienteFalso(salida)
    app.dependency_overrides[get_vision_client] = lambda: falso
    return falso


def _archivos(n: int = 3) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (f"f{i}.jpg", b"\xff\xd8\xff", "image/jpeg")) for i in range(n)]


def test_el_endpoint_devuelve_hallazgos_y_senal(cliente: Any) -> None:
    _con_modelo({"findings": [_hallazgo("foot_strike_position", "flag", "alcanzas con el pie")]})

    r = cliente.post("/api/vision/gait", files=_archivos())
    assert r.status_code == 200, r.text
    cuerpo = r.json()

    assert cuerpo["ok"] is True
    assert cuerpo["findings"][0]["observable"] == "foot_strike_position"
    assert cuerpo["cue"]["category"] == "sobrezancada"
    assert cuerpo["cue_blocked_by_safety"] is False


@pytest.mark.asyncio
async def test_en_ambar_el_endpoint_dice_por_que_no_hay_senal(cliente: Any) -> None:
    """Sin esta bandera la pantalla no puede distinguir «se te ve bien» de «hoy
    no te corrijo porque te duele algo», y son mensajes opuestos."""
    async with cliente.fabrica() as db:
        await LogRepo(db).add_wellness("u1", occurred_on=date.today(), pain_score=4)
        await db.commit()

    _con_modelo({"findings": [_hallazgo("trunk_lean", "flag")]})
    cuerpo = cliente.post("/api/vision/gait", files=_archivos()).json()

    assert cuerpo["cue"] is None
    assert cuerpo["cue_blocked_by_safety"] is True
    # Lo observado SÍ viaja: el corredor puede verlo, sólo que no se le corrige.
    assert cuerpo["findings"]


@pytest.mark.asyncio
async def test_la_molestia_del_perfil_veta_la_senal(cliente: Any) -> None:
    async with cliente.fabrica() as db:
        await ProfileRepo(db).save(
            "u1", goal_distance="10k", level="principiante", injuries=["molestia en la rodilla"]
        )
        await db.commit()

    _con_modelo({"findings": [_hallazgo("foot_strike_position", "flag")]})
    cuerpo = cliente.post("/api/vision/gait", files=_archivos()).json()

    assert cuerpo["cue"] is None
    # No es la puerta de seguridad quien corta: es la contraindicación.
    assert cuerpo["cue_blocked_by_safety"] is False


def test_demasiados_fotogramas_se_rechazan_antes_de_llamar_al_modelo(cliente: Any) -> None:
    falso = _con_modelo({"findings": []})
    r = cliente.post("/api/vision/gait", files=_archivos(MAX_FRAMES + 1))
    assert r.status_code == 413
    assert falso.llamadas == []


def test_un_formato_que_no_es_imagen_se_rechaza(cliente: Any) -> None:
    _con_modelo({"findings": []})
    r = cliente.post(
        "/api/vision/gait",
        files=[("files", ("clip.mp4", b"\x00\x00", "video/mp4"))],
    )
    assert r.status_code == 415


def test_sin_modelo_disponible_no_se_ofrece_captura_manual(cliente: Any) -> None:
    """Nadie va a teclear cómo cae su propio pie. Se dice que ahora no se puede
    y se deja intacto el resto del producto."""
    from apps.api.vision.client import AllVisionModelsUnavailableError

    _con_modelo(AllVisionModelsUnavailableError("se agotó la cadena"))
    cuerpo = cliente.post("/api/vision/gait", files=_archivos()).json()

    assert cuerpo["ok"] is False
    assert cuerpo["findings"] == []
    assert cuerpo["cue"] is None
    assert "mode" not in cuerpo


def test_el_analisis_no_escribe_nada(cliente: Any) -> None:
    """Igual que la lectura del reloj: mirar no registra."""
    _con_modelo({"findings": [_hallazgo("cadence_impression", "watch")]})
    antes = cliente.get("/api/today").json()
    cliente.post("/api/vision/gait", files=_archivos())
    assert cliente.get("/api/today").json() == antes


def test_el_maximo_de_fotogramas_es_el_mismo_en_los_dos_lados() -> None:
    """El navegador extrae diez y el servidor acepta diez. Si alguien sube uno
    de los dos y no el otro, la subida falla en producción y no aquí."""
    from pathlib import Path

    frames = Path(__file__).resolve().parents[3] / "apps" / "web" / "src" / "frames.ts"
    assert f"= {MAX_FRAMES}" in frames.read_text(encoding="utf-8")
