"""Golden game vertical slice: semantic request reaches real runtime-backed widgets."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

GOLDEN_GAME_NEED = "植物を育てながら音を組み合わせるゲームを作りたい"


def _widget_types(node: object) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        kind = node.get("type")
        if isinstance(kind, str):
            found.add(kind)
        for value in node.values():
            found |= _widget_types(value)
    elif isinstance(node, list):
        for value in node:
            found |= _widget_types(value)
    return found


def test_golden_game_generates_simulation_and_interactive_audio_without_fake_gap() -> None:
    response = TestClient(app).post(
        "/api/v1/ai/generate",
        json={
            "input": {
                "natural_language": GOLDEN_GAME_NEED,
                "generation_options": {"provider": "mock"},
            }
        },
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "success", body
    result = body["result"]

    assert result["validation"]["valid"] is True
    gap = result.get("capability_gap")
    assert gap is None or gap["blocks_completion"] is False

    document = result["forge_document"]
    widget_types = _widget_types(document)
    assert "simulation_loop" in widget_types
    assert "audio_mixer" in widget_types
    major, minor = (int(part) for part in document["version"].split(".", 1))
    assert (major, minor) >= (1, 14)


def test_golden_game_does_not_conflate_mixing_with_media_authoring() -> None:
    response = TestClient(app).post(
        "/api/v1/ai/generate",
        json={
            "input": {
                "natural_language": GOLDEN_GAME_NEED,
                "generation_options": {"provider": "mock"},
            }
        },
    )
    result = response.json()["result"]
    gap = result.get("capability_gap") or {}
    assert "effect.media_compose" not in gap.get("missing", [])
