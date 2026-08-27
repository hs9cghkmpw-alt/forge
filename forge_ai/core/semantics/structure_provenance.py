"""**その文書の構造を誰が作ったか**（FORGE-020A2 §3、2026-08-26）。

`forge_ai` は `backend` を import できないので、値の定義はここに置く。
backend 側の `GenerationStructureSource` と**値の文字列で照合**し、
食い違いはテストが落とす（`test_forge_020a2_structure_provenance.py`）。

---

## なぜ要るのか

R4 以降、次の順で文書が出来る。

```
Capability Plan → 決定的な EntitySpec → IR → Design Intent（AI）
```

**構造は決定的に組まれ、AI は Design Intent だけ答える**ことがある。
その状態で「local が答えた」を見て「Local Model が構造を決めた」と
記録すると嘘になる。

構造を作った段を、**その場で**記録する。
"""

from __future__ import annotations

from enum import Enum

__all__ = ["StructureSource"]


class StructureSource(str, Enum):
    """構造を作った段。**値は backend の enum と一致させる。**"""

    CURATED = "curated"
    DETERMINISTIC_CAPABILITY_PLAN = "deterministic_capability_plan"
    AI_ENTITY_SYNTHESIS = "ai_entity_synthesis"
    AI_GENERATED_EXTENSION = "ai_generated_extension"
    COMPOSED = "composed"
    UNKNOWN = "unknown"
