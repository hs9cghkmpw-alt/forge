"""**CI の job と、その job に入っている依存が食い違わないこと**
（2026-09-01、CI run 33470175316 を落とした実バグ）。

---

## 何が起きたか

会話入口の速い道を測る script を **frontend job** に置いた。あの job には
Flutter しか入っておらず、`backend/requirements.txt` は入れていない。

```text
ModuleNotFoundError: No module named 'httpx'
```

script は `app.ai.runtime.conversation_engine` を import する。そこから
`provider_router` → `cloud_provider` → `httpx` と辿る。**手元では通る**
（依存が全部入っているので）。CI で初めて落ちた。

Flutter も dart も要らない試験だったので、置き場所そのものが誤りだった。

## なぜテストで守るのか

「どの job に何が入っているか」を毎回覚えていられない。実際に間違えた。
**機械が見れば忘れない。**

ここでは直接 import だけを見る。`forge_ai` が backend へ依存しないことは
別のテストが守っているので（逆依存禁止）、実用上はこれで足りる。
"""

from __future__ import annotations

import pathlib
import re
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

WORKFLOW = _ROOT / ".github" / "workflows" / "ci.yml"

#: `python3 scripts/foo.py` のような呼び出し。
_SCRIPT_CALL = re.compile(r"python3?\s+(scripts/[\w./-]+\.py)")

#: backend の実装を直接 import している行。
_BACKEND_IMPORT = re.compile(r"^\s*(?:from|import)\s+app[\s.]", re.MULTILINE)


def _job_blocks(text: str) -> dict[str, str]:
    """`jobs:` 直下の job ごとに本文を切り出す。"""
    lines = text.splitlines()
    try:
        start = next(i for i, line in enumerate(lines) if line.rstrip() == "jobs:")
    except StopIteration:  # pragma: no cover
        raise AssertionError("ci.yml に jobs: が無い") from None

    blocks: dict[str, list[str]] = {}
    current: str | None = None
    for line in lines[start + 1:]:
        match = re.match(r"^  ([\w-]+):\s*$", line)
        if match is not None:
            current = match.group(1)
            blocks[current] = []
        elif current is not None:
            blocks[current].append(line)
    return {name: "\n".join(body) for name, body in blocks.items()}


class TestTheFrontendJobRunsOnlyWhatItCanRun(unittest.TestCase):
    """**frontend job には backend の依存が入っていない。**"""

    def setUp(self) -> None:
        self.assertTrue(WORKFLOW.is_file(), f"{WORKFLOW} が無い")
        self.blocks = _job_blocks(WORKFLOW.read_text(encoding="utf-8"))
        self.assertIn("frontend", self.blocks, "frontend job が見つからない")

    def _installs_backend_requirements(self, body: str) -> bool:
        return "backend/requirements.txt" in body

    def test_frontend_scripts_do_not_import_backend_app_code(self) -> None:
        body = self.blocks["frontend"]
        if self._installs_backend_requirements(body):
            self.skipTest("frontend job が backend の依存を入れるようになった")

        offenders: list[str] = []
        for relative in sorted(set(_SCRIPT_CALL.findall(body))):
            script = _ROOT / relative
            if not script.is_file():
                offenders.append(f"{relative}（ファイルが無い）")
                continue
            if _BACKEND_IMPORT.search(script.read_text(encoding="utf-8")):
                offenders.append(relative)

        self.assertEqual(
            offenders, [],
            "frontend job が backend の実装を import する script を呼んでいる。\n"
            f"{offenders}\n"
            "この job には backend/requirements.txt が入っていないので CI で落ちる"
            "（run 33470175316: ModuleNotFoundError: No module named 'httpx'）。\n"
            "Flutter や dart を要らない試験なら backend job へ置くこと。",
        )

    def test_every_script_the_workflow_calls_exists(self) -> None:
        """存在しない script を呼んでいないこと。"""
        text = WORKFLOW.read_text(encoding="utf-8")
        missing = [
            relative for relative in sorted(set(_SCRIPT_CALL.findall(text)))
            if not (_ROOT / relative).is_file()
        ]
        self.assertEqual(missing, [], f"CI が存在しない script を呼んでいる: {missing}")

    def test_the_conversation_fast_path_check_runs_somewhere(self) -> None:
        """**置き場所を直したついでに消えていないこと。**"""
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn(
            "scripts/converse_fast_path_e2e.py", text,
            "会話入口の速い道を測る step が CI から消えている",
        )


if __name__ == "__main__":
    unittest.main()
