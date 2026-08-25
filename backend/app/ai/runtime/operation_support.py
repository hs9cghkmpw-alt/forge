"""Supported Operation Contract — **enumに在ることと、使えることは違う**
(FORGE-019C §9、2026-08-25)。

---

## 何が嘘になっていたか

`SemanticOperationKind` は7つを宣言している。

```
SELECT_PRIMARY_METRIC / SET_DESIGN_ROLE / SET_EMPHASIS / SET_VISIBILITY
SET_LAYOUT_VARIANT / SET_GROUPING / SET_THEME_TONE
```

しかし本番で自然言語から到達できるのは**1つだけ**である。

* `TargetResolver` が拾う言い回しは「目立たせて / 強調 / primary / 主指標」
* `apply_semantic_intent()` が組み立てるのは `SelectPrimaryMetric` だけ
* `SemanticOperation` の union は2つ（`SetDesignRole` は engine から直接
  呼べば動くが、**自然言語からは到達しない**）
* 残り5つは**型すら無い**

この状態で「Forgeは7つの意味的操作をサポートする」と書けば嘘になる。
Roadmapの進捗も、Benchmarkの母数も、そこから狂う。

## だから3段に分ける

| | 意味 |
|---|---|
| `PRODUCTION_SUPPORTED` | **利用者が言葉で到達できる。** 数えてよい |
| `ENGINE_ONLY` | 型と実装はあるが、言葉からは届かない |
| `RESERVED` | 名前だけ。実装は無い |

## 分類し忘れを通さない

`_SUPPORT` に載っていない enum は `RESERVED` ではなく**例外**にする。
「新しい操作を足したが分類を忘れた」を `RESERVED` へ倒すと静かに
嘘が戻るし、`PRODUCTION_SUPPORTED` へ倒すのは論外である
（`CLAUDE.md` §3「分からないものを楽観側へ倒さない」）。

## 本番がここを通る

`RevisionService` は commit の前に `require_production_supported()` を
呼ぶ。分類されていない操作・到達してはいけない操作が万一組み立てられて
も、**記録される前に止まる**。

置物にしないための形である——この関数を外すと `/update` が
`RESERVED` な操作を受け入れてしまい、テストが落ちる。
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType

from app.ai.runtime.semantic_revision import SemanticOperationKind

__all__ = [
    "OperationSupportLevel",
    "UnsupportedOperation",
    "operation_support_table",
    "production_supported_operations",
    "require_production_supported",
    "support_level",
]


class OperationSupportLevel(str, Enum):
    """その操作が**どこまで本物か**。"""

    PRODUCTION_SUPPORTED = "production_supported"
    """自然言語から到達でき、本番の経路が最後まで通る。"""

    ENGINE_ONLY = "engine_only"
    """型と実装はあるが、**自然言語からは到達しない**。"""

    RESERVED = "reserved"
    """名前だけ。実装は無い。**「できる」と数えない。**"""


class UnsupportedOperation(Exception):
    """本番で受け付けてよい操作ではない。"""


_SUPPORT: dict[SemanticOperationKind, OperationSupportLevel] = {
    # 「収入をもっと目立たせて」→ `TargetResolver` → `SelectPrimaryMetric`
    SemanticOperationKind.SELECT_PRIMARY_METRIC:
        OperationSupportLevel.PRODUCTION_SUPPORTED,
    # 型も適用実装もあるが、`apply_semantic_intent()` は組み立てない。
    SemanticOperationKind.SET_DESIGN_ROLE: OperationSupportLevel.ENGINE_ONLY,
    # 以下は名前だけ。型が無い。
    SemanticOperationKind.SET_EMPHASIS: OperationSupportLevel.RESERVED,
    SemanticOperationKind.SET_VISIBILITY: OperationSupportLevel.RESERVED,
    SemanticOperationKind.SET_LAYOUT_VARIANT: OperationSupportLevel.RESERVED,
    SemanticOperationKind.SET_GROUPING: OperationSupportLevel.RESERVED,
    SemanticOperationKind.SET_THEME_TONE: OperationSupportLevel.RESERVED,
}


def operation_support_table() -> "MappingProxyType[SemanticOperationKind, OperationSupportLevel]":
    """分類表そのもの。**読むだけ。**"""
    return MappingProxyType(_SUPPORT)


def support_level(kind: SemanticOperationKind) -> OperationSupportLevel:
    """その操作の段。**分類されていなければ例外。**"""
    level = _SUPPORT.get(kind)
    if level is None:
        msg = f"semantic operation {kind.value!r} has no declared support level"
        raise UnsupportedOperation(msg)
    return level


def production_supported_operations() -> frozenset[SemanticOperationKind]:
    """**本番で数えてよい操作。** Roadmap も Benchmark もここを見る。"""
    return frozenset(
        kind for kind, level in _SUPPORT.items()
        if level is OperationSupportLevel.PRODUCTION_SUPPORTED
    )


def require_production_supported(kind: SemanticOperationKind) -> None:
    """本番の経路で使ってよいか。**違えば通さない**（fail closed）。"""
    level = support_level(kind)
    if level is not OperationSupportLevel.PRODUCTION_SUPPORTED:
        msg = (
            f"semantic operation {kind.value!r} is {level.value}, "
            "not reachable from production"
        )
        raise UnsupportedOperation(msg)
