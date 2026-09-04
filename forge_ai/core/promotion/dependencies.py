"""生成 Capability の依存 allowlist（SEC-06）。

## 何を allowlist するのか

**Forge 本体の依存表ではない。** 生成された Capability が依存してよいものの
全部である。Forge 本体は `dio` や `shared_preferences` に依存しているが、
それは生成物が使ってよいという意味ではない。

## 宣言ではなく観測を突き合わせる

「依存を宣言してください」だけにすると、宣言しなければ通ってしまう。
したがって突き合わせる相手は **静的検査が実際に見つけた import** である
（`effects.SourceInspectionResult.imports`）。

## UNKNOWN を安全扱いしない

脆弱性 DB へネットワーク接続していないので `security_status` は
基本 `UNKNOWN` である。これを「たぶん大丈夫」にしない。
**UNKNOWN を許すかどうかを Policy として明示的に分ける。**
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

_ALLOWLIST_PATH = (
    Path(__file__).resolve().parent.parent.parent
    / "data"
    / "generated_capability_dependencies.json"
)


class SecurityStatus(str, Enum):
    IN_REPO_REVIEWED = "IN_REPO_REVIEWED"
    UNKNOWN = "UNKNOWN"


class UnknownSecurityPolicy(str, Enum):
    """`security_status = UNKNOWN` をどう扱うか。**既定は拒否側。**"""

    REJECT = "reject"
    ALLOW_IF_BUNDLED = "allow_if_bundled"
    """既に同梱済みで、生成物のための**新規取得が発生しない**ものだけ許す。"""


#: 「新規取得が発生しない」と言える source。ここに無い source は取得を伴う。
_BUNDLED_SOURCES = frozenset(
    {"dart-sdk", "flutter-sdk", "python-stdlib", "this-repository"}
)


@dataclass(frozen=True, slots=True)
class DependencyRecord:
    ecosystem: str
    name: str
    version: str
    source: str
    provenance: str
    license: str
    identity: str
    security_status: SecurityStatus
    security_evaluated_at: str | None
    allowed_reason: str

    @property
    def bundled(self) -> bool:
        return self.source in _BUNDLED_SOURCES

    def to_dict(self) -> dict:
        return {
            "ecosystem": self.ecosystem,
            "name": self.name,
            "version": self.version,
            "source": self.source,
            "provenance": self.provenance,
            "license": self.license,
            "identity": self.identity,
            "security_status": self.security_status.value,
            "security_evaluated_at": self.security_evaluated_at,
            "allowed_reason": self.allowed_reason,
        }


@dataclass(frozen=True, slots=True)
class DependencyVerdict:
    """`observed` を allowlist へ突き合わせた結果。"""

    allowed: tuple[DependencyRecord, ...]
    unknown: tuple[str, ...]
    """allowlist に無い。**これがあれば Promotion 不可。**"""

    rejected_for_unknown_security: tuple[str, ...]
    """allowlist にはあるが security_status が Policy を満たさない。"""

    @property
    def ok(self) -> bool:
        return not self.unknown and not self.rejected_for_unknown_security

    def to_dict(self) -> dict:
        return {
            "allowed": [record.name for record in self.allowed],
            "unknown": list(self.unknown),
            "rejected_for_unknown_security": list(self.rejected_for_unknown_security),
            "identities": {r.name: r.identity for r in self.allowed},
        }


class DependencyAllowlist:
    def __init__(self, records: tuple[DependencyRecord, ...]) -> None:
        self._by_name = {record.name: record for record in records}

    @classmethod
    def load(cls, path: Path | None = None) -> "DependencyAllowlist":
        raw = json.loads((path or _ALLOWLIST_PATH).read_text(encoding="utf-8"))
        records = tuple(
            DependencyRecord(
                ecosystem=item["ecosystem"],
                name=item["name"],
                version=item["version"],
                source=item["source"],
                provenance=item["provenance"],
                license=item["license"],
                identity=item["identity"],
                security_status=SecurityStatus(item["security_status"]),
                security_evaluated_at=item["security_evaluated_at"],
                allowed_reason=item["allowed_reason"],
            )
            for item in raw["dependencies"]
        )
        return cls(records)

    @property
    def names(self) -> frozenset[str]:
        return frozenset(self._by_name)

    def evaluate(
        self,
        observed: frozenset[str],
        *,
        unknown_security_policy: UnknownSecurityPolicy = (
            UnknownSecurityPolicy.ALLOW_IF_BUNDLED
        ),
    ) -> DependencyVerdict:
        allowed: list[DependencyRecord] = []
        unknown: list[str] = []
        rejected: list[str] = []

        for name in sorted(observed):
            if name == ".":
                # artifact 内の相対 import。build_time_sandbox が別途境界を見る。
                continue
            record = self._by_name.get(name)
            if record is None:
                unknown.append(name)
                continue
            if record.security_status is SecurityStatus.UNKNOWN:
                if unknown_security_policy is UnknownSecurityPolicy.REJECT:
                    rejected.append(name)
                    continue
                if not record.bundled:
                    # 同梱でない UNKNOWN は、取得を伴ううえに素性も不明である。
                    rejected.append(name)
                    continue
            allowed.append(record)

        return DependencyVerdict(
            allowed=tuple(allowed),
            unknown=tuple(unknown),
            rejected_for_unknown_security=tuple(rejected),
        )
