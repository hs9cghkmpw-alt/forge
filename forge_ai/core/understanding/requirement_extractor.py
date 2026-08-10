"""Requirement Extractor(M007 Phase 1 Minimal Cognitive Slice、M006 11章)。

FORGE-MILESTONE-007 Phase 1.2で、Meaning Modelを正式に接続した
(Blueprint v1.3本来の3引数`extract(meaning, world, intent)`。Phase 1では
Meaning Model未実装のため`world`と`intent`のみの2引数だった)。

Functional/Data/Validation/Privacy/Accessibilityに加え、Meaning由来の
Constraint/Temporal/State/Permissionを生成する。
"""

from __future__ import annotations

from forge_ai.core.intent_model import Intent
from forge_ai.core.orchestration.cognitive_types import ExtractedMeaning, Requirement, RequirementSet
from forge_ai.core.world_model import World

# Domain category(文字列)ベースでPrivacy要件を判定する(WorldObjectの
# 英語識別子・自動生成された説明文をキーワード一致で判定するのは脆弱
# だったため、より確実なDomain区分ベースの判定へ変更した。実際に
# テストして、"患者"という日本語キーワードがWorldObjectの英語名"patient"
# にも自動生成の説明文にも一致しないという実バグを発見して修正した)。
_PRIVACY_SENSITIVE_DOMAIN_CATEGORIES = ("hospital",)
_PRIVACY_SENSITIVE_CONCEPT_NAMES = ("patient", "symptom", "medication")

# Meaning.actionsのうち、「共有」に関連する動詞(Permission/Collaboration
# Requirementへ変換する)。
_SHARING_ACTIONS = ("share",)


class RequirementExtractor:
    """`RequirementExtractorProtocol`を満たす。"""

    def extract(self, meaning: ExtractedMeaning, world: World, intent: Intent) -> RequirementSet:
        requirements: list[Requirement] = []
        counter = 0

        def next_id() -> str:
            nonlocal counter
            counter += 1
            return f"REQ-{counter:03d}"

        # Functional: Worldの各Object(=Domainの典型概念)を記録・表示できること。
        for obj in world.objects:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="functional",
                    description=f"'{obj.name}' を記録・表示・編集できること。",
                    mandatory=True,
                    rationale=f"World Modelの{obj.name}に基づく",
                    target_ref=obj.name,
                )
            )

        # Functional: Worldの各Relationship(=典型操作)を実行できること。
        for rel in world.relationships:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="functional",
                    description=f"利用者が'{rel.predicate}'(対象: {rel.obj})を実行できること。",
                    mandatory=True,
                    rationale="World Modelのrelationshipsに基づく",
                    operation_ref=rel.predicate,
                )
            )

        # Functional(Meaning由来、CEO Phase 1.2指摘): Meaningが抽出した
        # actionのうち、World Modelのrelationships(典型操作)にまだ
        # 含まれていないもの(例: "share"・"notify"・"view"等、ユーザーの
        # 入力文に固有の動詞)を、追加のFunctional Requirementとする。
        # "share"は別途Permission Requirement(下記)でも扱うため、
        # ここでは重複させない。
        existing_operations = {rel.predicate for rel in world.relationships}
        for action in meaning.actions:
            if action in existing_operations or action in _SHARING_ACTIONS:
                continue
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="functional",
                    description=f"利用者が'{action}'を実行できること(入力文から抽出)。",
                    mandatory=True,
                    rationale="Meaning.actionsに基づく(Meaning Model)",
                    operation_ref=action,
                    derived_from="meaning",
                )
            )

        # Data: 主要概念のデータ保持(Intent由来)。
        for concept in intent.required_concepts:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="data",
                    description=f"'{concept}' のデータを保持できること。",
                    mandatory=True,
                    rationale="Intent.required_conceptsに基づく",
                    target_ref=concept,
                )
            )

        # Data(Meaning由来): Meaning.entitiesのうち、World Modelにまだ
        # 含まれていないもの(例: "photo"・"mood"等、修飾語由来の概念)を
        # 追加のData Requirementとする。
        existing_entity_names = {o.name for o in world.objects} | set(intent.required_concepts)
        for entity in meaning.entities:
            if entity in existing_entity_names:
                continue
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="data",
                    description=f"'{entity}' のデータを保持できること(入力文から抽出)。",
                    mandatory=True,
                    rationale="Meaning.entitiesに基づく(Meaning Model)",
                    target_ref=entity,
                    derived_from="meaning",
                )
            )
            existing_entity_names.add(entity)

        # Validation: 主要概念は空のまま追加できない(既存M005の
        # add_item_failedバグ修正(D59)と同じ原則: 対象の入力欄が空の
        # まま追加操作をしても、それ自体はエラーではなく静かに無視して
        # よい)。ただしCEO実物監査(Phase 1.1)指摘4: これとは別に、
        # 必須項目を満たさないまま送信しようとした場合は、利用者から
        # 見て「反応がない壊れたアプリ」に見えないよう、具体的な
        # フィードバックが必要である。
        if intent.required_concepts:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="validation",
                    description="add操作等で対象の入力欄が空の場合、エラーとはせず静かに何もしないこと"
                    "(既存M005の教訓、空入力自体は契約違反ではない)。",
                    mandatory=True,
                    rationale="既存M005の実装教訓(空入力は契約違反ではない)",
                )
            )
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="validation",
                    description="一方、必須項目を満たさないまま送信しようとした場合は、"
                    "入力欄の近くに具体的な理由を表示すること。",
                    mandatory=True,
                    rationale="CEO実物監査(Phase 1.1)指摘4: 反応がないように見える挙動を避ける",
                )
            )
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="validation",
                    description="送信に失敗した場合も、利用者が入力済みの内容を失わないこと。",
                    mandatory=True,
                    rationale="CEO実物監査(Phase 1.1)指摘4",
                )
            )
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="validation",
                    description="エラー時は修正方法(何を直せばよいか)を明示すること。",
                    mandatory=True,
                    rationale="CEO実物監査(Phase 1.1)指摘4",
                )
            )
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="validation",
                    description="可能であれば、エラーの原因となった入力欄へ自動的にフォーカスを移すこと。",
                    mandatory=False,
                    rationale="CEO実物監査(Phase 1.1)指摘4(フォーカス制御は環境依存のため必須にはしない)",
                )
            )

        # Validation(Meaning由来のConstraint): Meaning.constraintsを
        # Validation Requirementへ変換する(例: "複数利用者による共有
        # アクセスが必要")。
        for constraint in meaning.constraints:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="validation",
                    description=f"制約: {constraint}",
                    mandatory=True,
                    rationale="Meaning.constraintsに基づく(Meaning Model)",
                )
            )

        # Schedule/Notification(Meaning由来のTemporal condition)。
        for temporal in meaning.temporal_conditions:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="schedule",
                    description=f"時間条件: {temporal} に基づく表示・通知タイミングを反映すること。",
                    mandatory=True,
                    rationale="Meaning.temporal_conditionsに基づく(Meaning Model)",
                )
            )

        # State/表示(Meaning由来のState condition)。
        for state in meaning.state_conditions:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="state",
                    description=f"状態条件: {state} を検知し、画面上で分かるようにすること。",
                    mandatory=True,
                    rationale="Meaning.state_conditionsに基づく(Meaning Model)",
                )
            )

        # Permission/Collaboration(Meaning由来のActor・共有Action)。
        has_sharing_action = any(a in _SHARING_ACTIONS for a in meaning.actions)
        if meaning.actors or has_sharing_action:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="permission",
                    description=f"共有・複数利用者({', '.join(meaning.actors) or '不特定の他者'})"
                    "に対するアクセス権限を管理できること。",
                    mandatory=True,
                    rationale="Meaning.actors/actions(共有)に基づく(Meaning Model)",
                    operation_ref="share" if has_sharing_action else None,
                    derived_from="meaning",
                )
            )

        # Preference(Meaning由来): 必須ではないが、利用者の希望として
        # 記録しておく(例: "写真の添付を希望")。
        for preference in meaning.preferences:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="preference",
                    description=f"利用者の希望: {preference}",
                    mandatory=False,
                    rationale="Meaning.preferencesに基づく(Meaning Model)",
                )
            )

        # Privacy: 機微なDomain区分、または機微な概念名を含む場合。
        object_names = {o.name for o in world.objects}
        is_privacy_sensitive = (
            world.domain.category.value in _PRIVACY_SENSITIVE_DOMAIN_CATEGORIES
            or bool(object_names & set(_PRIVACY_SENSITIVE_CONCEPT_NAMES))
        )
        if is_privacy_sensitive:
            requirements.append(
                Requirement(
                    requirement_id=next_id(),
                    category="privacy",
                    description="記録する情報の範囲・共有範囲について、利用者の明示的な同意を得ること。",
                    mandatory=True,
                    rationale=f"Domain({world.domain.category.value})または概念が機微な情報を扱う可能性があるため",
                )
            )

        # Accessibility: 常に最低限の1件を含める(M006の「今後蓄積すべき
        # 観点」を、常に少なくとも1つ明示するため)。
        requirements.append(
            Requirement(
                requirement_id=next_id(),
                category="accessibility",
                description="主要な操作がキーボード操作のみでも完了できること。",
                mandatory=False,
                rationale="M006 14章UX方針の既定要件",
            )
        )

        return RequirementSet(requirements=tuple(requirements))

