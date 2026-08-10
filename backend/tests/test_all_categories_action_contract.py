"""全Mockカテゴリ Action契約テスト(FORGE-MILESTONE-003.1 PHASE3/6)。

CEO実機で発見されたadd_item_failedを受け、全カテゴリについて
「生成DocumentがValidatorを通る」だけでなく、「Action参照先が実在し、
型が一致する」ことを、Validatorとは独立したロジックで再検証する
(Validator自体にバグがあった場合の多重防御)。

家計簿だけでなく、全カテゴリをパラメータ化して検証する
(指示書「家計簿だけの個別テストではなく、全カテゴリをパラメータ化して
検証すること」に対応)。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.generators.mock_generator import generate_forge_document  # noqa: E402
from app.ai.validators.schema_validator import validate_forge_document  # noqa: E402

# PHASE3で列挙された全カテゴリ。トリガーフレーズは既存のテスト
# (test_mock_generator.py・test_mock_generator_v2.py)と同じものを使う。
ALL_CATEGORY_PHRASES: dict[str, str] = {
    "Memo": "メモを作って",
    "Shopping": "買い物メモを作って",
    "Travel": "旅行の持ち物チェックを作って",
    "Household": "家事のチェックリストを作って",
    "Schedule": "今日の予定リストを作って",
    "Survey": "満足度アンケートを作って",
    "Checklist(ご飯)": "今日の晩ご飯を考えるメモを作って",
    "Child": "子どもの持ち物チェックを作って",
    "Pet": "ペットのお世話チェックリストを作って",
    "Gift": "プレゼントのアイデアリストを作って",
    "Budget": "家計簿をつけるメモを作って",
    "Generic fallback": "適当な入力文字列123",
}


def _walk_widgets(widget: dict):
    yield widget
    for child in widget.get("children", []):
        yield from _walk_widgets(child)


def _walk_actions(widget: dict):
    """widget木の中の全action(button.action, form.submit_action)を集める。"""
    for w in _walk_widgets(widget):
        if w["type"] == "button":
            yield w["action"]
        elif w["type"] == "form":
            yield w["submit_action"]


def _flatten_actions(action: dict):
    """composite/submit_formの中に潜むactionも再帰的に展開する。"""
    yield action
    if action["type"] == "composite":
        for sub in action.get("actions", []):
            yield from _flatten_actions(sub)
    elif action["type"] == "submit_form":
        yield from _flatten_actions(action["success_action"])


class TestAllCategoriesPassValidator(unittest.TestCase):
    """まず、Validator自体が全カテゴリを合格させることを確認する
    (回帰確認。個々のAction参照検証は下のテストクラスで行う)。"""

    def test_all_categories_valid(self) -> None:
        for name, phrase in ALL_CATEGORY_PHRASES.items():
            with self.subTest(category=name):
                doc = generate_forge_document(phrase)
                result = validate_forge_document(doc)
                self.assertTrue(result.valid, msg=f"{name}: {result.to_dict()}")


class TestActionReferenceContractIndependentOfValidator(unittest.TestCase):
    """Validatorとは独立したロジックで、Action参照の実在性・型一致を
    再検証する(Validator自体にバグがあった場合の多重防御。
    PHASE1で発見したadd_item_failedは、実はValidator側の問題ではなく
    Dart Runtime側の問題だったが、念のためPython側でも同じ観点の
    契約テストを整備しておく)。"""

    def _check_document(self, doc: dict) -> None:
        screen_ids = {s["id"] for s in doc["screens"]}
        self.assertIn(doc["initial_screen_id"], screen_ids)

        for screen in doc["screens"]:
            state = screen.get("state", {})
            form_ids = {w["id"] for w in _walk_widgets(screen["body"]) if w["type"] == "form"}

            for action in _walk_actions(screen["body"]):
                for a in _flatten_actions(action):
                    self._check_action(a, state, screen_ids, form_ids)

    def _check_action(self, action: dict, state: dict, screen_ids: set, form_ids: set) -> None:
        t = action["type"]
        if t == "add_item":
            target = action["target_state_ref"]
            source = action["source_state_ref"]
            self.assertIn(target, state, f"add_item.target_state_ref '{target}' が存在しない")
            self.assertEqual(state[target]["type"], "checklist",
                              f"add_item.target '{target}' はchecklist型であるべき")
            self.assertIn(source, state, f"add_item.source_state_ref '{source}' が存在しない")
            self.assertEqual(state[source]["type"], "string",
                              f"add_item.source '{source}' はstring型であるべき")
        elif t == "navigate":
            self.assertIn(action["target_screen_id"], screen_ids,
                           f"navigate先 '{action['target_screen_id']}' が存在しない")
        elif t == "go_back":
            pass  # 参照先は無い
        elif t in {"set_value", "set_state"}:
            self.assertIn(action["state_ref"], state, f"'{action['state_ref']}' が存在しない")
        elif t == "toggle_state":
            ref = action["state_ref"]
            self.assertIn(ref, state, f"toggle_state '{ref}' が存在しない")
            self.assertEqual(state[ref]["type"], "boolean", f"toggle_state '{ref}' はboolean型であるべき")
        elif t == "reset_state":
            self.assertIn(action["state_ref"], state, f"reset_state '{action['state_ref']}' が存在しない")
        elif t == "submit_form":
            self.assertIn(action["form_ref"], form_ids, f"form_ref '{action['form_ref']}' が存在しない")
        elif t == "composite":
            self.assertGreater(len(action.get("actions", [])), 0, "compositeのactionsが空")
        else:
            self.fail(f"未知のAction type: {t}")

    def test_all_categories_action_contracts(self) -> None:
        for name, phrase in ALL_CATEGORY_PHRASES.items():
            with self.subTest(category=name):
                doc = generate_forge_document(phrase)
                self._check_document(doc)

    def test_budget_category_add_item_contract_specifically(self) -> None:
        """CEO実機で問題が発見された家計簿カテゴリを、明示的に単独でも確認する
        (パラメータ化テストとは別に、根本原因調査で使った具体例をそのまま
        残しておく。ただし『家計簿だけ特別扱いする実装』ではなく、
        あくまでテストとして固有カテゴリを明示的に扱っているだけである)。"""
        doc = generate_forge_document("家計簿をつけるメモを作って")
        actions = list(_walk_actions(doc["screens"][0]["body"]))
        add_item_actions = [a for a in actions if a["type"] == "add_item"]
        self.assertEqual(len(add_item_actions), 1)
        action = add_item_actions[0]
        self.assertEqual(action["target_state_ref"], "items")
        self.assertEqual(action["source_state_ref"], "new_item_text")
        state = doc["screens"][0]["state"]
        self.assertEqual(state["items"]["type"], "checklist")
        self.assertEqual(state["new_item_text"]["type"], "string")


class TestNoDuplicateWidgetIdsAcrossAllCategories(unittest.TestCase):
    def test_no_duplicate_ids(self) -> None:
        for name, phrase in ALL_CATEGORY_PHRASES.items():
            with self.subTest(category=name):
                doc = generate_forge_document(phrase)
                all_ids = [
                    w["id"] for screen in doc["screens"] for w in _walk_widgets(screen["body"])
                ]
                self.assertEqual(len(all_ids), len(set(all_ids)), f"{name}: 重複ID {all_ids}")


if __name__ == "__main__":
    unittest.main()
