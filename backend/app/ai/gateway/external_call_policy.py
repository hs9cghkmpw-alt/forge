"""実 Provider へ出ていく通信を **既定で拒否する**（Default Deny）。

---

## なぜ要るのか — 2026-09-02 に実際に起きた事故

Visual Evidence を撮るために作業ホストで backend を起動したところ、その
コンテナの `backend/.env` に**実 API キーが入っていた**。`/converse` を
2 回叩いた時点で、実 Gemini API が呼ばれた。誰も「実 API を呼ぶ」とは
指示していない。**キーがそこにあったから呼ばれた。**

これは運用の不注意である前に、**Architecture の穴**である。

> API キーの存在それ自体を「呼んでよい」という同意として扱っていた。

キーの存在は設定であって、同意ではない。

## 何を禁止するか

| 経路 | 既定 |
|---|---|
| Cloud Provider（外部へ入力が出る・Quota を消費する） | **拒否** |
| Local Provider（このマシン、Quota も外部送信も無い） | 通常は許可。**テスト中は拒否** |

Cloud を開けるには `FORGE_ALLOW_REAL_PROVIDER_CALLS=1` を明示する。
テスト中に実 Provider を呼ぶ Real Provider Test は、さらに
`FORGE_REAL_PROVIDER_TEST=1` を要求する。**キーの有無は判定に使わない。**

## Fail Closed

値が `1` / `true` / `yes` / `on` 以外なら**拒否**する。`FORGE_ALLOW_REAL_
PROVIDER_CALLS=ture`（typo）を「たぶん true だろう」と解釈しない。
分からないものを楽観側へ倒さない（CLAUDE.md §3）。

## Mock Transport は「呼んでいない」

`httpx.MockTransport` を差し込むテストは、ネットワークへ出ていない。
その場合は `allow_mocked_transport()` で明示的に囲む。**環境変数ではなく
呼び出し側の明示**にしてあるのは、`.env` の中身で挙動が変わる経路を
もう一度作らないためである。
"""

from __future__ import annotations

import contextlib
import contextvars
import os
from collections.abc import Iterator

#: Cloud Provider への実通信を許す環境変数。**キーの有無とは無関係**。
ALLOW_REAL_PROVIDER_CALLS_ENV = "FORGE_ALLOW_REAL_PROVIDER_CALLS"

#: テスト中に実 Provider を呼ぶ Real Provider Test だけが立てる環境変数。
REAL_PROVIDER_TEST_ENV = "FORGE_REAL_PROVIDER_TEST"

#: 「真」と認める値。これ以外は**すべて拒否**（fail closed）。
_TRUTHY = frozenset({"1", "true", "yes", "on"})

#: `httpx.MockTransport` 等でネットワークへ出ないことが明らかな区間。
_mocked_transport: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "forge_mocked_transport", default=False,
)


class ExternalCallDenied(RuntimeError):
    """実 Provider への通信が Policy により拒否された。

    **これは失敗ではなく設計どおりの拒否である。** 呼び出し側は握り潰さず、
    そのまま Provider 失敗として扱ってよい（利用者へは Provider 非依存の
    文言が出る）。
    """

    def __init__(self, *, provider_id: str, deployment: str, reason: str) -> None:
        self.provider_id = provider_id
        self.deployment = deployment
        self.reason = reason
        super().__init__(
            f"実 Provider への通信を Policy が拒否しました "
            f"(provider={provider_id}, deployment={deployment}): {reason}"
        )


def _flag(name: str) -> bool:
    """環境変数を fail closed に解釈する。"""
    return os.environ.get(name, "").strip().lower() in _TRUTHY


def running_under_test() -> bool:
    """pytest が動かしているか。

    `PYTEST_CURRENT_TEST` は pytest がテストごとに立てる。unittest 単体
    実行や CI の他 step では立たないため、**これだけを根拠にしない**
    （下の判定では「テスト中はさらに厳しくする」方向にだけ使う）。
    """
    return "PYTEST_CURRENT_TEST" in os.environ


@contextlib.contextmanager
def allow_mocked_transport() -> Iterator[None]:
    """この区間の通信は `httpx.MockTransport` 等で外へ出ない、と宣言する。

    **本番コードから呼んではならない。** テストと、Transport を自分で
    差し込む検証用スクリプトのためにある。
    """
    token = _mocked_transport.set(True)
    try:
        yield
    finally:
        _mocked_transport.reset(token)


def external_provider_calls_allowed() -> bool:
    """Cloud Provider への実通信が許可されているか。"""
    if not _flag(ALLOW_REAL_PROVIDER_CALLS_ENV):
        return False
    if running_under_test() and not _flag(REAL_PROVIDER_TEST_ENV):
        return False
    return True


def local_provider_calls_allowed() -> bool:
    """Local Provider（このマシン）への実通信が許可されているか。

    通常運用では許可する——Local-first は製品の中核であり、ここを環境変数
    必須にすると「利用者に環境変数を触らせる」ことになる（Universal
    Quality §9）。**テスト中だけ**拒否して、決定的でない実行を防ぐ。
    """
    if running_under_test():
        return _flag(REAL_PROVIDER_TEST_ENV)
    return True


def assert_external_call_allowed(*, provider_id: str, deployment: str) -> None:
    """実通信の直前に呼ぶ。拒否なら `ExternalCallDenied` を送出する。

    `deployment` は `"cloud"` / `"local"`（`provider_registry.Deployment` の
    値）。未知の値は **cloud 扱い**にする——分からないものを楽観側へ倒さない。
    """
    if _mocked_transport.get():
        return

    normalized = (deployment or "").strip().lower()
    if normalized == "local":
        if local_provider_calls_allowed():
            return
        raise ExternalCallDenied(
            provider_id=provider_id,
            deployment="local",
            reason=(
                f"テスト実行中は Local Provider へも接続しません。"
                f"Real Provider Test なら {REAL_PROVIDER_TEST_ENV}=1 を明示してください。"
            ),
        )

    if external_provider_calls_allowed():
        return
    raise ExternalCallDenied(
        provider_id=provider_id,
        deployment=normalized or "unknown",
        reason=(
            f"既定では外部 Provider を呼びません。API キーが設定されていることは"
            f"同意ではありません。呼ぶ場合は {ALLOW_REAL_PROVIDER_CALLS_ENV}=1 を"
            f"明示してください"
            + (
                f"（テスト中はさらに {REAL_PROVIDER_TEST_ENV}=1 も必要です）"
                if running_under_test()
                else ""
            )
            + "。"
        ),
    )


def describe_policy() -> dict[str, object]:
    """診断・Evidence 用。**環境変数の値は含めない**（真偽値だけ）。"""
    return {
        "external_provider_calls_allowed": external_provider_calls_allowed(),
        "local_provider_calls_allowed": local_provider_calls_allowed(),
        "running_under_test": running_under_test(),
        "allow_env_name": ALLOW_REAL_PROVIDER_CALLS_ENV,
        "real_provider_test_env_name": REAL_PROVIDER_TEST_ENV,
    }
