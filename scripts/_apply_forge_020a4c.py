"""One-shot source transformation for FORGE-020A4C.

This file is intentionally mechanical: it applies the reviewed integrity-gate
changes to the exact 020A4B code shape, writes focused regression tests, and
updates durable handoff/report records.  The companion workflow executes it on
GitHub so the change can be tested in the repository's normal CI environment.
"""
from __future__ import annotations

from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def write(path: str, content: str) -> None:
    p = ROOT / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def replace_once(path: str, old: str, new: str) -> None:
    content = read(path)
    count = content.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one match, got {count}: {old[:100]!r}")
    write(path, content.replace(old, new, 1))


def prepend_once(path: str, marker: str, block: str) -> None:
    content = read(path)
    if marker in content:
        return
    write(path, block.rstrip() + "\n\n" + content)


# ---------------------------------------------------------------------------
# 1. Canonical forge_ai evidence types
# ---------------------------------------------------------------------------
path = "forge_ai/core/semantics/structure_provenance.py"
replace_once(
    path,
    '    "EntitySynthesisAttempt",\n    "EntitySynthesisRejectionReason",\n',
    '    "EntitySynthesisAttempt",\n    "EntitySynthesisContractEvidence",\n'
    '    "EntitySynthesisRejectionReason",\n    "EntitySynthesisRepair",\n',
)
replace_once(
    path,
    "\n\n@dataclass(frozen=True)\nclass StructureProvenance:",
    '''\n\nclass EntitySynthesisRepair(str, Enum):
    """Forge が AI の Entity 出力へ加えた構造的補正。本文は持たない。"""

    IDENTIFIER_NORMALIZED = "identifier_normalized"
    UNKNOWN_TYPE_TO_STRING = "unknown_type_to_string"
    CHOICE_TO_STRING = "choice_to_string"
    REQUIRED_INJECTED = "required_injected"
    LABEL_FALLBACK = "label_fallback"
    VISUAL_STYLE_FALLBACK = "visual_style_fallback"
    FIELD_DROPPED = "field_dropped"
    CHOICE_DROPPED = "choice_dropped"
    BOUNDS_DROPPED = "bounds_dropped"
    MEASURE_DOWNGRADED = "measure_downgraded"


@dataclass(frozen=True)
class EntitySynthesisContractEvidence:
    """生の Model 出力が Entity contract を自力で満たしたかの証拠。

    Prompt・利用者本文・Model 生出力は保持しない。構造的な事実だけを持つ。
    `strict_contract_passed` は fail-closed で、観測できなければ False。
    """

    raw_schema_valid: bool = False
    repairs_applied: tuple[EntitySynthesisRepair, ...] = ()
    fields_received: int = 0
    fields_accepted: int = 0
    strict_contract_passed: bool = False
    structured_output_mode: str = ""


@dataclass(frozen=True)
class StructureProvenance:''',
)
replace_once(
    path,
    "    attempted: bool = False\n    accepted: bool = False\n    rejection_reason: EntitySynthesisRejectionReason | None = None\n",
    "    attempted: bool = False\n    accepted: bool = False\n"
    "    rejection_reason: EntitySynthesisRejectionReason | None = None\n"
    "    contract: EntitySynthesisContractEvidence = EntitySynthesisContractEvidence()\n",
)


# ---------------------------------------------------------------------------
# 2. Observe raw contract vs Forge repairs in EntitySynthesizer
# ---------------------------------------------------------------------------
path = "forge_ai/core/ir/entity_synthesizer.py"
replace_once(
    path,
    "from forge_ai.core.orchestration.cognitive_context import (\n"
    "    EntitySynthesisAttempt,\n    EntitySynthesisRejectionReason,\n)\n",
    "from forge_ai.core.orchestration.cognitive_context import (\n"
    "    EntitySynthesisAttempt,\n    EntitySynthesisRejectionReason,\n)\n"
    "from forge_ai.core.semantics.structure_provenance import (\n"
    "    EntitySynthesisContractEvidence,\n    EntitySynthesisRepair,\n)\n",
)
helper = r'''

def _entity_contract_evidence(
    structured: object, *, structured_output_mode: str = ""
) -> EntitySynthesisContractEvidence:
    """AI 生出力と canonical Entity contract の差を privacy-safe に測る。

    Product sanitizer はこの後そのまま動く。ここでは「最終的に使えたか」
    ではなく「Model 自身が修復なしで契約を満たしたか」を測る。
    """
    if not isinstance(structured, dict) or not structured:
        return EntitySynthesisContractEvidence(structured_output_mode=structured_output_mode)

    repairs: list[EntitySynthesisRepair] = []

    def note(repair: EntitySynthesisRepair) -> None:
        if repair not in repairs:
            repairs.append(repair)

    raw_entity_name = structured.get("entity_name")
    entity_name = _sanitize_identifier(raw_entity_name)
    if entity_name is None or raw_entity_name != entity_name:
        note(EntitySynthesisRepair.IDENTIFIER_NORMALIZED)

    raw_entity_label = structured.get("entity_label")
    if _sanitize_label(raw_entity_label) != raw_entity_label:
        note(EntitySynthesisRepair.LABEL_FALLBACK)

    visual_style = structured.get("visual_style")
    if not isinstance(visual_style, str) or visual_style not in _VALID_VISUAL_STYLES:
        note(EntitySynthesisRepair.VISUAL_STYLE_FALLBACK)

    raw_fields = structured.get("fields")
    fields_received = len(raw_fields) if isinstance(raw_fields, list) else 0
    if not isinstance(raw_fields, list) or not raw_fields:
        note(EntitySynthesisRepair.FIELD_DROPPED)
        return EntitySynthesisContractEvidence(
            raw_schema_valid=False,
            repairs_applied=tuple(repairs),
            fields_received=fields_received,
            fields_accepted=0,
            strict_contract_passed=False,
            structured_output_mode=structured_output_mode,
        )

    seen: set[str] = set()
    valid_field_count = 0
    any_required = False
    for index, raw in enumerate(raw_fields):
        if index >= _MAX_FIELDS:
            note(EntitySynthesisRepair.FIELD_DROPPED)
            continue
        if not isinstance(raw, dict):
            note(EntitySynthesisRepair.FIELD_DROPPED)
            continue

        raw_name = raw.get("name")
        name = _sanitize_identifier(raw_name)
        if name is None or name in seen or name in _RESERVED_FIELD_NAMES:
            note(EntitySynthesisRepair.FIELD_DROPPED)
            continue
        if raw_name != name:
            note(EntitySynthesisRepair.IDENTIFIER_NORMALIZED)
        seen.add(name)
        valid_field_count += 1

        raw_label = raw.get("label")
        if _sanitize_label(raw_label) != raw_label:
            note(EntitySynthesisRepair.LABEL_FALLBACK)

        raw_type = raw.get("type")
        field_type = _VALID_FIELD_TYPES.get(raw_type) if isinstance(raw_type, str) else None
        if field_type is None:
            note(EntitySynthesisRepair.UNKNOWN_TYPE_TO_STRING)

        required = raw.get("required")
        if required is True:
            any_required = True
        elif required is not False:
            # Non-bool is silently treated as False and can later cause injection.
            note(EntitySynthesisRepair.REQUIRED_INJECTED)

        raw_choices = raw.get("choices")
        sanitized_choices = _sanitize_choices(raw_choices)
        if isinstance(raw_choices, list):
            exact_choices = tuple(
                x for x in raw_choices if isinstance(x, str) and x.strip()
            )
            if sanitized_choices != exact_choices:
                note(EntitySynthesisRepair.CHOICE_DROPPED)
        elif raw_choices not in (None, ()):
            note(EntitySynthesisRepair.CHOICE_DROPPED)

        if field_type == FieldType.CHOICE and len(sanitized_choices) < _MIN_CHOICES:
            note(EntitySynthesisRepair.CHOICE_TO_STRING)
        elif field_type != FieldType.CHOICE and sanitized_choices:
            note(EntitySynthesisRepair.CHOICE_DROPPED)

        if field_type == FieldType.NUMBER:
            raw_min, raw_max = raw.get("min_value"), raw.get("max_value")
            sanitized_bounds = _sanitize_bounds(raw_min, raw_max, field_type=field_type)
            if raw_min is not None or raw_max is not None:
                raw_pair = (
                    float(raw_min) if isinstance(raw_min, (int, float)) and not isinstance(raw_min, bool) else None,
                    float(raw_max) if isinstance(raw_max, (int, float)) and not isinstance(raw_max, bool) else None,
                )
                if sanitized_bounds != raw_pair:
                    note(EntitySynthesisRepair.BOUNDS_DROPPED)

            raw_measure = raw.get("measure")
            if not isinstance(raw_measure, str) or raw_measure.strip().lower() not in _VALID_MEASURES:
                note(EntitySynthesisRepair.MEASURE_DOWNGRADED)
        elif raw.get("measure") not in (None, "unknown"):
            note(EntitySynthesisRepair.MEASURE_DOWNGRADED)

    if valid_field_count and not any_required:
        note(EntitySynthesisRepair.REQUIRED_INJECTED)

    raw_schema_valid = (
        entity_name is not None
        and isinstance(raw_entity_label, str) and bool(raw_entity_label.strip())
        and isinstance(visual_style, str) and visual_style in _VALID_VISUAL_STYLES
        and valid_field_count > 0
        and any_required
        and not repairs
    )
    return EntitySynthesisContractEvidence(
        raw_schema_valid=raw_schema_valid,
        repairs_applied=tuple(repairs),
        fields_received=fields_received,
        fields_accepted=0,
        strict_contract_passed=raw_schema_valid and not repairs,
        structured_output_mode=structured_output_mode,
    )
'''
replace_once(path, "\n\nclass EntitySynthesizer:", helper + "\n\nclass EntitySynthesizer:")
replace_once(
    path,
    "        response = self._provider.complete(prompt)\n"
    "        structured = response.structured\n"
    "        if not isinstance(structured, dict) or not structured:\n"
    "            return None, EntitySynthesisAttempt(True, False, EntitySynthesisRejectionReason.EMPTY_OUTPUT)\n"
    "        if _sanitize_identifier(structured.get(\"entity_name\")) is None:\n"
    "            return None, EntitySynthesisAttempt(True, False, EntitySynthesisRejectionReason.INVALID_IDENTIFIER)\n"
    "        spec = self._spec_from_structured(structured)\n"
    "        if spec is None:\n"
    "            return None, EntitySynthesisAttempt(True, False, EntitySynthesisRejectionReason.NO_VALID_FIELDS)\n"
    "        return spec, EntitySynthesisAttempt(True, True, None)\n",
    "        response = self._provider.complete(prompt)\n"
    "        structured = response.structured\n"
    "        mode = str(getattr(self._provider, \"last_structured_output_mode\", \"\") or \"\")\n"
    "        contract = _entity_contract_evidence(structured, structured_output_mode=mode)\n"
    "        if not isinstance(structured, dict) or not structured:\n"
    "            return None, EntitySynthesisAttempt(\n"
    "                True, False, EntitySynthesisRejectionReason.EMPTY_OUTPUT, contract\n"
    "            )\n"
    "        if _sanitize_identifier(structured.get(\"entity_name\")) is None:\n"
    "            return None, EntitySynthesisAttempt(\n"
    "                True, False, EntitySynthesisRejectionReason.INVALID_IDENTIFIER, contract\n"
    "            )\n"
    "        spec = self._spec_from_structured(structured)\n"
    "        if spec is None:\n"
    "            return None, EntitySynthesisAttempt(\n"
    "                True, False, EntitySynthesisRejectionReason.NO_VALID_FIELDS, contract\n"
    "            )\n"
    "        contract = replace(contract, fields_accepted=len(spec.field_specs))\n"
    "        return spec, EntitySynthesisAttempt(True, True, None, contract)\n",
)


# ---------------------------------------------------------------------------
# 3. Track actual structured-output mode through provider/router/bridge
# ---------------------------------------------------------------------------
path = "backend/app/ai/foundation/openai_compatible.py"
replace_once(
    path,
    "        self._extra_headers = dict(extra_headers or {})\n",
    "        self._extra_headers = dict(extra_headers or {})\n"
    "        self._last_structured_output_mode = \"\"\n",
)
replace_once(
    path,
    "    # -- Deadline(011 §4) -------------------------------------------------\n",
    "    @property\n"
    "    def last_structured_output_mode(self) -> str:\n"
    "        \"\"\"実際に受理された応答を生成した mode。未実行/失敗は空。\"\"\"\n"
    "        return self._last_structured_output_mode\n\n"
    "    # -- Deadline(011 §4) -------------------------------------------------\n",
)
replace_once(
    path,
    "        store = default_capability_store()\n",
    "        self._last_structured_output_mode = \"\"\n"
    "        store = default_capability_store()\n",
)
replace_once(
    path,
    "        try:\n"
    "            return extract_json_object(content, error_type=self._response_format_error_type())\n"
    "        except Exception:\n"
    "            if not response_schema:\n"
    "                raise\n"
    "            # 応答は返ったが構造が壊れていた場合の**1回だけ**の再試行。\n"
    "            # 小さいモデルでは頻繁に起きるため即失敗にせず、緩い\n"
    "            # `json_object`で取り直す。2回目は無い。\n"
    "            retried = self._chat(prompt, {}, StructuredOutputMode.JSON_OBJECT)\n"
    "            return extract_json_object(retried, error_type=self._response_format_error_type())\n",
    "        try:\n"
    "            parsed = extract_json_object(\n"
    "                content, error_type=self._response_format_error_type()\n"
    "            )\n"
    "            self._last_structured_output_mode = mode.value\n"
    "            return parsed\n"
    "        except Exception:\n"
    "            if not response_schema:\n"
    "                raise\n"
    "            # 応答は返ったが構造が壊れていた場合の**1回だけ**の再試行。\n"
    "            # 小さいモデルでは頻繁に起きるため即失敗にせず、緩い\n"
    "            # `json_object`で取り直す。2回目は無い。\n"
    "            retried = self._chat(prompt, {}, StructuredOutputMode.JSON_OBJECT)\n"
    "            parsed = extract_json_object(\n"
    "                retried, error_type=self._response_format_error_type()\n"
    "            )\n"
    "            self._last_structured_output_mode = StructuredOutputMode.JSON_OBJECT.value\n"
    "            return parsed\n",
)

path = "backend/app/ai/gateway/ai_router.py"
replace_once(path, "    model: str = \"\"\n", "    model: str = \"\"\n    structured_output_mode: str = \"\"\n")
replace_once(
    path,
    "        return RouteAttempt(provider=provider, ok=True, latency_ms=latency, model=model), value\n",
    "        return RouteAttempt(\n"
    "            provider=provider, ok=True, latency_ms=latency, model=model,\n"
    "            structured_output_mode=str(\n"
    "                getattr(bound, \"last_structured_output_mode\", \"\") or \"\"\n"
    "            ),\n"
    "        ), value\n",
)
replace_once(
    path,
    "    @property\n    def used_fallback(self) -> bool:\n",
    "    @property\n"
    "    def structured_output_mode(self) -> str:\n"
    "        \"\"\"成功した試行が実際に使った構造化出力 mode。\"\"\"\n"
    "        for attempt in reversed(self.attempts):\n"
    "            if attempt.ok:\n"
    "                return attempt.structured_output_mode\n"
    "        return \"\"\n\n"
    "    @property\n    def used_fallback(self) -> bool:\n",
)
replace_once(
    path,
    "    last_provider_used: str | None = field(default=None, init=False)\n",
    "    last_provider_used: str | None = field(default=None, init=False)\n"
    "    last_structured_output_mode: str = field(default=\"\", init=False)\n",
)
replace_once(
    path,
    "        self.last_provider_used = result.provider_used\n"
    "        if result.experience_ref:\n",
    "        self.last_provider_used = result.provider_used\n"
    "        self.last_structured_output_mode = result.structured_output_mode\n"
    "        if result.experience_ref:\n",
)

path = "backend/app/ai/runtime/forge_ai_provider_bridge.py"
replace_once(
    path,
    "    def complete(self, prompt: Prompt) -> ProviderResponse:\n",
    "    @property\n"
    "    def last_structured_output_mode(self) -> str:\n"
    "        \"\"\"直近の呼び出しで実際に受理された構造化出力 mode。\"\"\"\n"
    "        return str(\n"
    "            getattr(self._llm_adapter, \"last_structured_output_mode\", \"\") or \"\"\n"
    "        )\n\n"
    "    def complete(self, prompt: Prompt) -> ProviderResponse:\n",
)


# ---------------------------------------------------------------------------
# 4. Durable GenerationRecord propagation + serializer debt
# ---------------------------------------------------------------------------
path = "backend/app/ai/gateway/generation_evidence.py"
marker = "    design_language_roles: tuple[str, ...] = ()\n"
insert = '''    entity_synthesis_raw_schema_valid: bool = False
    entity_synthesis_repairs: tuple[str, ...] = ()
    entity_synthesis_fields_received: int = 0
    entity_synthesis_fields_accepted: int = 0
    entity_synthesis_strict_contract_passed: bool = False
    entity_synthesis_structured_output_mode: str = ""
    """020A4C: Model 自身の契約能力と Forge repair を分離した構造 Evidence。

    生 Prompt / 生 Model 出力 / 利用者本文は持たない。未知は fail-closed。
    """

'''
replace_once(path, marker, insert + marker)
replace_once(
    path,
    '            "capabilities": list(self.capabilities),\n',
    '            "capabilities": list(self.capabilities),\n'
    '            "entity_synthesis_attempted": self.entity_synthesis_attempted,\n'
    '            "entity_synthesis_accepted": self.entity_synthesis_accepted,\n'
    '            "entity_synthesis_rejection_reason": self.entity_synthesis_rejection_reason,\n'
    '            "entity_synthesis_raw_schema_valid": self.entity_synthesis_raw_schema_valid,\n'
    '            "entity_synthesis_repairs": list(self.entity_synthesis_repairs),\n'
    '            "entity_synthesis_fields_received": self.entity_synthesis_fields_received,\n'
    '            "entity_synthesis_fields_accepted": self.entity_synthesis_fields_accepted,\n'
    '            "entity_synthesis_strict_contract_passed": self.entity_synthesis_strict_contract_passed,\n'
    '            "entity_synthesis_structured_output_mode": self.entity_synthesis_structured_output_mode,\n',
)

path = "backend/app/ai/runtime/prompt_pipeline.py"
replace_once(
    path,
    "    synthesis_attempt = getattr(context, \"entity_synthesis_attempt\", None)\n"
    "    stored = store.record(\n",
    "    synthesis_attempt = getattr(context, \"entity_synthesis_attempt\", None)\n"
    "    synthesis_contract = getattr(synthesis_attempt, \"contract\", None)\n"
    "    stored = store.record(\n",
)
replace_once(
    path,
    "            entity_synthesis_rejection_reason=(\n"
    "                getattr(getattr(synthesis_attempt, \"rejection_reason\", None), \"value\", None)\n"
    "            ),\n",
    "            entity_synthesis_rejection_reason=(\n"
    "                getattr(getattr(synthesis_attempt, \"rejection_reason\", None), \"value\", None)\n"
    "            ),\n"
    "            entity_synthesis_raw_schema_valid=bool(\n"
    "                getattr(synthesis_contract, \"raw_schema_valid\", False)\n"
    "            ),\n"
    "            entity_synthesis_repairs=tuple(\n"
    "                getattr(item, \"value\", str(item))\n"
    "                for item in (getattr(synthesis_contract, \"repairs_applied\", ()) or ())\n"
    "            ),\n"
    "            entity_synthesis_fields_received=int(\n"
    "                getattr(synthesis_contract, \"fields_received\", 0) or 0\n"
    "            ),\n"
    "            entity_synthesis_fields_accepted=int(\n"
    "                getattr(synthesis_contract, \"fields_accepted\", 0) or 0\n"
    "            ),\n"
    "            entity_synthesis_strict_contract_passed=bool(\n"
    "                getattr(synthesis_contract, \"strict_contract_passed\", False)\n"
    "            ),\n"
    "            entity_synthesis_structured_output_mode=str(\n"
    "                getattr(synthesis_contract, \"structured_output_mode\", \"\") or \"\"\n"
    "            ),\n",
)


# ---------------------------------------------------------------------------
# 5. Real Local Level 0 fail-closed gate
# ---------------------------------------------------------------------------
path = "backend/app/ai/gateway/local_model_evidence.py"
replace_once(
    path,
    "    domain_resolution: str = \"\"\n",
    "    entity_synthesis_strict_contract_passed: bool = False\n"
    "    entity_synthesis_repairs: tuple[str, ...] = ()\n"
    "    structured_output_mode: str = \"\"\n"
    "    \"\"\"020A4C: Model 自身の契約成功と Forge repair / mode provenance。\"\"\"\n\n"
    "    domain_resolution: str = \"\"\n",
)
replace_once(
    path,
    "        if not self.observed_tasks:\n",
    "        if not self.entity_synthesis_strict_contract_passed:\n"
    "            reasons.append(\"Entity Synthesis の生出力が strict contract を満たしていない\")\n"
    "        if self.entity_synthesis_repairs:\n"
    "            reasons.append(\n"
    "                \"Forge の Entity sanitizer による補正が必要だった\"
"
    "                f\"（{', '.join(self.entity_synthesis_repairs)}）\"\n"
    "            )\n"
    "        if self.structured_output_mode not in {\"strict_json_schema\", \"json_schema\"}:\n"
    "            reasons.append(\n"
    "                \"厳格な schema mode で受理された応答ではない\"
"
    "                f\"（structured_output_mode={self.structured_output_mode or '(記録なし)'}）\"\n"
    "            )\n\n"
    "        if not self.observed_tasks:\n",
)
replace_once(
    path,
    '            "structure_task": self.structure_task,\n',
    '            "structure_task": self.structure_task,\n'
    '            "entity_synthesis_strict_contract_passed": self.entity_synthesis_strict_contract_passed,\n'
    '            "entity_synthesis_repairs": list(self.entity_synthesis_repairs),\n'
    '            "structured_output_mode": self.structured_output_mode,\n',
)

path = "scripts/verify_local_model_level0.py"
replace_once(
    path,
    "    structure_task = \"\"\n"
    "    validator_passed = False\n",
    "    structure_task = \"\"\n"
    "    entity_synthesis_strict_contract_passed = False\n"
    "    entity_synthesis_repairs: tuple[str, ...] = ()\n"
    "    structured_output_mode = \"\"\n"
    "    validator_passed = False\n",
)
replace_once(
    path,
    "                structure_provider = records[-1].structure_provider\n"
    "                structure_task = records[-1].structure_task\n",
    "                structure_provider = records[-1].structure_provider\n"
    "                structure_task = records[-1].structure_task\n"
    "                entity_synthesis_strict_contract_passed = (\n"
    "                    records[-1].entity_synthesis_strict_contract_passed\n"
    "                )\n"
    "                entity_synthesis_repairs = records[-1].entity_synthesis_repairs\n"
    "                structured_output_mode = (\n"
    "                    records[-1].entity_synthesis_structured_output_mode\n"
    "                )\n",
)
replace_once(
    path,
    "        structure_task=structure_task,\n"
    "        host_id=str(host[\"host_id\"]),\n",
    "        structure_task=structure_task,\n"
    "        entity_synthesis_strict_contract_passed=(\n"
    "            entity_synthesis_strict_contract_passed\n"
    "        ),\n"
    "        entity_synthesis_repairs=entity_synthesis_repairs,\n"
    "        structured_output_mode=structured_output_mode,\n"
    "        host_id=str(host[\"host_id\"]),\n",
)


# ---------------------------------------------------------------------------
# 6. Focused regression / mutation tests
# ---------------------------------------------------------------------------
write(
    "forge_ai/tests/test_forge_020a4c_entity_contract_evidence.py",
    textwrap.dedent(r'''
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
    ''').lstrip(),
)

write(
    "backend/tests/test_forge_020a4c_real_structure_integrity.py",
    textwrap.dedent(r'''
        from app.ai.foundation.openai_compatible import OpenAICompatibleAdapter
        from app.ai.gateway.benchmark_evidence import Verification
        from app.ai.gateway.capability_evidence import GenerationStructureSource, StructureProvider
        from app.ai.gateway.generation_evidence import GenerationRecord, GenerationSource
        from app.ai.gateway.learning_events import Deployment
        from app.ai.gateway.local_model_evidence import LocalRuntimeBackend, RealLocalModelRun
        from app.ai.gateway.tasks import ForgeTask


        def _passing_run(**changes) -> RealLocalModelRun:
            values = dict(
                provider="local",
                model="qwen-test",
                task=ForgeTask.ENTITY_SYNTHESIS,
                observed_tasks=(ForgeTask.ENTITY_SYNTHESIS,),
                structure_source=GenerationStructureSource.AI_ENTITY_SYNTHESIS,
                structure_provider=StructureProvider.LOCAL,
                structure_task=ForgeTask.ENTITY_SYNTHESIS.value,
                entity_synthesis_strict_contract_passed=True,
                entity_synthesis_repairs=(),
                structured_output_mode="json_schema",
                domain_resolution="generated",
                runtime_backend=LocalRuntimeBackend.OLLAMA,
                model_id="qwen-test",
                deployment=Deployment.LOCAL,
                latency_ms=1.0,
                structured_output_ok=True,
                validator_passed=True,
                generation_evidence_uid="generation-uid",
                generation_source=GenerationSource.LOCAL_AI,
                verification=Verification.REAL,
            )
            values.update(changes)
            return RealLocalModelRun(**values)


        def test_repaired_output_cannot_count_even_if_validator_passes():
            run = _passing_run(
                entity_synthesis_strict_contract_passed=False,
                entity_synthesis_repairs=("unknown_type_to_string",),
            )
            assert run.validator_passed is True
            assert run.counts_as_real_local is False
            assert any("sanitizer" in reason for reason in run.why_not_counted())


        def test_unknown_contract_evidence_fails_closed():
            assert _passing_run(entity_synthesis_strict_contract_passed=False).counts_as_real_local is False


        def test_json_object_fallback_does_not_prove_strict_level0_contract():
            assert _passing_run(structured_output_mode="json_object").counts_as_real_local is False


        def test_strict_unrepaired_run_can_pass_integrity_predicate():
            assert _passing_run().counts_as_real_local is True


        def test_generation_record_serializer_keeps_diagnosis_without_raw_content():
            record = GenerationRecord(
                source=GenerationSource.LOCAL_AI,
                domain="generic",
                validator_passed=True,
                entity_synthesis_attempted=True,
                entity_synthesis_accepted=True,
                entity_synthesis_raw_schema_valid=False,
                entity_synthesis_repairs=("required_injected",),
                entity_synthesis_fields_received=2,
                entity_synthesis_fields_accepted=2,
                entity_synthesis_strict_contract_passed=False,
                entity_synthesis_structured_output_mode="json_schema",
            )
            payload = record.to_dict()
            assert payload["entity_synthesis_attempted"] is True
            assert payload["entity_synthesis_repairs"] == ["required_injected"]
            assert payload["entity_synthesis_strict_contract_passed"] is False
            assert "prompt" not in payload
            assert "raw_output" not in payload
            assert "user_text" not in payload


        def test_openai_compatible_records_actual_json_object_mode(monkeypatch):
            adapter = OpenAICompatibleAdapter(
                provider_name="local", base_url="http://unused", model="qwen-test"
            )
            monkeypatch.setattr(adapter, "_chat", lambda *args, **kwargs: '{"ok": true}')
            assert adapter.complete_structured("x", {}) == {"ok": True}
            assert adapter.last_structured_output_mode == "json_object"
    ''').lstrip(),
)


# ---------------------------------------------------------------------------
# 7. Durable report / handoff / debt / changelog
# ---------------------------------------------------------------------------
report = r'''# FORGE-020A4C — Real Structure Integrity Gate

Status: **IMPLEMENTED — CI verification pending at creation time**

## Why
020A4B proved that `ENTITY_SYNTHESIS` can traverse the production AIRouter path, but a second false-PASS path remained: real Local/Cloud Entity output is sanitized before IR/Validator. A repaired artifact could therefore be valid even when the model itself did not satisfy the Entity contract.

## What changed
- Added privacy-safe `EntitySynthesisContractEvidence` and closed `EntitySynthesisRepair` vocabulary.
- Product sanitization remains enabled; model contract ability and Forge repair ability are now separate facts.
- `EntitySynthesizer` observes raw structural violations before sanitization and propagates evidence through the existing `EntitySynthesisAttempt -> CognitiveContext -> GenerationRecord` path.
- `GenerationRecord.to_dict()` now serializes the existing attempt diagnosis plus 020A4C contract fields; no prompt/raw model output/user text is stored.
- OpenAI-compatible providers record the **actual accepted structured-output mode**. AIRouter and ForgeAIProviderBridge carry that observation to Entity Synthesis.
- Real Local Level 0 now fails closed unless the Entity output passed without Forge repair and was accepted under strict/json-schema mode.
- `JSON_OBJECT`/prompt fallback remains valid product behavior but is not sufficient evidence of strict Local model contract ability.

## Mutation intent covered
- unknown type -> STRING cannot count as Real Local
- required injection cannot count
- choice downgrade cannot count
- invalid visual style / label fallback are observable repairs
- Validator PASS alone cannot count a repaired run
- unknown contract evidence fails closed
- JSON_OBJECT fallback cannot prove strict contract compliance
- serializer exposes only closed structural diagnosis

## Truth boundaries
- Mock preflight is a **wiring proof**, not model semantic-quality proof.
- A usable repaired app may still be returned to the user; that does not become a Local AI positive.
- Real Local Model runs remain **0** until a genuine `qwen2.5:7b-instruct` production structural run satisfies the new gate.
- Do not run the real Qwen Level 0 until exact-SHA CI for this task is green.

## Dataset / training handoff
Future Generation Episodes / JSONL must keep `model_output_contract`, `forge_repairs`, and `final_artifact` separate. Forge-repaired output must not be mislabeled as an AI positive for SFT/preference/QLoRA candidates. QLoRA itself is not part of this task.

## Base evidence
- Base SHA: `e659181427224242458561a06a32af01b8295023`
- Base CI: run `33175691427` = success (4 jobs green, independently checked before implementation).

## Next
1. Confirm exact final implementation SHA CI is all green.
2. Record the final SHA/run in HANDOFF and this report.
3. Only then, on a machine with real Ollama + `qwen2.5:7b-instruct`, run preflight followed by `scripts/verify_local_model_level0.py`.
4. A repaired run must remain rejected; only unrepaired strict-contract Local structure generation may change Real Local Model runs from 0 to 1.
'''
write("docs/reports/FORGE-020A4C-REAL-STRUCTURE-INTEGRITY-report.md", report)

handoff = r'''# HANDOFF UPDATE — FORGE-020A4C Real Structure Integrity Gate

**Current task:** FORGE-020A4C — separate raw Local model contract ability from Forge repair ability.

- Base SHA: `e659181427224242458561a06a32af01b8295023`.
- Base CI run `33175691427`: SUCCESS / 4 jobs green.
- Implementation: contract-repair evidence + structured-output mode provenance + fail-closed Level 0 gate + serializer diagnosis + mutation-oriented tests.
- Mock preflight proves wiring only. It is not semantic/model-quality evidence.
- Normal product sanitization remains; repaired output can still make a usable app, but **cannot count as Real Local Level 0**.
- Real Local Model runs: **0** until a genuine unrepaired strict-contract Local structural run passes.
- **Do not run real Qwen Level 0 until this task's exact-SHA CI is green.**
- Detailed report: `docs/reports/FORGE-020A4C-REAL-STRUCTURE-INTEGRITY-report.md`.

### Next operator checklist
1. Read this HANDOFF and the 020A4C report before editing.
2. Verify branch HEAD and exact-SHA CI; do not trust chat-only claims.
3. If green, use a real Local runtime machine for preflight, then Qwen Level 0.
4. Preserve the distinction: model contract -> Forge repairs -> final artifact.
5. Never promote Forge-repaired output as an AI positive in future Dataset/JSONL/SFT/preference/QLoRA work.

---
'''
prepend_once("docs/HANDOFF.md", "HANDOFF UPDATE — FORGE-020A4C", handoff)
prepend_once(
    "CHANGELOG.md",
    "FORGE-020A4C — Real Structure Integrity Gate",
    """# FORGE-020A4C — Real Structure Integrity Gate\n\n"
    "- Separate raw Entity model-contract success from Forge sanitizer repairs.\n"
    "- Propagate actual structured-output mode provenance.\n"
    "- Real Local Level 0 now rejects repaired/unknown/non-schema-mode structural outputs.\n"
    "- Serialize privacy-safe Entity Synthesis diagnosis for durable learning evidence.\n""",
)
prepend_once(
    "TECH_DEBT.md",
    "TD020A4C",
    """# TD020A4C — Model contract vs Forge repair provenance\n\n"
    "**Resolved in FORGE-020A4C.** Previously Entity Synthesis could sanitize a real model's invalid structure and then satisfy Validator/Level0 evidence, conflating product robustness with model ability. Contract evidence and repair provenance now fail closed for Real Local Level 0. Structured-output fallback mode is also recorded. Future datasets must preserve model-output / Forge-repair / final-artifact separation.\n""",
)

print("FORGE-020A4C transformation applied")
