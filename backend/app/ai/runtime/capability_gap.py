"""**作れないと分かっていることを、利用者へ伝える**（TD90 / 020A2 §5）。

---

## 何が起きていたか

`CapabilityPlan` は R4 の時点で、

```
「植物を育てながら音を組み合わせるゲームを作りたい」
  missing: simulate.loop, effect.media_compose
```

を**正しく名指しできていた**。Forge は作れないと知っていた。

それなのに実際に返っていたのは、**植物と音を記録する CRUD** である。
「ゲームループと音の合成は作れません」とはどこにも出ない。会話にも
画面にも出ない。

**Forge は知っていて黙っていた。**

`GENERATIVE-SOFTWARE-DIRECTION.md` が禁じている
「作れないものを、作れる形に見せる」そのものである。

## どう伝えるか

wizard にしない。**会話の中で普通に言う。**

> ゲームループと音の合成は、いまの Forge ではまだ作れません。
> 植物と音を記録するところまでなら作れます。

## 本質が欠けているなら「完成」にしない

新しい状態 enum は増やさない。既存の `release_ready` を使う——
「これは仕上がっている」という意味の欄が既にあり、
**求められたことの本質が出来ていないなら仕上がっていない。**

### 「本質」の判定

層で決める。推測しない。

| 欠けた層 | 扱い |
|---|---|
| `SIMULATE` / `EFFECT` | **critical。** 道具が何をするものかが変わる |
| `VIEW` / `INTERACT` | critical ではない。見え方が落ちるが道具は使える |

「地図で見られない」は釣果記録を壊さない（一覧で足りる）。
「ゲームループが無い」はゲームを壊す——**それはもうゲームではない。**
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.semantics.capabilities import (
    SEMANTIC_CAPABILITIES,
    CapabilityLayer,
)

__all__ = ["CapabilityGap", "gap_from_plan"]

#: **道具が何をするものかを変えてしまう層。**
_CRITICAL_LAYERS = frozenset({CapabilityLayer.SIMULATE, CapabilityLayer.EFFECT})


@dataclass(frozen=True)
class CapabilityGap:
    """求められたが出せなかったもの。**利用者へ見せる形。**"""

    missing: tuple[str, ...] = ()
    partial: tuple[str, ...] = ()
    critical: tuple[str, ...] = ()
    """欠けると**道具の目的が成立しない**もの。"""

    message: str = ""
    """そのまま会話へ流せる日本語。**内部 ID を出さない。**"""

    @property
    def blocks_completion(self) -> bool:
        """**「完成」と言ってよいか。**

        `critical` が空でなければ、求められたことの本質が出来ていない。
        """
        return bool(self.critical)

    @property
    def is_empty(self) -> bool:
        return not (self.missing or self.partial)

    def to_dict(self) -> dict[str, object]:
        return {
            "missing": list(self.missing),
            "partial": list(self.partial),
            "critical": list(self.critical),
            "blocks_completion": self.blocks_completion,
            "message": self.message,
        }


def _label(capability_id: str) -> str:
    definition = SEMANTIC_CAPABILITIES.get(capability_id)
    return definition.label_ja if definition else capability_id


def _limitation(capability_id: str) -> str:
    definition = SEMANTIC_CAPABILITIES.get(capability_id)
    return definition.limitation if definition else ""


def _is_critical(capability_id: str) -> bool:
    definition = SEMANTIC_CAPABILITIES.get(capability_id)
    return definition is not None and definition.layer in _CRITICAL_LAYERS


def _buildable_summary(plan) -> str:  # noqa: ANN001
    """**出来るところを具体的に言う。** 「一部は作れます」で終わらせない。"""
    labels = [f.label for f in getattr(plan, "fields", ()) or ()]
    if labels:
        return "・".join(labels) + "を記録するところまでなら作れます。"
    if getattr(plan, "interactions", ()):
        return "ひとつずつ済みにしていくところまでなら作れます。"
    return ""


def gap_from_plan(plan) -> CapabilityGap:  # noqa: ANN001
    """Plan から、利用者へ伝える Capability Gap を組む。

    Plan が `missing` / `partial` を持っていなければ空の Gap を返す
    ——**無い問題を作らない。**
    """
    if plan is None:
        return CapabilityGap()

    missing = tuple(getattr(plan, "missing", ()) or ())
    partial = tuple(getattr(plan, "partial", ()) or ())
    if not missing and not partial:
        return CapabilityGap()

    critical = tuple(c for c in missing if _is_critical(c))

    lines: list[str] = []
    if critical:
        names = "・".join(_label(c) for c in critical)
        lines.append(f"{names}は、いまの Forge ではまだ作れません。")
    else:
        for capability_id in missing:
            limitation = _limitation(capability_id)
            if limitation:
                lines.append(f"{limitation}。")
    for capability_id in partial:
        limitation = _limitation(capability_id)
        if limitation:
            lines.append(f"{limitation}。")

    buildable = _buildable_summary(plan)
    if buildable:
        lines.append(buildable)

    return CapabilityGap(
        missing=missing, partial=partial, critical=critical,
        message="".join(lines),
    )
