from forge_ai.core.compiler import ForgeIRDocument, ForgeIRScreen, ForgeIRWidget


def test_logic_serializes_only_when_present() -> None:
    screen = ForgeIRScreen(id="s", title="T", state={}, body=ForgeIRWidget(type="column", id="root"))
    plain = ForgeIRDocument(version="1.15", initial_screen_id="s", screens=(screen,))
    assert "logic" not in plain.to_json_dict()

    logic = {
        "derived": {"balance": {"kind": "literal", "value": 10}},
        "visible_when": {"warning": {"kind": "literal", "value": False}},
    }
    enriched = plain.with_logic(logic)
    assert enriched.to_json_dict()["logic"] == logic
    assert "logic" not in plain.to_json_dict()
