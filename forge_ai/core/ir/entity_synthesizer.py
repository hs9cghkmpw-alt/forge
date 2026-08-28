"""EntitySynthesizer(FORGE-PRODUCT-VISION-002、2026-08-12)。

CEO「つくれるアプリの自由度をあげたい。トップレベルまで」への対応。

**解いている問題**: これまで、アプリが記録するデータの型
(Entity・Field・型・選択肢)は`ir_generator.py`の手書きテーブル
`_ENTITY_DEFINITIONS`にしか存在しなかった。そこに載っている領域だけが
型付きCRUDアプリ(日付ピッカー・選択肢・スライダー・グラフ・編集・
削除・タブ)になり、それ以外の全ての依頼は`compiler.py`のChecklist
(項目名の文字列が並ぶだけ、型も編集も無い)へ落ちていた。つまり
**「作れるアプリの種類」の上限が、人手でテーブルに書いた数と完全に
一致していた**——これが自由度の天井だった。

このモジュールは、その天井を外す。テーブルに無い領域については、
AIに`EntitySpec`(手書きテーブルとまったく同じ表現)を合成させ、
`IRGenerator.build_from_spec()`へ渡す。以降の経路——IR構築、
`ForgeLanguageCompiler`によるForge Language化、Widget選択、
Design Token適用、Validator——は、合成された定義と手書きの定義を
**一切区別しない**。

**AIに委ねる範囲は意図的に狭い**。AIが決めるのは「どんなデータを、
どんな型で記録するか」という意味の設計だけである。Widget種別・画面
構成・Action種別・色は、従来どおり決定的なPythonコードが組み立てる
(ADR-012の「実装判断はCompiler層に閉じる」方針は変えていない)。

**AIの出力を決して信用しない**。`synthesize()`は、返ってきた構造を
`_sanitize_*`群で決定的に検証・整形し、使える形にできなければ`None`を
返す。`None`の場合、呼び出し側(`pipeline_orchestrator.py`)は従来の
Checklist経路へ安全にフォールバックする——つまり、この機能が失敗しても
以前より悪くなることはない。この「AIの自己申告を鵜呑みにせず、
決定的なルールで上書きする」という形は、`conversation_engine.py`の
Question Policy(LLBの`next_action`を決定的に上書きする)と同じ設計に
揃えている。
"""

from __future__ import annotations

import re
from dataclasses import replace
from typing import Any

from forge_ai.core.ir.ir_generator import EntitySpec, FieldSpec
from forge_ai.core.ir.ir_types import FieldType, MeasureSemantics
from forge_ai.core.planner import ApplicationPlan
from forge_ai.prompt.prompt_builder import PromptBuilder
from forge_ai.provider.provider_interface import AIProvider
from forge_ai.core.orchestration.cognitive_context import (
    EntitySynthesisAttempt,
    EntitySynthesisRejectionReason,
)
from forge_ai.core.semantics.structure_provenance import (
    EntitySynthesisContractEvidence,
    EntitySynthesisRepair,
)

# Forge Language の `record_schemas` キー・`identifier`パターンに揃える
# (`ir_types.Entity`のdocstring参照)。
_IDENTIFIER_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")

# 1 Entityが持てるFieldの上限。Validator側の上限(MAX_RECORD_FIELDS=20・
# MAX_RECORD_SCHEMA_FIELDS=30、`schema_validator.py`)より意図的に厳しく
# している。理由は技術的制約ではなくUXであり、Prompt側でも「3〜6個」と
# 指示している——毎回20項目を入力させるフォームは、そもそも使われない。
_MAX_FIELDS = 8
# Prompt contract is intentionally stricter than the product sanitizer: the
# model is instructed to return no more than 6 fields. Product robustness may
# accept 7-8 fields, but that is not strict model-contract success.
_STRICT_CONTRACT_MAX_FIELDS = 6
# choice型1件が持てる選択肢の上限(Prompt側の指示は2〜6個)。
_MAX_CHOICES = 12
_MIN_CHOICES = 2

_VALID_FIELD_TYPES: dict[str, FieldType] = {
    "string": FieldType.STRING,
    "number": FieldType.NUMBER,
    "boolean": FieldType.BOOLEAN,
    "date": FieldType.DATE,
    "choice": FieldType.CHOICE,
}
# FORGE-R1-CLOSURE-015(2026-08-17)。数値Fieldが**どういう量か**を
# AIに選ばせる、閉じた選択肢。
#
# **自由記述にしない**のはDesign Roleと同じ理由である——Forgeが
# 保証できない値が入らず、選ばれなかった候補が学習素材として残る。
#
# 未知・未指定は`UNKNOWN`へ倒す。**`ADDITIVE`へ倒さない**のが要点で、
# 倒すと「評価の合計」「魚のサイズの合計」が復活する(§2の実バグ)。
_VALID_MEASURES: dict[str, MeasureSemantics] = {
    "additive": MeasureSemantics.ADDITIVE,
    "averageable": MeasureSemantics.AVERAGEABLE,
    "level": MeasureSemantics.LEVEL,
    "extremum": MeasureSemantics.EXTREMUM,
    "identifier": MeasureSemantics.IDENTIFIER,
    "unknown": MeasureSemantics.UNKNOWN,
}

_VALID_VISUAL_STYLES = frozenset({"calm", "warm", "vibrant", "neutral"})
_DEFAULT_VISUAL_STYLE = "calm"

# `ForgeLanguageCompiler._compile_single_screen()`が、Fieldごとに
# `field_<name>`・`edit_field_<name>`というState IDを組み立てる一方、
# `records`・`selected`という固定のState IDも使う。Field名がこれらと
# 衝突すると、生成されたアプリのStateが静かに壊れる(Validatorは
# State IDの重複自体は検出できるが、意味的な取り違えは検出できない)。
# 防御的に、衝突しうる名前を予約語として弾く。
_RESERVED_FIELD_NAMES = frozenset({"records", "selected", "id"})


def _entity_contract_evidence(
    structured: object, *, structured_output_mode: str = ""
) -> EntitySynthesisContractEvidence:
    """AI 生出力と canonical Entity contract の差を privacy-safe に測る。

    Product sanitizer はこの後そのまま動く。ここでは「最終的に使えたか」
    ではなく「Model 自身が修復なしで契約を満たしたか」を測る。
    """
    if not isinstance(structured, dict) or not structured:
        return EntitySynthesisContractEvidence(structured_output_mode=structured_output_mode)

    repairs: list[EntitySynthesisRepair] = []

    def note(repair: EntitySynthesisRepair) -> None:
        if repair not in repairs:
            repairs.append(repair)

    raw_entity_name = structured.get("entity_name")
    entity_name = _sanitize_identifier(raw_entity_name)
    if entity_name is None or raw_entity_name != entity_name:
        note(EntitySynthesisRepair.IDENTIFIER_NORMALIZED)

    raw_entity_label = structured.get("entity_label")
    if _sanitize_label(raw_entity_label) != raw_entity_label:
        note(EntitySynthesisRepair.LABEL_FALLBACK)

    visual_style = structured.get("visual_style")
    if not isinstance(visual_style, str) or visual_style not in _VALID_VISUAL_STYLES:
        note(EntitySynthesisRepair.VISUAL_STYLE_FALLBACK)

    raw_fields = structured.get("fields")
    fields_received = len(raw_fields) if isinstance(raw_fields, list) else 0
    if not isinstance(raw_fields, list) or not raw_fields:
        note(EntitySynthesisRepair.FIELD_DROPPED)
        return EntitySynthesisContractEvidence(
            raw_schema_valid=False,
            repairs_applied=tuple(repairs),
            fields_received=fields_received,
            fields_accepted=0,
            strict_contract_passed=False,
            structured_output_mode=structured_output_mode,
        )

    seen: set[str] = set()
    valid_field_count = 0
    any_required = False
    for index, raw in enumerate(raw_fields):
        if index >= _MAX_FIELDS:
            note(EntitySynthesisRepair.FIELD_DROPPED)
            continue
        if not isinstance(raw, dict):
            note(EntitySynthesisRepair.FIELD_DROPPED)
            continue

        raw_name = raw.get("name")
        name = _sanitize_identifier(raw_name)
        if name is None or name in seen or name in _RESERVED_FIELD_NAMES:
            note(EntitySynthesisRepair.FIELD_DROPPED)
            continue
        if raw_name != name:
            note(EntitySynthesisRepair.IDENTIFIER_NORMALIZED)
        seen.add(name)
        valid_field_count += 1

        raw_label = raw.get("label")
        if _sanitize_label(raw_label) != raw_label:
            note(EntitySynthesisRepair.LABEL_FALLBACK)

        raw_type = raw.get("type")
        field_type = _VALID_FIELD_TYPES.get(raw_type) if isinstance(raw_type, str) else None
        if field_type is None:
            note(EntitySynthesisRepair.UNKNOWN_TYPE_TO_STRING)

        required = raw.get("required")
        if required is True:
            any_required = True
        elif required is False or required is None:
            # `required` is optional per field. Omission is valid as long as
            # at least one accepted field explicitly has required=true.
            pass
        else:
            # A supplied non-bool is repaired to False by the sanitizer.
            note(EntitySynthesisRepair.REQUIRED_INJECTED)

        raw_choices = raw.get("choices")
        sanitized_choices = _sanitize_choices(raw_choices)
        if isinstance(raw_choices, list):
            exact_choices = tuple(
                x for x in raw_choices if isinstance(x, str) and x.strip()
            )
            if sanitized_choices != exact_choices:
                note(EntitySynthesisRepair.CHOICE_DROPPED)
        elif raw_choices not in (None, ()):
            note(EntitySynthesisRepair.CHOICE_DROPPED)

        if field_type == FieldType.CHOICE and len(sanitized_choices) < _MIN_CHOICES:
            note(EntitySynthesisRepair.CHOICE_TO_STRING)
        elif field_type != FieldType.CHOICE and sanitized_choices:
            note(EntitySynthesisRepair.CHOICE_DROPPED)

        if field_type == FieldType.NUMBER:
            raw_min, raw_max = raw.get("min_value"), raw.get("max_value")
            sanitized_bounds = _sanitize_bounds(raw_min, raw_max, field_type=field_type)
            if raw_min is not None or raw_max is not None:
                raw_pair = (
                    float(raw_min) if isinstance(raw_min, (int, float)) and not isinstance(raw_min, bool) else None,
                    float(raw_max) if isinstance(raw_max, (int, float)) and not isinstance(raw_max, bool) else None,
                )
                if sanitized_bounds != raw_pair:
                    note(EntitySynthesisRepair.BOUNDS_DROPPED)

            raw_measure = raw.get("measure")
            if not isinstance(raw_measure, str) or raw_measure.strip().lower() not in _VALID_MEASURES:
                note(EntitySynthesisRepair.MEASURE_DOWNGRADED)
        elif raw.get("measure") not in (None, "unknown"):
            note(EntitySynthesisRepair.MEASURE_DOWNGRADED)

    if valid_field_count and not any_required:
        note(EntitySynthesisRepair.REQUIRED_INJECTED)

    within_prompt_field_limit = fields_received <= _STRICT_CONTRACT_MAX_FIELDS
    raw_schema_valid = (
        entity_name is not None
        and within_prompt_field_limit
        and isinstance(raw_entity_label, str) and bool(raw_entity_label.strip())
        and isinstance(visual_style, str) and visual_style in _VALID_VISUAL_STYLES
        and valid_field_count > 0
        and any_required
        and not repairs
    )
    return EntitySynthesisContractEvidence(
        raw_schema_valid=raw_schema_valid,
        repairs_applied=tuple(repairs),
        fields_received=fields_received,
        fields_accepted=0,
        strict_contract_passed=raw_schema_valid and not repairs,
        structured_output_mode=structured_output_mode,
    )


class EntitySynthesizer:
    """`AIProvider`を注入して使う。状態を持たない。"""

    def __init__(self, provider: AIProvider, prompt_builder: PromptBuilder | None = None) -> None:
        self._provider = provider
        self._prompt_builder = prompt_builder or PromptBuilder()

    def synthesize(
        self, plan: ApplicationPlan, *, user_text: str, domain_name: str
    ) -> EntitySpec | None:
        """AIに1件分のデータ構造を設計させ、決定的に検証した`EntitySpec`
        を返す。使える形にできなかった場合は`None`(呼び出し側が従来の
        Checklist経路へフォールバックする)。

        Providerが例外を送出した場合はそのまま伝播させる(Provider障害を
        「合成できなかった」へ握り潰さない。`pipeline_orchestrator.py`の
        冒頭コメント「`NotImplementedError`は一切捕捉しない」と同じ方針)。
        """
        prompt = self._prompt_builder.build_entity_synthesis_prompt(
            user_text=user_text,
            plan_summary={
                "title": plan.title,
                "data_entities": list(plan.data_entities),
                "screens": [
                    {"name": s.name, "purpose": s.purpose, "key_elements": list(s.key_elements)}
                    for s in plan.screens
                ],
            },
            domain_name=domain_name,
        )
        response = self._provider.complete(prompt)
        return self._spec_from_structured(response.structured)

    def synthesize_with_attempt(
        self, plan: ApplicationPlan, *, user_text: str, domain_name: str
    ) -> tuple[EntitySpec | None, EntitySynthesisAttempt]:
        prompt = self._prompt_builder.build_entity_synthesis_prompt(
            user_text=user_text,
            plan_summary={"title": plan.title, "data_entities": list(plan.data_entities),
                          "screens": [{"name": s.name, "purpose": s.purpose,
                                       "key_elements": list(s.key_elements)} for s in plan.screens]},
            domain_name=domain_name,
        )
        response = self._provider.complete(prompt)
        structured = response.structured
        mode = str(getattr(self._provider, "last_structured_output_mode", "") or "")
        contract = _entity_contract_evidence(structured, structured_output_mode=mode)
        if not isinstance(structured, dict) or not structured:
            return None, EntitySynthesisAttempt(
                True, False, EntitySynthesisRejectionReason.EMPTY_OUTPUT, contract
            )
        if _sanitize_identifier(structured.get("entity_name")) is None:
            return None, EntitySynthesisAttempt(
                True, False, EntitySynthesisRejectionReason.INVALID_IDENTIFIER, contract
            )
        spec = self._spec_from_structured(structured)
        if spec is None:
            return None, EntitySynthesisAttempt(
                True, False, EntitySynthesisRejectionReason.NO_VALID_FIELDS, contract
            )
        contract = replace(contract, fields_accepted=len(spec.field_specs))
        return spec, EntitySynthesisAttempt(True, True, None, contract)

    # -- 以下、AI応答の決定的な検証・サニタイズ -------------------------

    def _spec_from_structured(self, structured: dict[str, Any]) -> EntitySpec | None:
        """AI応答(dict)から`EntitySpec`を組み立てる。1つでも回復不能な
        問題があれば`None`を返す。"""
        if not isinstance(structured, dict) or not structured:
            # TD40で確認したとおり、Geminiがスキーマを解釈できない場合、
            # 例外ではなく空dictが返ることがある。ここが実質的な防波堤。
            return None

        entity_name = _sanitize_identifier(structured.get("entity_name"))
        if entity_name is None:
            return None

        field_specs = self._sanitize_fields(structured.get("fields"), entity_name=entity_name)
        if not field_specs:
            return None

        entity_label = _sanitize_label(structured.get("entity_label")) or entity_name
        visual_style = structured.get("visual_style")
        if not isinstance(visual_style, str) or visual_style not in _VALID_VISUAL_STYLES:
            visual_style = _DEFAULT_VISUAL_STYLE

        return EntitySpec(
            name=entity_name,
            label=entity_label,
            field_specs=field_specs,
            visual_style=visual_style,
        )

    def _sanitize_fields(self, raw_fields: Any, *, entity_name: str) -> tuple[FieldSpec, ...]:
        """Fieldの配列を検証・整形する。1件も残らなかった場合は空を返す
        (呼び出し側が`None`へ倒す)。"""
        if not isinstance(raw_fields, list):
            return ()

        specs: list[FieldSpec] = []
        seen_names: set[str] = set()
        for raw in raw_fields:
            if len(specs) >= _MAX_FIELDS:
                break
            spec = _sanitize_one_field(raw, entity_name=entity_name, seen_names=seen_names)
            if spec is not None:
                specs.append(spec)
                seen_names.add(spec.name)

        if not specs:
            return ()

        # Prompt側で「最低1つはrequired」と指示しているが、守られる保証は
        # 無いため決定的に担保する。1つもrequiredが無いと、何も入力せずに
        # 空レコードを追加できてしまい、一覧が空行で埋まる。
        if not any(s.required for s in specs):
            # **`replace`で1属性だけ変える。**
            #
            # 以前はここでFieldSpecを手で組み直しており、`measure`を
            # 書き写し忘れていた（FORGE-016A §2、再現済み）。
            #
            #   AI:  amount / number / measure=additive / required=false
            #                ↓ 必須へ補正
            #   実際: amount / number / measure=unknown  / required=true
            #
            # R1で入れた「足せる量か」が失われ、Hero KPI（残高など）が
            # 出なくなっていた。`replace`なら**今後metadataを増やしても
            # 書き写し忘れが起きない**。
            specs[0] = replace(specs[0], required=True)
        return tuple(specs)


def _sanitize_one_field(
    raw: Any, *, entity_name: str, seen_names: set[str]
) -> FieldSpec | None:
    """Field 1件分。使えない場合は`None`(その1件だけを捨てる)。"""
    if not isinstance(raw, dict):
        return None

    name = _sanitize_identifier(raw.get("name"))
    if name is None or name in seen_names or name in _RESERVED_FIELD_NAMES:
        return None
    # Entity名と同名のFieldは、`record_schemas`の名前空間としては
    # 不正ではないが、生成物を読んだときに意味が取りづらくなるだけで
    # 利点が無いため、そのまま採用する(弾くほどの害は無い)。

    raw_type = raw.get("type")
    field_type = _VALID_FIELD_TYPES.get(raw_type) if isinstance(raw_type, str) else None
    if field_type is None:
        # 未知の型名(AIが"text"・"integer"等を返した場合)は、捨てずに
        # 最も安全なSTRINGへ倒す——「その項目を記録したい」という意図
        # 自体は正しいため、型の取り違えだけで項目ごと失うのは損。
        field_type = FieldType.STRING

    label = _sanitize_label(raw.get("label")) or name
    required = raw.get("required")
    required = bool(required) if isinstance(required, bool) else False

    choices = _sanitize_choices(raw.get("choices"))
    if field_type == FieldType.CHOICE and len(choices) < _MIN_CHOICES:
        # 「根拠のない選択肢を発明しない」という既存方針
        # (`ir_generator.py`の`_ENTITY_DEFINITIONS`冒頭コメント)を、
        # 合成経路でも守る。選択肢を出せなかったchoiceは、選択肢の
        # 無いドロップダウンにするのではなくSTRINGへ倒す。
        field_type = FieldType.STRING
        choices = ()
    if field_type != FieldType.CHOICE:
        choices = ()

    min_value, max_value = _sanitize_bounds(
        raw.get("min_value"), raw.get("max_value"), field_type=field_type
    )
    measure = _sanitize_measure(raw.get("measure"), field_type=field_type)

    return FieldSpec(
        name, label,
        field_type=field_type, required=required,
        choices=choices, min_value=min_value, max_value=max_value,
        measure=measure,
    )


def _sanitize_measure(raw: Any, *, field_type: FieldType) -> MeasureSemantics:
    """AIが言った「量の性質」を検証する。**分からなければUNKNOWN**。

    数値でないFieldは常に`UNKNOWN`——文字列に「足せる量か」を
    問う意味が無い。

    ここで`ADDITIVE`を既定にしないのが要点である。既定を「足せる」に
    すると、AIが黙っていただけのFieldが画面で一番大きな数値になる
    (§2の実バグそのもの)。分からないものは楽観側へ倒さない
    (`CLAUDE.md` §3)。
    """
    if field_type != FieldType.NUMBER:
        return MeasureSemantics.UNKNOWN
    if not isinstance(raw, str):
        return MeasureSemantics.UNKNOWN
    return _VALID_MEASURES.get(raw.strip().lower(), MeasureSemantics.UNKNOWN)


def _sanitize_identifier(raw: Any) -> str | None:
    """`identifier`パターン(英小文字スネークケース)へ整形する。
    整形しても条件を満たせない場合は`None`。

    AIには英小文字スネークケースを指示しているが、日本語や
    キャメルケースが返ることは実際にありうる。機械的に直せる範囲
    (大文字→小文字、空白/ハイフン→アンダースコア)は直し、
    それでも駄目な場合(例: 全て日本語)だけ諦める。
    """
    if not isinstance(raw, str):
        return None
    candidate = raw.strip().lower().replace(" ", "_").replace("-", "_")
    candidate = re.sub(r"[^a-z0-9_]", "", candidate)
    candidate = re.sub(r"_+", "_", candidate).strip("_")
    if not candidate or not _IDENTIFIER_PATTERN.match(candidate):
        return None
    # Forge Language の record_schema名・state_ref として使われるため、
    # 極端に長い名前は切り詰める(Validatorのパターン自体に長さ制限は
    # 無いが、生成物の可読性のため)。
    return candidate[:40]


def _sanitize_label(raw: Any) -> str | None:
    """表示名。空白のみ・非文字列は`None`(呼び出し側がnameで代替する)。"""
    if not isinstance(raw, str):
        return None
    label = raw.strip()
    if not label:
        return None
    return label[:60]


def _sanitize_choices(raw: Any) -> tuple[str, ...]:
    """選択肢。文字列以外・空文字・重複を除き、上限で打ち切る。"""
    if not isinstance(raw, list):
        return ()
    seen: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            continue
        value = item.strip()
        if value and value not in seen:
            seen.append(value[:40])
        if len(seen) >= _MAX_CHOICES:
            break
    return tuple(seen)


def _sanitize_bounds(
    raw_min: Any, raw_max: Any, *, field_type: FieldType
) -> tuple[float | None, float | None]:
    """min/max。NUMBER型で、両方が数値で、min < max のときだけ採用する。

    両方揃っている場合のみ`ForgeLanguageCompiler`が`slider`Widgetを
    選ぶ(`ir_types.Field`のdocコメント参照)ため、片方だけ・逆順・
    非数値は「指定なし」へ倒す(根拠のない上限/下限を発明しない、
    という既存方針と同じ)。
    """
    if field_type != FieldType.NUMBER:
        return (None, None)
    if isinstance(raw_min, bool) or isinstance(raw_max, bool):
        # Pythonでは bool は int のサブクラスであり、`isinstance(True, int)`
        # はTrueになる。True/Falseを0/1の範囲として採用してしまわないよう、
        # 数値判定より先に明示的に除外する。
        return (None, None)
    if not isinstance(raw_min, (int, float)) or not isinstance(raw_max, (int, float)):
        return (None, None)
    if not raw_min < raw_max:
        return (None, None)
    return (float(raw_min), float(raw_max))
