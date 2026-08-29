import json

from app.ai.validators.schema_validator import validate_forge_document_from_text


def _doc(version: str) -> dict:
    return {
        "version": version,
        "app": {"title": "Simulation"},
        "initial_screen_id": "main",
        "screens": [
            {
                "id": "main",
                "title": "Simulation",
                "state": {"ticks": {"type": "number", "value": 0}},
                "body": {
                    "type": "simulation_loop",
                    "id": "loop",
                    "state_ref": "ticks",
                    "step_ms": 50,
                    "max_ticks_per_advance": 8,
                },
            }
        ],
    }


def test_v1_13_accepts_simulation_loop():
    result = validate_forge_document_from_text(json.dumps(_doc("1.13")))
    assert result.valid, [e.to_dict() for e in result.errors]


def test_v1_12_rejects_simulation_loop():
    result = validate_forge_document_from_text(json.dumps(_doc("1.12")))
    assert not result.valid
    assert any(e.rule == "widget_not_allowed_in_version" for e in result.errors)


def test_v1_13_rejects_unsafe_simulation_frequency():
    doc = _doc("1.13")
    doc["screens"][0]["body"]["step_ms"] = 1
    result = validate_forge_document_from_text(json.dumps(doc))
    assert not result.valid
    assert any(e.path.endswith("/step_ms") for e in result.errors)
