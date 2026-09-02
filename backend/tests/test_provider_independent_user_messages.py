"""利用者の画面に **Provider の身元を出さない**（Constitution §4・§9）。

---

## 何を守るテストか

Forge は OpenAI でも Claude でも Gemini でも Ollama でもない。Provider は
差し替え可能な実装手段であって、製品の正体ではない。ところが実際の経路は
Provider が投げた文字列をそのまま利用者まで運んでいた。

```text
GeminiProvider -> RuntimeError("Gemini APIの無料枠の…")
routers/ai.py  -> ProviderError(str(exc))
exception_handlers -> ErrorEnvelope(message=…)   ← 利用者の画面
```

**利用者向け表示だけ**を Provider 非依存にする。`exc.message`・ログ・
Evidence・Provider 実装名は、実 Provider を正確に持ち続ける
（履歴や Evidence から Provider 名を一括削除しない）。

## 配線破壊試験

`exception_handlers.forge_ai_pipeline_error_handler` の
`user_facing_message(...)` を `exc.message` へ戻すと
`TestTheHttpEnvelopeIsProviderIndependent` が落ちる。落ちなければ、
このテストは置物である。
"""

from __future__ import annotations

import pathlib
import sys
import unittest

_ROOT = pathlib.Path(__file__).resolve().parents[2]
for path in (str(_ROOT), str(_ROOT / "backend")):
    if path not in sys.path:
        sys.path.insert(0, path)

from app.ai.runtime.provider_independent_messages import (  # noqa: E402
    _BY_SUB_REASON,
    mentions_provider_identity,
    redact_provider_identity_for_logs,
    user_facing_message,
)

try:
    from fastapi.testclient import TestClient  # noqa: E402

    from app.main import app  # noqa: E402

    _FASTAPI_AVAILABLE = True
except Exception:  # noqa: BLE001 — 依存が無い環境ではHTTP試験だけskipする
    _FASTAPI_AVAILABLE = False


class TestProviderIdentityIsDetected(unittest.TestCase):
    """**見つけられないものは消せない。**"""

    def test_known_provider_names_are_detected(self) -> None:
        for text in (
            "Gemini APIの無料枠の利用上限に達しました。",
            "OpenAIの応答が不正です",
            "claude が応答しませんでした",
            "Ollama へ接続できません",
            "qwen2.5:1.5b-instruct が落ちました",
            "mock を使用中です",
            "別のAI Providerを設定してください",
            "プロバイダーが見つかりません",
        ):
            with self.subTest(text=text):
                self.assertTrue(
                    mentions_provider_identity(text),
                    f"Provider の身元を見落としている: {text}",
                )

    def test_model_ids_embedded_in_words_are_detected(self) -> None:
        """`gemini-2.5-flash` のように語中へ埋まっていても見落とさない。"""
        self.assertTrue(mentions_provider_identity("model=gemini-2.5-flash"))
        self.assertTrue(mentions_provider_identity("gpt-4o-mini へ切り替えました"))

    def test_ordinary_japanese_is_not_flagged(self) -> None:
        """**通す文言まで潰さない。**"""
        for text in (
            "いまAIを利用できませんでした。しばらくしてからもう一度お試しください。",
            "今日のAI利用枠を使い切りました。日付が変わってからもう一度お試しください。",
            "AIの応答に時間がかかりすぎたため、いったん中止しました。",
        ):
            with self.subTest(text=text):
                self.assertFalse(mentions_provider_identity(text))


class TestTheReplacementIsItselfClean(unittest.TestCase):
    """差し替え先の文言が身元を含んでいたら、直した意味が無い。"""

    def test_every_replacement_is_provider_independent(self) -> None:
        for sub_reason, message in _BY_SUB_REASON.items():
            with self.subTest(sub_reason=sub_reason):
                self.assertFalse(mentions_provider_identity(message))

    def test_an_unknown_sub_reason_still_gets_a_clean_message(self) -> None:
        """**分からないものを楽観側へ倒さない。** 素通しではなく既定文言。"""
        result = user_facing_message("Gemini が落ちました", sub_reason="なにこれ")
        self.assertFalse(mentions_provider_identity(result))

    def test_a_missing_sub_reason_still_gets_a_clean_message(self) -> None:
        result = user_facing_message("Gemini が落ちました", sub_reason=None)
        self.assertFalse(mentions_provider_identity(result))

    def test_a_clean_message_passes_through_unchanged(self) -> None:
        original = "作りたい内容がまだはっきりしていません。"
        self.assertEqual(
            user_facing_message(original, sub_reason="unavailable"), original,
        )

    def test_rate_limited_keeps_telling_the_user_what_happened(self) -> None:
        """身元を消したついでに、**中身まで消さない。**"""
        result = user_facing_message(
            "Gemini APIの無料枠の利用上限に達しました。", sub_reason="rate_limited",
        )
        self.assertIn("利用上限", result)


class TestLogsKeepTheProviderIdentity(unittest.TestCase):
    """**Evidence と診断からは消さない。** 消してよいのは表示だけである。"""

    def test_the_provider_name_survives_in_logs(self) -> None:
        self.assertIn("gemini", redact_provider_identity_for_logs("provider=gemini failed"))

    def test_secret_like_strings_are_removed_from_logs(self) -> None:
        """CLAUDE.md §4: 鍵は長さも先頭数文字も出さない。"""
        redacted = redact_provider_identity_for_logs(
            "auth failed for sk-abcdefghijklmnopqrstuvwxyz",
        )
        self.assertNotIn("abcdefghijklmnop", redacted)
        self.assertIn("[REDACTED]", redacted)


@unittest.skipUnless(_FASTAPI_AVAILABLE, "fastapi/pydanticがインストールされていない環境ではskipする")
class TestTheHttpEnvelopeIsProviderIndependent(unittest.TestCase):
    """**本番が必ず通る場所で消えていること。**

    ここが落ちるかどうかが、この修正の配線試験である。
    """

    def setUp(self) -> None:
        self.client = TestClient(app)

    def test_a_provider_error_naming_gemini_does_not_reach_the_user(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        with patch(
            "app.routers.ai.ConversationEngine.step",
            side_effect=RuntimeError(
                "Gemini APIの無料枠の利用上限に達しました。(詳細: status=429)",
            ),
        ):
            response = self.client.post(
                "/api/v1/ai/converse",
                json={"message": "買い物で忘れる", "provider": "gemini"},
            )
        self.assertEqual(response.status_code, 503)
        message = response.json()["error"]["message"]
        self.assertNotIn("Gemini", message)
        self.assertFalse(
            mentions_provider_identity(message),
            f"利用者向けの文言に Provider の身元が出ている: {message}",
        )
        # 何が起きたかは、ちゃんと伝わっている。
        self.assertIn("利用上限", message)

    def test_an_unreachable_provider_does_not_name_itself(self) -> None:
        from unittest.mock import patch  # noqa: PLC0415

        with patch(
            "app.routers.ai.ConversationEngine.step",
            side_effect=RuntimeError("Ollama へ接続できませんでした (port 11434)"),
        ):
            response = self.client.post(
                "/api/v1/ai/converse",
                json={"message": "買い物で忘れる", "provider": "mock"},
            )
        message = response.json()["error"]["message"]
        self.assertFalse(mentions_provider_identity(message), message)
        # 内部の Port 番号も出さない(Universal Quality §9)。
        self.assertNotIn("11434", message)


if __name__ == "__main__":
    unittest.main()
