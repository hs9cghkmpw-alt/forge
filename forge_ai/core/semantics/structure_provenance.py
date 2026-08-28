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

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "EntitySynthesisAttempt",
    "EntitySynthesisContractEvidence",
    "EntitySynthesisRejectionReason",
    "EntitySynthesisRepair",
    "StructureProvenance",
    "StructureProvider",
    "StructureSource",
]


class StructureSource(str, Enum):
    """構造を作った段。**値は backend の enum と一致させる。**"""

    CURATED = "curated"
    DETERMINISTIC_CAPABILITY_PLAN = "deterministic_capability_plan"
    AI_ENTITY_SYNTHESIS = "ai_entity_synthesis"
    AI_GENERATED_EXTENSION = "ai_generated_extension"
    COMPOSED = "composed"
    UNKNOWN = "unknown"


class StructureProvider(str, Enum):
    """構造を作ったのが AI なら、**どの種類の Provider か。**

    `StructureSource` が「どの段が作ったか」で、こちらは「誰が」。
    決定的に組んだときは `NONE` である——**空文字にしない。**
    """

    LOCAL = "local"
    CLOUD = "cloud"
    TEST_DOUBLE = "test_double"
    NONE = "none"


class EntitySynthesisRejectionReason(str, Enum):
    """AI の Entity 合成を**受け取らなかった理由**。

    「試したが落とした」と「そもそも試していない」は違う。
    区別できないと、Local Model が伸びているのかどうかが分からない。
    """

    EMPTY_OUTPUT = "empty_output"
    INVALID_JSON = "invalid_json"
    INVALID_IDENTIFIER = "invalid_identifier"
    NO_VALID_FIELDS = "no_valid_fields"
    VALIDATION_FAILED = "validation_failed"
    SANITIZED_TO_EMPTY = "sanitized_to_empty"
    UNKNOWN = "unknown"


class EntitySynthesisRepair(str, Enum):
    """Forge が AI の Entity 出力へ加えた構造的補正。本文は持たない。"""

    IDENTIFIER_NORMALIZED = "identifier_normalized"
    UNKNOWN_TYPE_TO_STRING = "unknown_type_to_string"
    CHOICE_TO_STRING = "choice_to_string"
    REQUIRED_INJECTED = "required_injected"
    LABEL_FALLBACK = "label_fallback"
    VISUAL_STYLE_FALLBACK = "visual_style_fallback"
    FIELD_DROPPED = "field_dropped"
    CHOICE_DROPPED = "choice_dropped"
    BOUNDS_DROPPED = "bounds_dropped"
    MEASURE_DOWNGRADED = "measure_downgraded"


@dataclass(frozen=True)
class EntitySynthesisContractEvidence:
    """生の Model 出力が Entity contract を自力で満たしたかの証拠。

    Prompt・利用者本文・Model 生出力は保持しない。構造的な事実だけを持つ。
    `strict_contract_passed` は fail-closed で、観測できなければ False。
    """

    raw_schema_valid: bool = False
    repairs_applied: tuple[EntitySynthesisRepair, ...] = ()
    fields_received: int = 0
    fields_accepted: int = 0
    strict_contract_passed: bool = False
    structured_output_mode: str = ""


@dataclass(frozen=True)
class StructureProvenance:
    """**構造を誰が作ったか**を、1つの値として持つ。

    `source` / `provider` / `task` を別々の欄で持つと、片方だけ更新して
    ずれる。**3つで1つの事実**なので、まとめて置き換える。
    """

    source: StructureSource = StructureSource.UNKNOWN
    provider: StructureProvider = StructureProvider.NONE
    task: str = ""

    @property
    def is_ai(self) -> bool:
        """**AI が構造を作ったか。** ここ1箇所で判定する。"""
        return self.source in _AI_STRUCTURE_SOURCES


@dataclass(frozen=True)
class EntitySynthesisAttempt:
    """AI の Entity 合成を**試したか / 受け取ったか / なぜ落としたか**。"""

    attempted: bool = False
    accepted: bool = False
    rejection_reason: EntitySynthesisRejectionReason | None = None
    contract: EntitySynthesisContractEvidence = EntitySynthesisContractEvidence()


#: **AI が構造を作ったと言ってよい source。** ここだけを見る。
_AI_STRUCTURE_SOURCES = frozenset({
    StructureSource.AI_ENTITY_SYNTHESIS,
    StructureSource.AI_GENERATED_EXTENSION,
})
