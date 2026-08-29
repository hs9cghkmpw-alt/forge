from forge_ai.core.semantics.capability_plan import plan_capabilities
from forge_ai.core.semantics.roles import SemanticRole, extract_semantic_roles


def test_explicit_synthesis_is_normalized_as_combine_activity() -> None:
    roles = extract_semantic_roles("音を合成して書き出したい")

    assert "combine" in roles.of(SemanticRole.ACTIVITY)
    assert "sound" in roles.of(SemanticRole.RECORDED_DATA)


def test_audio_synthesis_export_requires_media_compose() -> None:
    plan = plan_capabilities("音を合成して書き出したい")

    assert "effect.media_compose" in plan.requested
    assert "effect.media_compose" in plan.missing
    assert "interact.audio_mix" in plan.requested
