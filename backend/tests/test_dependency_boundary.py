"""forge_ai が backend を import していないこと(FORGE-R1-CLOSURE-015 §5)。

---

## 何が問題だったか

`forge_ai/core/pipeline.py`が、Production時だけ遅延importで

    from app.ai.runtime.design_language import design_choice_guidance

を呼んでいた。コメントには「forge_aiはbackendをimportしない」と書いて
あったのに、**実際にはしていた**。しかもimport失敗を握り潰していたので、

```
Production          import成功 → Design Intent 動く
forge_ai standalone ImportError → Design Intent 動かない
```

という、**同じコードが環境によって別の振る舞いをする**状態だった。
forge_ai単体のテストが何件通っても、本番で語彙が渡っている証拠には
ならない。

## このファイルが守っているもの

1. forge_ai のどのファイルも `app.*` を import しない
2. 語彙は`DesignLanguageGuidance`として**外から注入される**
3. 注入すれば、standaloneでもProductionと同じように動く

3が要点である。「backendが無いから動かない」ではなく
「渡していないから動かない」——**同じ契約で同じように動く**。
"""

from __future__ import annotations

import ast
import os
import pathlib
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from app.ai.runtime.design_language import design_language_guidance  # noqa: E402
from forge_ai.contracts.design_language_contract import (  # noqa: E402
    DesignAxis,
    DesignChoice,
    DesignLanguageGuidance,
)
from forge_ai.core.pipeline import run_cognitive_pipeline  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402

_FORGE_AI = pathlib.Path(__file__).resolve().parents[2] / "forge_ai"


def _imported_modules(path: pathlib.Path) -> set[str]:
    """そのファイルが import しているモジュール名。

    文字列の検索ではなく**構文木**で見る。コメントやdocstringに
    `app.ai...`と書いてあるだけで落ちるようにすると、説明を書けなく
    なる(実際、直した経緯をコメントに残してある)。
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.add(node.module)
    return modules


class TestForgeAiDoesNotDependOnBackend(unittest.TestCase):
    def test_no_module_imports_the_backend_app_package(self) -> None:
        offenders: list[str] = []
        for path in sorted(_FORGE_AI.rglob("*.py")):
            if "tests" in path.parts or "__pycache__" in path.parts:
                continue
            for module in _imported_modules(path):
                if module == "app" or module.startswith("app."):
                    offenders.append(f"{path.relative_to(_FORGE_AI.parent)}: {module}")
        self.assertEqual(
            offenders, [],
            "forge_ai が backend を import している。"
            "語彙は DesignLanguageGuidance として注入すること(§5)",
        )


class _ScriptedProvider:
    """`design_intent`にだけ答える。他の段は何も返さない。"""

    def __init__(self, answer: dict) -> None:
        self._answer = answer

    def complete(self, prompt):  # noqa: ANN001
        if prompt.stage == "design_intent":
            return ProviderResponse(text="", structured=self._answer)
        return ProviderResponse(text="", structured={})


class TestTheSameContractWorksWithoutTheBackend(unittest.TestCase):
    """**standaloneとProductionで挙動が同じ**であること。

    backend由来の語彙と、その場で組み立てた同じ形の語彙で、同じ結果に
    なることを見る。「backendが無いと動かない」のではなく
    「渡さなければ動かない」という状態にできている、という確認である。
    """

    _ANSWER = {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}

    def _roles(self, guidance) -> dict:  # noqa: ANN001
        outcome = run_cognitive_pipeline(
            "家計簿をつけたい",
            provider=_ScriptedProvider(self._ANSWER),
            design_language=guidance,
        )
        found: dict[str, str] = {}

        def walk(widget) -> None:  # noqa: ANN001
            role = (widget.properties or {}).get("style_role")
            if isinstance(role, str):
                found[widget.id] = role
            for child in widget.children or ():
                walk(child)

        for screen in outcome.ir.screens:
            walk(screen.body)
        return found

    def _hand_built_guidance(self) -> DesignLanguageGuidance:
        """forge_ai側だけで組み立てた、同じ形の語彙。

        **backendのモジュールを一切使わない。** これが通るということは、
        forge_aiが`app.*`の存在に依存していないということである。
        """
        axes = (
            DesignAxis("screen_density", (
                DesignChoice("density.compact", "詰める"),
                DesignChoice("density.normal", "標準"),
                DesignChoice("density.relaxed", "ゆったり"),
            )),
            DesignAxis("list_surface", (
                DesignChoice("surface.card", "面に載せる"),
                DesignChoice("surface.elevated", "持ち上げる"),
            )),
        )
        allowed = {a.axis: {o.id for o in a.options} for a in axes}
        return DesignLanguageGuidance(
            axes=axes,
            is_valid_choice=lambda axis, role: isinstance(role, str) and role in allowed.get(axis, set()),
        )

    def test_the_backend_vocabulary_reaches_the_document(self) -> None:
        roles = self._roles(design_language_guidance())
        self.assertEqual(roles.get("root_tabs"), "density.relaxed")
        self.assertEqual(roles.get("records_list_view"), "surface.elevated")

    def test_a_hand_built_guidance_produces_the_same_result(self) -> None:
        self.assertEqual(self._roles(self._hand_built_guidance()),
                         self._roles(design_language_guidance()))

    def test_without_guidance_the_ai_is_not_asked(self) -> None:
        """渡さなければ既定値。**これは環境の違いではなく、明示的な状態。**"""
        roles = self._roles(None)
        self.assertEqual(roles.get("root_tabs"), "density.normal")

    def test_guidance_without_a_validator_is_not_usable(self) -> None:
        """検証できない答えを採用しない。"""
        axes = (DesignAxis("screen_density", (DesignChoice("density.compact", "詰める"),)),)
        self.assertFalse(DesignLanguageGuidance(axes=axes).is_usable)
        self.assertFalse(DesignLanguageGuidance(is_valid_choice=lambda a, r: True).is_usable)


if __name__ == "__main__":
    unittest.main()
