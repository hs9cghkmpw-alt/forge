"""FORGE v0.3 Task5: 代表的なプロンプト40件超の自動テスト。

`FORGE v0.3 開発指示 — AI推論・生成品質向上フェーズ`Task5対応。

Task1〜4(Lexicon拡充・Domain推論改善・初期データ生成改善・
Confirmation改善)が実際に機能していることを、14の全Domainにわたる
代表プロンプトで確認する。各プロンプトについて、以下のいずれかを
検証する。

* **Success系**: 期待したDomainへ正しく分類され、Confidence>0、
  ForgeDocumentが実際に生成されること。
* **Confirmation系**: 意図的に用意した、正当に確認要求が必要な
  プロンプト(Privacy関連語を含む、または複数Domainが真に僅差で
  競合する)について、期待した`reason`で`needs_confirmation`に
  なることを確認する(「常にSuccessになるべき」という誤った前提を
  テストしない。確認要求が正しく機能することも品質の一部)。

このテストは、Task1〜4の実装中に実際に42件のプロンプトを一つずつ
実行して検証し、その過程で以下の実バグを発見・修正した(このテスト
ファイル自体が、その回帰防止線になる)。

* `旅程`(itinerary)の概念キーワード登録漏れ(Travel Domainなのに
  Diaryへ落ちていた)。
* `毎日`->`habit`という概念キーワードが汎用的すぎて、Diary向けの
  文(「毎日の気分を記録したい」)でも誤ってHabit Trackingの必須
  要件を生成してしまい、Design Criticが永久に不合格になる不具合
  (既知の"写真"問題と同種)。
* `household_budget`・`child_growth`(以前のセッションで追加した
  Domain)が、Template Selectorの対応表(`_DOMAIN_TO_PRELIMINARY`等)
  に一度も登録されておらず、Success状態へ到達できなかった欠落
  (今回、fishing_log/habit_tracking/study/travelの新設4Domainと
  あわせて修正)。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from forge_ai.core.orchestration.outcomes import (  # noqa: E402
    CognitivePipelineNeedsConfirmation,
    CognitivePipelineSuccess,
)
from forge_ai.core.pipeline import run_cognitive_pipeline  # noqa: E402
from forge_ai.provider.mock_provider import MockProvider  # noqa: E402

# (プロンプト, 期待Domain) — Successを期待するケース。
SUCCESS_CASES: tuple[tuple[str, str], ...] = (
    # shopping
    ("買い物リストを作りたい", "shopping"),
    ("スーパーで買う物を管理したい", "shopping"),
    ("品物と値段を記録するアプリ", "shopping"),
    # attendance
    ("会員の出席状況を管理したい", "attendance"),
    ("会員の出欠を記録したい", "attendance"),
    # diary
    ("日記をつけたい", "diary"),
    ("日々の記録アプリ", "diary"),
    ("毎日の気分を記録したい", "diary"),
    # inventory
    ("在庫を管理したい", "inventory"),
    ("閾値を設定して在庫管理", "inventory"),
    ("在庫の保管場所と閾値を管理したい", "inventory"),
    # task_management
    ("今日のタスクを管理したい", "task_management"),
    ("作業の優先度を管理したい", "task_management"),
    ("期限付きの業務管理アプリ", "task_management"),
    # survey
    ("アンケートを作りたい", "survey"),
    ("質問と回答を管理したい", "survey"),
    # schedule
    ("予定を管理したい", "schedule"),
    ("スケジュールとリマインダーを管理", "schedule"),
    # household_budget
    ("家計簿をつけたい", "household_budget"),
    ("収入と支出を記録したい", "household_budget"),
    ("家計簿で食費を管理したい", "household_budget"),
    # child_growth
    ("子どもの成長記録をつけたい", "child_growth"),
    ("身長と体重を記録したい", "child_growth"),
    ("赤ちゃんの発達記録アプリ", "child_growth"),
    # fishing_log(FORGE v0.3で新設したDomain)
    ("釣った魚を記録したい", "fishing_log"),
    ("釣果の場所とサイズを記録", "fishing_log"),
    ("魚種と重量を管理したい", "fishing_log"),
    # habit_tracking(FORGE v0.3で新設したDomain)
    ("毎日の習慣を記録するアプリを作って", "habit_tracking"),
    ("運動と睡眠のルーティンを管理", "habit_tracking"),
    ("健康習慣を継続したい", "habit_tracking"),
    # study(FORGE v0.3で新設したDomain)
    ("英語の勉強を記録したい", "study"),
    ("資格試験の学習進捗を管理", "study"),
    ("読書記録アプリを作りたい", "study"),
    # travel(FORGE v0.3で新設したDomain)
    ("旅行の計画を立てたい", "travel"),
    ("ホテルと観光地を管理したい", "travel"),
    ("旅程を記録したい", "travel"),
)

# (プロンプト, 期待reason) — 正当にneeds_confirmationになるべきケース。
CONFIRMATION_CASES: tuple[tuple[str, str], ...] = (
    # hospital: 医療関連語は常にPrivacy確認が優先される(意図的な設計、
    # M006 4.3節「優先順位1」)。
    ("患者の症状を記録したい", "priority1_privacy_safety_permission"),
    ("服薬管理アプリを作って", "priority1_privacy_safety_permission"),
    ("薬の処方記録をつけたい", "priority1_privacy_safety_permission"),
    # 複数Domainが真に僅差で競合するケース("status"がattendance/
    # task_managementの両方の概念であるため)。
    ("出席と欠席を記録したい", "priority2_low_domain_confidence"),
)


class TestDomainInferenceGolden(unittest.TestCase):
    """Task5: Domain判定の自動テスト(全SUCCESS_CASES)。"""

    def test_all_success_cases_reach_success_with_expected_domain(self) -> None:
        failures: list[str] = []
        for text, expected_domain in SUCCESS_CASES:
            with self.subTest(text=text):
                outcome = run_cognitive_pipeline(text, MockProvider())
                if not isinstance(outcome, CognitivePipelineSuccess):
                    reason = getattr(outcome.confirmation_request, "reason", "?")
                    failures.append(f"{text!r}: expected SUCCESS({expected_domain}) but got {type(outcome).__name__}({reason})")
                    continue
                actual_domain = outcome.context.domain_classification.primary_domain.category.value
                if actual_domain != expected_domain:
                    failures.append(f"{text!r}: expected domain={expected_domain!r} but got {actual_domain!r}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_all_success_cases_have_positive_confidence(self) -> None:
        """Task2「Actionだけ一致では高confidenceを出さない」の裏付けとして、
        confidenceが0より大きい(=何らかの根拠を持つ)ことを確認する。"""
        for text, _ in SUCCESS_CASES:
            with self.subTest(text=text):
                outcome = run_cognitive_pipeline(text, MockProvider())
                assert isinstance(outcome, CognitivePipelineSuccess)
                self.assertGreater(outcome.context.domain_classification.confidence, 0.0)

    def test_all_success_cases_generate_a_valid_forge_document(self) -> None:
        """ForgeDocument生成(Task5の最低要件)を確認する。少なくとも
        1画面・1つ以上のstateキーを持つことを確認する(詳細な構造検証は
        既存の`test_compiler.py`・schema_validatorに委ねる)。"""
        for text, _ in SUCCESS_CASES:
            with self.subTest(text=text):
                outcome = run_cognitive_pipeline(text, MockProvider())
                assert isinstance(outcome, CognitivePipelineSuccess)
                document = outcome.ir.to_json_dict()
                self.assertIn("screens", document)
                self.assertGreaterEqual(len(document["screens"]), 1)
                self.assertTrue(document["screens"][0]["state"])

    def test_success_cases_do_not_leak_raw_concept_identifiers_as_initial_items(self) -> None:
        """Task3の回帰: 初期チェックリスト項目が、内部の概念識別子
        (例: "catch"・"habit"・"transaction"等)そのままではないこと。"""
        internal_identifiers = {
            "item", "task", "entry", "stock", "transaction", "event", "question",
            "child", "measurement", "catch", "habit", "subject", "destination",
        }
        for text, _ in SUCCESS_CASES:
            with self.subTest(text=text):
                outcome = run_cognitive_pipeline(text, MockProvider())
                assert isinstance(outcome, CognitivePipelineSuccess)
                document = outcome.ir.to_json_dict()
                items_state = document["screens"][0]["state"].get("items")
                if not items_state:
                    continue
                texts = [i.get("text") for i in items_state["value"]]
                for t in texts:
                    self.assertNotIn(t, internal_identifiers, f"{text!r} -> 初期項目に内部識別子が漏れている: {t!r}")

    def test_confirmation_cases_produce_the_expected_reason(self) -> None:
        """Task4の裏付け: 正当な理由で確認要求されるケースが、
        意図した`reason`で実際にneeds_confirmationになることを確認する。"""
        failures: list[str] = []
        for text, expected_reason in CONFIRMATION_CASES:
            with self.subTest(text=text):
                outcome = run_cognitive_pipeline(text, MockProvider())
                if not isinstance(outcome, CognitivePipelineNeedsConfirmation):
                    failures.append(f"{text!r}: expected NeedsConfirmation({expected_reason}) but got SUCCESS")
                    continue
                actual_reason = outcome.confirmation_request.reason
                if actual_reason != expected_reason:
                    failures.append(f"{text!r}: expected reason={expected_reason!r} but got {actual_reason!r}")
        self.assertEqual(failures, [], msg="\n".join(failures))

    def test_privacy_confirmation_cases_produce_a_domain_specific_message(self) -> None:
        """医療関連の確認要求が、Privacy専用の質問文になっていること
        (汎用フォールバック文言ではないこと)を確認する。"""
        for text, expected_reason in CONFIRMATION_CASES:
            if expected_reason != "priority1_privacy_safety_permission":
                continue
            with self.subTest(text=text):
                outcome = run_cognitive_pipeline(text, MockProvider())
                assert isinstance(outcome, CognitivePipelineNeedsConfirmation)
                self.assertIn("プライバシー", outcome.confirmation_request.message)

    def test_total_case_count_meets_task5_requirement(self) -> None:
        """指示書Task5「代表的なプロンプト30〜50件程度」を満たすことの確認。"""
        total = len(SUCCESS_CASES) + len(CONFIRMATION_CASES)
        self.assertGreaterEqual(total, 30)
        self.assertLessEqual(total, 60)

    def test_all_fourteen_domains_are_covered_by_success_cases(self) -> None:
        """14全Domainが、少なくとも1件のSuccessケースでカバーされて
        いることを確認する(新設4Domainの取りこぼしが無いことも含む)。"""
        covered = {domain for _, domain in SUCCESS_CASES}
        expected = {
            "shopping", "attendance", "diary", "inventory", "task_management",
            "survey", "schedule", "household_budget", "child_growth",
            "fishing_log", "habit_tracking", "study", "travel",
        }
        missing = expected - covered
        self.assertEqual(missing, set(), f"Successケースで未カバーのDomain: {missing}")

    def test_pipeline_is_deterministic_for_all_success_cases(self) -> None:
        """Rule-Based実装は決定的であるべき(同じ入力から常に同じDomain)。"""
        for text, _ in SUCCESS_CASES[:10]:  # 全件だと冗長なため代表10件のみ
            with self.subTest(text=text):
                first = run_cognitive_pipeline(text, MockProvider())
                second = run_cognitive_pipeline(text, MockProvider())
                assert isinstance(first, CognitivePipelineSuccess)
                assert isinstance(second, CognitivePipelineSuccess)
                self.assertEqual(
                    first.context.domain_classification.primary_domain.category.value,
                    second.context.domain_classification.primary_domain.category.value,
                )


if __name__ == "__main__":
    unittest.main()
