from forge_ai.core.semantics.capability_plan import plan_capabilities


def test_map_request_adds_explicit_numeric_coordinate_prerequisites():
    plan = plan_capabilities("観測地点を地図で見ながらメモを記録したい")
    fields = {field.name: field for field in plan.fields}
    assert fields["latitude"].kind == "number"
    assert fields["longitude"].kind == "number"
    assert fields["latitude"].capability == "data.number"
    assert fields["longitude"].capability == "data.number"


def test_map_prerequisites_do_not_invent_geocoding():
    plan = plan_capabilities("札幌駅という場所を地図で見たい")
    fields = {field.name: field for field in plan.fields}
    assert "latitude" in fields and "longitude" in fields
    # Coordinate fields are explicit inputs; no geocoded coordinate value is
    # fabricated by semantic planning.
    assert all(not hasattr(field, "value") for field in fields.values())
