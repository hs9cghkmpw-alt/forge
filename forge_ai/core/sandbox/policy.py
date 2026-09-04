"""生成物に**何を許すか**を型で持つ（Tier / Permission / 依存 allowlist）。

---

## なぜ Sandbox と同時に要るのか

Sandbox だけ作っても、Tier C（Network / Credential / OS / 決済 / 不可逆操作）が
人の承認なしに動けるなら意味が無い。逆に Permission だけ宣言させても、
実行が隔離されていなければ宣言を破れる。**2 つで 1 つの Gate である。**

## Tier

| Tier | 対象 | Promotion / 実行 |
|---|---|---|
| A | Local で決定論的、低リスク | 自動 |
| B | 制限付き filesystem / 制御された local runtime | Sandbox 通過後に自動 |
| C | Network、Credential、OS 統合、決済、不可逆・高リスク | **Human Gate 必須** |

Tier C は `human_approval` が無い限り Promotion も実行もしない。
**分からない Tier は C 扱い**にする——楽観側へ倒さない。

## 利用者へ見せる言葉

Tier も Permission も Forge の内部語彙である。利用者へは
「このアプリは○○への接続が必要です」のように**やることの言葉**へ直す
（`PermissionManifest.user_facing_sentences()`）。専門用語を丸投げしない。

## 依存 allowlist

生成物が `pub get` / `pip install` / `npm i` / `curl` で外部コードを
引き込むのを禁止する。**Forge が既に保持・検証した依存だけ**を使う。
新しい依存が要るなら、それは別 Capability（License / Digest / Provenance を
通す）であって、生成の副作用として起きてよいことではない。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "CapabilityTier",
    "DependencyPolicyViolation",
    "Permission",
    "PermissionManifest",
    "TierViolation",
    "assert_dependencies_allowed",
    "assert_execution_allowed",
    "assert_promotion_allowed",
    "tier_for_permissions",
]


class CapabilityTier(str, Enum):
    """Capability の危険度。**未知は C。**"""

    A = "A"
    """Local で決定論的、低リスク。"""

    B = "B"
    """制限付き filesystem / 制御された local runtime。"""

    C = "C"
    """Network、Credential、OS 統合、決済、不可逆・高リスク。Human Gate 必須。"""


class Permission(str, Enum):
    """生成 Capability が要求しうる権限。

    **列挙にない権限は宣言できない。** 自由文字列にすると、後から
    「これは permission ではない」という言い訳が効いてしまう。
    """

    LOCAL_COMPUTE = "local.compute"
    LOCAL_STORAGE_READ = "local.storage.read"
    LOCAL_STORAGE_WRITE = "local.storage.write"
    FILESYSTEM_WORKSPACE = "filesystem.workspace"
    FILESYSTEM_USER_FILES = "filesystem.user_files"
    NETWORK_OUTBOUND = "network.outbound"
    CREDENTIALS = "credentials"
    OS_INTEGRATION = "os.integration"
    PROCESS_SPAWN = "process.spawn"
    PAYMENT = "payment"
    IRREVERSIBLE_ACTION = "action.irreversible"


#: Tier C を強制する権限。1 つでも含めば C になる。
_TIER_C_PERMISSIONS = frozenset({
    Permission.NETWORK_OUTBOUND,
    Permission.CREDENTIALS,
    Permission.OS_INTEGRATION,
    Permission.PAYMENT,
    Permission.IRREVERSIBLE_ACTION,
    Permission.PROCESS_SPAWN,
})

#: Tier B へ上げる権限（C でなければ）。
_TIER_B_PERMISSIONS = frozenset({
    Permission.FILESYSTEM_USER_FILES,
    Permission.LOCAL_STORAGE_WRITE,
})

#: 利用者へ見せる言い換え。**内部語彙を出さない。**
_USER_FACING = {
    Permission.LOCAL_COMPUTE: "この端末の中だけで計算します",
    Permission.LOCAL_STORAGE_READ: "この道具が保存したデータを読みます",
    Permission.LOCAL_STORAGE_WRITE: "入力した内容をこの端末へ保存します",
    Permission.FILESYSTEM_WORKSPACE: "この道具専用の置き場だけを使います",
    Permission.FILESYSTEM_USER_FILES: "あなたのファイルを読み書きします",
    Permission.NETWORK_OUTBOUND: "インターネットへ接続します",
    Permission.CREDENTIALS: "ログイン情報を使います",
    Permission.OS_INTEGRATION: "パソコンの機能（通知やファイル関連付けなど）を使います",
    Permission.PROCESS_SPAWN: "ほかのプログラムを起動します",
    Permission.PAYMENT: "支払いに関わる操作をします",
    Permission.IRREVERSIBLE_ACTION: "あとから取り消せない操作をします",
}


class TierViolation(RuntimeError):
    """Tier の要求（主に Human Gate）を満たしていない。"""


class DependencyPolicyViolation(RuntimeError):
    """許可していない依存、または依存の獲得行為を検出した。"""


def tier_for_permissions(permissions: frozenset[Permission]) -> CapabilityTier:
    """宣言された権限から Tier を**計算する**。

    Tier を自己申告させない。申告と権限が食い違ったとき、申告を信じると
    「Tier A だと言い張る Network Capability」が通る。
    """
    if permissions & _TIER_C_PERMISSIONS:
        return CapabilityTier.C
    if permissions & _TIER_B_PERMISSIONS:
        return CapabilityTier.B
    return CapabilityTier.A


@dataclass(frozen=True)
class PermissionManifest:
    """Capability Contract の一部。**権限を宣言しない Capability は作れない。**

    `declared_tier` は自己申告だが、`tier` は権限から計算する。
    2 つが食い違えば `assert_execution_allowed` が拒否する。
    """

    capability_id: str
    permissions: frozenset[Permission] = frozenset()
    declared_tier: CapabilityTier | None = None
    human_approval: bool = False
    """Tier C に必要な人の承認。**既定は False。**"""

    approval_reference: str = ""
    """誰が・いつ承認したかの参照。承認したなら空にしない。"""

    @property
    def tier(self) -> CapabilityTier:
        return tier_for_permissions(self.permissions)

    @property
    def tier_matches_declaration(self) -> bool:
        return self.declared_tier is None or self.declared_tier == self.tier

    def user_facing_sentences(self) -> tuple[str, ...]:
        """利用者へ見せる説明。**Tier も Permission ID も出さない。**"""
        return tuple(
            _USER_FACING[p] for p in Permission if p in self.permissions
        )

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            # 未知の値が混ざっていても**落ちずに**そのまま出す。
            # ここで例外を投げると、Gate が typed な拒否理由を返す前に
            # 死んでしまい、「なぜ拒否したか」が残らない（2026-09-04 実測）。
            "permissions": sorted(
                getattr(p, "value", str(p)) for p in self.permissions
            ),
            "tier": self.tier.value,
            "declared_tier": self.declared_tier.value if self.declared_tier else None,
            "human_approval": self.human_approval,
            "approval_reference": self.approval_reference,
        }


def assert_execution_allowed(manifest: PermissionManifest) -> None:
    """実行してよいか。**Tier C は人の承認が無ければ拒否。**"""
    if not manifest.tier_matches_declaration:
        raise TierViolation(
            f"{manifest.capability_id}: 申告 Tier {manifest.declared_tier} と、"
            f"権限から計算した Tier {manifest.tier.value} が食い違う。"
            "申告ではなく権限を信じる"
        )
    if manifest.tier is CapabilityTier.C and not manifest.human_approval:
        raise TierViolation(
            f"{manifest.capability_id}: Tier C（"
            + "、".join(manifest.user_facing_sentences())
            + "）は人の承認なしに実行しない"
        )


def assert_promotion_allowed(manifest: PermissionManifest) -> None:
    """Promotion してよいか。実行と同じ条件に、承認の出所を足す。"""
    assert_execution_allowed(manifest)
    if manifest.tier is CapabilityTier.C and not manifest.approval_reference.strip():
        raise TierViolation(
            f"{manifest.capability_id}: Tier C の承認に出所が無い"
            "（誰がいつ承認したかを残さない承認は、後から検証できない）"
        )


#: 依存を**その場で取りに行く**行為。生成物の中に現れてはならない。
_ACQUISITION_PATTERNS = (
    re.compile(r"\bpub\s+(get|add|upgrade)\b"),
    re.compile(r"\bpip\s+install\b"),
    re.compile(r"\bpip3\s+install\b"),
    re.compile(r"\bnpm\s+(i|install|add)\b"),
    re.compile(r"\byarn\s+add\b"),
    re.compile(r"\bpnpm\s+(i|install|add)\b"),
    re.compile(r"\bgo\s+get\b"),
    re.compile(r"\bcargo\s+(add|install)\b"),
    re.compile(r"\bapt(-get)?\s+install\b"),
    re.compile(r"\bcurl\b[^\n]*\bhttps?://"),
    re.compile(r"\bwget\b[^\n]*\bhttps?://"),
    re.compile(r"\bgit\s+clone\b"),
)


def assert_dependencies_allowed(
    *,
    requested: frozenset[str],
    allowlist: frozenset[str],
    sources: tuple[str, ...] = (),
) -> None:
    """依存が allowlist の中に収まっているか、獲得行為が無いか。

    `requested` — 生成物が宣言した依存
    `allowlist` — Forge が既に保持・検証した依存
    `sources`   — 生成された Source / Script の本文（獲得行為の走査対象）

    **allowlist に無いものは拒否する。** 「たぶん安全な有名 package」も
    拒否する——安全かどうかを Forge が確かめていないのだから。
    """
    unknown = sorted(requested - allowlist)
    if unknown:
        raise DependencyPolicyViolation(
            "Forge が検証していない依存を要求している: "
            f"{unknown}。新しい依存の獲得は別 Capability であり、"
            "License / Digest / Provenance を通す"
        )
    for source in sources:
        # argv の list 形（`["pip", "install", ...]`）も同じ行為である。
        # 引用符とカンマを空白へ潰してから見る——**書き方を変えれば
        # 通る検出器は検出器ではない**（2026-09-04 の試験で `pip install`
        # の list 形を取りこぼした）。
        normalized = re.sub(r"""['"`,\[\]()]+""", " ", source)
        for pattern in _ACQUISITION_PATTERNS:
            found = pattern.search(source) or pattern.search(normalized)
            if found:
                raise DependencyPolicyViolation(
                    f"生成物が依存をその場で取得しようとしている: {found.group(0)!r}。"
                    "外部コードの取り込みは、生成の副作用として起きてよいことではない"
                )
