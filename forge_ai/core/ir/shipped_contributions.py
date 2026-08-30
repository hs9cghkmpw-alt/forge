"""**出荷済みの能力の出力宣言**（020E-5）。

`view.map` の widget 生成は、以前 `forge_language_compiler.py` の
`_attach_map_view()` にあった。**能力名で分岐する枝**だったので、
Self-Extension で獲得した能力には一生書かれない形だった。

宣言へ移した。出力は**1バイトも変えていない**——属性の順序も含めて
以前と同じ JSON になる（既存の v1.16 テストがそれを保証する）。

> **ここに行を足すのは「出荷済みの能力」だけである。**
> 獲得した能力は promotion 時に自分で
> `register_document_contribution()` を呼ぶ。表であることが本質で、
> 枝に戻してはならない。
"""

from __future__ import annotations

from forge_ai.core.ir.capability_document_contribution import (
    CapabilityDocumentContribution,
    FieldNameRef,
    register_document_contribution,
)

#: 地図。**明示的な数値の緯度・経度を要る。**
#:
#: 自由入力の地名から座標を導いてよいという意味ではない
#: （geocoding は別の能力である）。
MAP_VIEW_CONTRIBUTION = CapabilityDocumentContribution(
    capability_id="view.map",
    widget_type="map_view",
    widget_id="record_map",
    document_version="1.16",
    required_numeric_fields=("latitude", "longitude"),
    properties=(
        ("state_ref", "records"),
        ("latitude_field", FieldNameRef("latitude")),
        ("longitude_field", FieldNameRef("longitude")),
        ("title", "地図"),
        ("empty_text", "緯度と経度を記録すると地図に表示されます"),
        ("initial_zoom", 11),
        ("height", 320),
    ),
    label_property="label_field",
    fallback_container_id="map_root",
)


def register_shipped_contributions() -> None:
    """起動時に1度呼ぶ。**二重登録は同じ宣言なら無害。**"""
    register_document_contribution(MAP_VIEW_CONTRIBUTION)


register_shipped_contributions()
