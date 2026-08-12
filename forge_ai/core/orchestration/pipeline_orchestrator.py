"""CognitiveOrchestrator(M007 Phase 1 Minimal Cognitive Slice)。

CEO実物監査(Phase 1.1)対応: 「Blueprint v1.3の実装」ではなく、Blueprint
v1.3のうち第一段階として意図的に絞り込んだ範囲(Meaning Model等を除く
13 Transformation Stage)の実装であることを明示する。詳細な位置づけは
`FORGE-MILESTONE-007-PHASE1-report.md`参照。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3 Task3の疑似コードを
土台としつつ、Meaning Modelを含まない13段階として実装した。Cognitive
Pipelineの実行順序を知る唯一のコンポーネント。個別モジュールは自分が
Pipeline全体のどこにいるかを一切知らない。

**Legacy Protocolを一切importしない**(Blueprint 4.0節)。
`NotImplementedError`は一切捕捉しない(Blueprint 6.2節、Provider障害を
`CognitivePipelineFailed`へ誤って吸収しないため)。
"""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from forge_ai.core.domain_model import DomainRegistry
from forge_ai.core.ir.forge_language_compiler import ForgeLanguageCompiler
from forge_ai.core.ir.ir_generator import SUPPORTED_DOMAIN_CATEGORIES, IRGenerator
from forge_ai.core.orchestration.cognitive_context import CognitiveContext
from forge_ai.core.orchestration.cognitive_dependencies import CognitiveDependencies
from forge_ai.core.orchestration.cognitive_types import CriticIssue, CriticReport, OverallConfidence
from forge_ai.core.orchestration.confidence import compute_legacy_escalation_reasons, compute_overall_confidence, compute_shadow_judgment
from forge_ai.core.orchestration.errors import AmbiguityError, ConfirmationRequired, CriticFailure, PlanningError
from forge_ai.core.orchestration.outcomes import (
    CognitivePipelineFailed,
    CognitivePipelineNeedsConfirmation,
    CognitivePipelineOutcome,
    CognitivePipelineSuccess,
    assert_context_ready_for_success,
)


class CognitiveOrchestrator:
    """`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3 Task3.2。"""

    def __init__(self, domain_registry: DomainRegistry, dependencies: CognitiveDependencies) -> None:
        self._domain_registry = domain_registry
        self._deps = dependencies

    def run(self, raw_input: str, *, title_seed: str | None = None) -> CognitivePipelineOutcome:
        """`title_seed`(FORGE_v0.2_最終修正指示(Final Gate) P3対応、
        新設): 確認フロー経由で、元入力がノイズ的だった場合に、
        タイトル/goal導出だけへ渡す「意味のある部分」。省略時は
        `None`のままとなり、既存の挙動(`normalized_text`をそのまま
        goal導出に使う)を維持する(既存呼び出し元への後方互換)。
        """
        deps = self._deps
        context = CognitiveContext(raw_input=raw_input, started_at=datetime.now(timezone.utc).isoformat())

        try:
            # 1. Input Normalization
            normalized = deps.normalizer.normalize(context.raw_input)
            if title_seed is not None:
                normalized = dataclasses.replace(normalized, title_seed=title_seed)
            context = context.with_normalized_input(normalized)

            # 2. Ambiguity Detection
            ambiguity_report = deps.ambiguity_detector.detect(context.normalized_input, self._domain_registry)
            context = context.with_ambiguity_report(ambiguity_report)
            if ambiguity_report.detection_status == "failed":
                # M006 4.4節: 検出失敗時は楽観的に継続しない。
                if _is_high_risk_domain_hint(raw_input):
                    request = deps.escalation_handler.build_confirmation_request(context, reason="ambiguity_detection_failed_high_risk")
                    return CognitivePipelineNeedsConfirmation(
                        confirmation_request=request, reached_stage="ambiguity_detection",
                        partial_context=context, decision_trace=context.decision_trace,
                    )
                # 低リスクの場合のみ、警告を残して限定継続する。
                context = context.with_decision(_trace(
                    "ambiguity_detection", "検出失敗のまま低リスク限定継続",
                    "detection_statusがfailedだが、機微なキーワードが見つからないため継続",
                ))
            if ambiguity_report.has_priority1_issue:
                request = deps.escalation_handler.build_confirmation_request(context, reason="priority1_privacy_safety_permission")
                return CognitivePipelineNeedsConfirmation(
                    confirmation_request=request, reached_stage="ambiguity_detection",
                    partial_context=context, decision_trace=context.decision_trace,
                )
            if ambiguity_report.overall_severity == "high":
                # Priority1(Privacy等)以外のHIGH severity issue(例:
                # missing_goal、極端に短い入力)も、Genericへ静かに
                # フォールバックさせず確認を求める(M006 4.2節「HIGH→
                # ユーザーへの確認が必要」の原則をPriority1に限定しない)。
                request = deps.escalation_handler.build_confirmation_request(context, reason="ambiguity_high_severity")
                return CognitivePipelineNeedsConfirmation(
                    confirmation_request=request, reached_stage="ambiguity_detection",
                    partial_context=context, decision_trace=context.decision_trace,
                )

            # 3. Cognitive Intent Recognition
            intent = deps.intent_recognizer.recognize(context.normalized_input, context.ambiguity_report)
            context = context.with_intent(intent)
            context = context.with_decision(_trace(
                "cognitive_intent_recognition", f"goal={intent.goal!r}",
                f"required_concepts={intent.required_concepts}, required_actions={intent.required_actions}",
                confidence=intent.confidence,
            ))

            # 4. Domain Classification
            classification = deps.domain_classifier.classify(context.intent, self._domain_registry)
            context = context.with_domain_classification(classification)
            context = context.with_decision(_trace(
                "domain_classification", f"primary_domain={classification.primary_domain.category.value}",
                classification.rationale
                + f" | intent_extraction_confidence={intent.confidence:.2f}, "
                  f"domain_coverage={classification.domain_coverage:.2f}, "
                  f"score_margin={classification.score_margin:.2f}",
                confidence=classification.confidence,
            ))

            # Task042-1(ADR-007、2026-07-21)。overall_confidenceを計算し、
            # DecisionTraceへ記録するだけの、**観測専用**のステップ。
            # CEO承認済みの段階計画により、この時点ではいかなる`if`分岐にも
            # 使わない(下記_should_escalate_for_low_confidence()は、この
            # 導入前と全く同じ3信号モデルのまま、一切変更していない)。
            #
            # Task042-2 Phase B(2026-07-21)追加分: 現行モデルと
            # overall_confidenceモデルの判定を並行計算した`ShadowJudgment`
            # も、同じく観測専用として記録する。**Shadow側の結果は、
            # DecisionTrace・専用テスト・比較レポート以外のいかなる場所
            # でも参照しない**(下記`if _should_escalate_for_low_
            # confidence(...)`は、`shadow_judgment`・`overall_confidence`
            # のどちらも一切参照しない、現行モデルのみを使う元のロジックの
            # ままである)。
            overall_confidence = compute_overall_confidence(intent, classification)
            shadow_judgment = compute_shadow_judgment(intent, classification)
            context = context.with_decision(_trace(
                "overall_confidence_observation",
                f"overall_confidence={overall_confidence.value:.2f}(観測専用、制御フローには未使用)",
                f"intent_confidence={overall_confidence.intent_confidence.value:.2f}"
                f"(根拠: {'; '.join(overall_confidence.intent_confidence.basis)}), "
                f"domain_confidence={overall_confidence.domain_confidence.value:.2f}"
                f"(根拠: {'; '.join(overall_confidence.domain_confidence.basis)}), "
                f"available_components={len(overall_confidence.available_components)}件, "
                f"shadow_comparison={shadow_judgment.comparison_category}"
                f"(観測専用、制御フローには未使用)",
                confidence=overall_confidence.value,
                # Task042-1追加分(CEO指示、2026-07-21): Task042-2の比較実験
                # (現行モデル vs overall_confidenceモデル)のために、上記の
                # reason文字列を構文解析せずとも、overall_confidence・
                # available_components・intent_confidence・domain_confidence・
                # 各basisへ直接アクセスできるよう、OverallConfidenceオブジェクト
                # そのものを構造化データとして保持する。制御フローには
                # 引き続き一切使わない。
                confidence_observation=overall_confidence,
                # Task042-2 Phase B追加分: ShadowJudgment(現行モデル・
                # Shadowモデルの判定・不一致分類・risk_classification等を
                # 全て含む)をそのまま構造化データとして保持する。
                shadow_judgment=shadow_judgment,
            ))

            if _should_escalate_for_low_confidence(intent, classification) and not _is_low_risk_reversible(classification):
                request = deps.escalation_handler.build_confirmation_request(context, reason="priority2_low_domain_confidence")
                return CognitivePipelineNeedsConfirmation(
                    confirmation_request=request, reached_stage="domain_classification",
                    partial_context=context, decision_trace=context.decision_trace,
                )

            # 5. World Model Construction
            world = deps.world_builder.build(context.domain_classification, context.intent)
            context = context.with_world(world)

            # 6. Meaning Model(FORGE-MILESTONE-007 Phase 1.2で正式接続)
            meaning = deps.meaning_extractor.extract(context.normalized_input, context.world, context.intent)
            context = context.with_meaning(meaning)
            context = context.with_decision(_trace(
                "meaning_extraction",
                f"actors={meaning.actors}, entities={meaning.entities}, actions={meaning.actions}",
                f"constraints={meaning.constraints}, temporal={meaning.temporal_conditions}, "
                f"state={meaning.state_conditions}, evidence_spans={meaning.evidence_spans}, "
                f"rule=keyword_pattern_dictionary_v1",
                confidence=meaning.confidence,
            ))

            # 7. Requirement Extraction(meaning・world・intentの3引数、Blueprint本来の契約)
            requirements = deps.requirement_extractor.extract(context.meaning, context.world, context.intent)
            context = context.with_requirements(requirements)

            # 8. Preliminary Pattern Candidates(独立ノード、Application Planner内部へ隠さない)
            preliminary_candidates = deps.template_selector.select_preliminary(
                context.domain_classification.primary_domain, context.intent, context.requirements,
            )
            context = context.with_preliminary_candidates(preliminary_candidates)
            context = context.with_decision(_trace(
                "preliminary_template_selection", f"candidates={preliminary_candidates}",
                f"Domain={context.domain_classification.primary_domain.category.value}のヒントに基づく絞り込み",
            ))

            # 8. Application Planning(requirements・preliminary_candidatesを必ず渡す)
            plan = deps.planner.plan(context.intent, context.world, context.requirements, context.preliminary_candidates)
            context = context.with_plan(plan)

            # 9. Final Template Selection(CEO実物監査Phase 1.1(2回目)指摘1:
            # differs_from_preliminaryはTemplateSelector.select_final()
            # 自身が必ず正しく設定する。Orchestrator側での上書きは行わない
            # (以前は最初の呼び出し時のみOrchestratorがdataclasses.replace()
            # で上書きしており、Revision後の再選択では反映されない
            # バグがあった)。
            final_selection = deps.template_selector.select_final(context.plan, preliminary_candidates)
            context = context.with_template_selection(final_selection)
            context = context.with_decision(_trace(
                "final_template_selection", f"template={final_selection.template}",
                final_selection.rationale,
            ))

            while final_selection.differs_from_preliminary:
                mismatch_report = CriticReport(
                    release_ready=False,
                    score=0.0,
                    issues=(CriticIssue(
                        category="template_mismatch", severity="high",
                        evidence=f"Preliminary候補{preliminary_candidates}に対し、Final Template Selectionは{final_selection.template}を選択",
                        recommended_fix="Final Templateの要件に合わせてApplicationPlanを再設計する",
                        affected_component="application_plan", auto_fixable=True,
                    ),),
                )
                context = context.with_decision(_trace(
                    "cognitive_revision", f"trigger=template_mismatch, attempt={context.revision_attempt + 1}",
                    f"Preliminary候補{preliminary_candidates}外の'{final_selection.template}'が選ばれたため再計画",
                ))
                if context.revision_attempt >= context.max_revision_attempts:
                    request = deps.escalation_handler.build_confirmation_request(context, reason="preliminary_final_mismatch_exhausted")
                    return CognitivePipelineNeedsConfirmation(
                        confirmation_request=request, reached_stage="final_template_selection",
                        partial_context=context, decision_trace=context.decision_trace,
                    )
                revised_plan = deps.revision_engine.revise(context.plan, mismatch_report, context.revision_attempt)
                context = context.with_plan(revised_plan).with_revision_attempt_incremented()
                final_selection = deps.template_selector.select_final(context.plan, preliminary_candidates)
                context = context.with_template_selection(final_selection)
                context = context.with_decision(_trace(
                    "final_template_selection", f"template={final_selection.template}(再計画後)",
                    final_selection.rationale
                    + f" | differs_from_preliminary={final_selection.differs_from_preliminary}",
                ))

            # 10. Design Critic
            critic_report = deps.design_critic.evaluate(context.plan, context.template_selection, context.requirements)
            context = context.with_critic_report(critic_report)
            context = context.with_decision(_trace(
                "design_critic", f"release_ready={critic_report.release_ready}",
                f"implemented_checks_score={critic_report.implemented_checks_score:.2f}, "
                f"issues={[i.category for i in critic_report.issues]}",
                confidence=critic_report.implemented_checks_score,
            ))

            # 11. Cognitive Revision(9〜10と同じrevision_attemptカウンタを使う)
            while not context.critic_report.release_ready:
                if context.revision_attempt >= context.max_revision_attempts:
                    request = deps.escalation_handler.build_confirmation_request(context, reason="revision_exhausted")
                    return CognitivePipelineNeedsConfirmation(
                        confirmation_request=request, reached_stage="cognitive_revision",
                        partial_context=context, decision_trace=context.decision_trace,
                    )
                context = context.with_decision(_trace(
                    "cognitive_revision", f"trigger=critic_issues, attempt={context.revision_attempt + 1}",
                    f"未解決issues={[i.category for i in context.critic_report.issues]}",
                ))
                revised_plan = deps.revision_engine.revise(context.plan, context.critic_report, context.revision_attempt)
                context = context.with_plan(revised_plan).with_revision_attempt_incremented()
                final_selection = deps.template_selector.select_final(context.plan, preliminary_candidates)
                context = context.with_template_selection(final_selection)
                context = context.with_decision(_trace(
                    "final_template_selection", f"template={final_selection.template}(Revision後再評価)",
                    final_selection.rationale
                    + f" | differs_from_preliminary={final_selection.differs_from_preliminary}",
                ))
                critic_report = deps.design_critic.evaluate(context.plan, context.template_selection, context.requirements)
                context = context.with_critic_report(critic_report)
                context = context.with_decision(_trace(
                    "design_critic", f"release_ready={critic_report.release_ready}(Revision後再評価)",
                    f"implemented_checks_score={critic_report.implemented_checks_score:.2f}, "
                    f"issues={[i.category for i in critic_report.issues]}",
                    confidence=critic_report.implemented_checks_score,
                ))

            # 12. Forge IR Compilation
            # FORGE v0.6対応(FORGE IR v1 Phase2): 対象3 Domain
            # (fishing_log/household_budget/habit_tracking)のみ、
            # `IRGenerator` → `ForgeLanguageCompiler`という新しい経路を
            # 通す。それ以外のDomainは、既存の`deps.compiler.compile()`
            # (Checklist単一画面)をそのまま使う(無変更)。
            #
            # `IRGenerator`/`ForgeLanguageCompiler`は`CognitiveDependencies`
            # へは追加していない(状態を持たない純粋なクラスであり、
            # Mock差し替えの必要が無いため。`CognitiveDependencies`・
            # `_default_cognitive_dependencies()`・既存の全テスト
            # フィクスチャへの変更を避け、変更範囲を最小限に留める
            # ための意図的な設計判断)。
            #
            # **FORGE-PRODUCT-VISION-002(2026-08-12)での変更**: 以前は、
            # Curated Domain Library(手書きテーブル)に載っているDomain
            # だけがこの型付きCRUD経路を通り、それ以外は**全て**
            # Checklist(型も編集も無い、文字列が並ぶだけ)へ落ちていた。
            # つまり「作れるアプリの種類」の上限が、人手でテーブルに
            # 書いた数と一致していた。今回、テーブルに無いDomainについて
            # `EntitySynthesizer`(記録するデータ構造をAIに設計させ、
            # 決定的に検証する)を挟み、合成できた場合は**手書きDomainと
            # 同じ経路**へ合流させる。合成できなかった場合(AIの応答が
            # 不正、Provider未注入等)は、従来どおりChecklistへ安全に
            # フォールバックする——この機能が失敗しても以前より悪くは
            # ならない、という形にしている。
            domain_category_value = context.domain_classification.primary_domain.category.value
            ir = None
            entity_source = "curated"
            if domain_category_value in SUPPORTED_DOMAIN_CATEGORIES:
                ir = IRGenerator().generate(context.plan, domain_category=domain_category_value)
                assert ir is not None  # SUPPORTED_DOMAIN_CATEGORIESに含まれる場合は必ず生成される
            elif deps.entity_synthesizer is not None:
                synthesized_spec = deps.entity_synthesizer.synthesize(
                    context.plan,
                    user_text=context.raw_input,
                    domain_name=domain_category_value,
                )
                if synthesized_spec is not None:
                    ir = IRGenerator().build_from_spec(synthesized_spec)
                    entity_source = "synthesized"

            if ir is not None:
                context = context.with_decision(_trace(
                    "entity_source",
                    f"{entity_source}({domain_category_value})",
                    "Curated Domain Libraryの手書き定義を使用"
                    if entity_source == "curated"
                    else "AIが合成したデータ構造を使用(決定的な検証・サニタイズ済み)",
                ))
                forge_document = ForgeLanguageCompiler().compile(
                    ir, domain_category=domain_category_value, title=context.plan.title
                )
            else:
                # FORGE-AI-QUALITY-001(2026-08-11): 以前はここで
                # `context.template_selection.template`を一切渡しておらず、
                # Template Selectorが"form"等を選んでも常にChecklist単一
                # 画面になっていた(実機Gemini確認で発見)。`Compiler.
                # compile()`が実際に分岐へ対応しているのは現状"form"のみ
                # (`compiler.py`参照)、それ以外のtemplate名は引き続き
                # Checklistへフォールバックする。
                forge_document = deps.compiler.compile(
                    context.plan, domain_category=domain_category_value,
                    template=context.template_selection.template,
                )

            # 13. Initial Quality Evaluation(共有Legacy Protocol、無変更。M004の責務)
            initial_quality = deps.quality_engine.evaluate(forge_document, context.plan)

        except (AmbiguityError, ConfirmationRequired) as exc:
            request = deps.escalation_handler.build_confirmation_request(context, reason=str(exc))
            return CognitivePipelineNeedsConfirmation(
                confirmation_request=request, reached_stage=getattr(exc, "stage", "unknown"),
                partial_context=context, decision_trace=context.decision_trace,
            )
        except (PlanningError, CriticFailure) as exc:
            return CognitivePipelineFailed(
                error=exc, reached_stage=getattr(exc, "stage", "unknown"), decision_trace=context.decision_trace,
            )
        # NotImplementedErrorはここで一切捕捉しない(Blueprint 6.2節)。

        assert_context_ready_for_success(context)
        return CognitivePipelineSuccess(context=context, ir=forge_document, initial_quality=initial_quality)


def _trace(
    stage: str, decision: str, reason: str, *,
    confidence: float | None = None,
    confidence_observation: OverallConfidence | None = None,
    shadow_judgment: object | None = None,
):
    from forge_ai.core.orchestration.cognitive_types import DecisionTrace

    return DecisionTrace(
        stage=stage, decision=decision, reason=reason,
        confidence=confidence, confidence_observation=confidence_observation,
        shadow_judgment=shadow_judgment,
    )


_HIGH_RISK_HINT_KEYWORDS = ("医療", "福祉", "介護", "個人情報")


def _is_high_risk_domain_hint(raw_input: str) -> bool:
    """M006 4.4節: 検出失敗時、Privacy/Health/Welfare関連の可能性がある
    かどうかを、正式なDomain Classificationを待たずに軽量判定する。"""
    return any(keyword in raw_input for keyword in _HIGH_RISK_HINT_KEYWORDS)


def _should_escalate_for_low_confidence(intent, classification) -> bool:
    """CEO実物監査(Phase 1.1)指摘6への対応。単一の`classification.
    confidence`(=domain_coverage)だけで判断せず、以下3指標を明示的に
    組み合わせる。固定辞書によるIntent抽出と固定Domain辞書の一致
    (自己採点に近い性質)を、そのまま自然言語理解全体への高confidence
    とはみなさない。

    * intent_extraction_confidence(`intent.confidence`): Intent
      Recognizer自身が「入力から何かしら抽出できた」と判断した度合い。
    * domain_coverage(`classification.domain_coverage`): 抽出された
      concept/actionのうち、primary_domainが辞書上で説明できた割合。
    * domain_score_margin(`classification.score_margin`): 1位と2位の
      差。僅差の場合、辞書の偶然の一致による誤判定の可能性が上がる。

    **修正した論理矛盾(FORGE_v0.2_修正指示.md P1 5章)**: 以前は
    `margin < 0.2 and coverage < 0.8`という、margin(僅差)と
    coverage(説明力)の**両方**が低い場合にのみ確認要求していた。
    しかし「出欠を管理したい」のような、2つのDomain(attendance・
    task_management)が同じ概念("status")へ**完全同点**(margin=0.0)で
    一致するケースでは、その1つの概念だけでintentの信号を100%説明できて
    しまう(coverage=1.0)ため、`margin < 0.2 and coverage < 0.8`の
    AND条件が成立せず、**完全な同点にもかかわらず確認要求されない**という
    論理的な不整合が実際に発生することを確認した(coverageが高いことは
    「複数のDomainが同じ語彙を説明できる」ことの結果であり、「どちらが
    正しいか分かっている」ことの根拠にはならない)。

    修正: 事実上の同点(margin < 0.1)は、coverageの値に関わらず常に
    確認要求する(coverageが高いほど「説明はできるが、どちらか分からない」
    という不確実性がむしろ際立つため、高coverageを理由に見逃してはならない)。

    **Task042-2 Phase B(2026-07-21)でのリファクタリング**: 判定ロジック
    の実体を`confidence.compute_legacy_escalation_reasons()`へ切り出し、
    この関数は`bool(...)`を返すだけの薄いラッパーにした。切り出した
    関数は、この docstring が説明する4つの条件を一字一句同じ順序・
    同じ閾値で評価するため、**この関数の戻り値(bool)は、リファクタ
    リング前と完全に同じ**である(既存のテスト・既存挙動への影響は
    無い。Shadow比較(`compute_shadow_judgment()`)が同じロジックを
    参照できるようにするための、内部実装のみの変更)。
    """
    return bool(compute_legacy_escalation_reasons(intent, classification))


def _is_low_risk_reversible(classification) -> bool:
    """M006 4.3節「低リスクかつ後から安全に変更可能な用途のみ、Genericで
    仮設計可能」。第一段階では、primary_domainがGenericである場合のみを
    低リスクとみなす(Generic自体が「まだ確定していない」ことを前提にした
    Domainであるため)。"""
    return classification.primary_domain.category.value == "generic"
