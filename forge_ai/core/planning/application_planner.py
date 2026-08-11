"""Cognitive Application Planner(M007 Phase 1 Minimal Cognitive Slice、M006 12章)。

requirements・preliminary_candidatesを必須引数として受け取る
(Blueprint Task3・4.2)。第一段階では、単純な入力から単一〜少数画面の
ApplicationPlanを組み立てる、決定的なルールベース実装とする。

FORGE-MILESTONE-007 Phase 1.2で、Meaning Model由来の追加Requirement
(target_ref/operation_refがWorldの基本概念に含まれないもの。例:
"share"というAction、"photo"というEntity)を、`data_entities`・
`required_actions`へ実際に反映するよう拡張した(CEO指摘: 「単に
Decision Traceへ記録するだけで、Planへ反映されない実装は禁止」)。
"""

from __future__ import annotations

from forge_ai.core.domain_model import DomainConcept
from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import RequirementSet
from forge_ai.core.planner import ApplicationPlan, ScreenPlan
from forge_ai.core.world_model import World

# Planへ「validation_rules」として反映する(=descriptionそのものを
# UI上のルールとして扱う)ことで割当判定する分類。Temporal/State
# conditionは、単純なtarget_ref/operation_ref一致では表現しにくい
# 「画面上の表示・通知ルール」であるため、この方式で反映する
# (既存のValidation category(「descriptionがvalidation_rulesに実在
# すれば割当済み」)と同じ判定方式を、schedule/stateへも適用する)。
_DESCRIPTION_BASED_CATEGORIES = ("validation", "schedule", "state")

# FORGE-AI-CONNECT-001 TD24対応(2026-08-11、実際にGemini APIで再現した
# 実例に基づく)。「旅行の持ち物チェックリストを作って」で、"belongings"
# (持ち物、ユーザーが明示的に述べた具体的な概念)ではなく"destination"
# (旅行先、Domain判定のトリガーになった広い概念で`typical_concepts`の
# 先頭)が主役として選ばれ、実際にGeminiに「京都旅行」等の旅行先を
# 生成させてしまった(`TECH_DEBT.md` TD24参照)。
#
# FORGE-AI-QUALITY-001(2026-08-11)で、以前ここにあった
# `_PREFER_AS_PRIMARY_WHEN_MENTIONED = ("belongings",)`という、
# travel domain 1件のみを想定したConcept名の直書き許可リストを、
# `DomainConcept.primary_candidate`という一般的なDomain定義側の
# メタデータへ置き換えた(`domain_model.py`のdocstring参照)。
#
# **一般化の範囲について(正直な申告)**: 全15 Domainの`typical_concepts`
# を実際に精査した結果、「先頭概念がDomain判定のトリガーだが主役には
# 不向き」という問題を持つのはtravelの"destination"のみだった。そのため
# 「Intentが言及した概念を無条件に優先する」という、より汎用的な
# アルゴリズムへの刷新は見送った(`compiler.py`冒頭の既知の制限が
# 指摘するとおり、"price"・"quantity"のような「主役の属性」に過ぎない
# 概念が、単に言及されたというだけで誤って主役に昇格するリスクがある
# ため)。今回一般化したのは**メカニズム**(Domain定義側で
# `primary_candidate=False`を宣言するだけで、`application_planner.py`
# を一切変更せずに同種の問題へ対応できる)であり、**選定ルール自体**
# (「非トリガー概念が明示的に言及されていれば、トリガー概念より優先する」)
# は据え置いている。
def _prioritize_primary_candidate_concepts(
    data_entities: tuple[str, ...],
    required_concepts: tuple[str, ...],
    concept_metadata: dict[str, "DomainConcept"],
) -> tuple[str, ...]:
    """現在の先頭要素(`data_entities[0]`)が`primary_candidate=False`と
    宣言されており、かつ`data_entities`内に`primary_candidate=True`かつ
    実際に`required_concepts`として言及された別の概念が存在する場合、
    その概念を先頭へ移動する。該当が無ければ`data_entities`を
    そのまま返す(並び替えなし、既存の挙動を保つ)。
    """
    if not data_entities:
        return data_entities
    current_primary = data_entities[0]
    current_meta = concept_metadata.get(current_primary)
    if current_meta is None or current_meta.primary_candidate:
        return data_entities

    eligible_mentioned = [
        name for name in data_entities
        if name != current_primary
        and name in required_concepts
        and concept_metadata.get(name, DomainConcept(name, "")).primary_candidate
    ]
    if not eligible_mentioned:
        return data_entities
    preferred = eligible_mentioned[:1]
    rest = [name for name in data_entities if name not in preferred]
    return tuple(preferred) + tuple(rest)


class CognitiveApplicationPlanner:
    """`CognitivePlannerProtocol`を満たす。"""

    def plan(
        self,
        intent: Intent,
        world: World,
        requirements: RequirementSet,
        preliminary_candidates: tuple[str, ...],
    ) -> ApplicationPlan:
        base_data_entities = tuple(o.name for o in world.objects) or intent.required_concepts or ("item",)
        concept_metadata = {c.name: c for c in world.domain.typical_concepts}
        base_data_entities = _prioritize_primary_candidate_concepts(
            base_data_entities, intent.required_concepts, concept_metadata
        )
        base_required_actions = tuple(dict.fromkeys(
            rel.predicate for rel in world.relationships
        )) or intent.required_actions or ("add_item",)

        # Meaning由来の追加target_ref/operation_ref(Worldの基本概念に
        # まだ含まれていないもの)を、data_entities/required_actionsへ
        # 実際に反映する。**`derived_from == "meaning"`の要件のみ**を
        # 自動反映の対象とする(CEO実物監査で実際にテストして発見: 
        # 全てのmandatory要件を無条件で自動反映すると、Phase 1.1で
        # 検証した「Planへ実際に反映されていない要件はunassignedの
        # ままになる」という機械判定そのものが機能しなくなってしまう。
        # World由来・Intent由来の要件は、Planner自身の通常ロジック
        # (World基盤)で実際に反映された場合にのみ割当済みとする)。
        additional_data_entities: list[str] = []
        additional_actions: list[str] = []
        for r in requirements.requirements:
            if r.derived_from != "meaning" or not r.mandatory:
                continue
            if r.target_ref and r.target_ref not in base_data_entities and r.target_ref not in additional_data_entities:
                additional_data_entities.append(r.target_ref)
            if r.operation_ref and r.operation_ref not in base_required_actions and r.operation_ref not in additional_actions:
                additional_actions.append(r.operation_ref)

        data_entities = base_data_entities + tuple(additional_data_entities)
        required_actions = base_required_actions + tuple(additional_actions)

        # description一致で割当判定するカテゴリ(validation/schedule/
        # state)は、descriptionをそのままvalidation_rulesへ含める。
        description_based_reqs = tuple(
            r for r in requirements.requirements if r.category in _DESCRIPTION_BASED_CATEGORIES
        )

        primary_concept = data_entities[0] if data_entities else "item"
        empty_state_message = f"まだ{primary_concept}がありません。追加してください。"

        validation_rules = tuple(
            r.description for r in description_based_reqs
        ) or (
            "add操作等で対象の入力欄が空の場合、エラーとはせず静かに何もしないこと。",
            "必須項目を満たさないまま送信しようとした場合は、入力欄の近くに具体的な理由を表示すること。",
            "送信に失敗した場合も、利用者が入力済みの内容を失わないこと。",
            "エラー時は修正方法(何を直せばよいか)を明示すること。",
        )

        main_screen = ScreenPlan(
            name="main",
            purpose=intent.goal,
            key_elements=data_entities,
            required_actions=required_actions,
            empty_state_message=empty_state_message,
            validation_rules=validation_rules,
        )

        # 割当済み判定(CEO実物監査Phase 1.1(2回目)指摘3): カテゴリが
        # 存在するというだけで割当済みとみなさず、実際にPlanへ反映
        # されたかを機械的に検証する。
        #
        # * Functional/Data/Permission(target_ref付き): target_refが
        #   key_elements(=data_entities、Meaning由来の追加分を含む)に
        #   実在する場合のみ割当済み。
        # * Functional/Permission(operation_ref付き): operation_refが
        #   required_actions(=primary_flow、Meaning由来の追加分を含む)
        #   に実在する場合のみ割当済み。
        # * Validation/Schedule/State: descriptionそのものが
        #   validation_rulesに実在する場合のみ割当済み(Planner自身が
        #   requirements由来のdescriptionをそのままvalidation_rulesへ
        #   コピーするため、この一致は文字列の偶然一致ではなく意図した
        #   対応関係である)。
        # * target_ref/operation_refを持たない要件(Privacy/
        #   Accessibility/Preference等)は、機械的に判定できないため、
        #   常に未割当として扱う(判定不能を割当済みにしない、という
        #   CEO指摘3の原則)。
        assigned_descriptions: set[str] = set()
        for r in requirements.requirements:
            if r.category in ("functional", "data", "permission"):
                if r.target_ref is not None and r.target_ref in data_entities:
                    assigned_descriptions.add(r.description)
                elif r.operation_ref is not None and r.operation_ref in required_actions:
                    assigned_descriptions.add(r.description)
            elif r.category in _DESCRIPTION_BASED_CATEGORIES:
                if r.description in validation_rules:
                    assigned_descriptions.add(r.description)
            # privacy/accessibility/preference/その他: target_ref/
            # operation_refが無いため機械的に判定できず、常に未割当の
            # ままとする。

        unassigned = tuple(
            r.description for r in requirements.requirements
            if r.description not in assigned_descriptions
        )

        return ApplicationPlan(
            title=intent.goal or "無題のアプリ",
            screens=(main_screen,),
            data_entities=data_entities,
            primary_flow=required_actions,
            navigation_edges=(),  # 単一画面のため遷移なし(既知の制限、複数画面Templateでは今後拡張)
            unassigned_requirements=unassigned,
        )

