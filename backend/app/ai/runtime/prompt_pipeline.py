"""AI Runtime — Prompt Pipeline(FORGE v0.2 PART A — Cognitive Pipeline本番接続)。

**変更点(FORGE_v0.2_COMPLETE_IMPLEMENTATION_DIRECTIVE.md PART A 4章)**:
本番生成経路は、Legacyの`forge_ai.core.pipeline.run_pipeline()`ではなく
`forge_ai.core.pipeline.run_cognitive_pipeline()`を1回だけ呼ぶ(粗粒度
Facade)。これによりAmbiguity Detection・Domain Classification・Meaning
Model・Requirement Extraction・Template Selection・Design Critic・
Cognitive Revisionを含む、M006 Cognitive Architectureの全段階が本番経路へ
接続される(旧`run_pipeline()`はこれらを一切実行しない、より単純な後方
互換経路であり、新しい本番経路からは呼ばない。ただし後方互換のため
`forge_ai/`側の関数自体は削除しない)。

**責務(`docs/spec/ADAPTER_CONTRACT_V1.md` 1.2節を、Cognitive Pipeline用に
更新)**:
1. Engine/Provider検証
2. Provider解決(`ProviderRouter`)
3. M004 `run_cognitive_pipeline()`を1回だけ呼ぶ(個別コンポーネントは呼ばない)
4. `CognitivePipelineOutcome`(Success / NeedsConfirmation / Failed)を分岐処理
5. Success: IRをdict化 → Validator → 不合格時Repair → 再Validation →
   Repair後Quality再評価 → CriticResult変換
6. NeedsConfirmation: 例外にせず、`PipelineNeedsConfirmationResult`という
   正式な戻り値として返す(ディレクティブPART A 4.1節「例外として潰さず、
   公開APIの正式な結果型として返す」)
7. Failed: 既存Error Envelope体系(`PlanningError`)へ変換
8. Diagnostics作成(Decision Trace・Ambiguity・Domain Classification等を含む)
9. 結果返却

このファイルは`forge_ai.core.pipeline.run_cognitive_pipeline`・
`forge_ai.repair.repair_engine.RepairEngine`・
`forge_ai.quality.quality_engine.QualityEngine`の3つに限り、forge_ai/を
直接importしてよい。禁止されているのは`MeaningExtractor`/
`IntentBuilder`/`Planner`/`Compiler`という個別コンポーネントの直接呼び出し
であり、この3つ以外はこのファイルからimportしない(回帰テストで検査)。
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import Any

from forge_ai.core.orchestration.outcomes import (
    CognitivePipelineFailed,
    CognitivePipelineNeedsConfirmation,
    CognitivePipelineSuccess,
)
from forge_ai.core.orchestration.cognitive_types import DecisionTrace
from forge_ai.core.pipeline import run_cognitive_pipeline
from forge_ai.quality.quality_engine import QualityEngine
from forge_ai.repair.repair_engine import RepairEngine

from app.ai.foundation.interfaces import CriticResult
from app.ai.gateway.ai_router import AIRouter, NoProviderAvailableError, default_router
from app.ai.gateway.capability_evidence import (
    CapabilityUsage,
    CapabilityUsageSource,
    CapabilityUsageStatus,
    GenerationStructureSource,
    structure_source_is_ai,
)
from app.ai.runtime.capability import CAPABILITY_REGISTRY
from app.ai.runtime.capability_gap import CapabilityGap, gap_from_plan
from app.ai.gateway.generation_evidence import (
    DesignDecisionSource,
    DesignRoleDecision,
    GenerationRecord,
    GenerationSource,
    default_generation_store,
    source_for_generated,
)
from app.ai.gateway.intelligence_context import default_intelligence_resolver
from app.ai.runtime.design_language import design_language_guidance, design_roles_in
from app.ai.gateway.tasks import ForgeTask
from app.ai.runtime.forge_ai_adapter import (
    intent_ir_from_forge_ai_intent,
    plan_ir_from_application_plan,
    to_backend_repair_result,
    to_critic_result,
    to_repair_issues,
)
from app.ai.runtime.forge_ai_provider_bridge import ForgeAIProviderBridge
from app.ai.runtime.output_safety import OutputSafetyChecker
from app.ai.runtime.pipeline_errors import (
    ForgeValidationError,
    PlanningError,
    ProviderError,
    UnsupportedEngineError,
)
from app.ai.runtime.provider_router import ProviderRouter
from app.ai.validators.schema_validator import ValidationResult, validate_forge_document

# 共通指示書6.5節「修正回数には上限を設ける。推奨は最大2回。無限修正
# ループは禁止」。ADR 2.4節の二重ループ問題を踏まえ、このMAX_REPAIR_ATTEMPTS
# だけがリトライ回数を制御する(forge_ai.RepairEngineはmax_iterations=1で
# 構築し、内側の独自ループを無効化する)。
MAX_REPAIR_ATTEMPTS = 2

# 現時点でサポートするEngineは"forge_ai"のみ(ADR 4.0節)。
SUPPORTED_ENGINES = ("forge_ai",)


@dataclass(frozen=True)
class Diagnostics:
    """HTTPレスポンスの`diagnostics`フィールドに対応する(ADAPTER_CONTRACT_V1.md
    5.3節を、Cognitive Pipeline接続に合わせて拡張)。

    `conversion_warnings`はCEO実物監査対応(Fix 2): `plan_ir_from_
    application_plan()`がpresentation conceptと判定してdata_neededから
    除外した要素の警告を、以前はどこにも返さず捨てていた。ここへ含めて
    HTTPレスポンス経由で確認できるようにする。

    `repair_attempts`は既存フィールド名を維持する(Schema Repair、
    `forge_ai.repair.repair_engine.RepairEngine`の試行回数)。
    `cognitive_revision_attempts`はこれとは独立したカウンタであり、
    Cognitive Revision Loop(Design Criticの指摘に基づくApplicationPlanの
    修正)の試行回数を表す(2つのループのカウンタは完全に独立、共通指示書
    6.5節・M005 D59の教訓)。
    """

    engine_used: str
    provider_used: str
    repair_attempts: int
    intent_ir: dict[str, Any] | None = None
    plan_ir: dict[str, Any] | None = None
    conversion_warnings: tuple[str, ...] = ()
    cognitive_revision_attempts: int = 0
    ambiguity_report: dict[str, Any] | None = None
    domain_classification: dict[str, Any] | None = None
    decision_trace: tuple[dict[str, Any], ...] = ()

    injection_report: dict[str, Any] | None = None
    """FORGE-AI-CONNECT-001 TD21対応(2026-08-11)。呼び出し側
    (`routers/ai.py`)が`app.ai.runtime.injection_scan.scan_for_injection()`
    で事前に計算した結果をそのまま受け取り、診断として記録するだけ
    (`PromptPipeline`自体はforge_ai/のInjection Guardを直接呼ばない、
    既存の「このファイルはforge_ai/を3つに限り直接importしてよい」という
    制約を守るため)。検出のみで、ブロックはしない。"""

    safety_report: dict[str, Any] | None = None
    """FORGE-AI-CONNECT-001 TD20対応(2026-08-11)。最終Forge Documentに
    対する`OutputSafetyChecker`(`app/ai/runtime/output_safety.py`、
    backend内で完結しforge_ai/には依存しない)の検査結果。検出のみで、
    生成そのものはブロックしない(TD21と同じ設計方針)。"""


# `pipeline_orchestrator`が残すdecision traceのstage名。**ここが唯一の
# 接点**なので、名前が変わったらテストが落ちるようにしてある
# (`tests/test_generation_evidence.py`)。黙って`UNKNOWN`へ落ちると、
# 「Curatedの成功が1件も記録されない」に静かに戻る。
_DOMAIN_RESOLUTION_STAGE = "domain_resolution"

def _generation_source(decision_trace, provider_used: str | None, context=None) -> GenerationSource:  # noqa: ANN001
    """その生成物を**誰が作ったか**を、2つの事実から決める(014 §2)。

    ```
    domain_resolution == "curated"   → CURATED（決定的生成。AIは関与しない）
    それ以外                          → 実際に答えたProviderの事実から決める
    ```

    ---

    ## 013から変えた点

    013は`"generated"`を無条件に`CLOUD_AI`へ写していた。しかし
    `generated`が言っているのは「**決定的なCurated生成ではなかった**」
    だけであり、誰が作ったかは言っていない。

    このままLocal AIが構造を作るようになると、その実績が丸ごとCloud AIの
    成績として記録される。**Local Routingへ昇格してよいかの判断根拠が、
    最初から汚染される。**

    Mockも同じ問題を持っていた。013のテストではMock生成が`CLOUD_AI`に
    なっていた——Cloud AIの実績にMockの成功が混ざっていた。

    ## 誰が答えたかは`_BoundAdapter`が知っている

    `last_provider_used`は「**実際に**応答を返したProvider名」であり、
    Routerがfallbackした場合も正しい(010 Phase Bで入れた)。
    そこからRegistryの`deployment`/`test_only`を引く
    (`source_for_generated()`)。

    Curatedを先に見るのは、Curated経路では会話ステップのProviderが
    `last_provider_used`に残りうるためである。**生成stageがAIを
    呼んでいないのに、会話のProviderで由来を決めてはならない。**
    """
    for entry in decision_trace or ():
        if entry.get("stage") == _DOMAIN_RESOLUTION_STAGE:
            if str(entry.get("decision", "")).strip().lower() == "curated":
                return GenerationSource.CURATED
            break

    # **構造を作ったのが AI でないなら、AI の手柄にしない**
    # （FORGE-020A2 §3、2026-08-26）。
    #
    # R4 以降、`Capability Plan → 決定的な EntitySpec → IR` で構造が
    # 決まったあと、**Design Intent だけ AI を呼ぶ**ことがある。
    # `provider_used` だけを見ると、そこで `local` が返るので
    # `LOCAL_AI`——「Local Model が構造を決めた」——になってしまう。
    #
    # それは嘘である。Local Model は**見た目の役だけ**答えた。
    candidate = source_for_generated(provider_used)
    structure = _structure_source(context)

    # **構造を Forge が決定的に組んだと分かっているときだけ**格下げする。
    #
    # `UNKNOWN` では格下げしない。「記録されていない」を「決定的だった」
    # と読むのは推測であり、それこそこの層が禁じていることである
    # （`CLAUDE.md` §3）。代わりに、**本番が `UNKNOWN` を記録しないこと**
    # を別のテストで固定する——provenance の配線を外せばそちらが落ちる。
    deterministic = structure in (
        GenerationStructureSource.CURATED,
        GenerationStructureSource.DETERMINISTIC_CAPABILITY_PLAN,
    )
    if deterministic and candidate in (
        GenerationSource.LOCAL_AI, GenerationSource.CLOUD_AI,
    ):
        # AI は Design Intent だけ答えた。**構造を作った手柄にしない。**
        #
        # `TEST_DOUBLE` はここへ来ない——Mock の成功を `COMPOSITION` へ
        # 洗い流すと「Mock だった」が消える（014 §2 で分けた理由）。
        return GenerationSource.COMPOSITION
    return candidate


def _design_decisions(context, forge_document: dict):  # noqa: ANN001, ANN201
    """軸ごとの「どのroleが、誰の判断で選ばれたか」(§4)。

    ---

    ## 何を分けているのか

    ```
    ai            AIが選び、Forgeの検証を通った  ← 唯一「AIの成功例」
    fallback      AIへ聞いたが採れず既定で埋めた  ← AIの手柄ではない
    deterministic Compilerが構造から決めた        ← 見出し・一覧・ボタン
    ```

    `design_language_roles`(結果の一覧)だけを教師データにすると、
    **Forgeの既定値をAIの成功例として学習する**。「このNeedでは
    compactが良い」とAIが判断した事実は1つも無いのに、そう記録される。

    ## 持たないもの

    Prompt本文もProviderの生出力も入らない。入るのは軸ID・role ID・
    由来の3つだけである(§4.2、006 §22のPrivacy境界)。
    """
    decisions: list[DesignRoleDecision] = []

    intent = getattr(context, "design_intent", None)
    ai_axes: set[str] = set()
    if intent is not None:
        fallback_axes = set(getattr(intent, "fallback_axes", ()) or ())
        for axis, role in (getattr(intent, "choices", {}) or {}).items():
            if not role:
                continue
            ai_axes.add(str(role))
            decisions.append(DesignRoleDecision(
                axis=str(axis), role=str(role),
                source=(DesignDecisionSource.FALLBACK if axis in fallback_axes
                        else DesignDecisionSource.AI),
            ))

    # Compilerが構造から決めたrole。**AIへは一度も聞いていない**ので、
    # AIの成功例として数えてはならない。かといって由来不明でもない
    # ——構造から一意に決まる、という確かな由来がある。
    for role in design_roles_in(forge_document):
        if role in ai_axes:
            continue
        decisions.append(DesignRoleDecision(
            axis="", role=role, source=DesignDecisionSource.DETERMINISTIC,
        ))
    return tuple(decisions)


def _visual_structure(forge_document: dict) -> dict:
    """生成物の構造についての決定的な事実(§10)。

    Semantic Design Criticと**同じ関数**で測る。別々に数えると、
    Criticが「主KPIは1つ」と言っているのにEvidenceには2と残る、と
    いう食い違いが起きうる。1回のscanを2人が読む形にしてある。
    """
    from forge_ai.core.critic.semantic_design_critic import evaluate_semantic_design  # noqa: PLC0415

    return evaluate_semantic_design(forge_document).evidence.to_dict()


def _record_generation(
    bound,  # noqa: ANN001 — _BoundAdapter
    *,
    context,  # noqa: ANN001 — CognitivePipelineContext
    decision_trace,  # noqa: ANN001
    forge_document: dict,
    validator_passed: bool,
    repair_attempts: int,
    knowledge_references: tuple[str, ...] = (),
) -> int:
    """**生成物そのもの**のEvidenceを残す(013 §4、TD65)。

    `_note_generation_outcome()`との違いが要点である。あちらは
    「AI呼び出しの記録へ後から書き足す」ので、**AIを呼んでいなければ
    書き足す先が無い**。Curated Domainは生成stageでAIを1回も呼ばない
    ので、あちらだけでは成功例が永久に残らなかった(TD65の実測)。

    こちらはAI呼び出しの有無と**独立に**、1つの生成物につき1件残す。
    """
    store = default_generation_store()
    ai_calls = len(getattr(bound, "experience_refs", ()) or ())
    stored = store.record(
        GenerationRecord(
            source=_generation_source(
                decision_trace, getattr(bound, "last_provider_used", None), context,
            ),
            domain=_domain_identifier(context),
            validator_passed=validator_passed,
            forge_language_version=str(forge_document.get("version", "") or ""),
            repair_attempts=repair_attempts,
            ai_calls=ai_calls,
            design_language_roles=design_roles_in(forge_document),
            design_decisions=_design_decisions(context, forge_document),
            visual_structure=_visual_structure(forge_document),
            knowledge_references=knowledge_references,
            # **Capability Plan の結論を Evidence へ残す**
            # （GENERATED-UI-QG-V2-R4、2026-08-26）。
            #
            # `capabilities` は「使われた Capability の識別子」を持つ欄と
            # して013から在ったが、**本番から一度も埋まっていなかった**。
            # R4 で Capability Plan が本番経路に入ったので、その結論が
            # ここへ来る。
            #
            # Diagnostics の `decision_trace` はリクエスト単位で消える。
            # Local AI が後から「どういう Capability の組み合わせが
            # 受け入れられたか」を突き合わせるには、**残る側**に無いと
            # 意味がない。
            capabilities=_capabilities_used(context),
            capability_usage=_capability_usage(context, forge_document),
            structure_source=_structure_source(context),
            structure_provider=_structure_provider(context, bound),
            structure_task=_structure_task(bound),
        )
    )
    # **番号を返す。** 013はここで捨てていた。捨てると、後から
    # Runtime結果や利用者の承認を書き足そうとしても「どの生成物へ
    # 書くか」を本番が知らない——R0以前にExperienceで踏んだのと
    # 同じ形である(Storeもmethodもあるが、refが流れていない)。
    return stored.ref


def _structure_source(context) -> GenerationStructureSource:  # noqa: ANN001
    """**構造を作った段**（020A2 §3）。

    `CognitiveContext.structure_source` を読む。**Decision Trace の文字列を
    parse しない**——reason の書き方を変えただけで Evidence が壊れる。

    forge_ai 側の enum とは**値の文字列**で照合する（forge_ai は backend を
    import できない）。食い違いはテストが落とす。
    """
    value = getattr(getattr(context, "structure_source", None), "value", "")
    try:
        return GenerationStructureSource(value)
    except ValueError:
        # **知らない値を AI 側へ倒さない。**
        return GenerationStructureSource.UNKNOWN


def _structure_provider(context, bound) -> str:  # noqa: ANN001
    """構造を作った段が**実際に**使った Provider 名。

    決定的な経路（Curated / Capability Plan）は AI を呼んでいない——
    そこで Provider 名を書くと、また「呼んでもいない Provider の手柄」に
    なる（019B §4 / 020A で2回踏んだ）。**空にする。**
    """
    if structure_source_is_ai(_structure_source(context)):
        return str(getattr(bound, "last_provider_used", "") or "")
    return ""


def _structure_task(bound) -> str:  # noqa: ANN001
    """構造を作った段の Task。**観測した値**を入れる。"""
    task = getattr(bound, "task", None)
    return str(getattr(task, "value", "") or "")


def _capability_usage(context, forge_document: dict):  # noqa: ANN001, ANN201
    """Capability ごとの事実（020A2 §4）。

    ---

    ## ID の並びでは足りない

    R4 の `capabilities` は `unsupported:` のような**接頭辞つき文字列**で
    区別していた。書式に意味を持たせているだけで、読む側は必ず parse を
    書くことになる。将来 JSONL Dataset へ落とすとき、

        求められた / 実際に使われた / 一部だけ / 無かった

    の4つが区別できないと「この構成なら上手くいく」を学習できない。

    ## `used` は生成物を見て決める

    Plan が求めただけでは `used` にしない。**実際に文書へ現れたか**を
    Widget 型から確かめる。求めたのに出ていないものは
    `requested=True, used=False` として残る——それが「出せなかった」で
    ある。

    値も利用者の本文も入らない。**Capability ID だけ。**
    """
    plan = getattr(context, "capability_plan", None)
    if plan is None:
        return ()

    present = _widget_types_in(forge_document)
    usage: list[CapabilityUsage] = []
    seen: set[str] = set()

    def add(capability_id: str, status: CapabilityUsageStatus,
            source: CapabilityUsageSource) -> None:
        if capability_id in seen:
            return
        seen.add(capability_id)
        binding = CAPABILITY_REGISTRY.get(capability_id)
        widgets = set(binding.widget_types) if binding else set()
        usage.append(CapabilityUsage(
            capability_id=capability_id,
            requested=True,
            # Widget と結び付いていないものは、出たかどうかを判定できない。
            used=bool(widgets & present),
            status=status,
            source=source,
        ))

    missing = set(getattr(plan, "missing", ()) or ())
    partial = set(getattr(plan, "partial", ()) or ())
    for capability_id in getattr(plan, "requested", ()) or ():
        if capability_id in missing:
            status = CapabilityUsageStatus.MISSING
        elif capability_id in partial:
            status = CapabilityUsageStatus.PARTIAL
        else:
            status = CapabilityUsageStatus.IMPLEMENTED
        add(capability_id, status, CapabilityUsageSource.SEMANTIC_PLAN)

    # Field の Capability は Plan の `requested` に入っているが、
    # **構造上必ず要るもの**（`data.entity` 等）は決定的に足している。
    for planned in getattr(plan, "fields", ()) or ():
        add(
            planned.capability, CapabilityUsageStatus.IMPLEMENTED,
            CapabilityUsageSource.DETERMINISTIC,
        )
    return tuple(usage)


def _widget_types_in(node: object) -> set[str]:
    """生成物に**実際に現れた** Widget 型。"""
    found: set[str] = set()
    if isinstance(node, dict):
        kind = node.get("type")
        if isinstance(kind, str):
            found.add(kind)
        for value in node.values():
            found |= _widget_types_in(value)
    elif isinstance(node, list):
        for value in node:
            found |= _widget_types_in(value)
    return found


def _capabilities_used(context) -> tuple[str, ...]:  # noqa: ANN001
    """Capability Plan が要求した能力の識別子（R4、2026-08-26）。

    ---

    ## なぜ Context から読むのか

    最初これを `decision_trace` の `reason` 文字列から正規表現的に
    切り出す形で書いた。**書式へ依存する**——`reason` の書き方を変えた
    だけで Evidence が黙って空になる。同じ批判が `design_intent` の
    コメントに既に書いてある（「Decision Trace の文字列だけにすると、
    後から由来を取り出すのに書式へ依存することになる」）。

    `CognitiveContext.capability_plan` を読む。

    ## なぜ `unsupported` も残すのか

    `GenerationRecord.capabilities` は013から在ったが、**本番から一度も
    埋まっていなかった**。R4 で Capability Plan が本番経路に入ったので
    ここへ来る。

    **「持っていなかった」という事実も学習の材料である。** 出来たことだけ
    記録すると、Forge は自分の限界を学べない。接頭辞を付けて区別する。

    値は入らない——利用者の言葉も生成物の本文もここへは来ない
    （`GenerationRecord` の Privacy 境界、006 §22）。名前だけである。
    """
    plan = getattr(context, "capability_plan", None)
    if plan is None:
        return ()
    names: list[str] = []
    names.extend(getattr(plan, "views", ()) or ())
    names.extend(getattr(plan, "interactions", ()) or ())
    names.extend(f"partial:{name}" for name in getattr(plan, "partial", ()) or ())
    names.extend(
        f"unsupported:{name}" for name in getattr(plan, "unsupported", ()) or ()
    )
    return tuple(dict.fromkeys(names))


def _domain_identifier(context) -> str:  # noqa: ANN001
    """Forgeが分類したDomain識別子。**利用者の言葉ではない**(006 §22)。"""
    classification = getattr(context, "domain_classification", None)
    primary = getattr(classification, "primary_domain", None)
    category = getattr(primary, "category", None)
    return str(getattr(category, "value", "") or "")


def _note_generation_outcome(bound, *, validator_passed: bool, repair_attempts: int) -> None:
    """今回の生成に寄与したAI呼び出しへ、**後から分かった事実**を書き足す
    (FORGE-ROADMAP R0、2026-08-17)。

    記録そのものは`AIRouter.generate()`が既に済ませている。ここで
    足すのは、呼び出し時点では分からなかったもの——Validatorを
    通ったか、何回直したか——だけである。

    Storeを`default_experience_store()`から取らず**Routerから取る**
    のは、Routerが記録した先とここで書き足す先を必ず一致させる
    ためである。別々に解決すると、テストが差し替えたStoreと本番の
    Storeがずれ、「書いたはずが入っていない」が静かに起きる。
    """
    store = getattr(bound.router, "experience", None)
    if store is None or not bound.experience_refs:
        return
    store.note_generation_outcome(
        bound.experience_refs,
        validator_passed=validator_passed,
        repair_attempts=repair_attempts,
    )


@dataclass(frozen=True)
class PipelineRunResult:
    """`PromptPipeline.run()`の戻り値(成功時)。HTTP層がこれをそのまま
    Responseへ整形できる形にしている。"""

    forge_document: dict[str, Any]
    validation: ValidationResult
    quality: CriticResult | None
    diagnostics: Diagnostics

    capability_gap: CapabilityGap = field(default_factory=CapabilityGap)
    """**作れないと分かっていることを利用者へ伝える**（TD90 / 020A2 §5）。

    Plan は R4 の時点で `simulate.loop` を MISSING と正しく名指しできて
    いたのに、返っていたのは CRUD だけだった。**Forge は知っていて
    黙っていた。** ここが利用者へ届く口である。
    """

    generation_ref: int | None = None
    """この生成物の`GenerationRecord`番号(014 §3)。

    **013はこれを捨てていた。** `record()`が番号を返していたのに
    受け取らず、`PipelineRunResult`にも載せていなかった。その結果、
    後からRuntimeの結果や利用者の承認を書こうとしても
    「**どの生成物へ書くか**」を本番が知らない状態だった。

    R0以前にExperienceで踏んだのと同じ形である——Storeもmethodも
    あるが、refが流れていない。「Storeに記録された」で完成扱いしない
    (`CLAUDE.md` §3)。

    **HTTPレスポンスへは出さない。** 利用者に見せる情報ではなく、
    Forge内部で後続のEvidenceを紐づけるためのものである。

    `None`は「記録していない」——Confirmation要求で生成へ到達しな
    かった場合など。0と区別できるようにしてある。"""

    experience_refs: tuple[int, ...] = ()
    """この生成に寄与したAI呼び出しの`ExperienceRecord`番号(R0)。

    **HTTPレスポンスへは出さない**(`Diagnostics`ではなくこちらに
    置いてあるのはそのためである)。利用者に見せる情報ではなく、
    呼び出し側が**利用者の承認/訂正を後から書き足す**ための手掛かり
    である。"""


@dataclass(frozen=True)
class PipelineNeedsConfirmationResult:
    """`PromptPipeline.run()`の戻り値(確認要求時)。

    ディレクティブPART A 4.1節: `CognitivePipelineNeedsConfirmation`は
    例外として潰さず、公開APIの正式な結果型として返す。HTTP層はこれを
    `status = "needs_confirmation"`のレスポンスへ変換する(5.2節)。

    `ambiguity_report`・`domain_classification`はFORGE v0.2 P1 4章
    「Diagnosticsを失わない」対応で追加した(既定値`None`)。到達した
    段階までに実際に計算済みの情報のみを保持し、未到達の段階は`None`の
    ままにする(存在しない情報を捏造しない)。
    """

    reason: str
    message: str
    open_questions: tuple[str, ...]
    reached_stage: str
    engine_used: str
    provider_used: str
    decision_trace: tuple[dict[str, Any], ...] = ()
    ambiguity_report: dict[str, Any] | None = None
    domain_classification: dict[str, Any] | None = None
    injection_report: dict[str, Any] | None = None
    """FORGE-AI-CONNECT-001 TD21対応(2026-08-11)。`Diagnostics.
    injection_report`と同じ(呼び出し側が事前計算した結果をそのまま
    保持するだけ)。"""

    requested_provider: str | None = None
    """利用者が**明示的に要求した**Provider名(通常は`None`)。

    FORGE-AI-FOUNDATION-010 Phase Bで追加。`provider_used`とは意味が
    違う——`provider_used`は「実際に応答を返したのは誰か」という観測
    結果であり、確認往復の再開時に**そのまま指定し直してよい値では
    ない**(そもそも何も呼ばれていなければ`"none"`になる)。

    `/generate/confirm`はこの値を`ConfirmationStore`へ保存して再開時に
    渡す。再現すべきなのは「利用者の指定」であって「たまたま選ばれた
    Provider」ではない。`None`のまま保存すれば、再開時も同じように
    Routingが働く。"""


PromptPipelineOutcome = PipelineRunResult | PipelineNeedsConfirmationResult


def _decision_trace_to_dicts(decision_trace: tuple[DecisionTrace, ...]) -> tuple[dict[str, Any], ...]:
    """`DecisionTrace`(forge_ai/、frozen dataclass)をJSON化しやすいdictへ
    変換する(診断表示用の簡易シリアライズ)。"""

    return tuple(
        {
            "stage": entry.stage,
            "decision": entry.decision,
            "reason": entry.reason,
            "confidence": entry.confidence,
            "alternatives": list(entry.alternatives),
        }
        for entry in decision_trace
    )


def _ambiguity_report_to_dict(ambiguity_report: Any) -> dict[str, Any] | None:
    if ambiguity_report is None:
        return None
    return {
        "detection_status": ambiguity_report.detection_status,
        "overall_severity": ambiguity_report.overall_severity,
        "issues": [
            {"category": i.category, "severity": i.severity, "description": i.description}
            for i in ambiguity_report.issues
        ],
    }


def _domain_classification_to_dict(classification: Any) -> dict[str, Any] | None:
    if classification is None:
        return None
    primary = classification.primary_domain
    return {
        "primary_domain": primary.category.value,
        "display_name": primary.display_name,
        "confidence": classification.confidence,
        "score_margin": classification.score_margin,
        "rationale": classification.rationale,
        "candidates": [
            {"domain": c.domain.category.value, "raw_score": c.raw_score, "normalized_score": c.normalized_score}
            for c in classification.candidates
        ],
    }


class PromptPipeline:
    """ADR 1.2節のフローを、Facade方式で実行する。

    Widget/画面固有の知識を持たない(Runtime非依存)。判断ロジックは
    「Validator結果に基づく分岐」「Repairループの回数制御」に限定し、
    認知処理そのもの(Meaning/Intent/Planner/Compile)はforge_ai/
    (`run_pipeline()`)へ完全に委譲する(「巨大Manager」にしないための
    設計方針)。
    """

    def __init__(
        self,
        *,
        provider_router: ProviderRouter | None = None,
        ai_router: AIRouter | None = None,
        max_repair_attempts: int = MAX_REPAIR_ATTEMPTS,
    ) -> None:
        self._provider_router = provider_router or ProviderRouter()
        self._ai_router = ai_router
        self._max_repair_attempts = max_repair_attempts

    @property
    def ai_router(self) -> AIRouter:
        """AI呼び出しの唯一の出口(FORGE-AI-FOUNDATION-010 Phase B)。

        遅延解決にしているのは、`default_router()`のCatalogが環境変数を
        読むためである。import時に固定すると、テストが環境を差し替えても
        古いCatalogを見続ける。
        """
        return self._ai_router or default_router()

    def run(
        self,
        natural_language: str,
        *,
        engine: str = "forge_ai",
        provider: str | None = None,
        clarification_answers: tuple[str, ...] = (),
        injection_report: dict[str, Any] | None = None,
        title_seed: str | None = None,
    ) -> PromptPipelineOutcome:
        """フロー全体を1回実行する。

        `injection_report`(FORGE-AI-CONNECT-001 TD21対応、2026-08-11):
        呼び出し側が`app.ai.runtime.injection_scan.scan_for_injection()`で
        事前に計算した結果。このメソッド自身は計算せず、そのまま
        Diagnostics/PipelineNeedsConfirmationResultへ記録するだけ
        (このファイルがforge_ai/を直接importしてよい3つに限る制約を
        守るため)。

        `clarification_answers`(FORGE v0.2 Final Gate P0.1で新設、
        最終調整で複数累積対応へ変更): `needs_confirmation`への回答が
        ある場合に渡す。**複数回の確認往復があった場合、全ての回答を
        タプルで渡すこと**(1回目の回答を失わないため)。呼び出し側は
        あらかじめ`natural_language`へ結合済みの文字列を作ってはならない
        (以前の`confirmation_store.py`のバグ、6.3節参照)。この関数が
        `run_cognitive_pipeline()`へ両方を別引数として渡し、内部で
        ラベル無しの結合を1箇所(`forge_ai.core.pipeline._combine_
        with_answers()`)だけで行う。

        `title_seed`(FORGE-HANDOFF-LOCAL-AI-UX-004、2026-08-13):
        生成されるアプリのタイトルを導出する元にする短いテキスト。
        `/converse`経由の場合、`natural_language`は会話全体を要約した
        `build_brief`(説明文)であり、そこからタイトルを作ると
        「〜を記録・管理するための道具」という説明文がそのまま
        アプリ名になる(実機で確認)。ユーザー自身の短い言葉を
        ここへ渡す。Domain判定等は引き続き`natural_language`全体を使う。

        戻り値は`PipelineRunResult`(成功)または
        `PipelineNeedsConfirmationResult`(確認要求、正式な結果型として
        返す。例外にしない)のいずれか。

        送出しうる例外(いずれも`pipeline_errors.py`で定義、HTTP層が
        Error Envelopeへ変換する):
        - `UnsupportedEngineError`: `engine`が未知の値。
        - `ProviderError`(sub_reason="unavailable"): Provider名が
          未登録、またはMock以外の未実装Providerを実際に呼んだ場合。
        - `ForgeValidationError`: Repair試行後もValidator不合格。
        - `PlanningError`: `run_cognitive_pipeline()`が回復不能な失敗
          (`CognitivePipelineFailed`)を返した場合、または予期しない
          例外を送出した場合。
        """
        # 1. Engine検証
        if engine not in SUPPORTED_ENGINES:
            raise UnsupportedEngineError(
                f"engine '{engine}' はサポートされていません。利用可能: {SUPPORTED_ENGINES}",
                stage="engine_validation",
            )

        # 2. Provider解決 — **AIRouter経由**
        # (FORGE-AI-FOUNDATION-010 Phase B、2026-08-13)。
        #
        # 以前はここで`ProviderRouter.resolve()`を直接呼んでおり、
        # `/generate`・`/generate/confirm`・`/converse`のBUILD経路は
        # **Routerを一度も通っていなかった**。Quota切れのfallbackも
        # Circuit Breakerも、製品の主要生成経路には効いていなかった
        # ——「基盤はあるのに製品では使っていない」の3例目である。
        #
        # `provider`が明示されている場合だけ、その名前が実在するかを
        # 先に検証する(既存契約: 未登録名は`ProviderError`)。
        #
        # **`resolve()`ではなく`is_registered()`を使う**。名前の確認に
        # Adapterを取り出す必要は無く、取り出してしまうと「確認しただけ」
        # と「Routerを迂回してAIを呼んだ」がコード上区別できなくなる
        # (Anti-Bypass Regressionが誤検知する。実際に誤検知させて
        # 気付いた)。
        if provider is not None and not self._provider_router.is_registered(provider):
            raise ProviderError(
                f"Provider '{provider}' is not registered. "
                f"Available: {', '.join(self._provider_router.available_providers())}",
                sub_reason="unavailable",
                stage="provider_resolution",
            )

        bound = self.ai_router.bind(ForgeTask.COGNITIVE_STAGE, provider=provider)
        bridge = ForgeAIProviderBridge(bound)

        # 実際に応答を返したProvider名は**実行後**にしか分からない。
        # 明示指定が無い場合、ここで名前を確定させない
        # (`_provider_used()`が実行後の事実を読む)。
        def _provider_used() -> str:
            """実際に応答を返したProvider名。

            `"none"`は「**まだ一度もAIを呼んでいない**」という事実である
            (Ambiguity Detectionのような決定的な段階だけで確認要求へ
            抜けた場合に起きる)。以前ここは「既定として選ばれるはずの
            名前」を返しており、AIを呼んでいなくても`"mock"`と報告して
            いた。呼んでいないなら、呼んでいないと言う。

            ---

            ## `or provider` を外した (FORGE-020A、2026-08-26)

            上の説明に反して、`or provider` が残っていたため
            **AIを1回も呼んでいなくても「要求されたProvider名」を
            報告していた**。

            実測: Local Runtimeが起動していない状態で
            `provider="local"` を指定すると、Curated Domain Library が
            決定的に文書を作り(`GenerationSource.CURATED`)、LLMは1回も
            呼ばれないのに `provider_used: "local"` が返っていた。

            これは019B §4で`revision_provider`について直したものと
            **同じ嘘**である——「呼んでもいないProviderの手柄」。
            Local AIのLevel 0を測るときにこれが残っていると、
            **200 OK と `provider_used: local` を見て「動いた」と
            誤認する**。

            要求した名前は要求でしかない。**答えた事実だけを報告する。**
            """
            return bound.last_provider_used or "none"

        # 3. M004 run_cognitive_pipeline()を1回だけ呼ぶ(個別コンポーネントは
        # 呼ばない、Blueprint v1.3 Task1.2)。`CognitiveOrchestrator`は
        # `NotImplementedError`を意図的に捕捉せず伝播させるため
        # (Blueprint 6.2節)、ここでの捕捉は既存の挙動と同じ。
        # **Provider選択の前に知識を解決する**(FORGE-016A commit D /
        # 017A §8・§15)。CloudとLocalで渡す知識が変わると、「同じ問いに
        # 同じ知識で答えた」という比較ができなくなり、Benchmarkの前提が
        # 崩れる。ここで1回だけ決めて、以降は同じものを使う。
        knowledge_context = default_intelligence_resolver().resolve(
            ForgeTask.COGNITIVE_STAGE
        )

        try:
            outcome = run_cognitive_pipeline(
                natural_language,
                bridge,
                clarification_answers=clarification_answers,
                # FORGE-R1-CLOSURE-015 §5: Design Languageの語彙を**注入する**。
                # forge_aiはbackendをimportしないので、渡さなければAIは
                # roleを選ばない。ここを外すとProductionでDesign Intentが
                # 動かなくなり、対応するテストが落ちる。
                design_language=design_language_guidance(),
                # FORGE-HANDOFF-LOCAL-AI-UX-004(2026-08-13): `/converse`が
                # ユーザー自身の短い言葉を渡す。アプリのタイトルを
                # `build_brief`(説明文)ではなくユーザーの言葉から導出する
                # ため(`forge_ai.core.pipeline.run_cognitive_pipeline()`の
                # docstring参照)。`None`の場合は従来どおりの挙動。
                title_seed=title_seed,
            )
        except NoProviderAvailableError as exc:
            # Routerが候補を使い切った(枠切れ・Circuit Breaker・鍵なし・
            # 未実装スタブ等)。**理由込みで**伝える(§33)。ここでMockへ
            # 倒して偽のToolを作らない。
            #
            # `stage`を2つに分けているのは、**起きたことが違う**ため:
            #
            # * `provider`明示あり → その1つを呼んで失敗した。以前
            #   (Router導入前)は`NotImplementedError`として
            #   `forge_ir_compilation`を返していた経路であり、
            #   同じ意味の失敗なのでstageも保つ(既存契約)。
            # * `provider`指定なし → 候補を選ぶ段階で全滅した。
            #   IRの生成には一度も到達していない。
            stage = "forge_ir_compilation" if provider is not None else "provider_resolution"
            raise ProviderError(str(exc), sub_reason="unavailable", stage=stage) from exc
        except NotImplementedError as exc:
            # Mock以外の未実装Providerを実際に呼んだ場合、ここでNotImplementedErrorが
            # 発生する(foundation/providers.pyの_UnimplementedProvider)。
            raise ProviderError(str(exc), sub_reason="unavailable", stage="forge_ir_compilation") from exc
        except Exception as exc:  # noqa: BLE001 — 意図的な、分類のための最終防波堤
            raise PlanningError(
                f"run_cognitive_pipeline()が失敗しました: {exc}", stage="cognitive_pipeline_execution"
            ) from exc

        # 4. Outcome分岐
        if isinstance(outcome, CognitivePipelineNeedsConfirmation):
            request = outcome.confirmation_request
            partial = outcome.partial_context
            # FORGE v0.2 P1 4章「Diagnosticsを失わない」対応: ambiguity_report・
            # domain_classificationは、到達した段階までに実際に埋まっている
            # ものだけをそのまま返す(未到達の段階はNoneのまま、捏造しない)。
            return PipelineNeedsConfirmationResult(
                reason=request.reason,
                message=request.message,
                open_questions=request.open_questions,
                reached_stage=outcome.reached_stage,
                engine_used=engine,
                provider_used=_provider_used(),
                requested_provider=provider,
                decision_trace=_decision_trace_to_dicts(outcome.decision_trace),
                ambiguity_report=_ambiguity_report_to_dict(partial.ambiguity_report) if partial is not None else None,
                domain_classification=(
                    _domain_classification_to_dict(partial.domain_classification) if partial is not None else None
                ),
                injection_report=injection_report,
            )

        if isinstance(outcome, CognitivePipelineFailed):
            raise PlanningError(
                f"Cognitive Pipelineが段階'{outcome.reached_stage}'で失敗しました: {outcome.error.message}",
                stage=outcome.reached_stage,
            )

        assert isinstance(outcome, CognitivePipelineSuccess)  # noqa: S101 — 3型Unionの網羅性を明示

        # 5. IRをdict化
        current_ir = outcome.ir
        forge_document = current_ir.to_json_dict()
        context = outcome.context

        # 6. Validator(1回目)
        validation = validate_forge_document(forge_document)

        # 7/8. 不合格時Repair、再Validation(最大 self._max_repair_attempts 回)
        # Schema Repair Loopは、Cognitive Revision Loop(context.revision_attempt、
        # Design Criticの指摘に基づくApplicationPlanの修正)とは完全に独立した
        # カウンタである(共通指示書6.5節・M005 D59「二重ループ問題」の教訓)。
        repair_attempts = 0
        while not validation.valid and repair_attempts < self._max_repair_attempts:
            issues = to_repair_issues(validation)
            if not issues:
                # blockingなエラーが無い(warningのみ)場合、Repairしても
                # 直せるものが無い。無限に回さず打ち切る。
                break
            repair_attempts += 1
            # ADR 2.4節「二重ループ問題」への対応: max_iterations=1で構築し、
            # このwhileループだけがリトライ回数を制御する。
            repair_engine = RepairEngine(bridge, max_iterations=1)
            forge_ai_repair_result = repair_engine.repair(current_ir, issues)
            to_backend_repair_result(forge_ai_repair_result, repair_attempts)  # 診断用途
            current_ir = forge_ai_repair_result.ir
            forge_document = current_ir.to_json_dict()
            validation = validate_forge_document(forge_document)

        # 9. Repair後Quality再評価 / CriticResult変換
        critic_result: CriticResult | None = None
        if validation.valid:
            if repair_attempts > 0:
                # Repairが発生した場合、outcome.initial_qualityは修正前のIRに
                # 対する評価のままなので古い(ADR 2.5節)。再評価する。
                quality_score = QualityEngine().evaluate(current_ir, context.plan)
            else:
                quality_score = outcome.initial_quality
            # FORGE_v0.2_修正指示.md P1 6章対応(「100点乱発は禁止」):
            # `context.critic_report`(Design Critic、coverage_ratioを持つ)を
            # 実際に渡す。以前は`to_critic_result()`側に対応するロジックが
            # 実装されていたにもかかわらず、この呼び出し箇所が引数を渡して
            # いなかったため、実際には一度も機能していなかった
            # (実行して確認: 引数無しの場合、単純な入力でscore=100が
            # 返り続けることを確認した上で、この行を修正した)。
            critic_result = to_critic_result(quality_score, critic_report=context.critic_report)

            # --- Capability Gap（TD90 / 020A2 §5）----------------------
            #
            # **求められたことの本質が出来ていないなら「仕上がった」と
            # 言わない。** 新しい状態 enum は増やさず、既存の
            # `release_ready` を使う——「これは仕上がっている」という
            # 意味の欄が既にある。
            capability_gap = gap_from_plan(getattr(context, "capability_plan", None))
            if capability_gap.blocks_completion and critic_result is not None:
                critic_result = dataclasses.replace(
                    critic_result,
                    release_ready=False,
                    required_fixes=(
                        *critic_result.required_fixes,
                        capability_gap.message,
                    ),
                )
            _note_generation_outcome(bound, validator_passed=True, repair_attempts=repair_attempts)
            generation_ref = _record_generation(
                bound, context=context,
                decision_trace=_decision_trace_to_dicts(context.decision_trace),
                forge_document=forge_document, validator_passed=True,
                repair_attempts=repair_attempts,
                knowledge_references=knowledge_context.references,
            )
        else:
            # **失敗も残す。** 合格したものだけ記録すると、
            # 「Forgeは常にValidatorを通っている」という記録になる。
            # Validatorの合否はProduct Direction §5が挙げた
            # 「正しさの根拠」の1つであり、Cloudの出力そのものより
            # 信頼できる信号である——落とすわけにいかない。
            _note_generation_outcome(bound, validator_passed=False, repair_attempts=repair_attempts)
            _record_generation(
                bound, context=context,
                decision_trace=_decision_trace_to_dicts(context.decision_trace),
                forge_document=forge_document, validator_passed=False,
                repair_attempts=repair_attempts,
                knowledge_references=knowledge_context.references,
            )
            raise ForgeValidationError(
                f"Repair({repair_attempts}回)後もValidatorに合格しませんでした。",
                validation_errors=tuple(e.to_dict() for e in validation.errors),
                stage="validation",
            )

        # 10. Diagnostics作成(2.1・2.2節の変換は診断・ログ用途のみ、M004内部は駆動しない)
        intent_ir = intent_ir_from_forge_ai_intent(context.intent)
        plan_conversion = plan_ir_from_application_plan(context.plan, context.intent)
        # FORGE-AI-CONNECT-001 TD20対応(2026-08-11): 最終Forge Document
        # (Repair後の確定版)に対して実行する。検出のみ、ブロックはしない。
        safety_result = OutputSafetyChecker().check(forge_document)
        safety_report = {
            "safe": safety_result.safe,
            "issues": [
                {
                    "path": i.path,
                    "category": i.category,
                    "severity": i.severity,
                    "matched_phrase": i.matched_phrase,
                    "message": i.message,
                }
                for i in safety_result.issues
            ],
        }
        diagnostics = Diagnostics(
            engine_used=engine,
            provider_used=_provider_used(),
            repair_attempts=repair_attempts,
            intent_ir=_intent_ir_to_dict(intent_ir),
            plan_ir=_plan_ir_to_dict(plan_conversion.plan_ir),
            conversion_warnings=plan_conversion.warnings,
            cognitive_revision_attempts=context.revision_attempt,
            ambiguity_report=_ambiguity_report_to_dict(context.ambiguity_report),
            domain_classification=_domain_classification_to_dict(context.domain_classification),
            decision_trace=_decision_trace_to_dicts(context.decision_trace),
            injection_report=injection_report,
            safety_report=safety_report,
        )

        # 11. 結果返却
        return PipelineRunResult(
            generation_ref=generation_ref,
            experience_refs=bound.experience_refs,
            forge_document=forge_document,
            validation=validation,
            quality=critic_result,
            capability_gap=capability_gap,
            diagnostics=diagnostics,
        )


def _intent_ir_to_dict(intent_ir: Any) -> dict[str, Any]:
    """診断表示用の簡易シリアライズ(dataclassのフィールドをそのままdict化)。
    Enumはvalueへ変換する。"""
    result = {}
    for key, value in vars(intent_ir).items():
        result[key] = value.value if hasattr(value, "value") else value
    return result


def _plan_ir_to_dict(plan_ir: Any) -> dict[str, Any]:
    """診断表示用の簡易シリアライズ。"""
    return {
        "screens": [vars(s) for s in plan_ir.screens],
        "navigation_edges": list(plan_ir.navigation_edges),
        "template_hint": plan_ir.template_hint,
        "unassigned_actions": list(plan_ir.unassigned_actions),
        # FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。
        "schema_version": plan_ir.schema_version,
    }
