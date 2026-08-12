"""Prompt Builder。

キックオフ指示書7章: 「Promptは Builder経由のみ生成。文字列連結は禁止。」

`Prompt`は単一の巨大文字列ではなく、`system`/`instruction`/`context`という
明確に分離されたフィールドを持つ構造化データである。各Providerの実装が
最終的にLLM APIへ渡す形式(1本の文字列、role配列など)へ変換する責務を負う。
forge_ai/のどのモジュールも、prompt文字列を`+`やf-stringで組み立てない
(`PromptBuilder`のメソッド経由でのみ`Prompt`を得る)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Prompt:
    """1回のAI呼び出しに対応する、構造化されたプロンプト。

    system: このAI呼び出しの役割・制約(常に一定のルールを表す)。
    instruction: 今回何をしてほしいかの指示。
    context: 参照データ(World/Meaning/Intent等)。呼び出し先が必要に応じて
        参照する構造化データであり、文字列へ事前結合しない。
    """

    stage: str  # "meaning" | "intent" | "planning" | "entity_synthesis" | "compile" | "repair"
    system: str
    instruction: str
    context: dict[str, Any] = field(default_factory=dict)


class PromptBuilder:
    """全Prompt生成の唯一の入口。個々のstageごとに専用メソッドを持つ。"""

    def build_meaning_prompt(self, *, user_text: str, domain_name: str) -> Prompt:
        """Meaning抽出段階のPromptを構築する。"""
        return Prompt(
            stage="meaning",
            system=(
                "あなたはユーザーの自然文から、対象領域(Domain)に関連する"
                "概念・行為・キーワードを抽出する。Worldを直接変更してはならない。"
            ),
            instruction="次のユーザー発話から意味を抽出せよ。",
            context={"user_text": user_text, "domain_name": domain_name},
        )

    def build_intent_prompt(self, *, meaning_summary: dict[str, Any], domain_name: str) -> Prompt:
        """Intent構築段階のPromptを構築する。"""
        return Prompt(
            stage="intent",
            system=(
                "あなたは抽出された意味(Meaning)を、Forgeが処理可能な"
                "Intent構造(目的・必要概念・必要操作・制約)へ変換する。"
            ),
            instruction="次のMeaningからIntentを構築せよ。",
            context={"meaning": meaning_summary, "domain_name": domain_name},
        )

    def build_planning_prompt(self, *, intent_summary: dict[str, Any]) -> Prompt:
        """Application Plan生成段階のPromptを構築する。"""
        return Prompt(
            stage="planning",
            system=(
                "あなたはIntentからApplication Planを設計する。"
                "Runtime(Widget種別・UIフレームワーク)を一切知らない前提で、"
                "画面構成と目的だけを抽象的に記述せよ。"
            ),
            instruction="次のIntentからApplication Planを生成せよ。",
            context={"intent": intent_summary},
        )

    def build_entity_synthesis_prompt(
        self, *, user_text: str, plan_summary: dict[str, Any], domain_name: str
    ) -> Prompt:
        """FORGE-PRODUCT-VISION-002(2026-08-12)新規。「このアプリが
        繰り返し記録するデータは何か」をAIに設計させる段階のPrompt。

        **なぜこの段階が要るのか**: 以前は、記録するデータの型
        (Entity・Field・型・選択肢)が`ir_generator.py`の手書きテーブル
        (`_ENTITY_DEFINITIONS`、7 Domain分)にしか存在せず、そこに無い
        領域の依頼は、型の無い単なるChecklist(項目名の文字列が並ぶだけ)
        へ落ちていた。つまり「作れるアプリの種類」の上限が、人手で
        テーブルに書いた数と完全に一致していた。この段階を挟むことで、
        テーブルに無い領域でも、手書きDomainと**同じ**型付きCRUDアプリ
        (日付ピッカー・選択肢・スライダー・グラフ・編集・削除)を
        生成できるようになる。

        **AIに委ねる範囲を意図的に狭くしている**: ここでAIが決めるのは
        「どんなデータを、どんな型で記録するか」という**意味の設計**
        だけであり、Widget種別・画面構成・色・Action種別といった実装は
        一切決めさせない(それらは従来どおり`IRGenerator`→
        `ForgeLanguageCompiler`の決定的なPythonコードが組み立てる)。
        AIの出力は`entity_synthesizer.py`が決定的に検証・サニタイズし、
        通らなければ従来のChecklist経路へ安全に落ちる。
        """
        return Prompt(
            stage="entity_synthesis",
            system=(
                "あなたは、ユーザーの困りごとから「そのアプリが繰り返し記録する"
                "1件分のデータ」の構造を設計する。画面・ボタン・色・レイアウトの"
                "ことは一切考えなくてよい(それらは別の仕組みが決める)。"
                "あなたが決めるのは、記録する項目の名前・表示名・型だけである。\n"
                "\n"
                "規則:\n"
                "1. Entityは必ず1種類だけにすること。ユーザーが繰り返し追加していく"
                "「1件」に相当するものを選ぶ(例: 買い物なら『買う品物』1件、"
                "通院記録なら『受診1回』、勤怠なら『1日の勤務』)。\n"
                "2. 項目(fields)は3〜6個。多すぎると入力が面倒になり使われなくなる。"
                "ユーザーが実際に毎回入力する気になる項目だけに絞ること。\n"
                "3. entity_nameと各項目のnameは、英小文字のスネークケース"
                "(a-z, 0-9, _ のみ、先頭は英小文字)にすること。"
                "labelは日本語の短い表示名にすること。\n"
                "4. typeは string / number / boolean / date / choice のいずれか。\n"
                "   - 金額・数量・回数・時間などはnumber。\n"
                "   - 日付はdate。\n"
                "   - 『済んだか』『行ったか』のような二択はboolean。\n"
                "   - 分類・状態のように**選択肢を具体的に列挙できる**場合だけchoice。\n"
                "5. choiceを選んだ場合、choicesには実際にありえる選択肢を2〜6個"
                "入れること。**根拠なく選択肢を発明してはならない**。"
                "ユーザーの依頼から自然に導けない場合は、choiceではなくstringにすること。\n"
                "6. min_value/max_valueは、5段階評価・10点満点のように"
                "**上限と下限が本当に決まっている数値**の場合だけ設定する。"
                "金額・数量のように上限が無いものには設定しないこと。\n"
                "7. 最低1つの項目はrequired=trueにすること(何も入力せずに"
                "空のデータが増えていくのを防ぐため)。\n"
                "8. visual_styleは、その記録が持つ雰囲気に合うものを"
                "calm / warm / vibrant / neutral から1つ選ぶ"
                "(お金・健康・仕事のような落ち着いた対象はcalm/neutral、"
                "日記・育児・思い出のような対象はwarm、"
                "習慣・目標・達成のような対象はvibrant)。"
            ),
            instruction=(
                "次の依頼内容に対して、このアプリが繰り返し記録する1件分の"
                "データ構造を設計せよ。"
            ),
            context={"user_text": user_text, "plan": plan_summary, "domain_name": domain_name},
        )

    def build_compile_prompt(self, *, plan_summary: dict[str, Any]) -> Prompt:
        """Forge IRコンパイル段階のPromptを構築する。

        FORGE-AI-QUALITY-001(2026-08-11)対応: `example_items`の要求を
        追加した。以前はtitleしか要求しておらず、初期データ(チェック
        リストの初期項目)はCompiler側の静的な決め打ちテーブル
        (`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`)にしか依存できなかったため、
        「満足度アンケートを作って」→常に'最初の質問'のような、実際の
        依頼内容を反映しない画一的な出力になっていた(実機でGeminiに
        複数ジャンルのプロンプトを投げて確認・再現した)。
        """
        return Prompt(
            stage="compile",
            system=(
                "あなたはApplication PlanをForge IR(構造化された中間表現)へ"
                "変換する。ForgeのWidget/Action/State語彙のみを使うこと。"
                "titleに加え、このアプリの用途・ユーザーの依頼内容に即した、"
                "具体的で現実的な初期データ例(example_items、2〜4件の文字列)"
                "も提案すること。汎用的な言い回し(「最初の項目」等)ではなく、"
                "依頼内容から推測できる実在しそうな値にすること。"
            ),
            instruction="次のApplication PlanをForge IRへコンパイルせよ。",
            context={"plan": plan_summary},
        )

    def build_repair_prompt(self, *, ir_summary: dict[str, Any], issues: tuple[dict[str, Any], ...]) -> Prompt:
        """Repair段階のPromptを構築する。"""
        return Prompt(
            stage="repair",
            system="あなたはForge IRの検証エラーを最小差分で修正する。",
            instruction="次のIRと検証エラー一覧をもとに、修正方針を示せ。",
            context={"ir": ir_summary, "issues": list(issues)},
        )
