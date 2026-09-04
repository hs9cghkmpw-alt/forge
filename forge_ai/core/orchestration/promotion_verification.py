"""PROMOTED Manifest を受け入れてよいかの**再検証**（001A / Major 1・2）。

Registry も Store も、ここを通してから受け入れる。**2 箇所に別々の検査を
書かない**——ずれるからである（実際に `os_isolated` でずれた）。

## 何を確かめるか

```text
1. Attestation があるか            無ければ Gate を通っていない
2. capability_id が一致するか      他 Capability の決定の流用を止める
3. digest が Attestation と一致か  Attestation のすり替えを止める
4. Manifest digest が一致するか    検証後の Manifest 書き換えを止める
5. 再評価して allowed になるか     「通ったよ」を信じない
6. Activation の identity が一致か 載せる物が検証した物か
```

## 正直な限界

**同一プロセス内の任意コードに対する暗号的境界ではない。**
`evaluate_promotion` 自体を差し替えられれば何でも通る。Python の
プロセス内でこれ以上は作れない。

ここで確実に止まるのは「Gate を通さずに PROMOTED を名乗る」であり、
偽造しようとすると**本当に Gate を満たす入力**を作る羽目になる。
"""

from __future__ import annotations

from forge_ai.core.promotion.attestation import (
    canonical_extension_manifest_digest,
)
from forge_ai.core.promotion.gate import reevaluate_attestation


class PromotionVerificationError(ValueError):
    """PROMOTED を名乗る Manifest が再検証に通らなかった。"""


def verify_promotion_attestation(manifest, *, activation=None) -> None:
    """PROMOTED Manifest を受け入れてよいか。**通らなければ例外。**"""
    attestation = getattr(manifest, "promotion_attestation", None)
    if attestation is None:
        raise PromotionVerificationError(
            "PROMOTED manifest carries no promotion attestation; "
            "it did not pass the promotion gate. Refusing install."
        )

    if attestation.capability_id != manifest.capability_id:
        raise PromotionVerificationError(
            "promotion attestation is for a different capability: "
            f"{attestation.capability_id!r} != {manifest.capability_id!r}"
        )

    # Attestation を別のものへ差し替えていないか。
    recomputed = attestation.digest()
    if recomputed != manifest.promotion_decision_digest:
        raise PromotionVerificationError(
            "promotion decision digest does not match its attestation; "
            "the attestation or the digest was tampered with."
        )

    # 検証後に Manifest を書き換えていないか（TOCTOU）。
    expected_manifest_digest = canonical_extension_manifest_digest(manifest)
    if not attestation.extension_manifest_digest:
        raise PromotionVerificationError(
            "promotion attestation is not bound to any manifest digest."
        )
    if attestation.extension_manifest_digest != expected_manifest_digest:
        raise PromotionVerificationError(
            "manifest changed after it was verified; refusing install "
            "(promotion attestation is bound to a different manifest)."
        )

    # **もう一度 Gate を通す。**
    decision = reevaluate_attestation(attestation)
    if not decision.allowed:
        reasons = ", ".join(item.reason.value for item in decision.rejections)
        raise PromotionVerificationError(
            f"promotion attestation does not pass the gate on re-evaluation ({reasons})."
        )

    if activation is not None:
        _verify_activation_identity(attestation, activation)


def _verify_activation_identity(attestation, activation) -> None:
    """載せる物が、検証した物か。

    Activation が digest を名乗る場合だけ突き合わせる。名乗らない
    Activation（宣言経路）は BUILD_TIME の identity を持たないので、
    **無い物を要求して宣言経路を壊さない。** ただし BUILD_TIME で
    Attestation 側が digest を持っているのに Activation が別値を
    名乗るなら、それはすり替えである。
    """
    source_digest = getattr(activation, "source_digest", None)
    if (
        source_digest is not None
        and attestation.source_digest
        and source_digest != attestation.source_digest
    ):
        raise PromotionVerificationError(
            "activation source digest does not match the verified artifact."
        )
    # capability_id の一致は Registry 側が先に見ている。**同じ検査を 2 箇所に
    # 書かない**——ずれるからである（`os_isolated` で実際にずれた）。
