"""Semantic Capability / Runtime Primitive
(FORGE-USER-GUIDED-SELF-EXTENSION-006 §5・§29・§54、2026-08-13)。

`docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` §3〜§6 の実装。

---

## なぜこの層を足したのか

前の実装は「`view.heatmap`が無い」としか言えなかった。これは**誤診**である。
現物のRuntimeを監査して分かったこと:

* `bar_chart`(`widget_registry_v1_6.dart:81`)は**Record 1件につき棒1本**。
  グループ化も集計もしない。
* `ForgeRuntimeState`に派生状態(derived / computed / aggregate)の仕組みが
  **1つも無い**。

つまり「場所ごとの釣れやすさを濃淡で」に足りないものは1つではなく4つで、
しかも**種類が違う**:

    場所を座標として持つ      → データ型      → 無い
    場所ごとにまとめて数える  → データ変換    → 無い
    数の大小を色の濃さにする  → 表示パラメータ → 無い
    地理座標を投影して描く    → 新しい描画     → 無い

4つとも未実装である。ただし**新しい描画の実装が要るのは4番目だけ**で、
残る3つは既存の描画(`bar_chart`等)の上で成立する。1番目は汎用の
データPrimitiveであり、一度作れば「場所ごとの釣果数」「カテゴリごとの
支出合計」「月ごとの平均体重」が**すべて既存の`bar_chart`で描ける**。

> Widgetを1つ足すと表現が1つ増える。
> 集計Primitiveを1つ足すと表現の**族**が増える。

v1のレビューが「Self-Extensionは成立しない」と結論したのは、
**Widget粒度でしか不足を数えていなかったから**である。

### 実測して、自分の主張を1つ修正した(2026-08-13)

上の「族が増える」を検証するため、未実装Primitiveを1つずつ実装したと
仮定して、成立するSemanticの数を数えた。結果:

    view.calendar / transform.sort / transform.aggregate / data.image
        → いずれも +1個

つまり**「集計だけが特別に多くのパターンを解禁する」わけではない**。
この分解表の粒度では、どのPrimitiveも1パターンずつしか増やさない。
「族が増える」は、パターン数ではなく**同じパターンに何通りの
グループ化キーを渡せるか**の話であり、この指標では測れていない。

一方、実測が**支持した**のはこちらである:

    semantic.heatmap_by_place   残り4個
    semantic.map_markers        残り3個
    semantic.ranking_by_group   残り1個  ← transform.aggregate だけ

「地図で濃淡」は4個先だが、**同じ困りごとに答える「場所ごとの
ランキング」は1個先**である。`transform.aggregate`の価値は
「多くを解禁する」ことではなく、**ユーザーの要求に最も安く到達できる
道である**ことだった。この差は「view.heatmapが無い」という1語の診断
からは絶対に出てこない——それが分解の実際の効用である。

---

## この層がやらないこと

* LLMを呼ばない。決定的な純粋関数のみ。
* Primitiveを自動生成しない。表は人手管理である。
* 実装が無いものを「できる」と言わない。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = [
    "PRIMITIVE_REGISTRY",
    "CapabilityAvailability",
    "SEMANTIC_LABELS_JA",
    "CapabilityDecomposition",
    "PrimitiveKind",
    "RuntimePrimitive",
    "decompose",
    "primitive_by_id",
]


class PrimitiveKind(str, Enum):
    """Runtime Primitiveの種別(レビューv2 §4)。

    v1の Data / View / Effect に、`TRANSFORM`と`ENCODING`を足した。
    **この2つが無かったために、集計も濃淡も「Widgetが無い」としか
    言えなかった。**
    """

    DATA = "data"
    """何を保持するか。安全。"""

    TRANSFORM = "transform"
    """保持した値から別の値を導く。純粋関数であり安全。
    集計・絞り込み・並べ替えはここ。**Widgetではない**。"""

    VIEW = "view"
    """どう見せるか。安全。"""

    ENCODING = "encoding"
    """値を視覚属性へ写像する。安全。棒の長さ・色の濃さ・位置はここ。
    Viewと分けているのは、**同じViewでもEncodingを変えれば別の表現に
    なる**からである(棒グラフの長さ→色の濃さ)。"""

    EFFECT = "effect"
    """Forgeの外へ影響する。**唯一の安全審査対象**。"""


@dataclass(frozen=True)
class RuntimePrimitive:
    """実行できる最小単位。Widgetとは1:1ではない。"""

    id: str
    kind: PrimitiveKind
    label_ja: str
    implemented: bool
    """Runtimeに実装があるか。**無いものをあると言わない**。"""

    widget_types: tuple[str, ...] = ()
    """対応するForge LanguageのWidget型。`VIEW`以外は通常空である
    ——`TRANSFORM`はWidgetではないので、ここが空なのは正常。"""

    note: str = ""
    """未実装のものについて、何が必要かの短い説明(正直な申告のため)。"""


def _p(*args, **kwargs) -> RuntimePrimitive:
    return RuntimePrimitive(*args, **kwargs)


# ---------------------------------------------------------------------------
# Runtime Primitive Registry(静的・人手管理)
#
# `implemented=True` は「Flutter Runtimeに実体がある」ことを意味する。
# 実装状況は`frontend/lib/json_ui/`を実際に読んで確認した(2026-08-13)。
# ---------------------------------------------------------------------------
_PRIMITIVES: tuple[RuntimePrimitive, ...] = (
    # --- DATA -----------------------------------------------------------
    _p("data.text", PrimitiveKind.DATA, "文字", True, ("text_field",)),
    _p("data.number", PrimitiveKind.DATA, "数値", True, ("text_field", "slider")),
    _p("data.date", PrimitiveKind.DATA, "日付", True, ("date_field",)),
    _p("data.choice", PrimitiveKind.DATA, "選択肢", True, ("choice_field",)),
    _p("data.bool", PrimitiveKind.DATA, "済/未済", True, ("checkbox", "checklist")),
    _p("data.geo", PrimitiveKind.DATA, "地理座標", False,
       note="緯度経度の型と入力手段が無い。data.textで地名として持つことは可能"),
    _p("data.image", PrimitiveKind.DATA, "画像", False, note="保存形式と表示Widgetの両方が無い"),

    # --- TRANSFORM(Widgetではない。ここが空白地帯だった)---------------
    # 2026-08-13 実装(Phase 4)。`frontend/lib/json_ui/runtime/
    # forge_aggregate.dart`の純粋関数として実装し、`bar_chart`が
    # `group_by`/`aggregate`(Forge Language v1.9)から利用する。
    # **Widgetではないので`widget_types`は空である**——集計は特定の
    # Widgetに属さず、どのViewからでも呼べる。
    _p("transform.aggregate", PrimitiveKind.TRANSFORM, "グループごとの集計", True),
    _p("transform.filter", PrimitiveKind.TRANSFORM, "条件での絞り込み", False,
       note="同上。派生状態が無い"),
    _p("transform.sort", PrimitiveKind.TRANSFORM, "並べ替え", False,
       note="record_list_viewは保存順で描画する。並べ替えの指定手段が無い"),

    # --- VIEW -----------------------------------------------------------
    _p("view.list", PrimitiveKind.VIEW, "一覧", True, ("list", "record_list_view", "checklist")),
    _p("view.grid", PrimitiveKind.VIEW, "タイル", True, ("record_list_view",)),
    _p("view.bars", PrimitiveKind.VIEW, "棒の並び", True, ("bar_chart",)),
    _p("view.tabs", PrimitiveKind.VIEW, "タブ", True, ("tab_view",)),
    _p("view.spatial", PrimitiveKind.VIEW, "地図上の配置", False,
       note="地理座標の投影と地図タイルの描画。**本当に新しい実装が要る唯一の種類**"),
    _p("view.calendar", PrimitiveKind.VIEW, "暦の格子", False,
       note="月次グリッドの描画が無い"),

    # --- ENCODING(値 → 視覚属性)---------------------------------------
    _p("encoding.length", PrimitiveKind.ENCODING, "長さで表す", True, ("bar_chart",)),
    _p("encoding.color_intensity", PrimitiveKind.ENCODING, "色の濃さで表す", False,
       note="bar_chartは単色固定(widget_registry_v1_6.dart)。"
            "値→色の写像をパラメータ化すれば、新Widget無しで足りる"),
    _p("encoding.position", PrimitiveKind.ENCODING, "位置で表す", False,
       note="view.spatialに従属する"),

    # --- EFFECT(安全審査対象)-------------------------------------------
    _p("effect.share", PrimitiveKind.EFFECT, "外部への共有", False, note="未実装"),
    _p("effect.notify", PrimitiveKind.EFFECT, "通知", False, note="未実装。OS権限が要る"),
    _p("effect.camera", PrimitiveKind.EFFECT, "カメラ", False, note="未実装。OS権限が要る"),
    _p("effect.location", PrimitiveKind.EFFECT, "現在地取得", False, note="未実装。OS権限が要る"),
)

PRIMITIVE_REGISTRY: dict[str, RuntimePrimitive] = {p.id: p for p in _PRIMITIVES}


def primitive_by_id(primitive_id: str) -> RuntimePrimitive | None:
    return PRIMITIVE_REGISTRY.get(primitive_id)


# ---------------------------------------------------------------------------
# Semantic Capability → Runtime Primitive の分解表
#
# **ここが「意味」と「実行できるもの」の境界である**(v2 §4)。
# ユーザーは「ヒートマップ」と言うが、それは3つのPrimitiveの合成である。
# この表があることで、「heatmapが無い」ではなく「不足は4つで、うち
# 新しい描画が要るのは地理描画だけ」と言えるようになる。
#
# 過剰抽象化しない(§54末尾): 分解するのは、**分解すると不足箇所の
# 特定が変わるもの**だけである。`view.list`のように1対1のものは
# わざわざ分解しない。
# ---------------------------------------------------------------------------
_DECOMPOSITION: dict[str, tuple[str, ...]] = {
    # §33の例。3つに分かれ、うち2つは他でも使い回せる。
    "semantic.heatmap_by_place": (
        "data.geo", "transform.aggregate", "encoding.color_intensity", "view.spatial",
    ),
    # 地図に点を置くだけ(集計しない)。
    "semantic.map_markers": ("data.geo", "view.spatial", "encoding.position"),
    # **地図を使わない**、場所ごとの集計。地理描画が要らないため、
    # `transform.aggregate`さえあれば既存Widgetで成立する。
    "semantic.ranking_by_group": ("transform.aggregate", "view.bars", "encoding.length"),
    # 推移。時間軸の集計 + 並び。
    "semantic.trend_over_time": ("data.date", "transform.sort", "view.bars", "encoding.length"),
    "semantic.calendar_view": ("data.date", "view.calendar"),
    "semantic.photo_log": ("data.image", "view.list"),
}

# 会話上の語 → Semantic Capability。`capability.py`の`detection_keywords`と
# 役割が違う: あちらは「何が要求されたか」の検出、こちらは「その要求が
# どのPrimitiveへ分解されるか」の対応である。
_SEMANTIC_BY_CAPABILITY_ID: dict[str, str] = {
    "view.heatmap": "semantic.heatmap_by_place",
    "view.map": "semantic.map_markers",
    "view.calendar": "semantic.calendar_view",
    "view.line_chart": "semantic.trend_over_time",
    "data.photo": "semantic.photo_log",
}


# Semantic Capabilityのユーザー向け日本語。内部IDを画面へ出さない
# (§58: ユーザーに「Capability」「Primitive」と言わない)。
SEMANTIC_LABELS_JA: dict[str, str] = {
    "semantic.heatmap_by_place": "場所ごとの多さを濃淡で見る形",
    "semantic.map_markers": "地図に点を置く形",
    "semantic.ranking_by_group": "場所ごとの多さを並べて見る形",
    "semantic.trend_over_time": "時間の流れで見る形",
    "semantic.calendar_view": "カレンダーで見る形",
    "semantic.photo_log": "写真つきで残す形",
}


class CapabilityAvailability(str, Enum):
    """要求に対して、今のForgeが何を返せるか(§19)。"""

    EXACT = "exact"
    """要求どおりに作れる。"""

    FALLBACK = "fallback"
    """要求どおりではないが、**有用な代替なら作れる**。
    Smallest Useful Tool(§59)へ接続する状態。"""

    BLOCKED = "blocked"
    """有用な代替すら今は作れない。正直にそう言うべき状態。"""


@dataclass(frozen=True)
class CapabilityDecomposition:
    """1つのSemantic Capabilityを分解した結果。"""

    semantic_id: str
    required: tuple[RuntimePrimitive, ...]

    @property
    def available(self) -> tuple[RuntimePrimitive, ...]:
        return tuple(p for p in self.required if p.implemented)

    @property
    def missing(self) -> tuple[RuntimePrimitive, ...]:
        """**本当に足りないもの**。ここが「heatmapが無い」との違いである。"""
        return tuple(p for p in self.required if not p.implemented)

    # --- 「要求どおり作れない」と「何も出せない」を混ぜない -------------
    #
    # 指摘6の修正(2026-08-13)。以前は`blocking_missing`が
    # 「MissingのうちVIEWだけ」を返していたため、
    # `semantic.ranking_by_group`(transform.aggregateが未実装、VIEWは既存)
    # で**空になり**、あたかも問題が無いように読めた。
    # 実際には要求どおりには作れない。2つは別の問いである。

    @property
    def satisfiable_exactly(self) -> bool:
        """**要求どおりに**作れるか。Missingが1つでもあれば`False`。

        ユーザーの要求を満たせるかどうかは、種類に関係なく
        「必要なものが全部あるか」で決まる。`transform.aggregate`が
        無ければ「場所ごとの集計」は要求どおりには作れない——
        描画手段があることは、その事実を変えない。
        """
        return not self.missing

    @property
    def renderable_at_all(self) -> bool:
        """**何かは画面に出せる**か。

        `VIEW`が1つでも実装済みなら、より単純な形へ縮退して見せられる。
        `satisfiable_exactly`が`False`でもこちらが`True`なら、
        「要求どおりではないが、これなら今すぐ出せます」と提案できる
        ——§59の「Smallest Useful Tool」を判断する材料である。
        """
        return any(
            p.kind is PrimitiveKind.VIEW and p.implemented for p in self.required
        )

    @property
    def fallback_possible(self) -> bool:
        """縮退案を出せるか(要求どおりではないが、何かは見せられる)。"""
        return not self.satisfiable_exactly and self.renderable_at_all

    @property
    def availability(self) -> CapabilityAvailability:
        """「作れない」を**3種類に分ける**(§19)。

        2値では足りない理由: 「要求どおり作れない」だけでは、
        代替を出せるのか、何も出せないのかが分からない。この2つは
        ユーザーへ返すべき言葉がまったく違う。

            EXACT     → そのまま作る
            FALLBACK  → 「これなら今すぐ作れます」と**確認する**(§59)
            BLOCKED   → 正直に「作れません」と言う

        `FALLBACK`かどうかは、代替が**実際に存在するか**で決める
        ——「たぶん何か出せる」ではなく、Primitiveが揃っているかで判定する。
        """
        if self.satisfiable_exactly:
            return CapabilityAvailability.EXACT
        alternative = self.nearest_alternative()
        if self.renderable_at_all or (alternative is not None and alternative[1] == 0):
            return CapabilityAvailability.FALLBACK
        return CapabilityAvailability.BLOCKED

    @property
    def distance(self) -> int:
        """成立まであと何個のPrimitiveが要るか。

        これが分解の実用的な価値である。実測(2026-08-13):

            semantic.heatmap_by_place   残り4個
            semantic.map_markers        残り3個
            semantic.ranking_by_group   残り1個  ← transform.aggregate だけ

        「地図で濃淡」は遠いが、**同じ困りごとに答える「場所ごとの
        ランキング」は1個先**である。この差は「view.heatmapが無い」と
        いう1語の診断からは絶対に出てこない。
        """
        return len(self.missing)

    def nearest_alternative(self) -> tuple[str, int] | None:
        """意味的に近く、**より少ないPrimitiveで済む**代替を返す。

        `(semantic_id, 残りPrimitive数)`。完全に成立するものが無くても
        返す——「今は何も作れない」で終わらせず、**どれが一番近いか**を
        言えるようにするため(§30「新Capabilityが本当に必要かを最初に疑う」)。

        近さは必要Primitiveの重なりで測る。語の類似では測らない
        ——「ヒートマップ」と「ランキング」は語としては似ていないが、
        `transform.aggregate`を共有しており、**同じ困りごとに答えうる**。
        """
        best: tuple[str, int] | None = None
        for candidate, required_ids in _DECOMPOSITION.items():
            if candidate == self.semantic_id:
                continue
            primitives = [PRIMITIVE_REGISTRY[i] for i in required_ids if i in PRIMITIVE_REGISTRY]
            if not primitives:
                continue
            overlap = {p.id for p in primitives} & {p.id for p in self.required}
            if not overlap:
                continue
            remaining = sum(1 for p in primitives if not p.implemented)
            if remaining >= self.distance:
                continue  # 自分より遠い代替を勧めても意味が無い
            if best is None or remaining < best[1]:
                best = (candidate, remaining)
        return best

    def explain(self) -> str:
        """不足を**種類ごとに**説明する(内部語はユーザーへ出さない前提の、
        開発者・ログ向けの文字列)。"""
        if not self.missing:
            return f"{self.semantic_id}: 既存Primitiveで成立する"
        parts = [f"{p.label_ja}({p.kind.value})" for p in self.missing]
        return f"{self.semantic_id}: 不足 = " + " / ".join(parts)


def decompose(capability_id: str) -> CapabilityDecomposition | None:
    """`capability.py`のCapability idから、Runtime Primitiveへ分解する。

    対応が無ければ`None`——**分解表に無いものを推測で分解しない**。
    知らないことを知らないままにしておく方が、それらしい嘘より安全である。
    """
    semantic_id = _SEMANTIC_BY_CAPABILITY_ID.get(capability_id)
    if semantic_id is None:
        return None
    required_ids = _DECOMPOSITION.get(semantic_id)
    if not required_ids:
        return None
    required = tuple(
        PRIMITIVE_REGISTRY[i] for i in required_ids if i in PRIMITIVE_REGISTRY
    )
    return CapabilityDecomposition(semantic_id=semantic_id, required=required)
