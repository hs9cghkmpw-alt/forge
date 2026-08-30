from __future__ import annotations

from copy import deepcopy

from app.ai.validators.schema_validator import validate_forge_document


def _document(*, version: str = "1.16", latitude_type: str = "number") -> dict:
    return {
        "version": version,
        "initial_screen_id": "main",
        "record_schemas": {
            "location": {
                "fields": [
                    {"name": "latitude", "type": latitude_type, "label": "緯度", "required": True},
                    {"name": "longitude", "type": "number", "label": "経度", "required": True},
                    {"name": "name", "type": "string", "label": "名称", "required": True},
                ]
            }
        },
        "screens": [
            {
                "id": "main",
                "title": "位置情報",
                "state": {
                    "records": {
                        "type": "record_list",
                        "schema_ref": "location",
                        "value": [],
                    }
                },
                "body": {
                    "type": "map_view",
                    "id": "map",
                    "state_ref": "records",
                    "latitude_field": "latitude",
                    "longitude_field": "longitude",
                    "label_field": "name",
                    "initial_zoom": 11,
                    "height": 320,
                },
            }
        ],
    }


def test_v1_16_accepts_real_coordinate_backed_map_view() -> None:
    result = validate_forge_document(_document())
    assert result.valid, [e.to_dict() for e in result.errors]


def test_v1_15_rejects_map_view() -> None:
    result = validate_forge_document(_document(version="1.15"))
    assert not result.valid
    assert any(e.rule == "widget_not_allowed_in_version" for e in result.errors)


def test_map_coordinates_must_reference_numeric_schema_fields() -> None:
    result = validate_forge_document(_document(latitude_type="string"))
    assert not result.valid
    assert any(e.rule == "field_type_mismatch" and e.path.endswith("/latitude_field") for e in result.errors)


def test_map_rejects_missing_coordinate_field_reference() -> None:
    doc = deepcopy(_document())
    doc["screens"][0]["body"]["longitude_field"] = "missing_longitude"
    result = validate_forge_document(doc)
    assert not result.valid
    assert any(e.rule == "field_reference_exists" and e.path.endswith("/longitude_field") for e in result.errors)
