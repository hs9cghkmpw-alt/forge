"""Generated UI Quality Gate v2 — **撮影対象を本番から作る**
(`docs/spec/GENERATED-UI-QUALITY-GATE-V2.md`、2026-08-26)。

---

## なぜ本番で作るのか

Quality Gate が測るのは「Forge が実際に出す画面」である。手書きの
Document を撮っても、実装を直したときに絵が追随しない
（019A §7 で一度踏んだ形）。

だから `/api/v1/ai/generate` を**本番の経路で**叩き、返ってきた Document
をそのまま撮影対象にする。

## 通らなかった Need を隠さない

Need によっては、Forge が**確認を返す**（`needs_confirmation`）。
これは失敗ではなく、「その能力が無いので聞き返した」という正しい
振る舞いである（Capability Layer）。

**それを撮影対象から外し、かつ manifest に理由ごと残す。**
通ったものだけ並べて「8種類に対応した」と書くと嘘になる。

## 出力

```
docs/evidence/quality-gate-v2/manifest.json   何が通り、何が通らなかったか
docs/evidence/quality-gate-v2/<key>.json      通った Document
frontend/lib/forge_quality_gate_fixture.dart  撮影ハーネスが読む生成物
```
"""

from __future__ import annotations

import json
import os
import pathlib
import sys

_ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT))
sys.path.insert(0, str(_ROOT / "backend"))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")

OUTPUT_DIR = _ROOT / "docs" / "evidence" / "quality-gate-v2"
DART_FIXTURE = _ROOT / "frontend" / "lib" / "forge_quality_gate_fixture.dart"

#: 性格を散らした Need（spec §2）。**専用Templateは用意しない。**
NEEDS: tuple[tuple[str, str, str], ...] = (
    ("finance", "家計",
     "毎日の収入と支出を記録して残高を見たい"),
    ("worklog", "業務/Todo",
     "今日やる作業を登録して、終わったものを消していきたい"),
    ("kids", "子ども向け",
     "子どもが朝の支度をひとつずつチェックできるようにしたい"),
    ("photo", "写真中心",
     "旅行の写真を日付ごとに残してメモを付けたい"),
    ("map", "地図/探索",
     "釣った場所を地図に残して魚の種類を記録したい"),
    ("game", "ゲーム風",
     "植物を育てながら音を組み合わせるゲームを作りたい"),
    ("analytics", "データ分析",
     "部署ごとの売上を月別に集計してグラフで比べたい"),
    ("study", "学習アプリ",
     "英単語を出題して、正解率の推移を見たい"),
)


def _widget_types(node: object) -> set[str]:
    found: set[str] = set()
    if isinstance(node, dict):
        kind = node.get("type")
        if isinstance(kind, str):
            found.add(kind)
        for value in node.values():
            found |= _widget_types(value)
    elif isinstance(node, list):
        for value in node:
            found |= _widget_types(value)
    return found


def _dart_string(value: str) -> str:
    """Dart の**シングルクォート**文字列（`prefer_single_quotes`）。"""
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


def render_dart(documents: dict[str, dict]) -> str:
    entries = "".join(
        f"  {_dart_string(key)}: {_dart_literal(doc, 1)},\n"
        for key, doc in sorted(documents.items())
    )
    return (
        "// GENERATED FILE — DO NOT EDIT BY HAND.\n"
        "//\n"
        "// `scripts/export_quality_gate_fixtures.py` が本番の\n"
        "// `POST /api/v1/ai/generate` を叩いて生成する\n"
        "// (Generated UI Quality Gate v2)。\n"
        "//\n"
        "// **手で直さないこと。** 直すべきは生成側であり、ここを直すと\n"
        "// 「Backendが作る画面」と「撮影した画面」が別物になる。\n"
        "\n"
        "/// 撮影対象の Forge Document。キーは Need の識別子。\n"
        "const Map<String, Map<String, dynamic>> forgeQualityGateDocuments =\n"
        "    <String, Map<String, dynamic>>{\n"
        f"{entries}"
        "};\n"
    )


def main() -> int:
    from fastapi.testclient import TestClient

    from app.main import app

    client = TestClient(app)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    documents: dict[str, dict] = {}
    manifest: list[dict[str, object]] = []

    for key, label, need in NEEDS:
        response = client.post(
            "/api/v1/ai/generate",
            json={"input": {"natural_language": need,
                            "generation_options": {"provider": "mock"}}},
        )
        body = response.json()
        status = body.get("status")

        if response.status_code != 200 or status != "success":
            # **通らなかったものを隠さない**（spec §2）。
            reason = "http_error"
            detail = body.get("error") or {}
            if status == "needs_confirmation":
                reason = "capability_gap"
                detail = {
                    "question": (body.get("confirmation") or {}).get("question", ""),
                    "reached_stage": (body.get("confirmation") or {}).get(
                        "reached_stage", "",
                    ),
                }
            manifest.append({
                "key": key, "label": label, "need": need,
                "rendered": False, "reason": reason, "detail": detail,
            })
            print(f"  ✗ {key:10s} {label:10s} {reason}")
            continue

        result = body["result"]
        document = result["forge_document"]
        diagnostics = result.get("diagnostics") or {}
        trace = diagnostics.get("decision_trace") or []
        template = next(
            (e.get("decision") for e in trace
             if e.get("stage") == "final_template_selection"), "",
        )
        types = sorted(_widget_types(document.get("screens", [])))

        documents[key] = document
        (OUTPUT_DIR / f"{key}.json").write_text(
            json.dumps(document, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        manifest.append({
            "key": key, "label": label, "need": need,
            "rendered": True,
            "validator_passed": bool(result["validation"]["valid"]),
            "domain": (diagnostics.get("domain_classification") or {}).get(
                "primary_domain", "",
            ),
            "template": template,
            "provider_used": diagnostics.get("provider_used", ""),
            "screen_count": len(document.get("screens", [])),
            "widget_types": types,
            # **作れなかったものを manifest へ残す**（020A2 §4/§5）。
            #
            # 撮った絵だけを見ると「一覧と入力がある普通のアプリ」に
            # 見える。**求められたのに出せなかったもの**が並んで
            # 初めて、その絵が合格なのか不合格なのか判断できる。
            "capability_gap": result.get("capability_gap"),
        })
        print(f"  ✓ {key:10s} {label:10s} {template:24s} widgets={len(types)}")

    (OUTPUT_DIR / "manifest.json").write_text(
        json.dumps(
            {"needs": manifest, "rendered": len(documents),
             "total": len(NEEDS)},
            ensure_ascii=False, indent=2,
        ) + "\n",
        encoding="utf-8",
    )
    DART_FIXTURE.write_text(render_dart(documents), encoding="utf-8")

    print()
    print(f"  撮影対象 {len(documents)} / {len(NEEDS)}")
    print(f"  wrote {OUTPUT_DIR}")
    print(f"  wrote {DART_FIXTURE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
