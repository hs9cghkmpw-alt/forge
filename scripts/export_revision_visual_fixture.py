"""Visual Evidence の After を **本番のRevisionServiceから作る**
（FORGE-019A §7）。

---

## なぜ要るのか

019のVisual Evidenceは、Before と After の両方を**Dartに手で書いて**
いた。つまり

* Backendが実際に作るAfter
* スクリーンショットの元になるAfter

が**別々のSource of Truth**だった。Revisionのロジックを直しても
スクリーンショットは変わらないので、「この画像がその変更の証拠です」と
言えない——絵と実装がずれても誰も気付かない。

このスクリプトは Before を**本番の`RevisionService`へ通し**、返ってきた
文書をそのまま書き出す。手で書くのは Before だけになる。

## 使い方

    python scripts/export_revision_visual_fixture.py

書き出すもの:

    docs/visual-evidence/FORGE-019A/before.json
    docs/visual-evidence/FORGE-019A/after.json
    docs/visual-evidence/FORGE-019A/provenance.json
    frontend/lib/forge_019a_visual_fixture.dart

**このスクリプトの出力はcommitする。** そして
`backend/tests/test_visual_fixture_provenance.py` が「いま生成し直した
ものと一致するか」を見るので、実装が変わって絵が古くなればCIが落ちる。
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

OUTPUT_DIR = _ROOT / "docs" / "visual-evidence" / "FORGE-019A"
DART_FIXTURE = _ROOT / "frontend" / "lib" / "forge_019a_visual_fixture.dart"

#: 撮影シナリオ。**Beforeだけが手書きである。**
INTENT = "残高をもっと目立たせて"

BEFORE: dict = {
    "version": "1.12",
    "app": {"title": "わたしの家計"},
    "initial_screen_id": "home",
    "record_schemas": {
        "transaction": {"fields": [
            {"name": "name", "type": "string", "label": "項目", "required": True},
            {"name": "category", "type": "string", "label": "分類", "required": True},
            {"name": "amount", "type": "number", "label": "金額", "required": True},
        ]},
    },
    "screens": [{
        "id": "home", "title": "今月の家計",
        "state": {"records": {"type": "record_list", "schema_ref": "transaction", "value": [
            {"id": "salary", "fields": {"name": "給与", "category": "収入", "amount": 320000}},
            {"id": "rent", "fields": {"name": "家賃", "category": "支出", "amount": 85000}},
            {"id": "food", "fields": {"name": "食費", "category": "支出", "amount": 42000}},
        ]}},
        "body": {"type": "column", "id": "root", "children": [
            {"type": "section_header", "id": "summary_header", "title": "今月のサマリー",
             "style_role": "text.headline"},
            {"type": "metric_view", "id": "income", "label": "収入", "state_ref": "records",
             "value_field": "amount", "aggregate": "sum", "filter_field": "category",
             "filter_value": "収入", "unit": "円", "style_role": "metric.primary"},
            {"type": "metric_view", "id": "balance", "label": "残高", "state_ref": "records",
             "value_field": "amount", "aggregate": "sum",
             # `negative_when`は`sign_field`とセットでなければ
             # Validatorが通らない。019の手書きfixtureはここが欠けて
             # おり、**Validatorを通していない文書で撮影していた**
             # （Dart側は`fromJson`が通ることしか見ていなかった）。
             "sign_field": "category", "negative_when": "支出",
             "unit": "円", "style_role": "metric.secondary"},
            {"type": "metric_view", "id": "expense", "label": "支出", "state_ref": "records",
             "value_field": "amount", "aggregate": "sum", "filter_field": "category",
             "filter_value": "支出", "unit": "円", "style_role": "finance.expense"},
            {"type": "section_header", "id": "list_header", "title": "最近の取引",
             "style_role": "text.headline"},
            {"type": "text", "id": "transaction_1", "value": "家賃　−85,000円"},
            {"type": "text", "id": "transaction_2", "value": "食費　−42,000円"},
        ]},
    }],
}


def produce() -> dict:
    """Before を**本番の経路**へ通し、After と系譜を返す。

    差し替えているものは1つも無い。`RevisionService`・`TargetResolver`・
    `SemanticPatchEngine`・Validator・Semantic Design Critic は本番の
    実装そのままである。AIは呼ばない（局所的な意味操作なので不要）。
    """
    from app.ai.gateway.artifact_feedback import (
        default_artifact_registry,
        default_feedback_log,
    )
    from app.ai.gateway.generation_evidence import (
        GenerationRecord,
        GenerationSource,
        default_generation_store,
    )
    from app.ai.gateway.revision_evidence import default_revision_store
    from app.ai.runtime.revision_service import default_revision_service

    from app.ai.validators.schema_validator import validate_forge_document

    # **Beforeも本番のValidatorを通す。** 019は通していなかったので、
    # 不正な文書のスクリーンショットを証拠として出していた。
    before_validation = validate_forge_document(BEFORE)
    if not before_validation.valid:
        details = [e.to_dict() for e in before_validation.errors]
        msg = f"Beforeが本番のValidatorに通らない: {details}"
        raise SystemExit(msg)

    for store in (default_generation_store(), default_revision_store(),
                  default_artifact_registry(), default_feedback_log()):
        store.reset()

    generation = default_generation_store().record(GenerationRecord(
        source=GenerationSource.CURATED, domain="household_budget",
        validator_passed=True, forge_language_version="1.12",
    ))
    capability = default_artifact_registry().register(
        generation_ref=generation.ref, generation_uid=generation.uid,
        document=BEFORE,
    )
    outcome = default_revision_service().revise(
        artifact_id=capability.handle,
        seen_version_token=capability.version_token,
        document=BEFORE, change_request=INTENT,
    )
    return {
        "after": outcome.document,
        "provenance": {
            "task": "FORGE-019A",
            "intent": INTENT,
            "revision_mode": outcome.mode.value,
            "semantic_operation": outcome.operation_id,
            "semantic_target": {
                "screen_id": outcome.target.screen_id,
                "widget_id": outcome.target.widget_id,
                "semantic_identity": outcome.target.semantic_identity,
            } if outcome.target else None,
            "validator_passed": bool(outcome.validation.valid),
            "critic_passed": outcome.critic_passed,
            "patch_mode": outcome.record.patch_mode.value,
            "forge_language_version": outcome.record.forge_language_version,
            # **Revisionのuidは書かない。** プロセスごとに変わるので、
            # 生成し直すたびに差分が出て「ずれた」ように見えてしまう。
        },
    }


def _dart_string(value: str) -> str:
    """Dartの**シングルクォート**文字列にする。

    `flutter_lints`の`prefer_single_quotes`が有効なので、`json.dumps`の
    ダブルクォートをそのまま出すと`flutter analyze`（`--fatal-infos`）が
    落ちる。生成物もlintを通ること。
    """
    escaped = (
        value.replace("\\", "\\\\")
        .replace("'", "\\'")
        .replace("$", "\\$")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f"'{escaped}'"


def _dart_literal(value: object, indent: int = 0) -> str:
    pad = "  " * indent
    if isinstance(value, dict):
        if not value:
            return "<String, dynamic>{}"
        inner = "".join(
            f"{pad}  {_dart_string(str(k))}: {_dart_literal(v, indent + 1)},\n"
            for k, v in value.items()
        )
        return "<String, dynamic>{\n" + inner + pad + "}"
    if isinstance(value, list):
        if not value:
            return "<dynamic>[]"
        inner = "".join(f"{pad}  {_dart_literal(v, indent + 1)},\n" for v in value)
        return "<dynamic>[\n" + inner + pad + "]"
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return "null"
    if isinstance(value, (int, float)):
        return str(value)
    return _dart_string(str(value))


def render_dart(before: dict, after: dict, provenance: dict) -> str:
    return (
        "// GENERATED FILE — DO NOT EDIT BY HAND.\n"
        "//\n"
        "// `scripts/export_revision_visual_fixture.py` が生成する\n"
        "// (FORGE-019A §7)。\n"
        "//\n"
        "// After は**本番の RevisionService が実際に返した文書**である。\n"
        "// 手で書くと、Backendが作るAfterと絵のAfterが別々のSource of\n"
        "// Truthになり、実装を直しても絵が変わらない。\n"
        "//\n"
        f"// intent            : {provenance['intent']}\n"
        f"// revision_mode     : {provenance['revision_mode']}\n"
        f"// semantic_operation: {provenance['semantic_operation']}\n"
        f"// validator_passed  : {str(provenance['validator_passed']).lower()}\n"
        f"// critic_passed     : {str(provenance['critic_passed']).lower()}\n"
        "\n"
        "/// 撮影シナリオの Before（唯一の手書き入力）。\n"
        "Map<String, dynamic> forge019aBeforeDocument() => "
        + _dart_literal(before) + ";\n"
        "\n"
        "/// 本番の RevisionService が返した After。\n"
        "Map<String, dynamic> forge019aAfterDocument() => "
        + _dart_literal(after) + ";\n"
        "\n"
        "/// この絵がどの変更のものかを示す系譜。\n"
        "Map<String, dynamic> forge019aProvenance() => "
        + _dart_literal(provenance) + ";\n"
    )


def main() -> int:
    produced = produce()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for name, payload in (
        ("before.json", BEFORE),
        ("after.json", produced["after"]),
        ("provenance.json", produced["provenance"]),
    ):
        (OUTPUT_DIR / name).write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    DART_FIXTURE.write_text(
        render_dart(BEFORE, produced["after"], produced["provenance"]), encoding="utf-8",
    )
    print(f"wrote {OUTPUT_DIR} and {DART_FIXTURE}")
    print(json.dumps(produced["provenance"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
