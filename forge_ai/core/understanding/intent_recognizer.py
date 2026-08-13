"""Cognitive Intent Recognizer(FORGE-MILESTONE-007第一段階、M006 7章)。

normalized_input・ambiguity_reportのみを入力とする(Domain/World/
Meaningより前に実行する、Blueprint Task4.0)。

**第一段階の簡略化(正直な申告)**: 本格的な日本語形態素解析
(MeCab等)は新規依存になるため使わない(禁止事項)。代わりに、
CEO指定の6例(買い物・タスク管理・日記・アンケート・予定・在庫)を
対象とした、決定的なキーワード辞書によるsubstringマッチングを行う
(既存`DomainRegistry.resolve_from_keywords()`と同じ手法を、日本語の
名詞・動詞に対して適用したもの)。

この辞書は`domain_model.py`の各Domainの`typical_concepts`/
`typical_actions`(英語識別子)と対応させてあり、後続のDomain
Classification(4段階目)が、ここで抽出した`required_concepts`/
`required_actions`を各Domainの語彙と突き合わせてスコアリングできる
ようにしている。
"""

from __future__ import annotations

from forge_ai.core.intent_model import Intent
from forge_ai.core.lexicon import ACTION_KEYWORDS as _ACTION_KEYWORDS
from forge_ai.core.lexicon import CONCEPT_KEYWORDS as _CONCEPT_KEYWORDS
from forge_ai.core.orchestration.cognitive_types import AmbiguityReport, NormalizedInput

# FORGE v0.2 PART B 7.1節対応: 語彙表は`forge_ai/core/lexicon.py`(共有の
# 下位層)へ移動した。`input_processing/ambiguity_detector.py`も同じ語彙を
# 必要とするようになったが、Blueprint Task5.2「同階層モジュール間の直接
# import禁止」により`understanding/`から直接importできないため、
# 依存方向の下位である`core/`へ辞書を移し、二重管理を避けた
# (以前ここにあった2つのタプル定義は削除し、`core/lexicon.py`を正とする)。

# FORGE_v0.2_最終修正指示(Final Gate)P3対応: `Intent.goal`は
# `ApplicationPlan.title`(ひいてはアプリのタイトル)にそのまま使われる
# (`planning/application_planner.py`参照)。以前は入力文をそのまま
# `goal`にしていたため、「買い物リストを作りたい」のような依頼文の
# 語尾がそのままアプリのタイトルとして表示されていた。ユーザーが読んで
# 自然な名詞句になるよう、末尾の典型的な依頼表現を取り除く。
#
# **既知の制限**: 単純な末尾一致による簡易処理であり、本格的な
# 日本語の活用形処理(MeCab等)ではない(このセッション全体の既存方針、
# `lexicon.py`と同じ制約)。想定外の言い回しでは末尾が除去されず、
# 元の文がそのまま残るだけであり、クラッシュはしない。
_TRAILING_REQUEST_PHRASES: tuple[str, ...] = (
    "を作りたいです", "を作りたい", "を作って", "を作成したいです", "を作成したい", "を作成して",
    "が欲しいです", "が欲しい", "がほしいです", "がほしい",
    "を管理したいです", "を管理したい", "を管理して", "を管理する",
    "をつけたいです", "をつけたい", "をつけて",
    "を記録したいです", "を記録したい", "を記録して", "を記録する",
    "を整理したいです", "を整理したい",
    "を追跡したいです", "を追跡したい",
    # FORGE-HANDOFF-LOCAL-AI-UX-004(2026-08-13)追加分。`/converse`の
    # 入り口では、ユーザーは「〜が欲しい」ではなく**困りごと**を言う
    # (「買い物で何買うか忘れちゃう」)。この言い回しの末尾も、
    # タイトルとしては不要な部分である。
    #
    # **正直な限界**: 困りごとの文は、末尾を落としても完全な名詞句には
    # ならない(「買い物で何買うか」)。ここで行っているのは「タイトルに
    # 愚痴の語尾を残さない」ことまでであり、要約ではない。完全な
    # 名詞句化には日本語の構文解析が要る(このセッション全体の方針
    # どおり、新規依存は追加しない)。
    "を忘れちゃいます", "を忘れちゃう", "忘れちゃいます", "忘れちゃう",
    "を忘れてしまいます", "を忘れてしまう", "忘れてしまいます", "忘れてしまう",
    "をよく忘れます", "をよく忘れる", "を忘れます", "を忘れる",
    "で困っています", "で困ってます", "で困ってる", "に困っています", "に困ってる",
    "が続きません", "が続かない",
    "が面倒です", "が面倒くさい", "が面倒",
)


def _derive_title_like_goal(text: str) -> str:
    """入力文から、依頼表現の末尾を取り除いた、タイトルらしい名詞句を作る。
    どの末尾パターンにも一致しない場合、元の文をそのまま返す
    (情報を失わない、安全側のフォールバック)。"""
    for suffix in _TRAILING_REQUEST_PHRASES:
        if text.endswith(suffix):
            trimmed = text[: -len(suffix)].strip()
            if trimmed:
                return trimmed
    return text


class CognitiveIntentRecognizer:
    """`CognitiveIntentRecognizerProtocol`を満たす。"""

    def recognize(self, normalized: NormalizedInput, ambiguity_report: AmbiguityReport) -> Intent:
        text = normalized.normalized_text

        matched_concepts: list[str] = []
        for keyword, concept in _CONCEPT_KEYWORDS:
            if keyword in text and concept not in matched_concepts:
                matched_concepts.append(concept)

        matched_actions: list[str] = []
        for keyword, action in _ACTION_KEYWORDS:
            if keyword in text and action not in matched_actions:
                matched_actions.append(action)

        # ambiguity_reportがmissing_goal(HIGH)を検出している場合、
        # 入力自体が意味を成さない可能性が高い。confidenceを下げる
        # (M006 14章、Confidence Modelへの接続)。
        has_missing_goal = any(
            i.category == "missing_goal" and i.severity == "high" for i in ambiguity_report.issues
        )
        confidence = 0.2 if has_missing_goal else (0.9 if matched_concepts or matched_actions else 0.3)

        # 依頼表現の末尾除去(P3対応)は、概念/操作の抽出(上記)より**後**に
        # 行う。抽出はユーザーの生の入力文に対して行う必要があるため
        # (末尾を先に削ると「作りたい」等に含まれる動詞情報が
        # 概念/操作マッチングへ影響してしまう可能性を避ける)。
        #
        # FORGE_v0.2_最終修正指示(Final Gate) P3対応: `normalized.
        # title_seed`が設定されている場合(確認フロー経由で、元入力が
        # ノイズ的だった場合)、goal導出は`normalized_text`(ノイズを
        # 含む全体)ではなく`title_seed`(意味のある回答部分のみ)を使う。
        # 概念/操作の抽出(上記matched_concepts/matched_actions)は、
        # 引き続き`text`(normalized_text、全体)から行っており、
        # Domain判定の精度自体はノイズの影響を受けない設計を維持する
        # (goal/タイトルにだけノイズが混入しないようにする、という
        # 限定的な修正)。
        goal_seed = normalized.title_seed if normalized.title_seed else text
        goal = _derive_title_like_goal(goal_seed) if goal_seed else "(目的が不明な入力)"

        return Intent(
            goal=goal,
            required_concepts=tuple(matched_concepts),
            required_actions=tuple(matched_actions),
            constraints=(),
            confidence=confidence,
            evidence=tuple(matched_concepts) + tuple(matched_actions),
        )
