from app.ai.validators.schema_validator import validate_forge_document


def _doc(version: str = "1.15") -> dict:
    return {"version": version, "initial_screen_id": "s", "screens": [{"id": "s", "title": "T", "state": {}, "body": {"type": "column", "id": "root", "children": []}}]}


def test_ga1_logic_valid_and_unknown_op_rejected() -> None:
    doc = _doc(); doc["logic"] = {"derived": {"x": {"kind": "literal", "value": 1}}}
    assert validate_forge_document(doc).valid
    doc["logic"] = {"derived": {"x": {"kind": "binary", "op": "execute_python", "left": {"kind": "literal", "value": 1}, "right": {"kind": "literal", "value": 2}}}}
    result = validate_forge_document(doc)
    assert not result.valid and any(e.rule == "logic_binary_op" for e in result.errors)


def test_ga1_logic_rejected_before_v115() -> None:
    doc = _doc("1.14"); doc["logic"] = {"derived": {"x": {"kind": "literal", "value": 1}}}
    result = validate_forge_document(doc)
    assert not result.valid and any(e.rule == "field_not_allowed_in_version" for e in result.errors)


def test_aggregate_where_allows_field_refs_only_inside_where() -> None:
    doc = _doc(); doc["logic"] = {"derived": {"total": {"kind": "aggregate", "source": "records", "op": "sum", "field": "amount", "where": {"kind": "binary", "op": "eq", "left": {"kind": "field", "field": "category"}, "right": {"kind": "literal", "value": "food"}}}}}
    assert validate_forge_document(doc).valid
    doc["logic"] = {"derived": {"bad": {"kind": "field", "field": "amount"}}}
    result = validate_forge_document(doc)
    assert not result.valid and any(e.rule == "logic_expression_kind" for e in result.errors)
