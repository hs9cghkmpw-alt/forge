"""**自由文 → 持っている能力なら即表示 / 足りない分だけ作る → 次から速い。**

---

## 3つのシナリオ

| | 入力 | 期待 |
|---|---|---|
| A | いま持っている能力だけで作れる自由文 | **生成 0 回**・即表示 |
| B | 足りない能力が1つ要る自由文 | 足りない分**だけ** 1 回生成 → 検査 → **その同じ生成物**を組み込み → 表示 |
| C | B と意味は近いが**文章が違う**2回目 | **生成 0 回**・再利用・B より速い |

入力文は毎回ランダムに作る。**固定文へ Forge を最適化させない。**

## 再現できること

`--seed` を指定すれば完全に同じ試験を再実行できる。指定しなければ
無作為に選び、その seed をログへ残す。CI が落ちたらその seed を渡す。

## 秘密情報

Provider は Test Double である。実 API を呼ばない。
API キー・token の類は一切扱わない。
"""

from __future__ import annotations

import argparse
import json
import pathlib
import random
import shutil
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from forge_ai.core.ir.capability_document_contribution import (  # noqa: E402
    CapabilityDocumentContribution,
    register_document_contribution,
)
from forge_ai.core.ir.capability_ir import entity_spec_from_plan  # noqa: E402
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler  # noqa: E402
from forge_ai.core.ir.ir_generator import IRGenerator  # noqa: E402
from forge_ai.core.orchestration.capability_artifact_synthesis import (  # noqa: E402
    CapabilityArtifactSynthesizer,
)
from forge_ai.core.orchestration.extension_registry import (  # noqa: E402
    PROMOTED_CAPABILITIES,
)
from forge_ai.core.orchestration.flutter_capability_installer import (  # noqa: E402
    INSTALL_ROOT,
    FlutterCapabilityInstaller,
    verify_installed_capability,
)
from forge_ai.core.orchestration.reuse_first_pipeline import (  # noqa: E402
    ReuseFirstPipeline,
    installer_for,
)
from forge_ai.core.orchestration.synthesizing_build_time_implementer import (  # noqa: E402
    SynthesizingBuildTimeImplementer,
)
from forge_ai.core.semantics.capability_plan import plan_capabilities  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402
from forge_ai.testing.free_text_requests import (  # noqa: E402
    RequestShape,
    generate_request,
)
from scripts._acquired_calendar_source import (  # noqa: E402
    CALENDAR_CONTRACT,
    CALENDAR_PAYLOAD,
)

FRONTEND = ROOT / "frontend"
DOCUMENT_OUT = FRONTEND / "test_acquired" / "generated_document.json"
LOG_OUT = ROOT / "logs" / "forge-reuse-first-e2e-latest.json"

CAPABILITY = "view.calendar"
WIDGET_TYPE = "calendar_view"
MAX_PHRASING_ATTEMPTS = 12


class _TestDoubleProvider:
    """**実 Model ではない。** 実 Model が書いた証拠はまだ無い。"""

    def __init__(self) -> None:
        self.calls = 0

    def complete(self, prompt):  # noqa: ANN001, ANN202
        self.calls += 1
        return ProviderResponse(text="", structured=CALENDAR_PAYLOAD)


def _fail(message: str) -> None:
    print(f"FAIL: {message}")
    raise SystemExit(1)


def _build_document(need: str, plan, promoted):  # noqa: ANN001, ANN202
    """**本番の compiler で**画面を組み立てる。"""
    spec = entity_spec_from_plan(plan)
    if spec is None:
        return None
    return ForgeLanguageCompiler().compile(
        IRGenerator().build_from_spec(spec),
        domain_category="generic",
        title=need[:24],
        promoted_capabilities=tuple(promoted),
    )


def _register_contribution_from_artifact(artifact) -> None:  # noqa: ANN001
    """獲得能力が**自分で宣言した**出力を登録する。"""
    raw = next(
        (f.content for f in artifact.files if f.path == "capability_contribution.json"),
        None,
    )
    if raw is None:
        _fail("the generated artifact carries no capability_contribution.json")
    declaration = json.loads(raw)
    register_document_contribution(CapabilityDocumentContribution(
        capability_id=declaration["capability_id"],
        widget_type=declaration["widget_type"],
        widget_id=declaration["widget_id"],
        document_version=declaration["document_version"],
        properties=tuple((k, v) for k, v in declaration["properties"]),
        fallback_container_id=declaration.get(
            "fallback_container_id", "contribution_root",
        ),
    ))


def _understood_request(seed: int, shape: str, avoid_domain: str | None):  # noqa: ANN202
    """その言い方を Forge が読み取れるものになるまで、**決定的に**探す。

    読み取れなかった言い方は捨てずに記録する——**それは Forge の
    取りこぼしであって、無かったことにしてはならない。** 記録した
    miss はログに残り、報告にも出る。

    seed からの探索は決定的なので、同じ seed なら同じ文へ辿り着く。
    """
    misses: list[dict[str, object]] = []
    for attempt in range(MAX_PHRASING_ATTEMPTS):
        request = generate_request(seed + attempt * 1009, shape, avoid_domain=avoid_domain)
        plan = plan_capabilities(request.text)
        has_entity = entity_spec_from_plan(plan) is not None
        if shape == RequestShape.NEEDS_MONTHLY_VIEW:
            wanted = CAPABILITY in plan.requested
            gap_or_owned = (
                CAPABILITY in plan.missing
                or PROMOTED_CAPABILITIES.is_promoted(CAPABILITY)
            )
            if wanted and gap_or_owned and has_entity:
                return request, misses
            reason = (
                "月ごとに見たい意図を読み取れなかった" if not wanted
                else "記録する型を組めなかった（日付の欄が立たない）"
            )
        else:
            if not plan.missing and has_entity:
                return request, misses
            reason = (
                "足りない能力があると判定された" if plan.missing
                else "記録する型を組めなかった"
            )
        misses.append({"text": request.text, "reason": reason})
    return None, misses


def restore() -> None:
    root = FRONTEND / INSTALL_ROOT
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            shutil.rmtree(entry)
    FlutterCapabilityInstaller(
        frontend_root=FRONTEND, harness_files=frozenset(),
    ).rewrite_registrations()
    if DOCUMENT_OUT.exists():
        DOCUMENT_OUT.unlink()
    print("restored: no acquired capability is installed")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--restore", action="store_true")
    args = parser.parse_args()

    if args.restore:
        restore()
        return

    seed = args.seed if args.seed is not None else random.SystemRandom().randrange(1, 10**9)
    print(f"random seed: {seed}   （再現するには --seed {seed}）")

    restore()
    PROMOTED_CAPABILITIES.clear()

    provider = _TestDoubleProvider()
    implementer = SynthesizingBuildTimeImplementer(
        synthesizer=CapabilityArtifactSynthesizer(provider=provider),
        contract_for=lambda _cid: CALENDAR_CONTRACT,
        known_source_digests=frozenset(),
    )
    pipeline = ReuseFirstPipeline(
        implementer=implementer,
        installer=installer_for(FRONTEND, CALENDAR_CONTRACT.host_language),
        build_document=_build_document,
        label_for=lambda _cid: "カレンダーで見る",
        provider_call_count=lambda: provider.calls,
    )

    report: dict[str, object] = {"seed": seed, "scenarios": {}, "comprehension_misses": {}}

    # ---------------- A: 既存能力だけで作れる ----------------------------
    print("\n=== A. いま持っている能力だけで作れる要求 ===")
    request_a, misses_a = _understood_request(seed, RequestShape.EXISTING_ONLY, None)
    if request_a is None:
        _fail("could not generate an understood existing-only request")
    print(f"  入力: {request_a.text}")
    outcome_a = pipeline.handle(request_a.text)
    print(f"  必要な能力  : {outcome_a.requested}")
    print(f"  足りない能力: {outcome_a.missing_before}")
    print(f"  生成回数    : {outcome_a.generation_count}   Provider 呼び出し: {outcome_a.provider_calls}")
    print(f"  所要        : {outcome_a.timings.total_ms} ms")
    if outcome_a.failure:
        _fail(f"A failed: {outcome_a.failure}")
    if outcome_a.generation_count != 0 or outcome_a.provider_calls != 0:
        _fail("A generated code even though existing capabilities were enough")
    if outcome_a.document is None:
        _fail("A produced no document")
    report["scenarios"]["A"] = {"request": request_a.to_dict(), **outcome_a.to_dict()}
    report["comprehension_misses"]["A"] = misses_a

    # ---------------- B: 足りない能力が1つ ------------------------------
    print("\n=== B. 足りない能力が1つ要る要求 ===")
    request_b, misses_b = _understood_request(
        seed + 1, RequestShape.NEEDS_MONTHLY_VIEW, request_a.domain,
    )
    if request_b is None:
        _fail("could not generate an understood monthly-view request")
    print(f"  入力: {request_b.text}")
    outcome_b = pipeline.handle(request_b.text)
    print(f"  足りない能力: {outcome_b.missing_before}")
    print(f"  獲得        : {outcome_b.acquired}")
    print(f"  生成回数    : {outcome_b.generation_count}   Provider 呼び出し: {outcome_b.provider_calls}")
    print(f"  所要        : {outcome_b.timings.total_ms} ms  {outcome_b.timings.to_dict()}")
    if outcome_b.failure and "still missing" not in outcome_b.failure:
        _fail(f"B failed: {outcome_b.failure}")
    if outcome_b.generation_count != 1:
        _fail(f"B generated {outcome_b.generation_count} times; expected exactly 1")
    if outcome_b.acquired != (CAPABILITY,):
        _fail(f"B acquired {outcome_b.acquired}; expected ({CAPABILITY!r},)")

    # 検査を通った生成物が、そのまま載っているか。
    verified = implementer.last_verified
    if verified is None:
        _fail("no verified artifact was retained")
    installed_digest = verify_installed_capability(FRONTEND, "view_calendar")
    if installed_digest != verified.source_digest:
        _fail("installed source digest differs from the inspected artifact")
    print(f"  検査した生成物 = 載せた生成物: {installed_digest[:16]}…")

    # ここまでが「獲得を含む1回目」である。**その数字を報告する。**
    acquisition = outcome_b

    # 獲得能力が自分で宣言した出力を登録し、画面をもう一度組み立てる。
    # （この2回目は生成を伴わないので、B の所要には数えない。）
    _register_contribution_from_artifact(verified.artifact)
    document_run = pipeline.handle(request_b.text)
    if document_run.document is None:
        _fail("B produced no document after acquisition")
    payload = document_run.document.to_json_dict()
    if f'"{WIDGET_TYPE}"' not in json.dumps(payload, ensure_ascii=False):
        _fail(f"B document does not contain {WIDGET_TYPE!r}")
    DOCUMENT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DOCUMENT_OUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )
    print(f"  {WIDGET_TYPE} が生成 Document に入っている")
    report["scenarios"]["B"] = {
        "request": request_b.to_dict(),
        "source_digest": verified.source_digest,
        "build_id": verified.build_id,
        "runtime_fingerprint": verified.runtime_fingerprint,
        "installed_digest": installed_digest,
        # **獲得を含む1回目の数字。** 2回目で上書きしない。
        **acquisition.to_dict(),
        "document_run": document_run.to_dict(),
    }
    report["comprehension_misses"]["B"] = misses_b

    # ---------------- C: 別の文で、同じ能力を再利用 ----------------------
    print("\n=== C. 意味は近いが文章が違う2回目 ===")
    request_c, misses_c = _understood_request(
        seed + 2, RequestShape.NEEDS_MONTHLY_VIEW, request_b.domain,
    )
    if request_c is None:
        _fail("could not generate an understood second monthly-view request")
    if request_c.text == request_b.text:
        _fail("C reused the same sentence as B")
    print(f"  入力: {request_c.text}")
    calls_before = provider.calls
    started = time.perf_counter()
    outcome_c = pipeline.handle(request_c.text)
    elapsed_c = round((time.perf_counter() - started) * 1000.0, 1)
    print(f"  足りない能力: {outcome_c.missing_before}")
    print(f"  再利用      : {outcome_c.reused}")
    print(f"  生成回数    : {outcome_c.generation_count}   Provider 呼び出し: {outcome_c.provider_calls}")
    print(f"  所要        : {elapsed_c} ms")
    if outcome_c.failure:
        _fail(f"C failed: {outcome_c.failure}")
    if outcome_c.generation_count != 0:
        _fail(f"C regenerated {outcome_c.generation_count} times; the capability was already acquired")
    if provider.calls != calls_before:
        _fail("C called the provider again for an already-acquired capability")
    if CAPABILITY not in outcome_c.reused:
        _fail(f"C did not reuse {CAPABILITY!r}; reused={outcome_c.reused}")
    if outcome_c.document is None:
        _fail("C produced no document")
    report["scenarios"]["C"] = {"request": request_c.to_dict(), **outcome_c.to_dict()}
    report["comprehension_misses"]["C"] = misses_c

    report["provider_calls_total"] = provider.calls
    report["synthesis_count_total"] = implementer.synthesis_count
    report["build_count_total"] = implementer.build_count

    LOG_OUT.parent.mkdir(parents=True, exist_ok=True)
    LOG_OUT.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n",
    )

    print("\n=== まとめ ===")
    print(f"  seed                : {seed}")
    print(f"  生成回数 合計       : {implementer.synthesis_count}（B の1回だけ）")
    print(f"  Provider 呼び出し合計: {provider.calls}")
    print(f"  ログ                : {LOG_OUT.relative_to(ROOT)}")
    print("\n=== まだ言えないこと ===")
    print("  実 Model が書いた証拠は無い（Provider は Test Double）")
    print("  Real Local Model runs = 0 のまま")


if __name__ == "__main__":
    main()
