"""`POST /api/v1/ai/generate` のHTTP APIテスト(FORGE-MILESTONE-005 Task13)。

**重要な注記(未検証)**: Claudeのサンドボックスには`fastapi`・`pydantic`が
インストールされておらず(ネットワーク不可のため`pip install`できず)、
このファイル自体を一度も実行できていない。構文は`ast.parse`で静的に
確認済みだが、実際にFastAPIの`TestClient`を使った検証はCEO環境
(`pip install -r requirements.txt`実行後)で行う必要がある。

実行方法(CEO環境):
    cd backend
    pip install -r requirements.txt --break-system-packages
    python -m unittest tests.test_http_api -v
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _FASTAPI_AVAILABLE = True
except ImportError:
    _FASTAPI_AVAILABLE = False


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestGenerateEndpoint(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_successful_generation_returns_200(self) -> None:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "add item track shopping price"}},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "success")
        self.assertTrue(body["result"]["validation"]["valid"])
        self.assertEqual(body["result"]["diagnostics"]["provider_used"], "mock")
        self.assertEqual(body["result"]["diagnostics"]["engine_used"], "forge_ai")

    def test_empty_natural_language_returns_422(self) -> None:
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": ""}},
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "request_error")

    def test_missing_required_field_returns_422(self) -> None:
        """指示書11章「Request Schema不正422」の回帰テスト。"""
        response = self.client.post("/api/v1/ai/generate", json={"version": "1.0", "input": {}})
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "request_error")

    def test_malformed_json_syntax_returns_400(self) -> None:
        """指示書11章「JSON構文不正400」の回帰テスト。TestClientでは、
        `content=`に生の壊れた文字列を渡すことでJSON構文エラーを再現する
        (Starlette/FastAPIが自動的に400を返す標準動作)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            content=b"{not valid json",
            headers={"Content-Type": "application/json"},
        )
        self.assertEqual(response.status_code, 400)

    def test_unknown_engine_string_is_rejected_by_pydantic_before_reaching_pipeline(self) -> None:
        """CEO実物監査(3回目)対応: `engine`はHTTP層で`Literal["forge_ai"]`
        に制限されている(Fix 1)ため、未知のengine文字列はPydantic入力層
        (Pydanticのモデルバリデーション)で拒否され、`PromptPipeline`
        (よって`UnsupportedEngineError`/`planning_error`)には一切到達
        しない。契約: 未知のengine/provider文字列 → request_error /
        schema_invalid / HTTP 422。

        (旧`test_unsupported_engine_returns_error_envelope`から改名。
        以前は`category == "planning_error"`を期待していたが、Fix 1で
        engineをLiteral化した結果、この経路はもう発生しなくなったため
        誤りだった。)
        """
        response = self.client.post(
            "/api/v1/ai/generate",
            json={
                "version": "1.0",
                "input": {
                    "natural_language": "test",
                    "generation_options": {"engine": "not_a_real_engine"},
                },
            },
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "request_error")
        self.assertEqual(body["error"]["sub_reason"], "schema_invalid")

    def test_unknown_provider_string_is_rejected_by_pydantic_before_reaching_pipeline(self) -> None:
        """CEO実物監査(3回目)対応: `provider`もHTTP層で`Literal["mock",
        "openai", "claude", "gemini", "oss", "local"]`に制限されている
        (Fix 1。`local`はFORGE-020Aで追加)ため、
        許可リストに無い文字列はPydantic入力層で拒否され、
        `ProviderRouter.resolve()`(よって`provider_error`/`unavailable`)
        には一切到達しない。契約: 未知のengine/provider文字列 →
        request_error / schema_invalid / HTTP 422。

        (旧`test_unregistered_provider_returns_provider_error`から改名。
        以前は`category == "provider_error"`・`sub_reason == "unavailable"`
        を期待していたが、Fix 1でproviderをLiteral化した結果、
        許可リスト外の文字列はHTTP層で弾かれるようになったため誤りだった。
        `provider_error`/`unavailable`は、許可リストに含まれるが
        未実装のProvider(例: "openai")を指定した場合にのみ発生する
        ことを`test_unimplemented_provider_returns_provider_error`で
        別途確認する。)
        """
        response = self.client.post(
            "/api/v1/ai/generate",
            json={
                "version": "1.0",
                "input": {
                    "natural_language": "test",
                    "generation_options": {"provider": "does_not_exist"},
                },
            },
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "request_error")
        self.assertEqual(body["error"]["sub_reason"], "schema_invalid")

    def test_unimplemented_provider_returns_provider_error(self) -> None:
        """契約: 既知(許可リストに含まれる)だが未実装のprovider
        (例: "openai"はLiteralを通過するが、foundation/providers.pyの
        _UnimplementedProviderスタブのため実際に呼ぶとNotImplementedError
        になる) → provider_error / unavailable / HTTP 503。
        CEO実物監査(3回目)で、この契約をstatus_code・sub_reasonまで
        明示的に検証するよう強化した(以前はcategoryのみ確認していた)。
        """
        response = self.client.post(
            "/api/v1/ai/generate",
            json={
                "version": "1.0",
                "input": {"natural_language": "test", "generation_options": {"provider": "openai"}},
            },
        )
        self.assertEqual(response.status_code, 503)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "provider_error")
        self.assertEqual(body["error"]["sub_reason"], "unavailable")

    def test_error_envelope_never_leaks_stack_trace(self) -> None:
        """指示書12章「Stack trace等を本番レスポンスに含めない」の回帰テスト。
        意図的に存在しないengineでエラーを起こし、レスポンス全体の文字列
        表現に典型的な内部情報(ファイルパス・Pythonの例外クラス名)が
        含まれないことを確認する。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={
                "version": "1.0",
                "input": {"natural_language": "test", "generation_options": {"engine": "bogus"}},
            },
        )
        text = response.text
        self.assertNotIn("Traceback", text)
        self.assertNotIn(".py\"", text)
        self.assertNotIn("Error(", text)  # 例: "UnsupportedEngineError("のようなPythonクラス名表記

    def test_error_envelope_format_is_consistent_across_error_types(self) -> None:
        """全エラー種別が同じEnvelope形式(version/status/error{category,
        sub_reason,message,retryable})を持つことを確認する。

        **修正記録(CEO実物監査、pytest実行で発見)**: 以前は2件目の
        入力に`natural_language: "x"`(1文字)を使っていたが、FORGE v0.2
        PART A で`run_cognitive_pipeline()`を本番接続した結果、1文字の
        入力はAmbiguity Detection(missing_goal、`_MIN_MEANINGFUL_LENGTH=2`
        未満はHIGH severity)で捕捉され、Provider(`openai`)が実際に
        呼ばれる**前**に`needs_confirmation`へ抜けてしまうようになった
        (`status`が`"error"`ではなく`"needs_confirmation"`になり、本テストが
        falseに失敗していた)。本テストの意図はエラー種別間でEnvelope形式が
        一貫していることの確認であり、「1文字の入力」自体を検証したい
        わけではないため、Provider呼び出しまで実際に到達する
        `"test"`(他の`provider=openai`テストと同じ文言)へ差し替えた。
        `PromptPipeline.run("test", provider="openai")`を実際に実行し、
        `ProviderError`が送出されることをこのセッションで確認済み
        (`TestPromptPipelineFacade`側、6章参照)。"""
        responses = [
            self.client.post("/api/v1/ai/generate", json={"version": "1.0", "input": {"natural_language": ""}}),
            self.client.post(
                "/api/v1/ai/generate",
                json={"version": "1.0", "input": {"natural_language": "test", "generation_options": {"provider": "openai"}}},
            ),
        ]
        for response in responses:
            body = response.json()
            self.assertIn("version", body)
            self.assertIn("status", body)
            self.assertEqual(body["status"], "error")
            self.assertIn("category", body["error"])
            self.assertIn("sub_reason", body["error"])
            self.assertIn("message", body["error"])
            self.assertIn("retryable", body["error"])

    def test_single_character_input_triggers_needs_confirmation_not_provider_error(self) -> None:
        """上記修正の裏付けとなる回帰テスト: 1文字の入力は、Providerに
        関わらずAmbiguity Detection(missing_goal)で`needs_confirmation`
        になることを明示的に固定する(PART A接続の副作用を、意図した
        挙動として記録する)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "x", "generation_options": {"provider": "openai"}}},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "needs_confirmation")
        self.assertEqual(body["confirmation"]["reached_stage"], "ambiguity_detection")

    # -----------------------------------------------------------------
    # CEO実物監査(2回目)対応: Fix 1(Engine/Provider許可リスト化)、
    # Fix 3(max_repair_attempts上限2)
    # -----------------------------------------------------------------

    def test_engine_native_is_rejected_by_http_allowlist(self) -> None:
        """Fix 1回帰テスト: Router内部では'native'を'forge_ai'のエイリアス
        として解決できるが、HTTP公開APIでは`engine`にLiteral["forge_ai"]
        以外を許可しない(Pydanticが422で弾く)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "test", "generation_options": {"engine": "native"}}},
        )
        self.assertEqual(response.status_code, 422)

    def test_provider_local_is_accepted_by_http_allowlist(self) -> None:
        """**FORGE-020A で決定が変わった**(2026-08-26)。

        ---

        ## 元のテストの前提が、いま事実でない

        このテストは以前

            'local'はRouter内部の'oss'エイリアスだが、
            HTTP公開APIのproviderには含まれない

        と書いて422を期待していた。当時はそうだった。

        しかし現在の`local`は**エイリアスではない**——Provider Registry
        の独立した`provider_id`であり、`implementation_status=IMPLEMENTED`
        `deployment=LOCAL` `supports_structured_output=True`、
        `ProviderRouter._SPECIFIC_FACTORIES["local"] = LocalModelProvider`
        という実装を持つ。むしろ`oss`の方が
        `NotImplementedError`を投げるスタブで、Registry自身が
        「`local`が実質的な後継」と書いている。

        つまり**動く方を弾いて、動かない方を通していた**。

        `native` / `forge_ai` を弾く理由（Engine名との混同を型で防ぐ、
        ADR 4.0節）は`local`には当てはまらない。**Provider名である。**

        Vision §39 Level 0（Local Model が動く）は

            Runtime → LocalModelProvider → AIRouter → Forge pipeline
              → Validator → Evidence

        を通ることの証明なので、ここが閉じていると実機でも測れない。
        """
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "test", "generation_options": {"provider": "local"}}},
        )
        self.assertNotEqual(
            response.status_code, 422,
            "provider='local' が schema で弾かれている（本番経路が無い）",
        )

    def test_provider_forge_ai_is_rejected_by_http_allowlist(self) -> None:
        """Fix 1回帰テスト: 'forge_ai'はEngine名であり、HTTP公開APIの
        provider(LLM実装の選択)としては受理しない
        (Engine/Providerの混同を型で防ぐ、ADR 4.0節)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "test", "generation_options": {"provider": "forge_ai"}}},
        )
        self.assertEqual(response.status_code, 422)

    def test_engine_forge_ai_is_accepted(self) -> None:
        """許可リストの値そのものは引き続き受理されることの確認(過剰な
        制限になっていないか)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "add item", "generation_options": {"engine": "forge_ai", "provider": "mock"}}},
        )
        self.assertEqual(response.status_code, 200)

    def test_max_repair_attempts_zero_one_two_are_accepted(self) -> None:
        """Fix 3境界テスト: 0・1・2は許可される。"""
        for value in (0, 1, 2):
            with self.subTest(max_repair_attempts=value):
                response = self.client.post(
                    "/api/v1/ai/generate",
                    json={
                        "version": "1.0",
                        "input": {"natural_language": "add item", "generation_options": {"max_repair_attempts": value}},
                    },
                )
                self.assertEqual(response.status_code, 200)

    def test_max_repair_attempts_three_is_rejected(self) -> None:
        """Fix 3境界テスト: 3以上はHTTP入力層で422になる
        (M005契約「Repair最大2回」との矛盾を防ぐ)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "test", "generation_options": {"max_repair_attempts": 3}}},
        )
        self.assertEqual(response.status_code, 422)

    def test_max_repair_attempts_large_value_is_rejected(self) -> None:
        """Fix 3境界テスト: 以前のle=10の名残でないことを確認する
        (10は以前は許可されていたが、今は422になるべき)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "test", "generation_options": {"max_repair_attempts": 10}}},
        )
        self.assertEqual(response.status_code, 422)

    def test_unknown_version_in_generate_request_is_rejected(self) -> None:
        """FORGE v0.2 Final Gate P0.2の回帰テスト: `version`は
        `Literal["1.0"]`固定であり、未知のversion文字列は422で拒否される。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "2.0", "input": {"natural_language": "test"}},
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "request_error")

    def test_unknown_version_in_confirm_request_is_rejected(self) -> None:
        """FORGE v0.2 Final Gate P0.2の回帰テスト: `/generate/confirm`も
        同様に`version`を固定する。"""
        response = self.client.post(
            "/api/v1/ai/generate/confirm",
            json={"version": "0.9", "request_id": "does-not-matter", "answer": "test"},
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "request_error")

    def test_known_version_is_accepted(self) -> None:
        """version固定が過剰制限になっていないこと(正しい値は通ること)の確認。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "add item"}},
        )
        self.assertEqual(response.status_code, 200)

    def test_conversion_warnings_present_in_successful_response(self) -> None:
        """Fix 2回帰テスト: diagnostics.conversion_warningsがHTTPレスポンスに
        含まれる(以前はどこにも返されず、消えていた)。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "add item track shopping price"}},
        )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertIn("conversion_warnings", body["result"]["diagnostics"])
        self.assertIsInstance(body["result"]["diagnostics"]["conversion_warnings"], list)

    def test_cognitive_diagnostics_fields_present_in_successful_response(self) -> None:
        """FORGE v0.2 PART A 4.2節の回帰テスト: ambiguity_report・
        domain_classification・decision_traceがHTTPレスポンスへ到達する。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "add item track shopping price"}},
        )
        self.assertEqual(response.status_code, 200)
        diagnostics = response.json()["result"]["diagnostics"]
        self.assertIn("ambiguity_report", diagnostics)
        self.assertIn("domain_classification", diagnostics)
        self.assertIn("decision_trace", diagnostics)
        self.assertIsInstance(diagnostics["decision_trace"], list)
        self.assertGreaterEqual(len(diagnostics["decision_trace"]), 1)

    def test_needs_confirmation_returns_200_with_needs_confirmation_status(self) -> None:
        """FORGE v0.2 PART A 4.1・5.2節の回帰テスト: `CognitivePipelineNeedsConfirmation`
        は500/422のエラーではなく、`status: "needs_confirmation"`を持つ
        200レスポンスとして返る。`PromptPipeline.run()`をモックし、
        Cognitive層の個別の曖昧性検出ロジックには依存しない形で、
        ルーター層の分岐だけを検証する。"""
        from unittest.mock import patch

        from app.ai.runtime.prompt_pipeline import PipelineNeedsConfirmationResult

        fake_result = PipelineNeedsConfirmationResult(
            reason="priority1_privacy_safety_permission",
            message="対象者の情報範囲を確認させてください。",
            open_questions=("誰の情報を記録しますか？",),
            reached_stage="ambiguity_detection",
            engine_used="forge_ai",
            provider_used="mock",
            decision_trace=(),
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=fake_result):
            response = self.client.post(
                "/api/v1/ai/generate",
                json={"version": "1.0", "input": {"natural_language": "福祉支援記録をつけたい"}},
            )
        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["status"], "needs_confirmation")
        self.assertEqual(body["confirmation"]["reason"], "priority1_privacy_safety_permission")
        self.assertEqual(body["confirmation"]["reached_stage"], "ambiguity_detection")
        self.assertEqual(body["confirmation"]["open_questions"], ["誰の情報を記録しますか？"])
        self.assertTrue(body["confirmation"]["request_id"])  # 空文字でないことのみ確認(値自体はuuid4)

    def test_needs_confirmation_response_includes_diagnostics_and_rounds_remaining(self) -> None:
        """FORGE v0.2 P1 4章・7章の回帰テスト: needs_confirmation時にも
        ambiguity_report・domain_classificationを失わず、rounds_remaining
        (確認往復の残り回数)が含まれること。"""
        from unittest.mock import patch

        from app.ai.runtime.prompt_pipeline import PipelineNeedsConfirmationResult

        fake_result = PipelineNeedsConfirmationResult(
            reason="priority2_low_domain_confidence",
            message="どの分野のアプリか確認させてください。",
            open_questions=("どのようなアプリを作りたいですか？",),
            reached_stage="domain_classification",
            engine_used="forge_ai",
            provider_used="mock",
            decision_trace=({"stage": "domain_classification", "decision": "generic", "reason": "低confidence"},),
            ambiguity_report={"detection_status": "ok", "overall_severity": "low", "issues": []},
            domain_classification={"primary_domain": "generic", "confidence": 0.1},
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=fake_result):
            response = self.client.post(
                "/api/v1/ai/generate",
                json={"version": "1.0", "input": {"natural_language": "何か作りたい"}},
            )
        body = response.json()
        self.assertEqual(body["confirmation"]["rounds_remaining"], 2)  # MAX(3) - round_count(1)
        self.assertIsNotNone(body["diagnostics"])
        self.assertEqual(body["diagnostics"]["ambiguity_report"]["overall_severity"], "low")
        self.assertEqual(body["diagnostics"]["domain_classification"]["primary_domain"], "generic")
        self.assertEqual(len(body["diagnostics"]["decision_trace"]), 1)

    def test_confirm_round_trip_reaches_success(self) -> None:
        """FORGE v0.2 P0 2章の回帰テスト: 確認質問→回答送信→再生成が
        最後まで完成する(needs_confirmationで終わらず、successへ到達する)。

        FORGE v0.2 Final Gate P0.1の回帰テスト: 元の入力と回答は、
        事前に結合された1本の文字列としてではなく、`natural_language`
        (位置引数)と`clarification_answers`(キーワード引数、タプル)という
        **別々の引数**として`PromptPipeline.run()`へ渡されることを確認する
        (以前はこの2つを結合した文字列に、Forge内部の管理用ラベル
        「補足回答」を含めて渡していたため、そのラベル自体がSurvey
        Domainの概念語("回答")と誤って一致するという重大なバグがあった)。
        """
        from unittest.mock import patch

        from app.ai.runtime.prompt_pipeline import Diagnostics, PipelineNeedsConfirmationResult, PipelineRunResult

        needs_confirmation = PipelineNeedsConfirmationResult(
            reason="priority1_privacy_safety_permission",
            message="対象者の情報範囲を確認させてください。",
            open_questions=("誰の情報を記録しますか？",),
            reached_stage="ambiguity_detection",
            engine_used="forge_ai",
            provider_used="mock",
            decision_trace=(),
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=needs_confirmation):
            first = self.client.post(
                "/api/v1/ai/generate",
                json={"version": "1.0", "input": {"natural_language": "福祉支援記録をつけたい"}},
            )
        request_id = first.json()["confirmation"]["request_id"]

        success = PipelineRunResult(
            forge_document={"version": "1.0", "app": {"title": "T"}, "screens": []},
            validation=_valid_validation_result(),
            quality=None,
            diagnostics=Diagnostics(engine_used="forge_ai", provider_used="mock", repair_attempts=0),
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=success) as mock_run:
            second = self.client.post(
                "/api/v1/ai/generate/confirm",
                json={"version": "1.0", "request_id": request_id, "answer": "家族のみが対象です"},
            )
            # 元の入力(位置引数)には回答の文言が混ざっていないこと、
            # 回答は`clarification_answers`という別のキーワード引数(タプル)として
            # 渡されていることを、両方とも確認する。
            call_args, call_kwargs = mock_run.call_args
            called_natural_language = call_args[0]
            self.assertEqual(called_natural_language, "福祉支援記録をつけたい")
            self.assertNotIn("家族のみが対象です", called_natural_language)
            self.assertNotIn("補足回答", called_natural_language)
            self.assertEqual(call_kwargs.get("clarification_answers"), ("家族のみが対象です",))

        self.assertEqual(second.status_code, 200)
        self.assertEqual(second.json()["status"], "success")

    def test_confirm_accumulates_all_answers_across_multiple_rounds(self) -> None:
        """FORGE v0.2 Final Gate 最終調整 P1の回帰テスト(核心):
        2回連続で確認が続いた場合、1回目の回答("家族向け")が失われず、
        2回目(`/generate/confirm`)の`PromptPipeline.run()`呼び出しへ、
        **両方の回答**が`clarification_answers`として渡ることを確認する。
        以前は最新の回答1件しか渡っていなかった。
        """
        from unittest.mock import patch

        from app.ai.runtime.prompt_pipeline import Diagnostics, PipelineNeedsConfirmationResult, PipelineRunResult

        needs_confirmation_1 = PipelineNeedsConfirmationResult(
            reason="priority1_privacy_safety_permission", message="誰向けですか？",
            open_questions=(), reached_stage="ambiguity_detection",
            engine_used="forge_ai", provider_used="mock", decision_trace=(),
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=needs_confirmation_1):
            first = self.client.post(
                "/api/v1/ai/generate",
                json={"version": "1.0", "input": {"natural_language": "x"}},
            )
        first_request_id = first.json()["confirmation"]["request_id"]

        needs_confirmation_2 = PipelineNeedsConfirmationResult(
            reason="priority2_low_domain_confidence", message="何を管理しますか？",
            open_questions=(), reached_stage="domain_classification",
            engine_used="forge_ai", provider_used="mock", decision_trace=(),
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=needs_confirmation_2) as mock_run_1:
            second = self.client.post(
                "/api/v1/ai/generate/confirm",
                json={"version": "1.0", "request_id": first_request_id, "answer": "家族向け"},
            )
            # 1回目の確認往復: この時点でclarification_answersには
            # 「家族向け」の1件だけが含まれるはず。
            self.assertEqual(mock_run_1.call_args.kwargs.get("clarification_answers"), ("家族向け",))
        second_request_id = second.json()["confirmation"]["request_id"]

        success = PipelineRunResult(
            forge_document={"version": "1.0", "app": {"title": "T"}, "screens": []},
            validation=_valid_validation_result(), quality=None,
            diagnostics=Diagnostics(engine_used="forge_ai", provider_used="mock", repair_attempts=0),
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=success) as mock_run_2:
            third = self.client.post(
                "/api/v1/ai/generate/confirm",
                json={"version": "1.0", "request_id": second_request_id, "answer": "買い物リストです"},
            )
            # 2回目の確認往復(核心の確認): 1回目の回答「家族向け」を
            # 失わず、2回目の回答「買い物リストです」と**両方とも**
            # clarification_answersへ含まれていること。
            called_answers = mock_run_2.call_args.kwargs.get("clarification_answers")
            self.assertEqual(called_answers, ("家族向け", "買い物リストです"))

        self.assertEqual(third.status_code, 200)
        self.assertEqual(third.json()["status"], "success")

    def test_confirm_with_unknown_request_id_returns_422_request_error(self) -> None:
        response = self.client.post(
            "/api/v1/ai/generate/confirm",
            json={"version": "1.0", "request_id": "does-not-exist", "answer": "test"},
        )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["status"], "error")
        self.assertEqual(body["error"]["category"], "request_error")
        self.assertEqual(body["error"]["sub_reason"], "confirmation_session_not_found")

    def test_confirm_rounds_exceeded_returns_422(self) -> None:
        """FORGE v0.2 P0 2章「確認回数制御」の回帰テスト: 確認を無限に
        繰り返せない。"""
        from unittest.mock import patch

        from app.ai.runtime.confirmation_store import MAX_CONFIRMATION_ROUNDS, default_confirmation_store
        from app.ai.runtime.prompt_pipeline import PipelineNeedsConfirmationResult

        needs_confirmation = PipelineNeedsConfirmationResult(
            reason="priority1_privacy_safety_permission", message="確認してください。",
            open_questions=("誰の情報ですか？",), reached_stage="ambiguity_detection",
            engine_used="forge_ai", provider_used="mock", decision_trace=(),
        )
        # 既に上限に達したセッションを直接作る(往復を何度も繰り返さず、
        # 境界条件だけを狙って検証する)。
        session = default_confirmation_store.create(
            original_natural_language="test", engine="forge_ai", provider="mock",
            reached_stage="ambiguity_detection", reason="priority1_privacy_safety_permission",
            round_count=MAX_CONFIRMATION_ROUNDS,
        )
        with patch("app.routers.ai.PromptPipeline.run", return_value=needs_confirmation):
            response = self.client.post(
                "/api/v1/ai/generate/confirm",
                json={"version": "1.0", "request_id": session.request_id, "answer": "answer"},
            )
        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["error"]["category"], "request_error")
        self.assertEqual(body["error"]["sub_reason"], "confirmation_rounds_exceeded")

    def test_error_envelope_includes_reached_stage_when_available(self) -> None:
        """FORGE v0.2 P1 5章の回帰テスト: `reached_stage`がメッセージ文字列
        への埋め込みではなく、正式なフィールドとして返る。"""
        response = self.client.post(
            "/api/v1/ai/generate",
            json={"version": "1.0", "input": {"natural_language": "test", "generation_options": {"provider": "openai"}}},
        )
        body = response.json()
        self.assertIn("reached_stage", body["error"])
        self.assertEqual(body["error"]["reached_stage"], "forge_ir_compilation")


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestOpenApiSchema(unittest.TestCase):
    """Backend接続対応 指示書「可能ならバックエンドのレスポンススキーマを
    OpenAPI上で明示してください」の回帰テスト。`response_model=None`を
    使っていないため(P1 6章)、`/generate`・`/generate/confirm`の
    レスポンススキーマがOpenAPIへ実際に反映されていることを確認する。"""

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_openapi_schema_is_generated_without_error(self) -> None:
        response = self.client.get("/openapi.json")
        self.assertEqual(response.status_code, 200)
        schema = response.json()
        self.assertIn("paths", schema)

    def test_generate_endpoint_appears_in_openapi_schema(self) -> None:
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/v1/ai/generate", schema["paths"])
        self.assertIn("post", schema["paths"]["/api/v1/ai/generate"])

    def test_confirm_endpoint_appears_in_openapi_schema(self) -> None:
        schema = self.client.get("/openapi.json").json()
        self.assertIn("/api/v1/ai/generate/confirm", schema["paths"])

    def test_generate_endpoint_documents_success_and_error_responses(self) -> None:
        """`response_model=None`(禁止事項)を使っていないため、200
        (成功/確認要求)に加えて422/500/502/503/504のエラーレスポンスも
        OpenAPIへドキュメント化されていることを確認する。"""
        schema = self.client.get("/openapi.json").json()
        responses = schema["paths"]["/api/v1/ai/generate"]["post"]["responses"]
        for status_code in ("200", "422", "500", "502", "503", "504"):
            self.assertIn(status_code, responses, f"status {status_code} がOpenAPIへ文書化されていません")


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではスキップする")
class TestCorsConfiguration(unittest.TestCase):
    """Backend接続対応 指示書「ChromeからFastAPIへアクセスできるように、
    バックエンドのCORS設定を確認してください」の回帰テスト。
    `FORGE_ENV`環境変数による開発/本番分離(`app/main.py`)を検証する。
    """

    def test_localhost_origin_is_allowed_in_development_env(self) -> None:
        """既定(FORGE_ENV未設定 = development)では、Flutter Web開発
        サーバーの典型的なOrigin(localhostの任意のポート)が許可される。"""
        import importlib

        os.environ.pop("FORGE_ENV", None)
        import app.main as main_module

        importlib.reload(main_module)
        client = TestClient(main_module.app)
        response = client.options(
            "/api/v1/ai/generate",
            headers={
                "Origin": "http://localhost:54321",
                "Access-Control-Request-Method": "POST",
            },
        )
        self.assertEqual(response.headers.get("access-control-allow-origin"), "http://localhost:54321")

    def test_arbitrary_origin_is_rejected_in_production_env_without_explicit_allowlist(self) -> None:
        """本番相当(FORGE_ENV=production)で`FORGE_CORS_ALLOWED_ORIGINS`
        が未設定の場合、無条件のワイルドカード許可はしない(安全側)。"""
        import importlib

        os.environ["FORGE_ENV"] = "production"
        os.environ.pop("FORGE_CORS_ALLOWED_ORIGINS", None)
        try:
            import app.main as main_module

            importlib.reload(main_module)
            client = TestClient(main_module.app)
            response = client.options(
                "/api/v1/ai/generate",
                headers={
                    "Origin": "http://evil.example.com",
                    "Access-Control-Request-Method": "POST",
                },
            )
            self.assertIsNone(response.headers.get("access-control-allow-origin"))
        finally:
            os.environ.pop("FORGE_ENV", None)
            import importlib as _importlib

            import app.main as _main_module

            _importlib.reload(_main_module)


def _valid_validation_result():
    from app.ai.validators.schema_validator import ValidationResult

    return ValidationResult(valid=True, errors=[], warnings=[])


if __name__ == "__main__":
    unittest.main()
