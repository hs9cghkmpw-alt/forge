"""Cognitive Meaning Extractor(FORGE-MILESTONE-007 Phase 1.2、M006 10章)。

`CognitiveMeaningExtractorProtocol.extract(normalized, world, intent) ->
ExtractedMeaning`を実装する。第一段階のIntent Recognition・Domain
Classificationと同じく、決定的なキーワード・パターン辞書によるルール
ベース実装(実LLM非依存)。

文字列の羅列ではなく、`SemanticUnit`(subject/action/target/qualifiers/
evidence)という構造化された関係を保持することを重視する。
"""

from __future__ import annotations

from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import ExtractedMeaning, SemanticUnit
from forge_ai.core.world_model import World

# (キーワード, 正規化された値) — Actor抽出用。
_ACTOR_PATTERNS: tuple[tuple[str, str], ...] = (
    ("家族", "家族"),
    ("友人", "友人"),
    ("同僚", "同僚"),
    ("チーム", "チーム"),
    ("回答者", "回答者"),
    ("参加者", "参加者"),
)

# (キーワード, 意味カテゴリ("action"|"constraint"|"preference"), 正規化された値)
# の3つ組。1つのキーワードが複数カテゴリへ同時に寄与する場合がある
# (例: "共有"はaction("share")でもありconstraint("複数利用者")でもある)。
_ACTION_PATTERNS: tuple[tuple[str, str], ...] = (
    ("共有", "share"),
    ("記録", "record"),
    ("設定", "set"),
    ("確認", "view"),
    ("一覧", "list_view"),
    ("チェック", "check"),
    ("管理", "manage"),
    ("通知", "notify"),
    ("知らせ", "notify"),
    ("分かるように", "notify"),
)

_CONSTRAINT_PATTERNS: tuple[tuple[str, str], ...] = (
    ("共有", "複数利用者による共有アクセスが必要"),
)

_PREFERENCE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("写真", "写真の添付を希望"),
    ("気分", "気分の記録を希望"),
)

# (キーワード, 正規化された値) — 時間・周期条件。複合語(より具体的な
# ものを先に置き、substring判定なので後段の一般語との重複を避ける)。
_TEMPORAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("毎週月曜日", "毎週月曜日"),
    ("毎週", "毎週"),
    ("回答後", "回答後"),
    ("期限", "期限あり"),
)

# (キーワード, 正規化された値) — 状態条件。
_STATE_PATTERNS: tuple[tuple[str, str], ...] = (
    ("少なくなったら", "在庫が少ない状態"),
    ("少なくなった", "在庫が少ない状態"),
    ("優先度", "優先度による状態区分"),
)

# WorldのObjectと対応する、Entity抽出用の追加キーワード
# (Worldに既に無い、修飾語由来の新規entityのみ)。
_ADDITIONAL_ENTITY_PATTERNS: tuple[tuple[str, str], ...] = (
    ("写真", "photo"),
    ("気分", "mood"),
    ("期限", "deadline"),
    ("優先度", "priority"),
)


class CognitiveMeaningExtractor:
    """`CognitiveMeaningExtractorProtocol`を満たす。"""

    def extract(self, normalized, world: World, intent: Intent) -> ExtractedMeaning:
        text = normalized.normalized_text

        actors: list[str] = []
        actor_evidence: list[str] = []
        for keyword, value in _ACTOR_PATTERNS:
            if keyword in text and value not in actors:
                actors.append(value)
                actor_evidence.append(keyword)

        actions: list[str] = []
        action_evidence: list[str] = []
        semantic_units: list[SemanticUnit] = []
        for keyword, value in _ACTION_PATTERNS:
            if keyword in text and value not in actions:
                actions.append(value)
                action_evidence.append(keyword)
                semantic_units.append(SemanticUnit(
                    subject=actors[0] if actors else None,
                    action=value,
                    target=world.domain.typical_concepts[0].name if world.domain.typical_concepts else None,
                    qualifiers=(),
                    evidence=keyword,
                ))

        constraints: list[str] = []
        for keyword, value in _CONSTRAINT_PATTERNS:
            if keyword in text and value not in constraints:
                constraints.append(value)

        preferences: list[str] = []
        for keyword, value in _PREFERENCE_PATTERNS:
            if keyword in text and value not in preferences:
                preferences.append(value)

        temporal_conditions: list[str] = []
        for keyword, value in _TEMPORAL_PATTERNS:
            if keyword in text and value not in temporal_conditions:
                temporal_conditions.append(value)

        state_conditions: list[str] = []
        for keyword, value in _STATE_PATTERNS:
            if keyword in text and value not in state_conditions:
                state_conditions.append(value)

        # Entity: Worldに既にある概念名 + 修飾語由来の追加概念。
        entities: list[str] = [o.name for o in world.objects]
        for keyword, value in _ADDITIONAL_ENTITY_PATTERNS:
            if keyword in text and value not in entities:
                entities.append(value)

        evidence_spans = tuple(
            dict.fromkeys(actor_evidence + action_evidence + [
                kw for kw, v in _CONSTRAINT_PATTERNS + _TEMPORAL_PATTERNS + _STATE_PATTERNS + _PREFERENCE_PATTERNS
                if kw in text
            ])
        )

        # confidence: 何らかの修飾情報(actor/constraint/preference/
        # temporal/state)を実際に検出できた場合は高め、検出できず
        # Intentの基本concept/actionのみに留まる場合は中程度とする
        # (Intent Recognizer・Domain Classifierと同じ「実際の一致に
        # 基づく」方針を踏襲する)。
        has_qualifier_signal = bool(constraints or preferences or temporal_conditions or state_conditions)
        confidence = 0.9 if has_qualifier_signal else 0.6

        summary = text if text else intent.goal

        return ExtractedMeaning(
            summary=summary,
            semantic_units=tuple(semantic_units),
            actors=tuple(actors),
            entities=tuple(entities),
            actions=tuple(actions),
            constraints=tuple(constraints),
            preferences=tuple(preferences),
            temporal_conditions=tuple(temporal_conditions),
            state_conditions=tuple(state_conditions),
            evidence_spans=evidence_spans,
            confidence=confidence,
        )
