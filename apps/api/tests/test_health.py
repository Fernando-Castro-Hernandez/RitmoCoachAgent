"""La API responde y reporta qué modelo de voz está activo."""

from __future__ import annotations

from fastapi.testclient import TestClient

from apps.api.main import app

client = TestClient(app)


def test_health_responde_ok() -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_config_expone_el_modelo_activo() -> None:
    r = client.get("/api/config")
    assert r.status_code == 200
    assert "sonic" in r.json()["model_id"]


def test_config_no_filtra_secretos() -> None:
    """Reporta si hay credenciales configuradas, nunca su valor."""
    cuerpo = client.get("/api/config").text.lower()
    for prohibido in ("token", "secret_key", "password"):
        assert prohibido not in cuerpo
