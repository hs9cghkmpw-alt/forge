from app.ai.validators.schema_validator import validate_forge_document

def _doc(version="1.15"):
    return {"version": version, "initial_screen_id": "home", "screens": [{
      "id": "home", "title": "Game",
      "state": {"tick": {"type": "number", "value": 0}},
      "body": {"type": "simulation_progress", "id": "progress", "state_ref": "tick",
               "title": "成長", "stages": ["種", "芽", "花"], "ticks_per_stage": 2}}]}

def test_v115_accepts_visible_simulation_projection():
    assert validate_forge_document(_doc()).valid

def test_v114_rejects_v115_progress_widget():
    result = validate_forge_document(_doc("1.14"))
    assert not result.valid
    assert any(e.rule == "widget_not_allowed_in_version" for e in result.errors)
