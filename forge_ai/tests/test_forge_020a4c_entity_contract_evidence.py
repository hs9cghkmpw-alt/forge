from forge_ai.core.ir.entity_synthesizer import _entity_contract_evidence
from forge_ai.core.semantics.structure_provenance import EntitySynthesisRepair


def _valid() -> dict:
    return {
        "entity_name": "plant_log",
        "entity_label": "植物記録",
        "visual_style": "calm",
        "fields": [
            {
                "name": "watered_on",
                "label": "水やり日",
                "type": "date",
                "required": True,
                "choices": [],
                "measure": "unknown",
            }
        ],
    }


def test_strict_contract_passes_only_without_repairs():
    ev = _entity_contract_evidence(_valid(), structured_output_mode="json_schema")
    assert ev.raw_schema_valid is True
    assert ev.strict_contract_passed is True
    assert ev.repairs_applied == ()
    assert ev.fields_received == 1


def test_unknown_type_is_observed_as_repair_not_model_success():
    raw = _valid()
    raw["fields"][0]["type"] = "integer"
    ev = _entity_contract_evidence(raw, structured_output_mode="json_schema")
    assert EntitySynthesisRepair.UNKNOWN_TYPE_TO_STRING in ev.repairs_applied
    assert ev.strict_contract_passed is False


def test_required_injection_is_not_strict_success():
    raw = _valid()
    raw["fields"][0]["required"] = False
    ev = _entity_contract_evidence(raw, structured_output_mode="json_schema")
    assert EntitySynthesisRepair.REQUIRED_INJECTED in ev.repairs_applied
    assert ev.strict_contract_passed is False


def test_choice_downgrade_is_not_strict_success():
    raw = _valid()
    raw["fields"][0].update({"type": "choice", "choices": ["only-one"]})
    ev = _entity_contract_evidence(raw, structured_output_mode="json_schema")
    assert EntitySynthesisRepair.CHOICE_TO_STRING in ev.repairs_applied
    assert ev.strict_contract_passed is False


def test_visual_and_label_fallbacks_are_observed():
    raw = _valid()
    raw["visual_style"] = "beautiful_blue"
    raw["fields"][0]["label"] = ""
    ev = _entity_contract_evidence(raw, structured_output_mode="json_schema")
    assert EntitySynthesisRepair.VISUAL_STYLE_FALLBACK in ev.repairs_applied
    assert EntitySynthesisRepair.LABEL_FALLBACK in ev.repairs_applied
    assert ev.strict_contract_passed is False
