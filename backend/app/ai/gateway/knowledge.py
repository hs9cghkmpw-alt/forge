"""Forge Knowledge — **Local AIが「何から選ぶか」を知るための土台**
(FORGE-016A commit D / FORGE-017A §15、2026-08-24)。

---

## なぜ最初から scope / app_id を持つのか

017A §15の指示そのものである。

> KnowledgeEntryには最初から intelligence_scope / app_id / status /
> version / training・provenance boundary を考慮。

**後から付けられないから**である。Entryを1件でも作った後に遡って
`scope`を付けようとすると、既存の全Entryについて「これはGlobalか、
Appか、Personalか」を人間が判断し直すことになる。判断できないものは
`UNKNOWN`になり、`UNKNOWN`は使えないので、結局作り直しになる。

`app_id`はコードに1箇所も存在しなかった（017 Reviewの実測）。
**ここが最初の1箇所である。**

## Personal を Global へ混ぜない（017 §17）

`KnowledgeStore`は`scope`で**引ける範囲を分ける**。Global用の検索は
Personal Entryを返せない——「返さない運用」ではなく、Storeが構造として
分かれている。

## 何が Knowledge で、何が Knowledge でないか

Knowledgeは**Forgeが持っている語彙の説明**である。

```
✅ 「metric.primary とは、その画面で一番大事な数値のこと」
✅ 「density.compact は一覧中心の画面で使う」
❌ 利用者が作ったアプリの中身
❌ 利用者の発話
```

利用者由来のものをKnowledgeへ入れる経路は、**このモジュールには無い**。
入れるなら Consent と Sanitize を通った後の別契約になる（017 §7・§9）。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.ai.gateway.learning_contract import DataResidency, IntelligenceScope
from app.ai.gateway.learning_foundation import TrainingProvenance

__all__ = [
    "KnowledgeContext",
    "KnowledgeEntry",
    "KnowledgeStatus",
    "KnowledgeStore",
    "default_knowledge_store",
]


class KnowledgeStatus(str, Enum):
    """そのEntryを**いま使ってよいか**。"""

    ACTIVE = "active"
    """現行。検索に出る。"""

    DEPRECATED = "deprecated"
    """使わない。**消さずに残す**——過去の生成物がこれを参照している
    ので、消すと「なぜこの選択をしたのか」が辿れなくなる。"""

    DRAFT = "draft"
    """**既定値。** まだ検索に出さない。

    分からないものを「使ってよい」へ倒さない（`CLAUDE.md` §3）。
    """

    @property
    def is_retrievable(self) -> bool:
        return self is KnowledgeStatus.ACTIVE


@dataclass(frozen=True)
class KnowledgeEntry:
    """Forgeが持っている語彙の1項目。

    **利用者由来の内容は入らない。** ここにあるのはForge自身が書いた
    説明であり、Provenanceもそう記録される。
    """

    entry_id: str
    """`design_role.metric.primary`のような安定した識別子。
    **本文が変わってもこれは変わらない**——版は`version`で表す。"""

    content: str
    """AIへ渡す説明文。**Forgeが書いたもの。**"""

    scope: IntelligenceScope = IntelligenceScope.GLOBAL
    """誰の知能のためか（017A §10）。"""

    app_id: str | None = None
    """`scope=APP`のときに必須。**Appの境界の起点**（017 §18）。"""

    residency: DataResidency = DataResidency.LOCAL_ONLY
    """外へ出してよいか。**既定は出さない。**"""

    status: KnowledgeStatus = KnowledgeStatus.DRAFT
    version: int = 1
    """本文が変わるたびに上がる。生成物のEvidenceはこれを参照する
    ——後から「どの版の知識で作られたか」を辿るため。"""

    provenance: TrainingProvenance = TrainingProvenance.UNKNOWN
    """この知識が**何に由来するか**。Forgeが書いたものは
    `FORGE_SYNTHETIC`。利用者データ由来なら`FORGE_USER_DATA`で、
    **現時点でその値を持つEntryは存在しない。**"""

    def __post_init__(self) -> None:
        if self.scope is IntelligenceScope.APP and not self.app_id:
            # **app_idの無いApp Knowledgeを作らせない。** 作れると、
            # どのAppのものか分からないEntryがGlobalへ紛れ込む。
            msg = f"scope=APP のKnowledgeEntryには app_id が要る: {self.entry_id}"
            raise ValueError(msg)
        if self.scope is not IntelligenceScope.APP and self.app_id:
            msg = f"scope={self.scope.value} のEntryに app_id は付けられない: {self.entry_id}"
            raise ValueError(msg)

    @property
    def reference(self) -> str:
        """Evidenceへ残す形。**本文ではなく識別子と版**（016 §12.1）。"""
        return f"{self.entry_id}@v{self.version}"


@dataclass(frozen=True)
class KnowledgeContext:
    """1回の推論のために解決された知識（017A §15）。

    **Provider選択の前に解決する。** Cloudへ行くかLocalへ行くかで
    渡す知識が変わると、「同じ問いに同じ知識で答えた」という比較が
    できなくなる——Benchmarkの前提が崩れる。

    Evidenceへ残すのは`references`だけである。**本文は残さない**
    （016 §12.1「raw retrieved textではなく識別子だけ」）。
    """

    entries: tuple[KnowledgeEntry, ...] = ()
    scope: IntelligenceScope = IntelligenceScope.GLOBAL
    app_id: str | None = None

    @property
    def references(self) -> tuple[str, ...]:
        """Evidenceへ残す識別子。**本文を含まない。**"""
        return tuple(e.reference for e in self.entries)

    @property
    def is_empty(self) -> bool:
        return not self.entries

    def to_dict(self) -> dict[str, object]:
        """診断・Evidence用。**本文が現れないことが不変条件である。**"""
        return {
            "scope": self.scope.value,
            "app_id": self.app_id,
            "entry_count": len(self.entries),
            "references": list(self.references),
        }


class KnowledgeStore:
    """Knowledgeの保持と検索。

    **scopeで引ける範囲が分かれている**（017 §17・§18）。Global用の
    検索がPersonal Entryを返すことは、構造として起きない。
    """

    def __init__(self) -> None:
        self._entries: dict[str, KnowledgeEntry] = {}

    def add(self, entry: KnowledgeEntry) -> KnowledgeEntry:
        self._entries[entry.entry_id] = entry
        return entry

    def add_all(self, entries: "list[KnowledgeEntry] | tuple[KnowledgeEntry, ...]") -> int:
        for entry in entries:
            self.add(entry)
        return len(self._entries)

    def get(self, entry_id: str) -> KnowledgeEntry | None:
        return self._entries.get(entry_id)

    def retrieve(
        self,
        *,
        scope: IntelligenceScope = IntelligenceScope.GLOBAL,
        app_id: str | None = None,
        limit: int | None = None,
    ) -> tuple[KnowledgeEntry, ...]:
        """その範囲で使える知識。

        ---

        ## 境界の規則

        | 求める範囲 | 返るもの |
        |---|---|
        | `GLOBAL` | Globalのみ |
        | `APP` + `app_id` | **そのApp** + Global |
        | `PERSONAL` | Personal + Global |

        **AppはGlobalを見られるが、GlobalはAppを見られない。**
        逆向きを許すと、あるAppの知識が全利用者の生成へ効いてしまう
        （017 §18「App-specific knowledgeをGlobalへ無条件混入しない」）。

        **Personalは誰にも見えない。** 別のscopeの検索に現れる経路が
        無い（017 §17）。
        """
        allowed: set[IntelligenceScope] = {IntelligenceScope.GLOBAL}
        if scope is IntelligenceScope.APP:
            allowed.add(IntelligenceScope.APP)
        elif scope is IntelligenceScope.PERSONAL:
            allowed.add(IntelligenceScope.PERSONAL)

        found = [
            entry for entry in self._entries.values()
            if entry.status.is_retrievable
            and entry.scope in allowed
            and (entry.scope is not IntelligenceScope.APP or entry.app_id == app_id)
        ]
        found.sort(key=lambda e: e.entry_id)
        return tuple(found[:limit] if limit is not None else found)

    def reset(self) -> None:
        self._entries.clear()

    def size(self) -> int:
        return len(self._entries)


_DEFAULT_STORE: KnowledgeStore | None = None


def default_knowledge_store() -> KnowledgeStore:
    """本番が使う唯一のStore。**Forge自身の語彙で初期化される。**"""
    global _DEFAULT_STORE  # noqa: PLW0603 — プロセス内Singleton(既存のStoreと同じ方針)
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = KnowledgeStore()
        _DEFAULT_STORE.add_all(_forge_global_knowledge())
    return _DEFAULT_STORE


def _forge_global_knowledge() -> tuple[KnowledgeEntry, ...]:
    """Design Languageの語彙をKnowledgeへ変換する。

    **`design_language`が正である。** ここは写すだけで、独自の説明を
    書かない——2箇所に書くと必ずずれる。
    """
    from app.ai.runtime.design_language import knowledge_entries  # noqa: PLC0415

    return tuple(
        KnowledgeEntry(
            entry_id=f"design_role.{raw['id']}",
            content=(
                f"{raw['id']}（{raw['category']}）: {raw['meaning']} "
                f"使うとき: {raw['use_when']} 避けるとき: {raw['avoid_when']}"
            ),
            scope=IntelligenceScope.GLOBAL,
            residency=DataResidency.LOCAL_ONLY,
            status=KnowledgeStatus.ACTIVE,
            # **Forgeが書いた説明である。** 利用者データ由来ではない。
            provenance=TrainingProvenance.FORGE_SYNTHETIC,
        )
        for raw in knowledge_entries()
    )
