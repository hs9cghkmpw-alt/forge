"""OutputSafetyChecker(FORGE-AI-CONNECT-001 TD20対応)のテスト。

実行方法:
    cd backend
    python -m pytest tests/test_output_safety.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.runtime.output_safety import OutputSafetyChecker  # noqa: E402


def _checklist_document() -> dict:
    return {
        "version": "1.0",
        "app": {"title": "買い物リスト"},
        "screens": [
            {
                "id": "main",
                "title": "買い物リスト",
                "body": {
                    "type": "column",
                    "id": "root",
                    "children": [
                        {
                            "type": "text_field",
                            "id": "add_field",
                            "placeholder": "追加する項目を入力",
                        },
                        {
                            "type": "button",
                            "id": "add_button",
                            "label": "追加",
                        },
                    ],
                },
            }
        ],
    }


class TestOutputSafetyCheckerBenignDocument(unittest.TestCase):
    def test_normal_checklist_document_is_safe(self) -> None:
        result = OutputSafetyChecker().check(_checklist_document())
        self.assertTrue(result.safe)
        self.assertEqual(result.issues, ())

    def test_empty_document_is_safe(self) -> None:
        result = OutputSafetyChecker().check({})
        self.assertTrue(result.safe)
        self.assertEqual(result.issues, ())


class TestOutputSafetyCheckerHighRiskPii(unittest.TestCase):
    def test_credit_card_field_label_is_detected_as_high_severity_and_unsafe(self) -> None:
        document = _checklist_document()
        document["screens"][0]["body"]["children"].append(
            {"type": "text_field", "id": "card_field", "label": "クレジットカード番号を入力してください"}
        )
        result = OutputSafetyChecker().check(document)
        self.assertFalse(result.safe)
        self.assertTrue(any(i.severity == "high" for i in result.issues))
        self.assertTrue(any(i.category == "excessive_pii_collection" for i in result.issues))

    def test_password_field_placeholder_is_detected(self) -> None:
        document = _checklist_document()
        document["screens"][0]["body"]["children"].append(
            {"type": "text_field", "id": "pw_field", "placeholder": "パスワードを入力"}
        )
        result = OutputSafetyChecker().check(document)
        self.assertFalse(result.safe)

    def test_detection_is_case_insensitive_for_english_terms(self) -> None:
        document = _checklist_document()
        document["screens"][0]["body"]["children"].append(
            {"type": "text_field", "id": "cvv_field", "label": "CVVコードを入力"}
        )
        result = OutputSafetyChecker().check(document)
        self.assertFalse(result.safe)


class TestOutputSafetyCheckerMediumRiskPii(unittest.TestCase):
    def test_birthdate_field_is_detected_as_medium_severity_but_stays_safe(self) -> None:
        """medium severityは記録するが、safe判定には影響しない
        (誤検知でsafe=Falseになりすぎないようにする設計、TD20参照)。"""
        document = _checklist_document()
        document["screens"][0]["body"]["children"].append(
            {"type": "text_field", "id": "birthdate_field", "label": "生年月日を入力してください"}
        )
        result = OutputSafetyChecker().check(document)
        self.assertTrue(result.safe)
        self.assertTrue(any(i.severity == "medium" for i in result.issues))


class TestOutputSafetyCheckerPathReporting(unittest.TestCase):
    def test_issue_path_identifies_the_offending_field(self) -> None:
        document = _checklist_document()
        document["screens"][0]["body"]["children"].append(
            {"type": "text_field", "id": "card_field", "label": "口座番号を教えてください"}
        )
        result = OutputSafetyChecker().check(document)
        self.assertFalse(result.safe)
        paths = [i.path for i in result.issues]
        self.assertTrue(any("children[2].label" in p for p in paths))


if __name__ == "__main__":
    unittest.main()
