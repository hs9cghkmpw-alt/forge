"""**実際にビルドして載せた能力だけが、Validator の語彙を広げられる**（020F）。

---

## 解いている問題

Validator（生成物を検査する仕組み）の許可 widget は、版ごとの
**固定の集合**だった。

```python
WIDGET_TYPES_V1_16_ADDITIONS = {"map_view"}
```

人が書き足す表なので、Self-Extension で獲得した能力の widget は
**永久に「未知の widget」として弾かれる**。獲得しても検査を通れない。

## しかし「宣言したから通す」にはしない

ここを緩めると、**Dart（実際に描く側）が知らない widget を通してしまう。**
Validator は通るのに実行時に描けない——それは fail-open（危ない側に
倒す）である。

そこで通す条件を**2つとも**要求する。

| 条件 | 意味 |
|---|---|
| PROMOTED である | Evidence Gate を通って獲得済み |
| **loaded な BUILD_TIME activation を持つ** | **新しい runtime が実際にビルドされ、載っている** |

`requested`（利用者が欲しいと言っただけ）では広がらない。
`DECLARATIVE` な獲得でも広がらない——あちらは**既存の widget** を
組み替えるものであり、新しい widget 型を持ち込まないからである。

つまり「Dart が描けるはず」と推測せず、
**新しい runtime を作った事実**にだけ紐付ける。

## 何も獲得していなければ空集合

既定は空である。**忘れても緩まない向き**に倒してある。
"""

from __future__ import annotations

__all__ = ["runtime_attested_widget_types"]


def runtime_attested_widget_types() -> frozenset[str]:
    """実 runtime を伴って獲得された widget 型。

    取得に失敗したら**空集合**を返す（例外で生成を落とさないが、
    緩める方向にも倒さない）。
    """
    try:
        from forge_ai.core.ir.capability_document_contribution import (
            document_contribution_for,
        )
        from forge_ai.core.orchestration.extension_plan import ExtensionRoute
        from forge_ai.core.orchestration.extension_registry import (
            PROMOTED_CAPABILITIES,
        )
    except Exception:  # noqa: BLE001 — forge_ai を読めない環境では広げない
        return frozenset()

    accepted: set[str] = set()
    for item in PROMOTED_CAPABILITIES.items():
        capability_id = item.capability_id
        # **BUILD_TIME 以外は広げない。** 新しい runtime を作っていない。
        if item.route is not ExtensionRoute.BUILD_TIME:
            continue
        activation = item.activation
        # **載っていることを要求する。** metadata だけでは通さない。
        if getattr(activation, "loaded", False) is not True:
            continue
        if not getattr(activation, "build_id", ""):
            continue
        if not getattr(activation, "runtime_fingerprint", ""):
            continue
        if getattr(activation, "capability_id", "") != capability_id:
            continue
        contribution = document_contribution_for(capability_id)
        if contribution is None:
            # 出力宣言が無い能力は widget を出さない。広げる理由が無い。
            continue
        widget_type = contribution.widget_type.strip()
        if widget_type:
            accepted.add(widget_type)
    return frozenset(accepted)
