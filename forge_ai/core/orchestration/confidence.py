"""Confidence Model計算ロジック(ADR-007、Task042-1・Task042-2 Phase B)。

`docs/adr/ADR-007-confidence-must-affect-control-flow.md`が要求する
`overall_confidence`(M006 14.1節)を、既存の`Intent`・
`DomainClassification`から計算する。

**Task042-1(2026-07-21)の位置づけ(最重要)**: このモジュールが提供する
`compute_overall_confidence()`は、**観測専用**である。呼び出し側
(`pipeline_orchestrator.py`)は、この結果を`DecisionTrace`へ記録する
だけであり、**いかなる`if`分岐にも使わない**。既存の制御フロー
(`_should_escalate_for_low_confidence()`・`_is_low_risk_reversible()`、
`pipeline_orchestrator.py`)は、このモジュール導入前と全く同じロジック
のまま、一切変更していない。

**Task042-2 Phase B(2026-07-21)で追加した内容**: 「現行モデル」
(`intent_confidence`・`domain_coverage`・`score_margin`という3信号への
4つのOR条件、MIN的性質)と「Shadowモデル」(`overall_confidence`という
単一の集約値、AVG的性質)の判定を、**同一入力に対して並行計算し比較する**
`ShadowJudgment`を追加した。

**この`ShadowJudgment`もPhase Bの時点では観測専用である。** 実際の
Success/Confirmation判定には、引き続き`pipeline_orchestrator.py`の
`_should_escalate_for_low_confidence()`・`_is_low_risk_reversible()`
だけが使われる(下記`compute_legacy_escalation_reasons()`は、
`_should_escalate_for_low_confidence()`が実際に使う判定ロジックそのもの
を、理由付きで再利用可能な形に切り出したもの——**ロジックの実体は1箇所
だけに存在し、重複させない**設計)。

Task042-2 Phase Bの成果物は、DecisionTrace・専用テスト・比較レポート
(`forge_ai/tests/test_confidence_model_comparison.py`)としてのみ
使われ、Phase C(実際の置換、別途CEO承認が必要)より前には、パイプラインの
挙動を一切変えない。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import ConfidenceRecord, DomainClassification, OverallConfidence


def compute_overall_confidence(intent: Intent, classification: DomainClassification) -> OverallConfidence:
    """`intent`・`classification`から`OverallConfidence`を組み立てる。

    **観測専用(このモジュールのdocstring参照)**。`entity_confidence`・
    `planning_confidence`・`template_confidence`は、対応する段階が
    まだ個別のconfidenceを算出していないため、常に`None`のままである
    (Task042-1時点の既知の制限、`OverallConfidence`のdocstring参照)。
    """
    intent_confidence = ConfidenceRecord(
        value=intent.confidence,
        basis=(
            f"required_concepts={len(intent.required_concepts)}件抽出",
            f"required_actions={len(intent.required_actions)}件抽出",
        ),
    )
    domain_confidence = ConfidenceRecord(
        value=classification.domain_coverage,
        basis=(
            f"primary_domain={classification.primary_domain.category.value}",
            f"score_margin={classification.score_margin:.2f}",
            f"candidates={len(classification.candidates)}件中の最上位",
        ),
    )
    return OverallConfidence(intent_confidence=intent_confidence, domain_confidence=domain_confidence)


# ---------------------------------------------------------------------------
# Task042-2 Phase B: Shadow Judgment(現行モデル vs overall_confidence
# モデルの比較、観測専用)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ThresholdsUsed:
    """現行モデル・Shadowモデル双方が使う閾値を、コード中に埋め込むだけで
    なく、後から比較可能な構造化データとして保持する(CEO指示)。

    値そのものは、`_should_escalate_for_low_confidence()`(現行モデル、
    `pipeline_orchestrator.py`)が実際に使っている値と完全に一致させる
    (この定数を変更する場合は、必ず現行モデルの実装もあわせて確認する
    こと。逆に、Shadow側の閾値のみを変更したい場合は、後述の`compute_
    shadow_judgment()`へ`thresholds`引数として別のインスタンスを渡す
    ことで、現行モデルに触れずに実験できる)。
    """

    legacy_coverage_threshold: float = 0.5
    legacy_intent_confidence_threshold: float = 0.5
    legacy_margin_near_tie_threshold: float = 0.1
    legacy_margin_combined_threshold: float = 0.2
    legacy_coverage_combined_threshold: float = 0.8
    shadow_overall_confidence_threshold: float = 0.5
    shadow_medium_band_upper: float = 0.8


DEFAULT_THRESHOLDS_USED = ThresholdsUsed()


def compute_legacy_escalation_reasons(
    intent: Intent, classification: DomainClassification, thresholds: ThresholdsUsed = DEFAULT_THRESHOLDS_USED,
) -> tuple[str, ...]:
    """現行モデル(`_should_escalate_for_low_confidence()`、
    `pipeline_orchestrator.py`)が確認要求と判断する、全ての理由を
    列挙する。

    **重要**: `_should_escalate_for_low_confidence()`は、このタプルが
    **空でないかどうか**(`bool(...)`)だけを見る、薄いラッパーに
    リファクタリングした(Task042-2 Phase B)。判定ロジックの実体は
    ここ1箇所だけに存在し、現行モデル本体とShadow比較の両方が同じ
    ロジックを参照する(重複させない)。**この関数自体の呼び出し順・
    各条件式は、リファクタリング前の`_should_escalate_for_low_
    confidence()`と一字一句同じであり、`bool(この関数の戻り値)`は
    リファクタリング前と完全に同じ結果を返す**(既存挙動への影響
    無し、と言えるのはこのため)。

    元の実装(短絡評価で最初に一致した1件だけでTrueを返す)とは異なり、
    **該当する理由を全て集める**(Shadow比較の診断情報としては、
    「なぜ確認要求になったか」を複数把握できる方が有用なため。
    `bool(タプル)`による最終的な真偽値は、OR条件として元の実装と
    等価)。
    """
    coverage = classification.domain_coverage
    intent_confidence = intent.confidence
    margin = classification.score_margin

    reasons: list[str] = []
    if coverage < thresholds.legacy_coverage_threshold:
        reasons.append(f"domain_coverage={coverage:.2f}が閾値{thresholds.legacy_coverage_threshold}未満")
    if intent_confidence < thresholds.legacy_intent_confidence_threshold:
        reasons.append(
            f"intent_confidence={intent_confidence:.2f}が閾値"
            f"{thresholds.legacy_intent_confidence_threshold}未満"
        )
    if margin < thresholds.legacy_margin_near_tie_threshold:
        reasons.append(f"score_margin={margin:.2f}が僅差閾値{thresholds.legacy_margin_near_tie_threshold}未満(事実上の同点)")
    if margin < thresholds.legacy_margin_combined_threshold and coverage < thresholds.legacy_coverage_combined_threshold:
        reasons.append(
            f"score_margin={margin:.2f}<{thresholds.legacy_margin_combined_threshold} かつ "
            f"domain_coverage={coverage:.2f}<{thresholds.legacy_coverage_combined_threshold}"
        )
    return tuple(reasons)


def classify_risk(
    *, intent_confidence: float, domain_confidence: float, score_margin: float, overall_confidence: float,
    thresholds: ThresholdsUsed = DEFAULT_THRESHOLDS_USED,
) -> str:
    """CEO指示の5分類 + 「高信頼度で問題無し」の計6種類のいずれかを返す。

    個別信号が閾値を下回っているかどうかを優先して判定し(診断として
    より具体的なため)、どの信号も低くない場合にのみMEDIUM帯かどうかを
    見る、という優先順位にした(1つの入力が同時に複数の分類基準へ
    該当しうる場合の、決定的な判定順序)。

    `score_margin`の「低い」判定には、現行モデルの2つの関連閾値
    (`legacy_margin_near_tie_threshold`・`legacy_margin_combined_
    threshold`)のうち、より緩い(大きい)方——
    `legacy_margin_combined_threshold`(既定0.2)——を使う(分類目的の
    簡略化であり、制御フローには使わない。この関数自体がShadow比較・
    レポート専用であるため)。
    """
    low_signals: list[str] = []
    if intent_confidence < thresholds.legacy_intent_confidence_threshold:
        low_signals.append("intent_confidence")
    if domain_confidence < thresholds.legacy_coverage_threshold:
        low_signals.append("domain_confidence")
    if score_margin < thresholds.legacy_margin_combined_threshold:
        low_signals.append("score_margin")

    if len(low_signals) >= 2:
        return "multiple_signals_low"
    if len(low_signals) == 1:
        return f"{low_signals[0]}_only_low"
    if thresholds.shadow_overall_confidence_threshold <= overall_confidence < thresholds.shadow_medium_band_upper:
        return "medium_band"
    return "high_confidence"


@dataclass(frozen=True)
class ShadowJudgment:
    """現行モデルとoverall_confidenceモデルの判定を、同一入力に対して
    並行計算した結果(Task042-2 Phase B、観測専用)。

    **このオブジェクトの値は、Success/Confirmation判定には一切使わ
    れない**(DecisionTrace・比較レポート・専用テストでのみ参照する)。
    """

    legacy_should_escalate: bool
    shadow_should_escalate: bool
    agrees: bool
    legacy_reasons: tuple[str, ...]
    shadow_reason: str | None
    intent_confidence: float
    domain_confidence: float
    score_margin: float
    overall_confidence: float
    thresholds_used: ThresholdsUsed
    risk_classification: str

    @property
    def comparison_category(self) -> str:
        """CEO指示の4分類(`both_escalate`・`both_continue`・
        `legacy_escalate_shadow_continue`・
        `legacy_continue_shadow_escalate`)のいずれか1つを返す。
        `agrees`から導出可能な値だが、レポート等でそのまま文字列として
        使えるよう、プロパティとして用意した。"""
        if self.legacy_should_escalate and self.shadow_should_escalate:
            return "both_escalate"
        if not self.legacy_should_escalate and not self.shadow_should_escalate:
            return "both_continue"
        if self.legacy_should_escalate and not self.shadow_should_escalate:
            return "legacy_escalate_shadow_continue"
        return "legacy_continue_shadow_escalate"


def compute_shadow_judgment(
    intent: Intent, classification: DomainClassification, thresholds: ThresholdsUsed = DEFAULT_THRESHOLDS_USED,
) -> ShadowJudgment:
    """`intent`・`classification`から`ShadowJudgment`を組み立てる。
    観測専用(このモジュールのdocstring参照)。"""
    overall = compute_overall_confidence(intent, classification)

    legacy_reasons = compute_legacy_escalation_reasons(intent, classification, thresholds)
    legacy_should_escalate = bool(legacy_reasons)

    if overall.value < thresholds.shadow_overall_confidence_threshold:
        shadow_reason: str | None = (
            f"overall_confidence={overall.value:.2f}が閾値"
            f"{thresholds.shadow_overall_confidence_threshold}未満"
        )
    else:
        shadow_reason = None
    shadow_should_escalate = shadow_reason is not None

    risk_classification = classify_risk(
        intent_confidence=overall.intent_confidence.value,
        domain_confidence=overall.domain_confidence.value,
        score_margin=classification.score_margin,
        overall_confidence=overall.value,
        thresholds=thresholds,
    )

    return ShadowJudgment(
        legacy_should_escalate=legacy_should_escalate,
        shadow_should_escalate=shadow_should_escalate,
        agrees=legacy_should_escalate == shadow_should_escalate,
        legacy_reasons=legacy_reasons,
        shadow_reason=shadow_reason,
        intent_confidence=overall.intent_confidence.value,
        domain_confidence=overall.domain_confidence.value,
        score_margin=classification.score_margin,
        overall_confidence=overall.value,
        thresholds_used=thresholds,
        risk_classification=risk_classification,
    )
