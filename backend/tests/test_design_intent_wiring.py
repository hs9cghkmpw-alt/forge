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
    design_language_guidance,
    is_valid_choice,
)
from forge_ai.core.orchestration.outcomes import CognitivePipelineSuccess  # noqa: E402
from forge_ai.core.pipeline import run_cognitive_pipeline  # noqa: E402
from forge_ai.provider.mock_provider import MockProvider  # noqa: E402
from forge_ai.provider.provider_interface import ProviderResponse  # noqa: E402

_REQUEST = "家計簿をつけたい"


def _run(provider):  # noqa: ANN001, ANN202
    """本番と同じ形で動かす。**語彙は明示的に注入する。**

    §5でこうなった。以前はforge_aiがbackendを遅延importしていたので、
    何も渡さなくても本番だけ語彙が解決していた——standaloneと
    Productionで挙動が違い、どちらが本当かテストからは分からなかった。
    いまは渡さなければAIへ聞かない。**渡す側の責任が見えている。**
    """
    return run_cognitive_pipeline(
        _REQUEST, provider=provider, design_language=design_language_guidance()
    )


class _DesignIntentProvider:
    """`design_intent` 段だけ差し替え、他の段は MockProvider に委ねる。

    こうしないと「AIが選んだから変わった」のか「Mockの都合で変わった」
    のかが分からない。
    """

    def __init__(
        self, answer: object, *, raise_on_design_intent: bool = False, inner: object = None
    ) -> None:
        self._answer = answer
        self._raise = raise_on_design_intent
        # `inner`を渡せるのは、本番のHTTP経路を通したまま**AIだけを
        # 差し替える**ため。Bridgeをそのまま内側に置くので、他の段は
        # 本番と同じものが動く。
        self._inner = inner or MockProvider()
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

    def test_the_production_path_builds_a_usable_guidance(self) -> None:
        """backendが**forge_aiへ注入する契約**が成立していること。

        §5でこの向きへ直した。以前はforge_aiがbackendを遅延importし、
        失敗を握り潰していたので、Productionとstandaloneで同じコードが
        別の振る舞いをしていた。
        """
        guidance = design_language_guidance()
        self.assertTrue(guidance.is_usable, "本番経路で語彙が使えない状態になっている")
        self.assertEqual(len(guidance.axes), len(design_choice_guidance()))
        self.assertIs(guidance.is_valid_choice, is_valid_choice)

    def test_the_guidance_rejects_an_answer_from_another_axis(self) -> None:
        guidance = design_language_guidance()
        self.assertTrue(guidance.validate("screen_density", "density.compact"))
        self.assertFalse(guidance.validate("screen_density", "metric.primary"))

    def test_generating_an_app_asks_the_ai_to_choose_design_roles(self) -> None:
        provider = _DesignIntentProvider(
            {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
        )
        outcome = _run(provider)
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertEqual(
            len(provider.design_intent_prompts), 1,
            "本番の生成でdesign_intent Promptが1回も組み立てられていない",
        )

    def test_the_prompt_carries_the_closed_option_set(self) -> None:
        """自由記述にしない。**選択肢そのものがPromptに載っている**こと。"""
        provider = _DesignIntentProvider({"screen_density": "density.relaxed"})
        _run(provider)
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
        outcome = _run(provider)
        roles = _style_roles(outcome.ir)
        self.assertEqual(roles.get("root_tabs"), "density.relaxed")
        self.assertEqual(roles.get("records_list_view"), "surface.elevated")

    def test_a_different_choice_produces_a_different_document(self) -> None:
        """固定値を返しているだけ、ではないこと。"""
        relaxed = _run(_DesignIntentProvider(
            {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
        ))
        compact = _run(_DesignIntentProvider(
            {"screen_density": "density.compact", "list_surface": "surface.card"}
        ))
        self.assertNotEqual(_style_roles(relaxed.ir), _style_roles(compact.ir))
        self.assertEqual(_style_roles(compact.ir).get("root_tabs"), "density.compact")

    def test_the_document_still_validates_against_the_schema(self) -> None:
        """AIが選んだroleでも Forge Document として通ること。

        **Runtimeが保証できない値が生成物へ入らない**という約束の側。
        """
        from app.ai.validators.schema_validator import validate_forge_document

        outcome = _run(_DesignIntentProvider(
            {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
        ))
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
        outcome = _run(provider)
        roles = _style_roles(outcome.ir)
        self.assertEqual(roles.get("root_tabs"), "density.normal", "軸違いのroleが採用された")
        self.assertEqual(roles.get("records_list_view"), "surface.elevated")

    def test_an_invented_value_is_rejected(self) -> None:
        provider = _DesignIntentProvider(
            {"screen_density": "density.enormous", "list_surface": "font_size: 36"}
        )
        outcome = _run(provider)
        roles = _style_roles(outcome.ir)
        self.assertEqual(roles.get("root_tabs"), "density.normal")
        self.assertEqual(roles.get("records_list_view"), "surface.card")

    def test_a_broken_response_shape_does_not_break_generation(self) -> None:
        for answer in ("density.relaxed", ["density.relaxed"], None, {}):
            with self.subTest(answer=answer):
                outcome = _run(_DesignIntentProvider(answer))
                self.assertIsInstance(outcome, CognitivePipelineSuccess)
                self.assertEqual(_style_roles(outcome.ir).get("root_tabs"), "density.normal")

    def test_generation_survives_a_provider_failure(self) -> None:
        """**Design Languageが入ったせいで生成が落ちる**のは本末転倒。"""
        provider = _DesignIntentProvider({}, raise_on_design_intent=True)
        outcome = _run(provider)
        self.assertIsInstance(outcome, CognitivePipelineSuccess)
        self.assertEqual(_style_roles(outcome.ir).get("root_tabs"), "density.normal")


class TestTheRecordSeparatesAIFromDefault(unittest.TestCase):
    """**AIが選んだ**と**Forgeが既定で埋めた**が混ざらないこと。

    混ざると「AIの選択が受け入れられた」という学習素材が嘘になる
    (`CLAUDE.md` §3「分からないものを楽観側へ倒さない」)。
    """

    def test_an_accepted_choice_is_recorded_as_ai(self) -> None:
        outcome = _run(_DesignIntentProvider(
            {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
        ))
        entry = _trace_entry(outcome.context, "design_intent")
        self.assertIsNotNone(entry, "design_intentが決定の記録に残っていない")
        self.assertEqual(entry.decision, "ai")
        self.assertIn("density.relaxed", entry.reason)

    def test_a_fully_rejected_answer_is_recorded_as_fallback(self) -> None:
        outcome = _run(_DesignIntentProvider(
                {"screen_density": "metric.primary", "list_surface": "metric.primary"}
            ))
        entry = _trace_entry(outcome.context, "design_intent")
        self.assertEqual(entry.decision, "fallback", "既定で埋めたのに「AIが選んだ」と記録された")
        self.assertIn("screen_density", entry.reason)
        self.assertIn("list_surface", entry.reason)

    def test_a_partly_rejected_answer_names_the_fallback_axis(self) -> None:
        outcome = _run(_DesignIntentProvider(
                {"screen_density": "density.compact", "list_surface": "nonsense"}
            ))
        entry = _trace_entry(outcome.context, "design_intent")
        self.assertEqual(entry.decision, "ai")
        self.assertIn("list_surface", entry.reason)


class TestTheEvidenceSeparatesAiFromFallback(unittest.TestCase):
    """**§4の本体。** Generation Evidenceで「AIが選んだ」と「Forgeが
    既定で埋めた」が混ざらないこと。

    混ざると、Local AIは**Forgeの既定値をAIの成功例として学習する**
    ——「このNeedではcompactが良い」とAIが判断した事実は1つも無いのに、
    そう記録される。
    """

    def setUp(self) -> None:
        from app.ai.gateway.generation_evidence import default_generation_store
        from fastapi.testclient import TestClient

        from app.main import app

        self.store = default_generation_store()
        self.store.reset()
        self.client = TestClient(app)

    def _record(self, answer: object):
        """本番のHTTP経路を通したまま、**`design_intent`の答えだけ**
        差し替えて1回生成し、残った記録を返す。

        Pipelineも記録も本番のものである——差し替えているのはAIの
        答えだけなので、「記録まで届いているか」を確かめられる。
        """
        import app.ai.runtime.prompt_pipeline as pipeline_module

        original = pipeline_module.run_cognitive_pipeline

        def patched(text, provider=None, **kwargs):  # noqa: ANN001, ANN202
            return original(text, _DesignIntentProvider(answer, inner=provider), **kwargs)

        pipeline_module.run_cognitive_pipeline = patched
        try:
            response = self.client.post(
                "/api/v1/ai/generate",
                json={"input": {"natural_language": _REQUEST,
                                "generation_options": {"provider": "mock"}}},
            )
            self.assertEqual(response.status_code, 200, response.text)
        finally:
            pipeline_module.run_cognitive_pipeline = original
        records = self.store.all_records()
        self.assertTrue(records, "生成の記録が残っていない")
        return records[0]

    def test_an_accepted_choice_is_recorded_as_ai(self) -> None:
        from app.ai.gateway.generation_evidence import DesignDecisionSource

        record = self._record(
            {"screen_density": "density.relaxed", "list_surface": "surface.elevated"}
        )
        by_axis = {d.axis: d for d in record.design_decisions if d.axis}
        self.assertEqual(by_axis["screen_density"].role, "density.relaxed")
        self.assertIs(by_axis["screen_density"].source, DesignDecisionSource.AI)
        self.assertIs(by_axis["list_surface"].source, DesignDecisionSource.AI)

    def test_a_rejected_choice_is_recorded_as_fallback(self) -> None:
        from app.ai.gateway.generation_evidence import DesignDecisionSource

        record = self._record({"screen_density": "metric.primary"})
        by_axis = {d.axis: d for d in record.design_decisions if d.axis}
        self.assertIs(by_axis["screen_density"].source, DesignDecisionSource.FALLBACK)
        self.assertEqual(by_axis["screen_density"].role, "density.normal")

    def test_the_training_view_excludes_fallbacks(self) -> None:
        """**§4.3。** ACCEPTEDされた生成物でも、既定値をAIの成功例に
        混ぜない。ここを型で分けておく。"""
        record = self._record({"screen_density": "density.compact"})
        ai_roles = {d.role for d in record.ai_selected_roles}
        fallback_axes = {d.axis for d in record.fallback_roles}
        self.assertIn("density.compact", ai_roles)
        self.assertIn("list_surface", fallback_axes)
        self.assertFalse(
            ai_roles & {d.role for d in record.fallback_roles},
            "AIが選んだroleと既定で埋めたroleが混ざっている",
        )

    def test_compiler_roles_are_not_counted_as_ai_successes(self) -> None:
        """Compilerが構造から決めたrole(見出し・一覧)はAIの手柄ではない。"""
        from app.ai.gateway.generation_evidence import DesignDecisionSource

        record = self._record({"screen_density": "density.compact"})
        deterministic = {d.role for d in record.design_decisions
                         if d.source is DesignDecisionSource.DETERMINISTIC}
        self.assertIn("text.headline", deterministic)
        self.assertNotIn("text.headline", {d.role for d in record.ai_selected_roles})

    def test_the_evidence_carries_no_free_text(self) -> None:
        """**§4.2。** Prompt本文もProviderの生出力も入らない。"""
        record = self._record({"screen_density": "density.compact"})
        rendered = repr(record.to_dict())
        self.assertNotIn(_REQUEST, rendered, "利用者の発話がEvidenceへ入っている")


if __name__ == "__main__":
    unittest.main()
