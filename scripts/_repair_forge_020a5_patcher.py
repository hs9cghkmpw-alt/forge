from pathlib import Path

p = Path(__file__).resolve().parent / "_apply_forge_020a5_entity_schema.py"
text = p.read_text(encoding="utf-8")
marker = "# Extend existing 020A4C contract tests with the same-category hole discovered"
if marker not in text:
    raise SystemExit("patcher marker missing")
prefix = text.split(marker, 1)[0]
lines = [
    "# Extend existing 020A4C contract tests with the same-category hole discovered",
    "# by skeptical review: 7 choices is inside the product sanitizer ceiling but",
    "# outside the strict model contract.",
    'contract_test = ROOT / "forge_ai/tests/test_forge_020a4c_entity_contract_evidence.py"',
    'text = contract_test.read_text(encoding="utf-8")',
    'if "test_seven_choices_cannot_masquerade_as_strict_model_success" in text:',
    '    raise SystemExit("choice-cardinality test already present unexpectedly")',
    'extra = (',
    '    "\\n\\ndef test_seven_choices_cannot_masquerade_as_strict_model_success():\\n"',
    '    "    raw = _valid()\\n"',
    '    "    raw[\\\"fields\\\"][0].update({\\n"',
    '    "        \\\"type\\\": \\\"choice\\\",\\n"',
    '    "        \\\"choices\\\": [\\\"a\\\", \\\"b\\\", \\\"c\\\", \\\"d\\\", \\\"e\\\", \\\"f\\\", \\\"g\\\"],\\n"',
    '    "    })\\n"',
    '    "    ev = _entity_contract_evidence(raw, structured_output_mode=\\\"json_schema\\\")\\n"',
    '    "    assert ev.strict_contract_passed is False\\n"',
    ')',
    'contract_test.write_text(text.rstrip() + extra + "\\n", encoding="utf-8")',
    "",
    'print("FORGE-020A5 entity schema contract patch applied")',
    "",
]
p.write_text(prefix + "\n".join(lines), encoding="utf-8")
print("FORGE-020A5 patcher repaired")
