"""Template Engine(`app/ai/runtime/template_engine.py`)のテスト。

実行方法:
    cd backend
    python -m pytest tests/test_template_engine.py -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.ai.runtime.template_engine import Template  # noqa: E402


class TestTemplateSchemaVersion(unittest.TestCase):
    def test_schema_version_defaults_to_1_0_and_is_backward_compatible(self) -> None:
        """FORGE-AI-CONNECT-001 TD22対応(2026-08-11)。既存の呼び出し方
        (`schema_version`を渡さない)が引き続き動作し、既定値"1.0"に
        なることの回帰テスト。"""
        template = Template(
            id="checklist",
            category="checklist",
            priority=1,
            capabilities=("check", "add_item"),
            required_widgets=("checklist_view",),
        )
        self.assertEqual(template.schema_version, "1.0")


if __name__ == "__main__":
    unittest.main()
