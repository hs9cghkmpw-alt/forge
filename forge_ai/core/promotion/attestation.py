"""Promotion Attestation — **Gate を通った入力一式**（001A / Major 1・2）。

## なぜ digest を信用しないのか

独立レビューの指摘は正しい。以前の実装は

    if not manifest.promotion_decision_digest:
        raise ValueError(...)

としか見ていなかった。したがって

    replace(manifest, status=PROMOTED, promotion_decision_digest="fake")

で Registry を通せた（2026-09-04 に実際に再現した）。

**「`promoted()` だけが digest を埋める」というコメントは、Python の
dataclass / `replace` に対する Security Boundary にならない。**

## 採った方法——digest ではなく入力を持ち、受け取る側が再評価する

Attestation は「通った」という**結論**ではなく、Gate が判定に使った
**入力一式**を持つ。Registry と Store は、渡された入力で
`evaluate_promotion` を**もう一度走らせて**から受け入れる。

```text
以前: 「通ったよ」という印を信じる
いま: 「通ったと言うなら、その入力でもう一度やってみせろ」
```

偽造するには「本当に Gate を満たす入力一式」を作るしかない。それは
偽造ではなく**実際に条件を満たすこと**である。

## 正直な限界

**同一プロセス内の任意コードに対する暗号的境界にはならない。**
`evaluate_promotion` 自体を差し替えられればどうにでもなる。Python の
プロセス内でこれ以上の保証は作れない。

ここで防げるのは「Gate を通さずに PROMOTED を名乗る」——つまり
**うっかりと、安直な迂回**である。それが現実の失敗のほぼ全部だった。

## Manifest への束縛（Major 2）

Attestation は `extension_manifest_digest` を持つ。これは
**status と promotion 関連 field を除いた** ExtensionManifest の正準 digest
である（除かないと verified → promoted で値が変わって照合できない）。

install 時に現在の Manifest から digest を計算し直して突き合わせるので、
**検証後に Manifest を書き換えると拒否される。**
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace
from hashlib import sha256
from typing import TYPE_CHECKING, Any, Mapping

if TYPE_CHECKING:  # pragma: no cover - typing only
    from forge_ai.core.orchestration.extension_manifest import ExtensionManifest


def _canonical(payload: Mapping[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def canonical_extension_manifest_digest(manifest: "ExtensionManifest") -> str:
    """ExtensionManifest の正準 digest。

    **status / promotion_attestation / promotion_decision_digest は含めない。**
    これらは昇格そのもので変わるため、含めると verified と promoted で
    値が変わって照合できなくなる。

    逆に言えば、**それ以外のすべて**——route / evidence / 確認要否 /
    capability_id / label / 由来——を束縛する。verify 後にどれかを
    書き換えれば digest が変わり、install が落ちる。
    """
    evidence = manifest.evidence
    return sha256(
        _canonical(
            {
                "capability_id": manifest.capability_id,
                "label_ja": manifest.label_ja,
                "route": manifest.route.value,
                "requires_confirmation": manifest.requires_confirmation,
                "source_reason": manifest.source_reason,
                "evidence": {
                    name: getattr(evidence, name)
                    for name in sorted(evidence.__dataclass_fields__)
                },
            }
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class PromotionAttestation:
    """Gate が判定に使った入力一式。**結論ではなく入力である。**"""

    capability_id: str
    requires_generated_source: bool

    # Permission Manifest（承認と出所を含む。1 文字変えれば digest が変わる）
    permissions: tuple[str, ...]
    declared_tier: str | None
    human_approval: bool
    approval_reference: str

    # Effect
    declared_effects: tuple[str, ...]
    observed_effects: tuple[str, ...]
    observed_imports: tuple[str, ...]
    internal_imports: tuple[str, ...]
    files_inspected: int

    # Sandbox
    sandbox_backend: str
    sandbox_policy_version: str
    sandbox_policy_digest: str

    # 実行 Evidence
    tests_pass: bool
    build_pass: bool
    runtime_probe_pass: bool

    # Identity
    source_digest: str
    artifact_digest: str
    permission_manifest_digest: str
    extension_manifest_digest: str = ""

    # Policy
    unknown_security_policy: str = "reject"
    command_sources: tuple[str, ...] = ()

    def bound_to_manifest(self, digest: str) -> "PromotionAttestation":
        """昇格する Manifest へ束縛する。**空 digest では束縛しない。**"""
        if not digest:
            raise ValueError("cannot bind an attestation to an empty manifest digest")
        return replace(self, extension_manifest_digest=digest)

    def to_dict(self) -> dict:
        return {
            "capability_id": self.capability_id,
            "requires_generated_source": self.requires_generated_source,
            "permissions": list(self.permissions),
            "declared_tier": self.declared_tier,
            "human_approval": self.human_approval,
            "approval_reference": self.approval_reference,
            "declared_effects": list(self.declared_effects),
            "observed_effects": list(self.observed_effects),
            "observed_imports": list(self.observed_imports),
            "internal_imports": list(self.internal_imports),
            "files_inspected": self.files_inspected,
            "sandbox_backend": self.sandbox_backend,
            "sandbox_policy_version": self.sandbox_policy_version,
            "sandbox_policy_digest": self.sandbox_policy_digest,
            "tests_pass": self.tests_pass,
            "build_pass": self.build_pass,
            "runtime_probe_pass": self.runtime_probe_pass,
            "source_digest": self.source_digest,
            "artifact_digest": self.artifact_digest,
            "permission_manifest_digest": self.permission_manifest_digest,
            "extension_manifest_digest": self.extension_manifest_digest,
            "unknown_security_policy": self.unknown_security_policy,
            "command_sources": list(self.command_sources),
        }

    @classmethod
    def from_dict(cls, raw: Mapping[str, Any]) -> "PromotionAttestation":
        return cls(
            capability_id=str(raw["capability_id"]),
            requires_generated_source=bool(raw["requires_generated_source"]),
            permissions=tuple(str(x) for x in raw["permissions"]),
            declared_tier=(
                str(raw["declared_tier"]) if raw.get("declared_tier") else None
            ),
            human_approval=bool(raw["human_approval"]),
            approval_reference=str(raw["approval_reference"]),
            declared_effects=tuple(str(x) for x in raw["declared_effects"]),
            observed_effects=tuple(str(x) for x in raw["observed_effects"]),
            observed_imports=tuple(str(x) for x in raw["observed_imports"]),
            internal_imports=tuple(str(x) for x in raw.get("internal_imports", ())),
            files_inspected=int(raw["files_inspected"]),
            sandbox_backend=str(raw["sandbox_backend"]),
            sandbox_policy_version=str(raw["sandbox_policy_version"]),
            sandbox_policy_digest=str(raw["sandbox_policy_digest"]),
            tests_pass=bool(raw["tests_pass"]),
            build_pass=bool(raw["build_pass"]),
            runtime_probe_pass=bool(raw["runtime_probe_pass"]),
            source_digest=str(raw["source_digest"]),
            artifact_digest=str(raw["artifact_digest"]),
            permission_manifest_digest=str(raw["permission_manifest_digest"]),
            extension_manifest_digest=str(raw.get("extension_manifest_digest", "")),
            unknown_security_policy=str(raw.get("unknown_security_policy", "reject")),
            command_sources=tuple(str(x) for x in raw.get("command_sources", ())),
        )

    def digest(self) -> str:
        """Attestation 全体の指紋。**1 field でも変われば変わる。**"""
        return sha256(_canonical(self.to_dict()).encode("utf-8")).hexdigest()


def canonical_permission_manifest_digest(manifest: Any) -> str:
    """Permission Manifest の正準 digest。

    権限・申告 Tier・承認・**承認の出所**を含む。承認出所を後から書き換えると
    digest が変わるので、install で落ちる。
    """
    if manifest is None:
        return ""
    return sha256(_canonical(manifest.to_dict()).encode("utf-8")).hexdigest()
