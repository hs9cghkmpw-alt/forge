"""**どの Capability が、どう扱われたか**（FORGE-020A2 §3・§4、2026-08-26）。

---

## §4 なぜ ID の並びでは足りないか

R4 で `GenerationRecord.capabilities` を埋めた。ただし入っていたのは
`views` / `interactions` / `partial` / `unsupported` 中心で、
**実際に使われた Field の Capability**（`data.text` / `data.date` /
`data.number`）が抜けていた。

将来 JSONL Dataset へ落とすとき、

* 何を**求められて**
* 何が**実際に使われて**
* 何が**一部しか出来ず**
* 何が**無かった**か

の4つが区別できないと、「この構成なら上手くいく」を学習できない。
`unsupported:` のような**接頭辞つき文字列**で区別するのは、書式に
意味を持たせているだけであり、読む側が必ず parse を書くことになる。

型にする。**値も利用者の本文も入らない。Capability ID だけである。**

## §3 なぜ「構造を誰が作ったか」を分けるか

R4 以降、次の順で文書が出来る。

```
Capability Plan → deterministic EntitySpec → IR → Design Intent(AI)
```

**構造は決定的に組まれ、AI は Design Intent だけ答える**ことがある。
その状態で `last_provider_used == "local"` になると、
`GenerationSource.LOCAL_AI`——「Local Model が構造を決めた」——に
なってしまう。

それは嘘である。Local Model は**見た目の役だけ**答えた。

`GenerationStructureSource` を分けて、**構造を誰が作ったか**を
別の欄で言う。Level 0 はこちらを見る。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "CapabilityUsage",
    "CapabilityUsageSource",
    "CapabilityUsageStatus",
    "GenerationStructureSource",
    "structure_source_is_ai",
]


class GenerationStructureSource(str, Enum):
    """**その文書の構造を誰が作ったか。**

    `GenerationSource`（誰が「生成した」か）とは別の軸である。
    後者は Provider の話であり、こちらは**どの段が構造を決めたか**。
    """

    CURATED = "curated"
    """Curated Domain Library の手書き定義。AI は1回も呼ばれていない。"""

    DETERMINISTIC_CAPABILITY_PLAN = "deterministic_capability_plan"
    """**役から決まった Capability Plan。** Forge の決定的な処理である。

    Design Intent で AI を呼んでいても、**構造を作ったのは AI ではない。**
    """

    AI_ENTITY_SYNTHESIS = "ai_entity_synthesis"
    """**AI が記録するデータ構造を設計した。** ここが「AI が構造を作った」。"""

    AI_GENERATED_EXTENSION = "ai_generated_extension"
    """AI が既存の構造を拡張した（Self-Extension 経路。まだ発生しない）。"""

    COMPOSED = "composed"
    """複数の段が構造へ寄与した。"""

    UNKNOWN = "unknown"
    """**既定値。** 記録し損ねたものを AI 側へ倒さない。"""


#: **AI が構造を作ったと言ってよいもの。**
_AI_STRUCTURE_SOURCES = frozenset({
    GenerationStructureSource.AI_ENTITY_SYNTHESIS,
    GenerationStructureSource.AI_GENERATED_EXTENSION,
})


def structure_source_is_ai(source: GenerationStructureSource) -> bool:
    """**AI が構造生成を担当したか。**

    `DETERMINISTIC_CAPABILITY_PLAN` は `False` である——Design Intent だけ
    AI が答えても、構造は Forge が決定的に組んでいる。
    """
    return source in _AI_STRUCTURE_SOURCES


class CapabilityUsageStatus(str, Enum):
    """その Capability が**どこまで出来たか。**"""

    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    MISSING = "missing"


class CapabilityUsageSource(str, Enum):
    """その Capability を**誰が決めたか。**"""

    SEMANTIC_PLAN = "semantic_plan"
    """役から決まった。"""

    DETERMINISTIC = "deterministic"
    """Forge が構造上必ず要るものとして足した。"""

    AI = "ai"
    """AI が決めた。"""

    FALLBACK = "fallback"
    """他が失敗して既定へ落ちた。"""


@dataclass(frozen=True)
class CapabilityUsage:
    """1つの Capability についての事実。

    **値は入らない。** 利用者の言葉も生成物の本文も、この型では
    表現できない（`GenerationRecord` と同じ Privacy 境界、006 §22）。
    """

    capability_id: str
    requested: bool
    used: bool
    """**実際に生成物へ現れたか。** `requested` だけで `used` でないものが
    「求められたが出せなかった」である。"""

    status: CapabilityUsageStatus
    source: CapabilityUsageSource = CapabilityUsageSource.SEMANTIC_PLAN

    @property
    def used_successfully(self) -> bool:
        """**「出来た」と言ってよいか。** `PARTIAL` は含めない。"""
        return self.used and self.status is CapabilityUsageStatus.IMPLEMENTED

    def to_dict(self) -> dict[str, object]:
        return {
            "capability_id": self.capability_id,
            "requested": self.requested,
            "used": self.used,
            "status": self.status.value,
            "source": self.source.value,
        }
