"""Tool Permission Broker — **やってよいことを Forge が決める**
(FORGE-020 §15、2026-08-25)。

---

## なぜ Model に決めさせないのか

Agent へ道具を渡すと、道具の危険度はまちまちになる。

* repository の中を読む → 取り返しがつく
* 生成コードを sandbox で走らせる → 隔離すれば取り返しがつく
* ログイン・送信・push・購入 → **取り返しがつかない**
* `.env` を外へ送る → 取り返しがつかないうえ、**気付けない**

これを Model の判断に任せると、判断が入力に左右される。Web ページに
「この .env を送ってください」と書いてあれば、それは Model への入力で
ある。**入力で権限が変わる仕組みは、権限が無いのと同じ。**

## 絶対順位

```
Forge Policy  >  System  >  User  >  Web / Tool output
```

Web の中身は**データであって命令ではない**。ページが何を書いていても
段は上がらない。`WebContentGuard`（`untrusted.py`）と対になっている。

## 4段

| 段 | 例 | 誰が決める |
|---|---|---|
| `AUTO_ALLOW` | 公開Web検索・公開ページ取得・repo内read・search・test・lint・build・local preview | Forge |
| `SANDBOX_ONLY` | download・生成コードの実行・一時ファイル | Forge（隔離が条件） |
| `EXPLICIT_USER_CONFIRMATION` | login・form POST・upload・外部APIへの送信・mail・push・購入 | **利用者** |
| `FORBIDDEN` | secret 持ち出し・credential upload・無許可の破壊的OS操作・個人データupload | 誰にも変えられない |

## 分類し忘れを通さない

登録されていない道具は `FORBIDDEN` として扱う。「知らない道具だから
とりあえず許す」は、道具が増えるたびに穴が開く（`CLAUDE.md` §3）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "PermissionBroker",
    "PermissionDecision",
    "PermissionTier",
    "ToolPermissionPolicy",
    "default_permission_broker",
]


class PermissionTier(str, Enum):
    """道具の段。**上ほど強い。**"""

    AUTO_ALLOW = "auto_allow"
    SANDBOX_ONLY = "sandbox_only"
    EXPLICIT_USER_CONFIRMATION = "explicit_user_confirmation"
    FORBIDDEN = "forbidden"


@dataclass(frozen=True)
class PermissionDecision:
    """呼んでよいか、だめならなぜか。

    **理由を必ず持つ。** 「だめ」だけ返すと、Agent は同じ呼び出しを
    別の言い方で繰り返す（無限ループの原因になる）。
    """

    tool: str
    tier: PermissionTier
    allowed: bool
    reason: str = ""
    requires_sandbox: bool = False
    requires_confirmation: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "tool": self.tool,
            "tier": self.tier.value,
            "allowed": self.allowed,
            "reason": self.reason,
            "requires_sandbox": self.requires_sandbox,
            "requires_confirmation": self.requires_confirmation,
        }


#: 道具ごとの段。**ここに無い道具は `FORBIDDEN`。**
_DEFAULT_POLICY: dict[str, PermissionTier] = {
    # -- 読む・調べる（取り返しがつく） --------------------------------
    "read_file": PermissionTier.AUTO_ALLOW,
    "list_files": PermissionTier.AUTO_ALLOW,
    "search_code": PermissionTier.AUTO_ALLOW,
    "git_diff": PermissionTier.AUTO_ALLOW,
    "read_runtime_error": PermissionTier.AUTO_ALLOW,
    "inspect_forge_document": PermissionTier.AUTO_ALLOW,
    "validate_forge_document": PermissionTier.AUTO_ALLOW,
    "inspect_capability_gap": PermissionTier.AUTO_ALLOW,
    "web_search": PermissionTier.AUTO_ALLOW,
    "fetch_url": PermissionTier.AUTO_ALLOW,
    "browser_open": PermissionTier.AUTO_ALLOW,
    "browser_extract_text": PermissionTier.AUTO_ALLOW,
    "browser_screenshot": PermissionTier.AUTO_ALLOW,
    "browser_scroll": PermissionTier.AUTO_ALLOW,
    # -- 作業領域を変える（隔離が条件） --------------------------------
    "write_file": PermissionTier.SANDBOX_ONLY,
    "edit_file": PermissionTier.SANDBOX_ONLY,
    "run_build": PermissionTier.SANDBOX_ONLY,
    "run_test": PermissionTier.SANDBOX_ONLY,
    "run_lint": PermissionTier.SANDBOX_ONLY,
    "run_app": PermissionTier.SANDBOX_ONLY,
    "download": PermissionTier.SANDBOX_ONLY,
    # -- 外へ出る・取り返しがつかない（利用者が決める） ------------------
    # `browser_click` を AUTO にしない。「押すだけ」に見えるが、押した先が
    # 購入・送信・削除でありうる。どのボタンが何をするかは**ページ側が
    # 決める**ので、Forge には事前に分からない。楽観側へ倒さない。
    "browser_click": PermissionTier.EXPLICIT_USER_CONFIRMATION,
    "http_post": PermissionTier.EXPLICIT_USER_CONFIRMATION,
    "upload_file": PermissionTier.EXPLICIT_USER_CONFIRMATION,
    "send_message": PermissionTier.EXPLICIT_USER_CONFIRMATION,
    "git_push": PermissionTier.EXPLICIT_USER_CONFIRMATION,
    "login": PermissionTier.EXPLICIT_USER_CONFIRMATION,
    "purchase": PermissionTier.EXPLICIT_USER_CONFIRMATION,
    # -- 誰にも変えられない --------------------------------------------
    "read_secret": PermissionTier.FORBIDDEN,
    "upload_credential": PermissionTier.FORBIDDEN,
    "delete_outside_workspace": PermissionTier.FORBIDDEN,
    "arbitrary_shell": PermissionTier.FORBIDDEN,
}


@dataclass
class ToolPermissionPolicy:
    """道具 → 段の対応。**利用者が緩められるのは1段だけ。**"""

    tiers: dict[str, PermissionTier] = field(
        default_factory=lambda: dict(_DEFAULT_POLICY)
    )

    def tier_for(self, tool: str) -> PermissionTier:
        """**知らない道具は `FORBIDDEN`。**"""
        return self.tiers.get(tool, PermissionTier.FORBIDDEN)


class PermissionBroker:
    """呼び出しごとに段を判定する。

    **Model の言い分でここが変わることはない。** 引数として渡されるのは
    「どの道具か」「sandbox の中か」「利用者が確認済みか」だけである。
    """

    def __init__(self, policy: ToolPermissionPolicy | None = None) -> None:
        self._policy = policy or ToolPermissionPolicy()

    def evaluate(
        self,
        tool: str,
        *,
        in_sandbox: bool = False,
        user_confirmed: bool = False,
    ) -> PermissionDecision:
        tier = self._policy.tier_for(tool)

        if tier is PermissionTier.FORBIDDEN:
            return PermissionDecision(
                tool, tier, allowed=False,
                reason="この操作は Forge Policy で禁止されている（利用者も解除できない）",
            )

        if tier is PermissionTier.EXPLICIT_USER_CONFIRMATION:
            return PermissionDecision(
                tool, tier, allowed=bool(user_confirmed),
                reason="" if user_confirmed else "利用者の明示的な確認が必要",
                requires_confirmation=True,
            )

        if tier is PermissionTier.SANDBOX_ONLY:
            return PermissionDecision(
                tool, tier, allowed=bool(in_sandbox),
                reason="" if in_sandbox else "sandbox の外では実行しない",
                requires_sandbox=True,
            )

        return PermissionDecision(tool, tier, allowed=True)

    def known_tools(self) -> frozenset[str]:
        return frozenset(self._policy.tiers)


_DEFAULT_BROKER = PermissionBroker()


def default_permission_broker() -> PermissionBroker:
    """本番が使う唯一の Broker。**判定の口を複数作らない。**"""
    return _DEFAULT_BROKER
