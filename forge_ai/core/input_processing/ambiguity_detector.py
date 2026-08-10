"""Ambiguity Detector(FORGE-MILESTONE-007第一段階、M006 4章。
FORGE_v0.2_修正指示.md P2 8章で8分類完成)。

M006 4章の8分類(missing_goal/missing_actor/missing_domain/missing_data/
missing_action/conflicting_requirements/multiple_possible_templates/
privacy_safety_permission)を**全て**実装した。

* missing_goal(HIGH): 入力が極端に短い、または空。
* privacy_safety_permission(HIGH、M006 4.3節「優先順位1」に対応):
  医療・福祉・個人情報等のキーワードを含む場合。
* missing_actor(LOW): 利用者・関係者を示唆する語が文中に無い。
  M006 4.2節「LOW: Actorが明示されていないが『利用者本人』と仮定して
  問題ない」に対応する既定値の記録専用であり、通常の入力のほとんどで
  該当する(意図的な設計。単独では確認要求を発生させない)。
* missing_domain(MEDIUM): `forge_ai/core/lexicon.py`の概念語彙が
  1件も一致しない(=どのDomainの語彙とも一致しない)場合。
* conflicting_requirements(MEDIUM): 明確に矛盾しうる語のペア
  (`lexicon.CONTRADICTION_PAIRS`)が、それぞれ否定を伴わない形で
  同時に出現する場合(P2 9章対応、下記4.1節参照)。
* multiple_possible_templates(MEDIUM): 一致した概念語が、Generic以外の
  2つ以上の異なるDomainに属する場合(Domainをまたいだ概念の重複、
  例:「出欠」は`attendance`・`task_management`の両方に対応しうる)。
* missing_data(MEDIUM): 汎用的な操作語(`lexicon.GENERIC_ACTION_HINTS`、
  「管理」「作る」等)はあるが、対象となる概念語が1件も無い場合
  (例:「管理したい」だけで対象が不明)。
* missing_action(MEDIUM): 概念語は一致するが、`lexicon.ACTION_KEYWORDS`
  にも`lexicon.GENERIC_ACTION_HINTS`にも1件も一致しない場合
  (例:「買い物」だけで、動詞が一切無い)。

**P2 8章での設計上の注意(以前の見送り理由と、今回の解決方法)**:
`lexicon.ACTION_KEYWORDS`(Domain Classificationのスコアリング用)は
意図的に「管理」「作る」等の汎用動詞を含まない設計であり、この辞書の
「0件一致」だけを操作意図の代理指標にすると、「買い物リストを作りたい」
のようなごく普通の入力でも誤検出することを、前回実装時に検証で確認
していた。今回は、Ambiguity Detection専用の、より広い動詞集合
`lexicon.GENERIC_ACTION_HINTS`を新設して使うことで、この誤検出を
避けた。6例のGolden Testで実際に誤検出が発生しないことを確認済み
(`test_input_processing.py`)。
"""

from __future__ import annotations

import re

from forge_ai.core.domain_model import DomainRegistry
from forge_ai.core.lexicon import ACTION_KEYWORDS, ACTOR_HINTS, CONCEPT_KEYWORDS, CONTRADICTION_PAIRS, GENERIC_ACTION_HINTS
from forge_ai.core.orchestration.cognitive_types import AmbiguityIssue, AmbiguityReport

# M006 4.3節「優先順位1」に対応する、Privacy/Safety/Permission関連の
# 軽量なキーワード予備チェック(正式なDomain Classificationの代わりでは
# ない。Blueprint 4.0節・M006 4.4節と同じ位置づけ)。
_PRIVACY_SAFETY_KEYWORDS = (
    "医療", "病歴", "症状", "薬", "処方",
    "福祉", "支援記録", "要介護",
    "個人情報", "マイナンバー", "パスワード", "口座番号",
)

_MIN_MEANINGFUL_LENGTH = 2

# severityの重大度順(集約に使う)。
_SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3}

# P2 9章「否定語を考慮する」対応: 矛盾ペアの直前に否定語が付いている場合、
# 実際には矛盾していない(例:「公開はしない」は「公開」の否定であり、
# 「非公開」と組み合わさっても矛盾ではなく同じ意図の言い換えになりうる)。
# 簡易ヒューリスティックであり、完全な構文解析ではない(既知の制限、
# 語順が大きく異なる/離れた位置の否定は捕捉できない)。
_NEGATION_MARKERS = ("しない", "せず", "なし", "不要", "いらない", "ではない")
_NEGATION_WINDOW = 6  # 語の直後、何文字以内の否定語を「その語への否定」とみなすか


def _is_negated(text: str, word: str) -> bool:
    """`word`の直後`_NEGATION_WINDOW`文字以内に否定語があれば、その語は
    否定された(打ち消された)とみなす。"""
    for match in re.finditer(re.escape(word), text):
        window = text[match.end(): match.end() + _NEGATION_WINDOW]
        if any(marker in window for marker in _NEGATION_MARKERS):
            return True
    return False


class AmbiguityDetector:
    """`AmbiguityDetectorProtocol`を満たす。"""

    def detect(self, normalized, registry: DomainRegistry) -> AmbiguityReport:
        text = normalized.normalized_text.strip()
        issues: list[AmbiguityIssue] = []

        # 1. missing_goal(HIGH)
        if len(text) < _MIN_MEANINGFUL_LENGTH:
            issues.append(
                AmbiguityIssue(
                    category="missing_goal",
                    severity="high",
                    description=f"入力が短すぎて目的を判断できません(文字数: {len(text)})。",
                )
            )

        # 2. privacy_safety_permission(HIGH、M006 4.3節優先順位1)
        for keyword in _PRIVACY_SAFETY_KEYWORDS:
            if keyword in text:
                issues.append(
                    AmbiguityIssue(
                        category="privacy_safety_permission",
                        severity="high",
                        description=f"'{keyword}' という、機微な情報を扱う可能性のある語が含まれています。"
                        "記録範囲・共有範囲の確認が必要です。",
                    )
                )
                break  # 1件検出できれば十分(複数該当してもHIGHは1件で足りる)

        # 3. missing_actor(LOW、既定値記録専用)
        if not any(hint in text for hint in ACTOR_HINTS):
            issues.append(
                AmbiguityIssue(
                    category="missing_actor",
                    severity="low",
                    description="利用者・関係者が明示されていません。「利用者本人」と仮定して続行します。",
                )
            )

        # 概念語のマッチ状況(missing_domain・multiple_possible_templates・
        # missing_data・missing_actionの全てで使う)
        matched_concepts_to_domains: dict[str, list[str]] = {}
        for keyword, concept in CONCEPT_KEYWORDS:
            if keyword in text:
                domains_with_concept = [
                    d.category.value
                    for d in registry.all_domains()
                    if d.category.value != "generic" and any(c.name == concept for c in d.typical_concepts)
                ]
                if domains_with_concept:
                    matched_concepts_to_domains.setdefault(concept, [])
                    for d in domains_with_concept:
                        if d not in matched_concepts_to_domains[concept]:
                            matched_concepts_to_domains[concept].append(d)
        has_concept_match = bool(matched_concepts_to_domains)

        # 動詞側のマッチ状況(missing_data・missing_actionで使う)
        has_strict_action_match = any(keyword in text for keyword, _ in ACTION_KEYWORDS)
        has_generic_action_hint = any(hint in text for hint in GENERIC_ACTION_HINTS)
        has_any_action_signal = has_strict_action_match or has_generic_action_hint

        # 4. missing_domain(MEDIUM): 既知の概念語が1件も一致しない
        if not has_concept_match:
            issues.append(
                AmbiguityIssue(
                    category="missing_domain",
                    severity="medium",
                    description="どの分野(買い物・タスク管理・日記等)向けのアプリか、キーワードから判断できません。",
                )
            )

        # 5. multiple_possible_templates(MEDIUM): 一致した概念語が2つ以上の
        # 異なるDomainにまたがる場合(例:「出欠」はattendance/task_managementの両方)
        all_matched_domains: set[str] = set()
        for domains_for_concept in matched_concepts_to_domains.values():
            all_matched_domains.update(domains_for_concept)
        if len(all_matched_domains) >= 2:
            issues.append(
                AmbiguityIssue(
                    category="multiple_possible_templates",
                    severity="medium",
                    description=f"複数の分野({', '.join(sorted(all_matched_domains))})に該当しうる語が含まれています。",
                )
            )

        # 6. conflicting_requirements(MEDIUM、P2 9章: 否定語を考慮する)
        for word_a, word_b in CONTRADICTION_PAIRS:
            if word_a in text and word_b in text:
                if _is_negated(text, word_a) or _is_negated(text, word_b):
                    # どちらかが否定されている場合、実際には矛盾していない
                    # 可能性が高い(例:「公開はしないが、非公開設定もしたい」
                    # ではなく「公開はしない」で完結している場合等)。
                    continue
                issues.append(
                    AmbiguityIssue(
                        category="conflicting_requirements",
                        severity="medium",
                        description=f"'{word_a}' と '{word_b}' が同時に要求されており、矛盾する可能性があります。",
                    )
                )
                break

        # 7. missing_data(MEDIUM): 操作の意図はあるが、対象の概念語が無い
        if has_any_action_signal and not has_concept_match:
            issues.append(
                AmbiguityIssue(
                    category="missing_data",
                    severity="medium",
                    description="何を操作したいかは伝わりますが、対象となるデータが分かりません。",
                )
            )

        # 8. missing_action(MEDIUM): 概念語はあるが、操作を示す語が一切無い
        if has_concept_match and not has_any_action_signal:
            issues.append(
                AmbiguityIssue(
                    category="missing_action",
                    severity="medium",
                    description="対象は伝わりますが、追加・記録・管理等、何をしたいかが分かりません。",
                )
            )

        if not issues:
            overall_severity = "low"
        else:
            # FORGE v0.2 PART B 7.1節対応: 以前は「issuesが1件でもあれば
            # 無条件でmedium以上」という集約だったため、missing_actor(LOW)
            # のような「既定値で継続してよい」issueが1件あるだけで、
            # 完全に明確な入力までoverall_severityが"medium"へ格上げされて
            # しまっていた。M006 4.2節「LOW: 既定値を採用して続行する」の
            # 意図に合わせ、最も重大な(severityが最も高い)issueに基づいて
            # 集約する(LOWのみならoverall_severityも"low"のまま)。
            highest = max(issues, key=lambda i: _SEVERITY_RANK.get(i.severity, 0))
            overall_severity = highest.severity

        return AmbiguityReport(issues=tuple(issues), overall_severity=overall_severity, detection_status="ok")
