"""Cognitive Domain Classifier(FORGE-MILESTONE-007第一段階、M006 8章)。

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3 Task4.3の
スコアリング設計をそのまま実装する。IntentのRequired concepts/actionsと、
各Domainのtypical_concepts/typical_actionsとの実際の一致数に基づく。

confidenceは「Intentが実際に述べた情報のうち、primary_domainが説明
できた割合」(B案、Blueprint 4.3節で複数案を比較した上で採用したもの)。

**FORGE v0.3 Task2対応(スコアリング全面改訂)**: 以前はConcept一致と
Action一致を同じ重み(各1点)で加算していたため、「記録する」のような
汎用動詞1語だけの一致(Diary domainの`add_entry`)が、他Domainの
具体的なConcept一致と**同点**になってしまい、Domain判定が不安定に
なる不具合を実際に再現・確認した(例:「毎日の習慣を記録するアプリ」
が、"habit"というConceptを正しく検出していながら、"記録"→"add_entry"
というActionのみでDiaryへ競り勝たれてしまっていた)。

`Domain Score = Concept Score(重み高) + Action Score(重み低)`
へ改訂し、Concept一致を最も重視する設計にした。**「Object Score」に
ついて**: 指示書はConcept/Action/Objectの3項を挙げているが、この
実装のDomain定義(`typical_concepts`)は「対象領域に典型的なモノ
(Object/Entity)」を表す語彙であり、Concept ScoreとObject Scoreは
本アーキテクチャ上、同一の signal(`matched_concepts`)に由来する
(意図的な設計判断、`DomainConcept`のdocstring参照)。3項を別々の
独立したsignalとして扱う設計は今回採用しなかった。
"""

from __future__ import annotations

import dataclasses

from forge_ai.core.domain_model import DomainRegistry
from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import DomainCandidate, DomainClassification

# FORGE v0.3 Task2: Concept一致をAction一致より重視する重み付け。
# 具体的な倍率(2倍)は、実際に「記録する」1語のAction一致だけでは
# Concept 1件一致に競り勝てないようにする、という最低限の要求を
# 満たす値として選んだ(暫定値、実運用データに基づく再調整の余地が
# あることを明記する)。
_CONCEPT_WEIGHT = 2.0
_ACTION_WEIGHT = 1.0

# Action一致のみ(Concept一致が0件)の場合、confidenceに上限を課す
# (指示書「Actionだけ一致では高confidenceを出さないこと」の直接的な
# 保証。重み付けだけでは「他の候補が無い場合」に高confidenceのまま
# 残ってしまう可能性があるため、明示的な上限として二重に保証する)。
_ACTION_ONLY_CONFIDENCE_CAP = 0.5


class CognitiveDomainClassifier:
    """`CognitiveDomainClassifierProtocol`を満たす。"""

    def classify(self, intent: Intent, registry: DomainRegistry) -> DomainClassification:
        required_concepts = set(intent.required_concepts)
        required_actions = set(intent.required_actions)
        # FORGE v0.3 Task2: total_signalも同じ重みで計算し、confidence
        # (raw_score / total_signal)の分母・分子で重みの単位を揃える。
        total_signal = len(required_concepts) * _CONCEPT_WEIGHT + len(required_actions) * _ACTION_WEIGHT

        candidates: list[DomainCandidate] = []
        for domain in registry.all_domains():
            domain_concept_names = {c.name for c in domain.typical_concepts}
            matched_concepts = required_concepts & domain_concept_names
            matched_actions = required_actions & set(domain.typical_actions)
            raw_score = len(matched_concepts) * _CONCEPT_WEIGHT + len(matched_actions) * _ACTION_WEIGHT
            candidates.append(
                DomainCandidate(
                    domain=domain,
                    raw_score=raw_score,
                    normalized_score=0.0,  # 後段で埋める
                    matched_concepts=tuple(sorted(matched_concepts)),
                    matched_actions=tuple(sorted(matched_actions)),
                )
            )

        candidates.sort(key=lambda c: c.raw_score, reverse=True)

        # normalized_scoreを埋める(全体のシグナル数に対する割合)。
        divisor = max(1.0, total_signal)
        candidates = [
            dataclasses.replace(c, normalized_score=c.raw_score / divisor) for c in candidates
        ]

        primary = candidates[0]

        if primary.raw_score == 0:
            # 必須条件1(Blueprint 4.5節、CEO指摘5): 全Domainのスコアが0
            # -> Genericを明示的に選ぶ(スコア降順ソートの偶然に依存しない)。
            generic = next((c for c in candidates if c.domain.category.value == "generic"), primary)
            return DomainClassification(
                primary_domain=generic.domain,
                candidates=tuple(candidates),
                confidence=0.0,
                score_margin=0.0,
                rationale="Intentと一致するconcept/actionが見つからず、Genericへ既定しました。",
            )

        # FORGE_v0.2_修正指示.md P1 5章対応: score_marginは、Genericを
        # 除いた「実質的な競合Domain」との差で計算する。
        #
        # **発見した論理的不整合(このセッションで実際に再現・確認)**:
        # 以前は`candidates[1]`(2位、Genericを含む)をそのまま
        # 「次点」として使っていた。GenericのDomain定義は意図的に
        # 単一の広い概念("item")のみを持つため、"item"を含む多くの
        # 実在Domain(例: Shopping)と**常にtie(同点)**してしまう。
        # 結果、「買い物リストを作りたい」のようなごく普通の入力ですら
        # `score_margin = 0.0`になり、後続の低confidence判定
        # (`_should_escalate_for_low_confidence`)が「Genericとの
        # 意味の無いtie」と「本当に複数の実Domainが競合しているtie」
        # (例: 「出欠」がattendance/task_managementの両方に一致する
        # 場合)を区別できなくなっていた。
        #
        # 修正: primaryがGeneric自身でない限り、Genericを次点候補の
        # 対象から除外する(Genericは「何も一致しない場合の安全な
        # 既定値」であり、意味のある競合相手ではないため)。
        non_generic_runner_up = next(
            (c for c in candidates[1:] if c.domain.category.value != "generic"), None
        )
        if primary.domain.category.value == "generic":
            second_score = candidates[1].raw_score if len(candidates) > 1 else 0.0
        elif non_generic_runner_up is not None:
            second_score = non_generic_runner_up.raw_score
        else:
            second_score = 0.0
        score_margin = (primary.raw_score - second_score) / divisor

        confidence = primary.normalized_score
        # FORGE v0.3 Task2: Concept一致が0件(=Action一致のみでprimaryが
        # 決まった)場合、confidenceへ明示的な上限を課す。
        if not primary.matched_concepts:
            confidence = min(confidence, _ACTION_ONLY_CONFIDENCE_CAP)

        evidence = ", ".join(primary.matched_concepts + primary.matched_actions) or "(該当なし)"
        rationale = f"一致: {evidence}(raw_score={primary.raw_score:.1f}, margin={score_margin:.2f})"
        if not primary.matched_concepts:
            rationale += "(Action一致のみのためconfidenceに上限を適用)"

        return DomainClassification(
            primary_domain=primary.domain,
            candidates=tuple(candidates),
            confidence=confidence,
            score_margin=score_margin,
            rationale=rationale,
        )
