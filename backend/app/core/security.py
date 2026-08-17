"""JWT検証・認可の共通ロジック(`core/README.md`が予告していた
`security.py`)。FORGE V2 Phase 1が必要とする、最小限の認証機構。

**このファイルは意図的に2層へ分離してある**:

1. `extract_user_id_from_claims()` — 既にデコード済みのJWT
   claims(`dict`)から`user_id`を取り出す**純粋なロジック**。
   外部ライブラリに一切依存しないため、このサンドボックスでも
   実際に実行・検証できる。
2. `get_current_user_id()` — 実際にHTTPリクエストの`Authorization`
   ヘッダからJWTを取り出し、Supabaseで検証する、FastAPI依存の
   関数。**注記(2026-08-17更新)**: `fastapi`はインストール済みに
   なったので、moduleのimportは通る(013 §8で訂正)。

   **ただし`_verify_and_decode()`は今も`NotImplementedError`である。**
   実際のSupabaseプロジェクト・実際のJWTでの検証は未実施であり、
   この関数を通る経路は**本番で使えない**。「importできる」ことを
   「動く」と読まないこと。

この分離により、「JWTから`user_id`を正しく取り出せるか」という
ロジックの核心部分は、外部ライブラリの有無に関わらずテストできる
(`backend/tests/core/test_security.py`参照)。
"""

from __future__ import annotations

from typing import Any

from app.core.exceptions import PermissionError_


def extract_user_id_from_claims(claims: dict[str, Any]) -> str:
    """デコード済みのJWT claimsから、`user_id`(Supabaseの`sub`
    クレーム)を取り出す。

    Supabase AuthのJWTは、`sub`クレームにUser IDを格納する
    (Supabase公式ドキュメントの標準的な仕様)。`sub`が無い・空文字の
    場合は、不正なトークンとして`PermissionError_`を送出する。
    """
    user_id = claims.get("sub")
    if not user_id or not isinstance(user_id, str):
        raise PermissionError_(
            user_id="<unknown>",
            action="authenticate",
            reason="JWT claims is missing a valid 'sub' (user id) field",
        )
    return user_id


def get_current_user_id(authorization_header: str | None) -> str:
    """`Authorization: Bearer <token>`ヘッダから、認証されたUserの
    IDを取り出す。

    **未検証(上記docstring参照)**: 実際のJWT検証(署名・有効期限の
    確認)は、この関数の実装が呼び出す想定の`_verify_and_decode()`
    (下記、Supabase JWT Secretを用いたローカル検証、または
    Supabaseクライアント経由の検証のいずれかをCEO環境で選択する)が
    担う。ここでは、ヘッダの形式チェックと、デコード後のclaimsを
    `extract_user_id_from_claims()`へ渡す配線のみを行う。
    """
    if not authorization_header or not authorization_header.startswith("Bearer "):
        raise PermissionError_(
            user_id="<unknown>", action="authenticate",
            reason="Missing or malformed Authorization header (expected 'Bearer <token>')",
        )
    token = authorization_header[len("Bearer "):].strip()
    if not token:
        raise PermissionError_(user_id="<unknown>", action="authenticate", reason="Empty bearer token")

    claims = _verify_and_decode(token)
    return extract_user_id_from_claims(claims)


def _verify_and_decode(token: str) -> dict[str, Any]:
    """**未検証・要CEO環境確認**: Supabase発行のJWTを検証・デコード
    する。実装方針としては、(a) `SUPABASE_JWT_SECRET`環境変数を用いた
    ローカル検証(`pyjwt`ライブラリ、`jwt.decode(token, secret,
    algorithms=["HS256"])`)、または(b) Supabaseクライアントの
    `client.auth.get_user(token)`経由の検証、のいずれかを、CEO環境で
    実際のSupabaseプロジェクト設定に合わせて選択する。

    (a)は追加の依存(`pyjwt`、現状`requirements.txt`に無い)が必要に
    なる。(b)は既存の`supabase`依存だけで完結するが、Supabase Auth
    サーバーへのネットワーク呼び出しを伴う(レイテンシが増える)。
    **この選択自体は、Phase 1のScope外の実装判断としてRemaining
    Risksへ記録した(Final Report参照)。**
    """
    raise NotImplementedError(
        "_verify_and_decode() requires either the 'pyjwt' package (not yet in "
        "requirements.txt) or a live Supabase client (unavailable in this sandbox). "
        "CEO environment must implement one of the two documented strategies before "
        "this function can be used."
    )
