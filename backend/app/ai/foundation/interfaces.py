"""Forge AI Foundation — インターフェース定義のみ(FORGE-MILESTONE-002 PHASE6)。

**重要: このモジュールは実装ではなく設計である。** 実際にLLMを呼び出すコードは
一切含まない(指示書PHASE6「AIはまだ実装しない。Interfaceのみ」に従う)。

目的: Planner・Validator・Repair Engine を「共通化」することで、
OpenAI/Claude/Gemini/OSS/自作Forge AI のどれでも差し替え可能にする
(FORGE-MILESTONE-002 全体方針)。この共通化の核心は、各段階を
Protocol(構造的部分型)として定義し、実装を後から差し込めるようにすることにある。

依存方向の原則(FORGE-MERGE-001以来の一貫した方針):
  - このモジュールは`ai/validators/schema_validator.py`(既存の決定的Validator)
    を「利用してよい」(Validatorは既に実装済みで安定しているため)。
  - このモジュールはFastAPI/Pydanticに依存しない(domain/README.mdの
    フレームワーク非依存原則を、AI層にも適用する)。
  - 各Providerの実装(OpenAI SDK呼び出し等)は、このファイルではなく
    `providers/`配下の別ファイルに置く想定(未実装、7章参照)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol

from app.ai.validators.schema_validator import ValidationResult

# ---------------------------------------------------------------------------
# 中間表現(IR)
# ---------------------------------------------------------------------------


class Platform(str, Enum):
    """FORGE-MILESTONE-004 PHASE1新規。IntentIR.platformが取りうる値。
    Forgeの実際の対象(Flutter、複数プラットフォーム出力)に合わせ、
    既定値はCROSS_PLATFORMとする。"""

    MOBILE = "mobile"
    WEB = "web"
    DESKTOP = "desktop"
    CROSS_PLATFORM = "cross_platform"


class Complexity(str, Enum):
    """FORGE-MILESTONE-004 PHASE1新規。IntentIR.complexityが取りうる値。
    Plannerが画面数・State数等の設計判断の粗さを決める際の目安として使う想定
    (今回は型のみ定義し、実際の判定ロジックは実装しない)。"""

    SIMPLE = "simple"
    MEDIUM = "medium"
    COMPLEX = "complex"


@dataclass(frozen=True)
class IntentIR:
    """Intent Interpreterの出力。UI Schemaは含まない(共通指示書6.1節の原則)。

    FORGE-MILESTONE-004 PHASE1で、entities/platform/complexity/category/
    output_typeの5フィールドを追加した。全て既定値を持たせており、
    既存の`IntentIR(purpose="x")`という呼び出し方(test_ai_foundation.py・
    test_ai_runtime.py等)は変更せずそのまま動く(後方互換性を維持)。

    FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。`schema_version`を追加。
    現時点で存在するIntentIRのVersionは"1.0"のみであり、Migration機構は
    意図的に実装していない(「存在しないMigrationを実装済みのように
    見せる」ことを避けるため、TECH_DEBT.md TD22の対応方針どおり)。
    将来2つ目のバージョンが実際に必要になった時点でMigrationを追加する。
    """

    purpose: str
    target_users: tuple[str, ...] = ()
    required_features: tuple[str, ...] = ()
    constraints: tuple[str, ...] = ()
    open_questions: tuple[str, ...] = ()
    privacy_notes: tuple[str, ...] = ()
    accessibility_notes: tuple[str, ...] = ()

    # FORGE-MILESTONE-004 PHASE1で追加。
    entities: tuple[str, ...] = ()
    """アプリが扱う対象(例: "item", "person")。forge_ai/の`required_concepts`・
    World Modelの`WorldObject`に相当する概念だが、IntentIRの一部として
    表現することで、Backend側のPlanner/Template Selectorが単一のIntentIRだけを
    見て判断できるようにしている。"""

    platform: Platform = Platform.CROSS_PLATFORM
    """対象プラットフォーム。現状のForge Runtimeは実質Flutter(複数プラットフォーム
    出力)のみに対応するため、既定はCROSS_PLATFORM。将来Platform別に出力を
    変える判断が必要になった場合の拡張点として、今回は型だけ用意する。"""

    complexity: Complexity = Complexity.SIMPLE
    """要求の複雑さの見積もり。Plannerが画面数等の設計判断の粗さを決める
    目安として使う想定(今回は型のみ、判定ロジックは未実装)。"""

    category: str | None = None
    """Domain/Templateカテゴリのヒント(例: "shopping", "survey")。
    forge_ai/の`DomainCategory`・Mock Generatorの既存9〜12カテゴリと
    緩やかに対応する自由文字列(Enumにしなかった理由: カテゴリは今後
    Template追加のたびに増える可能性があり、コード変更無しに新カテゴリを
    表現できる必要があるため)。"""

    output_type: str | None = None
    """期待される出力の種類のヒント(例: "checklist", "form", "memo")。
    PlanIR.template_hintと概念的に重なるが、IntentIR側にも持たせることで、
    Template Selector(PHASE5)がPlanを経由せずIntentIRだけからも
    大まかな絞り込みができるようにしている。"""

    schema_version: str = "1.0"
    """FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。このIntentIR構造自体の
    バージョン。Forge Language(JSON)のv1.0/v1.1/v1.2バージョニング方針
    (`docs/spec/LANGUAGE_FREEZE.md`)とは別概念(こちらはAI Runtime内部の
    中間表現のバージョン)。"""


@dataclass(frozen=True)
class ScreenPlan:
    screen_id: str
    purpose: str
    data_needed: tuple[str, ...] = ()
    actions_needed: tuple[str, ...] = ()
    empty_state_needed: bool = True
    error_state_needed: bool = True


@dataclass(frozen=True)
class PlanIR:
    """Product Plannerの出力。まだForge Language JSONではない、より高レベルな設計。

    FORGE-MILESTONE-004の「AppPlan」はこの`PlanIR`と同一概念であり、
    新しい型は追加していない(重複定義を避ける。runtime/planner.pyの
    `Plan = PlanIR`エイリアスと合わせて、AppPlan相当の別名として扱う)。

    FORGE-MILESTONE-005 Task5で`unassigned_actions`を追加した。既定値
    `()`を持たせており、既存の`PlanIR(screens=...)`という呼び出し方
    (test_ai_foundation.py・test_ai_runtime.py等)は変更せずそのまま動く
    (IntentIRのentities/platform等追加時と同じ、後方互換の手法)。
    """

    screens: tuple[ScreenPlan, ...]
    navigation_edges: tuple[tuple[str, str], ...] = ()  # (from_screen_id, to_screen_id)
    template_hint: str | None = None  # 例: "checklist" / "form" / "memo"(PHASE4のTemplateへの示唆)

    unassigned_actions: tuple[str, ...] = ()
    """`ADAPTER_CONTRACT_V1.md` 2.2節(CEO監査指摘4)への対応。forge_ai.
    Intentが持つ`required_actions`のうち、どの画面(ScreenPlan)にも
    割り当てられなかったものを、捨てずにここへ保持する
    (`actions_needed=()`で単純に破棄しない)。"""

    schema_version: str = "1.0"
    """FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。`IntentIR.schema_version`
    と同じ考え方(このPlanIR構造自体のバージョン、Migration機構は
    2つ目のバージョンが実際に必要になるまで意図的に未実装)。"""


@dataclass(frozen=True)
class CriticResult:
    """共通指示書6.6節のCritic出力形式(score/release_ready/issues/required_fixes)を
    Python型として表現したもの。"""

    score: int
    release_ready: bool
    issues: tuple[dict[str, str], ...] = field(default_factory=tuple)
    required_fixes: tuple[str, ...] = field(default_factory=tuple)


# ---------------------------------------------------------------------------
# 各段階のインターフェース(Protocol)
# ---------------------------------------------------------------------------


class IntentPlanner(Protocol):
    """自然言語 → IntentIR。UI Schemaは生成しない。"""

    def interpret(self, natural_language_input: str, conversation_history: tuple[str, ...]) -> IntentIR: ...


class ProductPlanner(Protocol):
    """IntentIR → PlanIR。画面・状態・操作・遷移を設計する(コードは書かない)。"""

    def plan(self, intent: IntentIR, available_templates: tuple[str, ...]) -> PlanIR: ...


class LanguageGenerator(Protocol):
    """PlanIR → Forge Language JSON(Draft)。共通指示書の「Forge Schema Compiler」に相当。

    戻り値は必ず Validator を通すこと(呼び出し元の責務。このinterface自体は
    無検証実行を許可しない、という制約を型では表現できないため、
    ai/foundation/pipeline.py(将来追加予定、8章)側のオーケストレーションで担保する)。
    """

    def generate(self, plan: PlanIR) -> dict[str, Any]: ...


class RepairEngine(Protocol):
    """Validator不合格時、最小差分で修復案を提案する。

    共通指示書6.5節の方針(JSON Patchに近い形式、最大2回)を踏襲する。
    実際の差分形式(RFC 6902 / Semantic Operation)は
    docs/DECISIONS.md D4で未確定のまま(今回のPHASE6でも決定しない、
    UX変更相当のためCEO承認が必要な範囲に近いと判断した)。
    """

    def repair(self, document: dict[str, Any], errors: ValidationResult, attempt: int) -> dict[str, Any]: ...


class Critic(Protocol):
    """合格した文書に対する品質評価。共通指示書6.6節のCriticに相当。"""

    def evaluate(self, document: dict[str, Any], intent: IntentIR) -> CriticResult: ...


class PluginRouter(Protocol):
    """Action/Plugin呼び出しの許可判定・解決を行う。Plugin本体は未実装
    (禁止事項によりPHASE6でも実装しない)。将来Pluginが実装された際、
    Validatorの安全性検査(未許可Plugin使用の検出)と対になる。
    """

    def is_allowed(self, plugin_name: str) -> bool: ...
    def resolve(self, plugin_name: str) -> object | None: ...


class Memory(Protocol):
    """3層構造(Working/Project/User)。FORGE-ARCH-001での初期設計を踏襲する。

    - Working: 直近の会話ターン・現在の文書(揮発性、リクエスト単位)。
    - Project: 文書の全バージョン履歴・採用/却下履歴(永続、プロジェクト単位)。
    - User: ユーザー横断の好み(既定OFF、明示的opt-inのみ。10章のプライバシー方針)。
    """

    def get_working_context(self, session_id: str) -> dict[str, Any]: ...
    def get_project_history(self, project_id: str) -> tuple[dict[str, Any], ...]: ...
    def get_user_preferences(self, user_id: str) -> dict[str, Any] | None: ...  # Noneなら未opt-in


class Conversation(Protocol):
    """複数ターンの対話状態を管理する。IntentPlannerへ渡す会話履歴の出所。"""

    def append_turn(self, session_id: str, role: str, content: str) -> None: ...
    def get_history(self, session_id: str, max_turns: int = 10) -> tuple[str, ...]: ...


class PromptBuilder(Protocol):
    """IntentIR/PlanIR/Few-shot例/Language Schemaから、実際にLLMへ送るプロンプトを
    組み立てる。Provider(LLMAdapter)ごとにプロンプト形式が異なりうるため、
    Providerとは独立した層として分離している。
    """

    def build_intent_prompt(self, natural_language_input: str, conversation_history: tuple[str, ...]) -> str: ...
    def build_plan_prompt(self, intent: IntentIR, available_templates: tuple[str, ...]) -> str: ...
    def build_repair_prompt(self, document: dict[str, Any], errors: ValidationResult) -> str: ...


class LLMAdapter(Protocol):
    """モデルプロバイダの違いを吸収する、交換可能な推論エンジンの抽象化。

    FORGE-ARCH-001で設計した`InferenceProvider`と同じ役割を、より明確に
    Structured Output前提で再定義したもの。全Providerがこのインターフェースに
    従うことで、Planner/Repair/Criticは「どのモデルを使っているか」を知らずに済む。
    """

    def complete_structured(self, prompt: str, response_schema: dict[str, Any]) -> dict[str, Any]:
        """promptとJSON Schema(response_schema)を渡し、そのSchemaに適合する
        構造化データを返す。Provider内部でどう実現するか(ネイティブのstructured
        output機能・function calling・prompt工夫等)は実装側の責務。"""
        ...
