"""`app/core/security.py`のテスト(FORGE V2 Phase 1)。

`extract_user_id_from_claims()`・`get_current_user_id()`のヘッダ
検証部分は、外部ライブラリ(fastapi/pydantic/jwt/supabase)に一切
依存しないため、このサンドボックスでも実際に実行・検証できる。
`_verify_and_decode()`(実際のJWT署名検証)自体は、CEO環境でのみ
検証可能(`NotImplementedError`を送出することを確認するテストに
留める、下記)。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from app.core.exceptions import PermissionError_  # noqa: E402
from app.core.security import extract_user_id_from_claims, get_current_user_id  # noqa: E402


class TestExtractUserIdFromClaims(unittest.TestCase):
    def test_extracts_sub_claim(self) -> None:
        self.assertEqual(extract_user_id_from_claims({"sub": "user-123"}), "user-123")

    def test_raises_when_sub_is_missing(self) -> None:
        with self.assertRaises(PermissionError_):
            extract_user_id_from_claims({})

    def test_raises_when_sub_is_empty_string(self) -> None:
        with self.assertRaises(PermissionError_):
            extract_user_id_from_claims({"sub": ""})

    def test_raises_when_sub_is_not_a_string(self) -> None:
        with self.assertRaises(PermissionError_):
            extract_user_id_from_claims({"sub": 12345})

    def test_ignores_unrelated_claims(self) -> None:
        self.assertEqual(
            extract_user_id_from_claims({"sub": "user-123", "email": "a@example.com", "role": "authenticated"}),
            "user-123",
        )


class TestGetCurrentUserIdHeaderValidation(unittest.TestCase):
    """実際のJWT検証(`_verify_and_decode`)には到達しない、ヘッダ形式
    チェックの部分だけを検証する(この部分は外部ライブラリに依存
    しない)。"""

    def test_raises_when_header_is_none(self) -> None:
        with self.assertRaises(PermissionError_):
            get_current_user_id(None)

    def test_raises_when_header_is_empty_string(self) -> None:
        with self.assertRaises(PermissionError_):
            get_current_user_id("")

    def test_raises_when_header_does_not_start_with_bearer(self) -> None:
        with self.assertRaises(PermissionError_):
            get_current_user_id("Basic abcdef")

    def test_raises_when_bearer_token_is_empty(self) -> None:
        with self.assertRaises(PermissionError_):
            get_current_user_id("Bearer ")
        with self.assertRaises(PermissionError_):
            get_current_user_id("Bearer    ")

    def test_well_formed_header_reaches_the_unimplemented_verification_step(self) -> None:
        """CEO環境で`_verify_and_decode()`が実装されるまでは
        `NotImplementedError`になることを確認する(=ヘッダ形式
        チェック自体は正しく通過し、次の未実装ステップまで到達する
        ことの裏付け)。"""
        with self.assertRaises(NotImplementedError):
            get_current_user_id("Bearer some.jwt.token")


if __name__ == "__main__":
    unittest.main()
