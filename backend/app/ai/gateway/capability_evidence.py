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

from forge_ai.core.semantics.structure_provenance import (
    StructureProvider,
    StructureSource,
)

__all__ = [
    "CapabilityUsage",
    "CapabilityUsageSource",
    "CapabilityUsageStatus",
    "GenerationStructureSource",
    "StructureProvider",
    "StructureSource",
    "structure_source_is_ai",
]


#: **その文書の構造を誰が作ったか。**
#:
#: `GenerationSource`（誰が「生成した」か）とは別の軸である。後者は
#: Provider の話であり、こちらは**どの段が構造を決めたか**。
#:
#: 定義は `forge_ai` 側にあり、ここは**別名を置くだけ**である
#: （020A2 と 020A3 の merge、2026-08-27）。
#:
#: 以前は backend にも同じ値の enum を書き、テストで値の一致を見て
#: いた。**同じ値の enum が2つあると `is` 比較が常に False になる**
#: ——TD85（`Deployment` enum が2つ）で実際に踏んだ形である。
#: 別名なら**同じ物**なので、ずれようがない。
GenerationStructureSource = StructureSource


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
