"""Fix full-suite regressions exposed by the FORGE-020A4C skeptical run."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: str, old: str, new: str) -> None:
    p = ROOT / path
    content = p.read_text(encoding="utf-8")
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected one match, got {count}")
    p.write_text(content.replace(old, new, 1), encoding="utf-8")


replace_once(
    "backend/tests/test_forge_020a3b_level0_provider_integrity.py",
    '        "structure_task": ForgeTask.ENTITY_SYNTHESIS.value,\n'
    '        "runtime_backend": LocalRuntimeBackend.OLLAMA,\n',
    '        "structure_task": ForgeTask.ENTITY_SYNTHESIS.value,\n'
    '        # 020A4C: a truly passing fixture must explicitly prove that the\n'
    '        # model met the Entity contract without Forge repair, under schema mode.\n'
    '        "entity_synthesis_strict_contract_passed": True,\n'
    '        "entity_synthesis_repairs": (),\n'
    '        "structured_output_mode": "json_schema",\n'
    '        "runtime_backend": LocalRuntimeBackend.OLLAMA,\n',
)

replace_once(
    "backend/tests/test_generation_evidence.py",
    '            # `structure_provider` は enum になったので、文字列を入れられる\n'
    '            # 欄ではなくなった（merge で 020A3 側の型へ寄せた）。\n'
    '            text_fields,\n'
    '            {\n'
    '                "domain", "forge_language_version", "uid",\n'
    '                "structure_task", "entity_synthesis_rejection_reason",\n'
    '            },\n',
    '            # `entity_synthesis_structured_output_mode` (020A4C) is also a\n'
    '            # closed identifier copied from StructuredOutputMode.value; it is\n'
    '            # neither model content nor user content.\n'
    '            # `structure_provider` は enum になったので、文字列を入れられる\n'
    '            # 欄ではなくなった（merge で 020A3 側の型へ寄せた）。\n'
    '            text_fields,\n'
    '            {\n'
    '                "domain", "forge_language_version", "uid",\n'
    '                "structure_task", "entity_synthesis_rejection_reason",\n'
    '                "entity_synthesis_structured_output_mode",\n'
    '            },\n',
)

print("FORGE-020A4C full-suite fixture/privacy fixes applied")
