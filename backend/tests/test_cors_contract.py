"""Development CORSの**HTTP契約**
(FORGE-PRE-R1-INTEGRITY-GATE-013 §1、2026-08-17)。

---

## 経緯（正確に残す）

013 §1 は「`backend/app/main.py` の `allow_origin_regex` が
raw string内で二重escapeされており、実機Flutter Webからのlocalhost
Originで既にCORS障害を踏んでいる」という指摘だった。

**現HEAD(`02c559c`)では再現しなかった。** 実コードは

    r"^https?://(localhost|127\\.0\\.0\\.1)(:\\d+)?$"

（raw stringなのでバックスラッシュは1つ）であり、
`git log -p -- backend/app/main.py` を全履歴で追っても二重escapeされた
版は一度も存在しない。HTTPレベルで叩いても、期待するOriginは全部通り、
期待しないOriginは全部落ちた。

指摘の前提は成立していなかった、というのが**実測の結論**である。

## それでもこのファイルを置く理由

再現しなかったからといって、この契約が守られている保証は無かった
——**HTTPレベルで確認するテストが1つも無かった**のは事実である。
regexは目で見て正しくても、

* Starlette/FastAPIのCORSMiddlewareが実際にどう解釈するか
* `allow_credentials=True` との組み合わせでheaderがどう返るか
* preflight(OPTIONS)が200を返すか

は別の話であり、そこを測っていなければ「たまたま動いている」と
区別が付かない。次に誰かが`\\\\.`と書いてしまったとき、**このテストが
落ちる**。

`main.py`のregexを二重escapeへ戻すと、このファイルの
`TestAllowedOriginsPass`が落ちることを確認済み。
"""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

os.environ.setdefault("FORGE_FEATURE_WORKSPACE", "true")
os.environ.setdefault("FORGE_FEATURE_FOLDER", "true")
# CORS設定は`app.main`のimport時に確定する（`FORGE_ENV`で分岐）。
os.environ.setdefault("FORGE_ENV", "development")

try:
    from fastapi.testclient import TestClient

    from app.main import app

    _AVAILABLE = True
except ImportError:  # pragma: no cover — 環境依存
    _AVAILABLE = False

_ENDPOINT = "/api/v1/ai/converse"


@unittest.skipUnless(_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class _CorsCase(unittest.TestCase):
    def setUp(self) -> None:
        self.client = TestClient(app)

    def preflight(self, origin: str):
        """実際のブラウザと同じpreflightを送る。

        `Access-Control-Request-Method` を付けないと、Starletteは
        preflightとして扱わない——付け忘れると「通ったように見える」
        テストになる。
        """
        return self.client.options(
            _ENDPOINT,
            headers={
                "Origin": origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )


class TestAllowedOriginsPass(_CorsCase):
    """開発中のFlutter Webは**任意のポート**で立ち上がる。

    `flutter run -d chrome` はポートを毎回変えるので、ポートを
    列挙する方式では動かない。だからregexで受けている。
    """

    _ORIGINS = (
        "http://localhost:56000",
        "http://localhost:12345",
        "http://127.0.0.1:56000",
        "http://127.0.0.1:8001",
        "http://localhost",          # ポート無し
        "https://localhost:443",     # https
        "https://127.0.0.1:8443",
    )

    def test_the_preflight_returns_200(self) -> None:
        for origin in self._ORIGINS:
            with self.subTest(origin=origin):
                self.assertEqual(self.preflight(origin).status_code, 200)

    def test_the_allow_origin_header_echoes_the_origin(self) -> None:
        """`*`ではなく**そのOriginそのもの**が返ること。

        `allow_credentials=True` のとき`*`は仕様上使えないので、
        echoされていなければブラウザは弾く。
        """
        for origin in self._ORIGINS:
            with self.subTest(origin=origin):
                response = self.preflight(origin)
                self.assertEqual(
                    response.headers.get("access-control-allow-origin"), origin,
                    "localhost Originが許可されていない。開発中の"
                    "Flutter Webからbackendを呼べない状態である。",
                )

    def test_an_actual_post_also_carries_the_header(self) -> None:
        """preflightだけ通ってもブラウザは動かない。**本リクエスト**にも
        headerが要る。"""
        response = self.client.post(
            _ENDPOINT,
            json={"message": "テスト", "provider": "mock"},
            headers={"Origin": "http://localhost:56000"},
        )
        self.assertEqual(
            response.headers.get("access-control-allow-origin"),
            "http://localhost:56000",
        )


class TestForeignOriginsAreRejected(_CorsCase):
    """**regexの穴を塞ぐ。**

    `.` をescapeし忘れる・`^$`を書き忘れると、下のOriginが通る。
    通ると、任意のサイトが利用者のブラウザ経由でForgeを呼べる。
    """

    _ORIGINS = (
        "http://evil-localhost.example",   # 前方に付ける
        "https://localhost.evil.example",  # 後方に付ける
        "http://127X0X0X1:56000",          # `.`を任意文字として通す穴
        "http://localhost.example.com",
        "https://example.com",
        "http://192.168.0.1:8000",         # LANの別ホスト
    )

    def test_no_allow_origin_header_is_returned(self) -> None:
        for origin in self._ORIGINS:
            with self.subTest(origin=origin):
                self.assertIsNone(
                    self.preflight(origin).headers.get("access-control-allow-origin"),
                    "外部Originを許可している。",
                )


@unittest.skipUnless(_AVAILABLE, "fastapi/pydanticが無い環境ではスキップする")
class TestHealthIsReachable(unittest.TestCase):
    """CI smokeが叩くendpointが存在すること
    (`.github/workflows/ci.yml` の backend-smoke)。

    smokeが404で緑になっては意味が無いので、ここでも押さえる。
    """

    def test_health_returns_200(self) -> None:
        self.assertEqual(TestClient(app).get("/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
