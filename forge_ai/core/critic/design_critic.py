"""Design Critic(M007 Phase 1 Minimal Cognitive Slice、M006 14章)。

Validatorとは別に、設計としての良し悪しを評価する。**最小実装**として、
M006 14章の14評価軸のうち、決定的に判定しやすい8軸を実装する
(Completeness/Simplicity/Empty State Quality/Validation Coverage/
Navigation Coherence/Privacy/Accessibility/Intent Meaning Fidelity)。
残り6軸(Domain Consistency/State Completeness/Action Completeness/
Error Recovery/Explainability/Runtime Safety)は未実装であり、
`CriticReport.unevaluated_axes`に明示する。

**CEO実物監査(Phase 1.1)対応**: 以前は実装済み4軸だけで
`score=1.00`となり、「アプリ全体の品質が完璧」であるかのように
誤解されうる問題があった。以下を追加した。

* `implemented_checks_score`/`coverage_ratio`を分離し、`score`
  (後方互換)とは別に、「実装済み軸のうち何割を評価したか」を
  明示する(CEO提示A案)。
* 未割当の必須(`mandatory=True`)要件が残っている場合、
  `release_ready=True`にしない(4評価軸が全て満点でも、である)。
* Privacy要件が未割当(mandatory=True)の場合、blocking(high)issueにする。
* Accessibility要件が未割当の場合: mandatory=Falseならmedium/
  non-blocking、mandatory=Trueならhigh/blocking(Privacyと同じ扱い)。
  第一段階の既定実装ではAccessibility要件は常にmandatory=Falseで
  生成されるため、通常はmedium/non-blockingとなる。
* 画面が1つで遷移が不要な場合と、複数画面なのにnavigation_edgesが
  空(遷移設計が欠落)の場合を区別する。

**FORGE-MILESTONE-007 Phase 1.2でMeaning Model導入に伴い追加**:
`intent_meaning_fidelity`軸(M006 14章の"Intent Fidelity"に対応)。
Meaning由来(`derived_from == "meaning"`)のmandatory要件が未割当の
場合、blocking issueにする(一般的な`unassigned_mandatory_requirement`
とは別に、Meaning固有の観点として明示的に評価する)。
"""

from __future__ import annotations

from forge_ai.core.orchestration.cognitive_types import CriticIssue, CriticReport, RequirementSet, TemplateSelection
from forge_ai.core.planner import ApplicationPlan

_RELEASE_READY_THRESHOLD = 0.6

# M006 14章が定義する14評価軸のうち、このクラスが実際に評価するもの。
_EVALUATED_AXES: tuple[str, ...] = (
    "completeness", "simplicity", "empty_state_quality", "validation_coverage",
    "navigation_coherence", "privacy", "accessibility", "intent_meaning_fidelity",
)
_ALL_M006_AXES: tuple[str, ...] = (
    "completeness", "simplicity", "intent_meaning_fidelity", "domain_consistency",
    "navigation_coherence", "state_completeness", "action_completeness",
    "validation_coverage", "empty_state_quality", "error_recovery",
    "accessibility", "privacy", "explainability", "runtime_safety",
)
_UNEVALUATED_AXES: tuple[str, ...] = tuple(a for a in _ALL_M006_AXES if a not in _EVALUATED_AXES)


class DesignCritic:
    """`DesignCriticProtocol`を満たす。"""

    def evaluate(
        self, plan: ApplicationPlan, template_selection: TemplateSelection, requirements: RequirementSet
    ) -> CriticReport:
        issues: list[CriticIssue] = []
        axis_scores: list[float] = []
        has_blocking_issue = False

        # Completeness: 全画面にkey_elementsが1つ以上あるか。
        screens_without_elements = [s for s in plan.screens if not s.key_elements]
        completeness = 1.0 if not screens_without_elements else 0.3
        axis_scores.append(completeness)
        if screens_without_elements:
            issues.append(CriticIssue(
                category="completeness", severity="high",
                evidence=f"{[s.name for s in screens_without_elements]}にkey_elementsが無い",
                recommended_fix="各画面に最低1つのデータ項目を割り当てる",
                affected_component="application_plan", auto_fixable=False,
            ))
            has_blocking_issue = True

        # Simplicity: 画面数が過剰でないか(第一段階は1〜3画面を妥当とする)。
        simplicity = 1.0 if len(plan.screens) <= 3 else 0.5
        axis_scores.append(simplicity)
        if len(plan.screens) > 3:
            issues.append(CriticIssue(
                category="simplicity", severity="medium",
                evidence=f"画面数が{len(plan.screens)}と多い",
                recommended_fix="関連する画面を統合できないか検討する",
                affected_component="application_plan", auto_fixable=False,
            ))

        # Empty State Quality: 全画面にempty_state_messageがあるか。
        screens_without_empty_state = [s for s in plan.screens if not s.empty_state_message]
        empty_state_quality = 1.0 if not screens_without_empty_state else 0.4
        axis_scores.append(empty_state_quality)
        if screens_without_empty_state:
            issues.append(CriticIssue(
                category="empty_state", severity="medium",
                evidence=f"{[s.name for s in screens_without_empty_state]}にEmpty State文言が無い",
                recommended_fix="データが0件の場合の案内文言を追加する",
                affected_component="application_plan", auto_fixable=True,
            ))

        # Validation Coverage: 全画面にvalidation_rulesがあるか。
        screens_without_validation = [s for s in plan.screens if not s.validation_rules]
        validation_coverage = 1.0 if not screens_without_validation else 0.5
        axis_scores.append(validation_coverage)
        if screens_without_validation:
            issues.append(CriticIssue(
                category="validation_coverage", severity="low",
                evidence=f"{[s.name for s in screens_without_validation]}にValidation記述が無い",
                recommended_fix="最低限の入力検証(空入力の扱い等)を明記する",
                affected_component="application_plan", auto_fixable=True,
            ))

        # Navigation Coherence(CEO実物監査Phase 1.1で新設): 画面が1つ
        # だけの場合は遷移が不要であり満点。複数画面なのに
        # navigation_edgesが空の場合のみ、遷移設計の欠落として指摘する
        # (「遷移が要らない」ことと「遷移設計を忘れた」ことを区別する)。
        if len(plan.screens) <= 1:
            navigation_coherence = 1.0
        elif plan.navigation_edges:
            navigation_coherence = 1.0
        else:
            navigation_coherence = 0.3
            issues.append(CriticIssue(
                category="navigation_coherence", severity="high",
                evidence=f"画面数が{len(plan.screens)}あるにもかかわらず、navigation_edgesが空です。",
                recommended_fix="画面間の遷移(どの操作でどの画面へ移動するか)を明記する",
                affected_component="application_plan", auto_fixable=False,
            ))
            has_blocking_issue = True
        axis_scores.append(navigation_coherence)

        # Privacy(CEO実物監査Phase 1.1で新設): privacy分類の要件が
        # unassigned_requirementsに残っている場合、blocking issueにする。
        unassigned_privacy = [
            r for r in requirements.requirements
            if r.category == "privacy" and r.description in plan.unassigned_requirements
        ]
        privacy_score = 1.0 if not unassigned_privacy else 0.0
        axis_scores.append(privacy_score)
        if unassigned_privacy:
            issues.append(CriticIssue(
                category="privacy", severity="high",
                evidence=f"未割当のPrivacy要件が{len(unassigned_privacy)}件残っています。",
                recommended_fix="記録範囲・共有範囲の確認をApplicationPlanへ反映する",
                affected_component="application_plan", auto_fixable=False,
            ))
            has_blocking_issue = True

        # Accessibility(CEO実物監査Phase 1.1で新設、2回目監査で方針を
        # 明確化): 既定(mandatory=False)の未割当はmedium/non-blocking。
        # ただしAccessibility要件がmandatory=Trueとして生成された場合
        # (第一段階の既定実装では発生しないが、将来の拡張に備える)は、
        # Privacyと同様にhigh/blockingとして扱う。
        unassigned_accessibility = [
            r for r in requirements.requirements
            if r.category == "accessibility" and r.description in plan.unassigned_requirements
        ]
        unassigned_mandatory_accessibility = [r for r in unassigned_accessibility if r.mandatory]
        accessibility_score = 1.0 if not unassigned_accessibility else 0.5
        axis_scores.append(accessibility_score)
        if unassigned_mandatory_accessibility:
            issues.append(CriticIssue(
                category="accessibility", severity="high",
                evidence=f"未割当の**必須**Accessibility要件が{len(unassigned_mandatory_accessibility)}件残っています。",
                recommended_fix="キーボード操作等のアクセシビリティ要件をApplicationPlanへ反映する",
                affected_component="application_plan", auto_fixable=False,
            ))
            has_blocking_issue = True
        elif unassigned_accessibility:
            issues.append(CriticIssue(
                category="accessibility", severity="medium",
                evidence=f"未割当のAccessibility要件が{len(unassigned_accessibility)}件残っています(mandatory=False)。",
                recommended_fix="キーボード操作等のアクセシビリティ要件をApplicationPlanへ反映する",
                affected_component="application_plan", auto_fixable=False,
            ))

        # 未割当の必須(mandatory=True)要件が残っている場合、4軸(以下7軸)
        # が全て満点でもrelease_readyにしない(CEO実物監査Phase 1.1指摘5)。
        unassigned_mandatory = [
            r for r in requirements.requirements
            if r.mandatory and r.description in plan.unassigned_requirements
        ]
        if unassigned_mandatory:
            issues.append(CriticIssue(
                category="unassigned_mandatory_requirement", severity="high",
                evidence=f"未割当の必須要件が{len(unassigned_mandatory)}件残っています: "
                         f"{[r.description[:30] for r in unassigned_mandatory]}",
                recommended_fix="必須要件を画面へ割り当てるか、Plan全体の対応方針を明記する",
                affected_component="application_plan", auto_fixable=False,
            ))
            has_blocking_issue = True

        # Intent Meaning Fidelity(CEO実物監査Phase 1.2で新設、M006 14章
        # "Intent Fidelity"に対応): Meaning由来(derived_from=="meaning")
        # のmandatory要件が未割当の場合、blockingにする。一般的な
        # unassigned_mandatory_requirementとは別に、「入力文の意味に
        # 忠実か」という観点として明示的に評価する。
        unassigned_meaning_mandatory = [
            r for r in requirements.requirements
            if r.derived_from == "meaning" and r.mandatory and r.description in plan.unassigned_requirements
        ]
        meaning_fidelity_score = 1.0 if not unassigned_meaning_mandatory else 0.0
        axis_scores.append(meaning_fidelity_score)
        if unassigned_meaning_mandatory:
            issues.append(CriticIssue(
                category="intent_meaning_fidelity", severity="high",
                evidence=f"入力文から抽出したMeaning由来の必須要件が{len(unassigned_meaning_mandatory)}件、"
                         f"Planへ反映されていません: {[r.description[:40] for r in unassigned_meaning_mandatory]}",
                recommended_fix="Meaning由来のAction/Entity/Constraint/Permission等をApplicationPlanへ反映する",
                affected_component="application_plan", auto_fixable=False,
            ))
            has_blocking_issue = True

        implemented_checks_score = sum(axis_scores) / len(axis_scores) if axis_scores else 0.0
        coverage_ratio = len(_EVALUATED_AXES) / len(_ALL_M006_AXES)

        release_ready = (
            implemented_checks_score >= _RELEASE_READY_THRESHOLD
            and not any(i.severity == "high" for i in issues)
            and not has_blocking_issue
        )

        return CriticReport(
            release_ready=release_ready,
            score=implemented_checks_score,
            issues=tuple(issues),
            implemented_checks_score=implemented_checks_score,
            coverage_ratio=coverage_ratio,
            evaluated_axes=_EVALUATED_AXES,
            unevaluated_axes=_UNEVALUATED_AXES,
        )

