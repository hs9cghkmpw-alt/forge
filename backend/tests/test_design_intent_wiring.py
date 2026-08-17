"""Design Intent が**本番経路から実際に呼ばれている**ことの検査
(FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014、TD69、2026-08-17)。

---

## なぜ backend 側に置くのか

Design Language の語彙(`app.ai.runtime.design_language`)は backend に
あり、`forge_ai` は backend を import しない。したがって
`forge_ai` 単体のテストでは `_design_axes()` が**空**になり、AIへは
何も聞かれない——**そこでいくらテストを書いても、本番でAIが呼ばれて
いるかどうかは分からない。**

`app` と `forge_ai` の両方が import できるのは backend のテストだけで
あり、それが本番と同じ配線である。ここに置くのはそのためである。

## このファイルが守っているもの

`CLAUDE.md` §3「作ったが本番から呼ばれないを作らない」。同じ失敗を
4回している(TD59 / 007 §10 / 010 Phase B / TD64)。Design Intent は
5回目になりかけた——語彙も Selector も作ったのに、**Conversation へ
渡していなかった**。

以下のどれを外しても、このファイルのテストが落ちる。

1. `pipeline.py` の `design_intent_selector=` 注入
2. `pipeline_orchestrator.py` の `selector.select()` 呼び出し
3. `pipeline_orchestrator.py` から Compiler への `design_intent=` 引き渡し
4. `forge_language_compiler.py` の `_intent_role()` 適用
5. `design_language.py` の `design_choice_guidance()` / `is_valid_choice()`
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))  # forge_ai/ はrepoルート直下

from app.ai.runtime.design_language import (  # noqa: E402
    design_choice_guidance,
    is_valid_choice,
)
from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess  # noqa: E402
from forge_ai.core.pipeline import (  # noqa: E402
    _design_axes,
    _design_choice_validator,
    run_cognitive_pipeline,
)
from forge_ai.provider.mock_provider import MockProvider  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402

_REQUEST = "家計簿をつけたい"


class _DesignIntentProvider:
    """`design_intent` 段だけ差し替え、他の段は MockProvider に委ねる。

    こうしないと「AIが選んだから変わった」のか「Mockの都合で変わった」
    のかが分からない。
    """

    def __init__(self, answer: object, *, raise_on_design_intent: bool = False) -> None:
        self._answer = answer
        self._raise = raise_on_design_intent
        self._inner = MockProvider()
        self.design_intent_prompts: list[object] = []

    def complete(self, prompt):  # noqa: ANN001
        if prompt.stage == "design_intent":
            self.design_intent_prompts.append(prompt)
            if self._raise:
                raise RuntimeError("provider unreachable")
            return ProviderResponse(text="", structured=self._answer)
        return self._inner.complete(prompt)


def _style_roles(document) -> dict[str, str]:
    """widget id → style_role。"""
    found: dict[str, str] = {}

    def walk(widget) -> None:  # noqa: ANN001
        role = (widget.properties or {}).get("style_role")
        if isinstance(role, str):
            found[widget.id] = role
        for child in widget.children or ():
            walk(child)

    for screen in document.screens:
        walk(screen.body)
    return found


def _trace_entry(context, stage: str):  # noqa: ANN001
    for entry in context.decision_trace:
        if entry.stage == stage:
            return entry
    return None


class TestTheProductionPipelineActuallyAsksTheAI(unittest.TestCase):
    """**AIへ聞いているか。** 語彙を作っただけで誰も呼んでいない、を防ぐ。"""

    def test_the_production_path_resolves_the_design_axes(self) -> None:
        """backendが居る環境（＝本番）では軸が解決できる。

        forge_ai単体では空になるのが正しい挙動なので、**それを本番だと
        誤認しない**ためにここで確かめる。
        """
        axes = _design_axes()
        self.assertTrue(axes, "本番経路でDesign Axesが空。AIへ何も聞いていない")
        self.assertEqual(len(axes), len(design_choice_guidance()))
        self.assertIs(_design_choice_validator(), is_valid_choice)

    def test_generating_an_app_asks_the_ai_to_choose_design_roles(self) -> None:
        provider = _DesignIntentProvider(
            {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
        )
        outcome = run_cognitive_pipeline(_REQUEST, provider=provider)
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertEqual(
            len(provider.design_intent_prompts), 1,
            "本番の生成でdesign_intent Promptが1回も組み立てられていない",
        )

    def test_the_prompt_carries_the_closed_option_set(self) -> None:
        """自由記述にしない。**選択肢そのものがPromptに載っている**こと。"""
        provider = _DesignIntentProvider({"screen_density": "density.relaxed"})
        run_cognitive_pipeline(_REQUEST, provider=provider)
        prompt = provider.design_intent_prompts[0]
        rendered = f"{prompt.system}\n{prompt.instruction}\n{prompt.context}"
        for axis in design_choice_guidance():
            self.assertIn(axis["axis"], rendered)
            for option in axis["options"]:
                self.assertIn(option["id"], rendered)


class TestTheAIChoiceReachesTheGeneratedApp(unittest.TestCase):
    """**選ばせた答えが生成物に届いているか。** 聞いただけで捨てている、を防ぐ。"""

    def test_the_ai_choice_appears_in_the_document(self) -> None:
        provider = _DesignIntentProvider(
            {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
        )
        outcome = run_cognitive_pipeline(_REQUEST, provider=provider)
        roles = _style_roles(outcome.ir)
        self.assertEqual(roles.get("root_tabs"), "density.relaxed")
        self.assertEqual(roles.get("records_list_view"), "surface.elevated")

    def test_a_different_choice_produces_a_different_document(self) -> None:
        """固定値を返しているだけ、ではないこと。"""
        relaxed = run_cognitive_pipeline(
            _REQUEST,
            provider=_DesignIntentProvider(
                {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
            ),
        )
        compact = run_cognitive_pipeline(
            _REQUEST,
            provider=_DesignIntentProvider(
                {"screen_density": "density.compact", "list_surface": "surface.card"}
            ),
        )
        self.assertNotEqual(_style_roles(relaxed.ir), _style_roles(compact.ir))
        self.assertEqual(_style_roles(compact.ir).get("root_tabs"), "density.compact")

    def test_the_document_still_validates_against_the_schema(self) -> None:
        """AIが選んだroleでも Forge Document として通ること。

        **Runtimeが保証できない値が生成物へ入らない**という約束の側。
        """
        from app.ai.validators.schema_validator import validate_forge_document

        outcome = run_cognitive_pipeline(
            _REQUEST,
            provider=_DesignIntentProvider(
                {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
            ),
        )
        result = validate_forge_document(outcome.ir.to_json_dict())
        self.assertTrue(result.valid, [e.to_dict() for e in result.errors])


class TestForgeDoesNotTrustTheAnswer(unittest.TestCase):
    """**AIの答えを検証しているか。** 通ってはいけない値が通らないこと。"""

    def test_a_role_from_another_axis_is_rejected(self) -> None:
        """`metric.primary`は語彙としては正しいが、`screen_density`の
        答えとしては誤り。**語彙に在ることを許可と読み替えない。**"""
        provider = _DesignIntentProvider(
            {"screen_density": "metric.primary", "list_surface": "surface.elevated"}
        )
        outcome = run_cognitive_pipeline(_REQUEST, provider=provider)
        roles = _style_roles(outcome.ir)
        self.assertEqual(roles.get("root_tabs"), "density.normal", "軸違いのroleが採用された")
        self.assertEqual(roles.get("records_list_view"), "surface.elevated")

    def test_an_invented_value_is_rejected(self) -> None:
        provider = _DesignIntentProvider(
            {"screen_density": "density.enormous", "list_surface": "font_size: 36"}
        )
        outcome = run_cognitive_pipeline(_REQUEST, provider=provider)
        roles = _style_roles(outcome.ir)
        self.assertEqual(roles.get("root_tabs"), "density.normal")
        self.assertEqual(roles.get("records_list_view"), "surface.card")

    def test_a_broken_response_shape_does_not_break_generation(self) -> None:
        for answer in ("density.relaxed", ["density.relaxed"], None, {}):
            with self.subTest(answer=answer):
                outcome = run_cognitive_pipeline(
                    _REQUEST, provider=_DesignIntentProvider(answer)
                )
                self.assertIsInstance(outcome, CognitivePipelineSuccess)
                self.assertEqual(_style_roles(outcome.ir).get("root_tabs"), "density.normal")

    def test_generation_survives_a_provider_failure(self) -> None:
        """**Design Languageが入ったせいで生成が落ちる**のは本末転倒。"""
        provider = _DesignIntentProvider({}, raise_on_design_intent=True)
        outcome = run_cognitive_pipeline(_REQUEST, provider=provider)
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertEqual(_style_roles(outcome.ir).get("root_tabs"), "density.normal")


class TestTheRecordSeparatesAIFromDefault(unittest.TestCase):
    """**AIが選んだ**と**Forgeが既定で埋めた**が混ざらないこと。

    混ざると「AIの選択が受け入れられた」という学習素材が嘘になる
    (`CLAUDE.md` §3「分からないものを楽観側へ倒さない」)。
    """

    def test_an_accepted_choice_is_recorded_as_ai(self) -> None:
        outcome = run_cognitive_pipeline(
            _REQUEST,
            provider=_DesignIntentProvider(
                {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
            ),
        )
        entry = _trace_entry(outcome.context, "design_intent")
        self.assertIsNotNone(entry, "design_intentが決定の記録に残っていない")
        self.assertEqual(entry.decision, "ai")
        self.assertIn("density.relaxed", entry.reason)

    def test_a_fully_rejected_answer_is_recorded_as_fallback(self) -> None:
        outcome = run_cognitive_pipeline(
            _REQUEST,
            provider=_DesignIntentProvider(
                {"screen_density": "metric.primary", "list_surface": "metric.primary"}
            ),
        )
        entry = _trace_entry(outcome.context, "design_intent")
        self.assertEqual(entry.decision, "fallback", "既定で埋めたのに「AIが選んだ」と記録された")
        self.assertIn("screen_density", entry.reason)
        self.assertIn("list_surface", entry.reason)

    def test_a_partly_rejected_answer_names_the_fallback_axis(self) -> None:
        outcome = run_cognitive_pipeline(
            _REQUEST,
            provider=_DesignIntentProvider(
                {"screen_density": "density.compact", "list_surface": "nonsense"}
            ),
        )
        entry = _trace_entry(outcome.context, "design_intent")
        self.assertEqual(entry.decision, "ai")
        self.assertIn("list_surface", entry.reason)


if __name__ == "__main__":
    unittest.main()
