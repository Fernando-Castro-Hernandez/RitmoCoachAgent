"""El bucle de herramientas, cerrado.

Hasta aquí las herramientas existían, estaban probadas, y **no se le declaraban
al modelo**: `prompt_start` aceptaba `tools` y nadie se los pasaba. El coach
hablaba muy bien y no podía consultar nada. Estas pruebas fijan las tres piezas
que faltaban y una invariante de seguridad.

La que más importa es `test_el_user_id_del_modelo_se_descarta`. El esquema le
pide al modelo un `user_id` y el ejecutor lo tira: el que vale es el de la
sesión. Un modelo al que se le puede convencer de cambiar de identificador es un
modelo al que se le puede pedir el plan de otra persona, y eso no se arregla con
una frase en el prompt.
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from apps.api import protocol
from apps.api.bridge import NovaBridge, _argumentos_de
from apps.api.db.models import Base
from apps.api.db.repo import ProfileRepo
from apps.api.tests.conftest import FakeStream, tipos_enviados
from apps.api.tool_runner import ToolRunner
from apps.api.tool_specs import TOOL_NAMES, tool_specs
from apps.api.tools import CoachTools

HOY = date(2026, 8, 17)


@pytest_asyncio.fixture
async def fabrica() -> Any:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conexion:
        await conexion.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


# ── las especificaciones ─────────────────────────────────────────────


def test_toda_herramienta_declarada_existe_de_verdad() -> None:
    """El olvido falla el build, no la conversación.

    Las descripciones se escriben a mano —son prompt, no documentación— así que
    los dos sitios se pueden desincronizar. Que se desincronicen tiene que doler
    aquí y no en producción, con el modelo llamando a algo que no está.
    """
    for nombre in TOOL_NAMES:
        assert hasattr(CoachTools, nombre), f"«{nombre}» está declarada y no existe"


def test_toda_herramienta_publica_esta_declarada() -> None:
    """Y al revés: una herramienta que el modelo no conoce es código muerto."""
    publicas = {
        n
        for n in dir(CoachTools)
        if not n.startswith("_")
        and callable(getattr(CoachTools, n))
        # Los repositorios que `CoachTools` expone como atributos no son
        # herramientas del coach.
        and n not in {"profiles", "state", "logs"}
    }
    assert publicas == set(TOOL_NAMES)


def test_el_esquema_viaja_como_cadena() -> None:
    """La API lo exige, y mandarlo como objeto falla con un error que no dice
    cuál de los dos formatos quería."""
    for especificacion in tool_specs():
        crudo = especificacion["toolSpec"]["inputSchema"]["json"]
        assert isinstance(crudo, str)
        esquema = json.loads(crudo)
        assert esquema["type"] == "object"
        assert esquema["additionalProperties"] is False


def test_create_plan_le_avisa_al_modelo_de_que_puede_negarse() -> None:
    """Que el modelo sepa de antemano que ese camino existe es lo que hace que
    preguntar no se sienta un fallo suyo."""
    descripcion = next(
        e["toolSpec"]["description"] for e in tool_specs() if e["toolSpec"]["name"] == "create_plan"
    )
    assert "negarse" in descripcion
    assert "needs_context" in descripcion


def test_log_run_le_avisa_de_que_el_ritmo_no_es_suyo() -> None:
    descripcion = next(
        e["toolSpec"]["description"] for e in tool_specs() if e["toolSpec"]["name"] == "log_run"
    )
    assert "No mandes el ritmo" in descripcion


# ── el ejecutor ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_el_user_id_del_modelo_se_descarta(fabrica: Any) -> None:
    """La invariante de seguridad del módulo.

    El modelo pide el plan de «otro-corredor» y recibe el de la sesión. No hay
    forma de que un argumento cambie de quién habla.
    """
    async with fabrica() as db:
        await ProfileRepo(db).save("mio", goal_distance="10k")
        await db.commit()

    ejecutor = ToolRunner(fabrica, user_id="mio", today=HOY)
    resultado = await ejecutor.run("get_week_context", {"user_id": "otro-corredor"})

    assert resultado.get("user_id", "mio") == "mio"
    assert "otro-corredor" not in json.dumps(resultado, default=str)


@pytest.mark.asyncio
async def test_una_herramienta_inventada_no_calla(fabrica: Any) -> None:
    """Se le dice cuáles hay: con la lista delante suele corregirse en el turno."""
    ejecutor = ToolRunner(fabrica, user_id="u1", today=HOY)
    resultado = await ejecutor.run("dame_el_plan_ya", {})

    assert resultado["ok"] is False
    assert "get_today_session" in resultado["available"]


@pytest.mark.asyncio
async def test_un_argumento_inventado_no_tumba_la_conversacion(fabrica: Any) -> None:
    ejecutor = ToolRunner(fabrica, user_id="u1", today=HOY)
    resultado = await ejecutor.run("get_week_context", {"inventado": 3})

    assert resultado["ok"] is False
    assert "argumentos inválidos" in resultado["error"]


@pytest.mark.asyncio
async def test_un_fallo_no_devuelve_una_cifra_plausible(fabrica: Any) -> None:
    """Lo peor que puede pasar es que el coach diga que no puede consultarlo.

    Devolver un valor por defecto sería exactamente la cifra inventada que todo
    el sistema existe para evitar.
    """
    ejecutor = ToolRunner(fabrica, user_id="u1", today=HOY)
    resultado = await ejecutor.run("explain_technique_cue", {"cue_id": "no-existe"})

    assert resultado.get("ok") is not True
    assert "distance_km" not in resultado


# ── el puente responde ───────────────────────────────────────────────


class EjecutorFalso:
    def __init__(self, resultado: dict[str, Any]) -> None:
        self.resultado = resultado
        self.llamadas: list[tuple[str, dict[str, Any]]] = []

    async def run(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        self.llamadas.append((name, arguments))
        return self.resultado


@pytest.mark.asyncio
async def test_sin_ejecutor_no_se_declaran_herramientas() -> None:
    """Una sesión mal cableada calla, en vez de pedir cosas que nadie contesta."""
    stream = FakeStream()
    puente = NovaBridge(stream=stream)
    await puente.start("eres un coach")

    inicio = stream.input_stream.sent[1]["event"]["promptStart"]
    assert "toolConfiguration" not in inicio


@pytest.mark.asyncio
async def test_con_ejecutor_el_modelo_las_ve() -> None:
    stream = FakeStream()
    puente = NovaBridge(stream=stream, tool_runner=EjecutorFalso({"ok": True}))
    await puente.start("eres un coach")

    inicio = stream.input_stream.sent[1]["event"]["promptStart"]
    declaradas = {t["toolSpec"]["name"] for t in inicio["toolConfiguration"]["tools"]}
    assert declaradas == set(TOOL_NAMES)


@pytest.mark.asyncio
async def test_el_puente_ejecuta_y_contesta() -> None:
    """El bucle entero: el modelo pide, se ejecuta, y se le devuelve.

    Antes de esto el `toolUse` se traducía a un evento y ahí se acababa: nadie
    ejecutaba y nadie contestaba, así que el coach esperaba una respuesta que no
    llegaba nunca.
    """
    ejecutor = EjecutorFalso({"ok": True, "distance_km": 8.0})
    stream = FakeStream(
        [
            {
                "event": {
                    "toolUse": {
                        "toolUseId": "tu-1",
                        "toolName": "get_today_session",
                        "content": '{"user_id": "u1"}',
                    }
                }
            },
            {"event": {"completionEnd": {}}},
        ]
    )
    puente = NovaBridge(stream=stream, tool_runner=ejecutor)
    await puente.start("eres un coach")

    async for evento in puente.events():
        if evento.kind == "turn_end":
            break

    assert ejecutor.llamadas == [("get_today_session", {"user_id": "u1"})]
    # Tres eventos de vuelta: apertura del bloque, el resultado, y el cierre.
    assert "toolResult" in tipos_enviados(stream)


def test_el_resultado_se_empareja_por_tool_use_id() -> None:
    """Sin el `toolUseId` el modelo no sabe a cuál de sus preguntas se le
    contesta, y con dos llamadas en el mismo turno las cruza."""
    eventos = protocol.tool_result_block("p", "c", tool_use_id="tu-7", result={"ok": True})
    assert (
        eventos[0]["event"]["contentStart"]["toolResultInputConfiguration"]["toolUseId"] == "tu-7"
    )
    assert json.loads(eventos[1]["event"]["toolResult"]["content"]) == {"ok": True}


@pytest.mark.parametrize(
    ("peticion", "esperado"),
    [
        ({"content": '{"distance_km": 8}'}, {"distance_km": 8}),
        ({"content": {"distance_km": 8}}, {"distance_km": 8}),
        ({"input": {"distance_km": 8}}, {"distance_km": 8}),
        # Un JSON roto no puede tumbar el turno: se ejecuta sin argumentos y la
        # herramienta se queja, que es un camino que ya está probado.
        ({"content": "{roto"}, {}),
        ({}, {}),
    ],
)
def test_los_argumentos_se_leen_vengan_como_vengan(
    peticion: dict[str, Any], esperado: dict[str, Any]
) -> None:
    assert _argumentos_de(peticion) == esperado


def test_ningun_esquema_le_pide_el_user_id_al_modelo() -> None:
    """Lo enseñó una sonda contra el modelo real.

    Declarado como obligatorio, el modelo contestó «dime tu user_id para
    seguir»: no lo tiene, y un parámetro que no puede rellenar se convierte en
    una pregunta al corredor. Un identificador interno filtrado a la
    conversación. Se impone en el ejecutor; el modelo no lo ve.
    """
    for especificacion in tool_specs():
        esquema = json.loads(especificacion["toolSpec"]["inputSchema"]["json"])
        assert "user_id" not in esquema["properties"]
        assert "user_id" not in esquema["required"]
