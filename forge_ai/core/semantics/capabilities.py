"""**Forge Capability の唯一の定義場所**（FORGE-020A2、2026-08-26）。

---

## なぜ1つに寄せるのか

R4 の時点で、同じ「Forge Capability」に **Source of Truth が2つ**あった。

| | 場所 | 使われ方 |
|---|---|---|
| A | `backend/app/ai/runtime/capability.py` | 会話・Missing Capability |
| B | `forge_ai/core/semantics/capability_plan.py` | 生成の Capability Plan |

同じ概念が別の ID で書かれていた（`record.photo` と `data.photo`、
`interact.notify` と `effect.notify`、`view.total` と `view.metric`）。

**会話が「写真は作れない」と言い、生成が別 ID で「partial」と言う。**
どちらが正なのか誰も答えられない状態であり、片方だけ直せば静かに
食い違う——このリポジトリで何度も踏んだ「同じことをする層を2つ残す」
（TD59）と同じ形である。

## 置き場所が forge_ai である理由

`forge_ai` は `backend` を import してはならない（ADR 7.3）。
逆（backend → forge_ai）は成立している。

Capability の**意味**は生成にも会話にも要る。両方から読める場所は
`forge_ai` しかない。

```
Semantic Capability Catalog        ← ここ（forge_ai）
        ↓
Runtime Support Adapter            ← backend/app/ai/runtime/capability.py
        ↓
Validator / Renderer / Conversation
```

## この表が持つもの / 持たないもの

**持つ**: ID・層・意味・利用者向けの名前・安全区分・検出語・
代替候補・**Forge が意味として支援できる度合い**。

**持たない**: Widget 名も、Forge Language の型も、確認 Policy の
実装も持たない。それは Runtime Adapter の仕事である。

## 「支援できる度合い」を2箇所で手管理しない

`SupportLevel` はここにしか無い。Adapter は Widget との**結び付き**
だけを持つ。両者が食い違っていないことは**テストが機械的に照合する**
（`IMPLEMENTED` なのに Widget が無い、`MISSING` なのに Widget がある、
のどちらも落ちる）。

人が2箇所を見比べて揃える運用にしない——それが二重表である。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

__all__ = [
    "SEMANTIC_CAPABILITIES",
    "CapabilityDefinition",
    "CapabilityLayer",
    "SafetyClass",
    "SupportLevel",
    "capability",
    "capability_ids",
    "is_known_capability",
]


class CapabilityLayer(str, Enum):
    """Capability の層。**安全審査の対象は `EFFECT` だけである。**

    抽象度の違うものを同じ平面に並べない（005 §32 の判断を引き継ぐ）。
    """

    DATA = "data"
    """何を記録するか。"""

    VIEW = "view"
    """どう見せるか。"""

    INTERACT = "interact"
    """利用者が画面で何をするか。"""

    EFFECT = "effect"
    """**外へ何をするか。** ここだけが安全審査の対象。"""

    SIMULATE = "simulate"
    """時間経過・生成的な振る舞い。`simulate.loop` は実Runtimeまで実装済み。"""


class SafetyClass(str, Enum):
    """**確認が要るか**を決める区分。"""

    SAFE = "safe"
    """自分のデータの中で閉じる。確認不要。"""

    SENSITIVE = "sensitive"
    """外部・他人・OS 機能に触れる。**実行前に確認が要る。**"""


class SupportLevel(str, Enum):
    """**Forge がその能力を持っているか。**

    ここが唯一の宣言場所である。Adapter は Widget との結び付きだけを
    持ち、両者の整合はテストが照合する。
    """

    IMPLEMENTED = "implemented"
    PARTIAL = "partial"
    """出来るが本来の形ではない。**「出来る」と言い切らない。**

    例: 写真は**文字として**記録する。推移は**時系列グラフではない**。
    """

    MISSING = "missing"
    """**持っていない。** 代用して黙らない。"""


@dataclass(frozen=True)
class CapabilityDefinition:
    """1つの Capability の意味。**Widget 名は入らない。**"""

    id: str
    layer: CapabilityLayer
    label_ja: str
    """利用者へ見せる日本語。**内部 ID を UI へ出さない。**"""

    intent: str
    """何をしたいという要求なのか（人が読むための説明）。"""

    support: SupportLevel
    safety: SafetyClass = SafetyClass.SAFE

    detection_keywords: tuple[str, ...] = field(default=())
    """要求されたと判定する語。決定的な substring マッチ（形態素解析は使わない）。"""

    nearest_supported_id: str | None = None
    """出来ないときに代わりに提案できる ID。**`None` なら正直に「できない」と言う。**"""

    limitation: str = ""
    """`PARTIAL` / `MISSING` のとき、**何が出来ないのか**。

    「partial」とだけ書いて済ませない。利用者へそのまま見せられる言葉。
    """


def _c(*args, **kwargs) -> CapabilityDefinition:
    return CapabilityDefinition(*args, **kwargs)


_L = CapabilityLayer
_S = SupportLevel
_F = SafetyClass

#: **唯一の Capability 表。**
#:
#: ID は「会話側が既に本番で使っていたもの」を正とした（`data.*` /
#: `view.*` / `effect.*`）。R4 が別名で持っていたもの（`record.photo` /
#: `interact.notify` / `view.total`）は**別名を残さず**ここへ統合した。
#: 別名を残すと、片方だけ直したときに静かに食い違う。
_CATALOG: tuple[CapabilityDefinition, ...] = (
    # --- DATA: 何を記録するか ---------------------------------------
    _c("data.entity", _L.DATA, "1件分のデータ", "繰り返し記録する1件の型を持つ",
       _S.IMPLEMENTED),
    _c("data.text", _L.DATA, "文字の記録", "文字を残す", _S.IMPLEMENTED,
       detection_keywords=("メモ", "名前", "タイトル", "内容")),
    _c("data.number", _L.DATA, "数値の記録", "数を残す", _S.IMPLEMENTED,
       detection_keywords=("金額", "値段", "点数", "回数", "体重", "サイズ", "個数")),
    _c("data.date", _L.DATA, "日付の記録", "いつのことかを残す", _S.IMPLEMENTED,
       detection_keywords=("日付", "いつ", "期限", "何日")),
    _c("data.choice", _L.DATA, "選択肢からの記録", "決まった候補から選ぶ", _S.IMPLEMENTED,
       detection_keywords=("カテゴリ", "種類", "分類", "選択肢")),
    _c("data.bool", _L.DATA, "済/未済の記録", "終わったかどうかを残す", _S.IMPLEMENTED,
       detection_keywords=("チェック", "済み", "完了したか")),
    _c("data.photo", _L.DATA, "写真の記録", "写真そのものを残す", _S.PARTIAL,
       detection_keywords=("写真", "画像", "撮った"), nearest_supported_id="data.text",
       limitation="写真そのものは扱えません。ファイル名やメモを文字として残します"),
    _c("data.audio", _L.DATA, "音の記録", "音そのものを残す", _S.PARTIAL,
       detection_keywords=("録音", "音声で残", "音を"), nearest_supported_id="data.text",
       limitation="音そのものは扱えません。名前やメモを文字として残します"),

    # --- VIEW: どう見せるか -----------------------------------------
    _c("view.list", _L.VIEW, "一覧で見る", "記録を並べて見る", _S.IMPLEMENTED,
       detection_keywords=("一覧", "リストで見", "並べて")),
    _c("view.grid", _L.VIEW, "タイル状に見る", "並べて見渡す", _S.IMPLEMENTED,
       detection_keywords=("タイル", "グリッド")),
    _c("view.metric", _L.VIEW, "合計を大きく見る", "合計・残高を1つの数として見る",
       _S.IMPLEMENTED,
       detection_keywords=("合計", "総額", "残高", "いくら使った", "トータル")),
    _c("view.bar_chart", _L.VIEW, "棒グラフで見る", "量を棒で見比べる", _S.IMPLEMENTED,
       detection_keywords=("棒グラフ", "グラフで", "グラフにして")),
    _c("view.tabs", _L.VIEW, "タブで切り替える", "画面を切り替える", _S.IMPLEMENTED,
       detection_keywords=("タブ", "切り替え")),
    _c("view.group_compare", _L.VIEW, "グループごとに比べる",
       "分類ごとに集計して見比べる", _S.IMPLEMENTED,
       detection_keywords=("比べ", "比較", "ごとに集計")),
    _c("view.trend", _L.VIEW, "推移を見る", "時間の流れに沿った変化を見る", _S.PARTIAL,
       detection_keywords=("推移", "伸び", "変化をグラフ"),
       nearest_supported_id="view.bar_chart",
       limitation="時系列のグラフはまだ描けません。日付順の一覧と合計で近似します"),
    _c("view.map", _L.VIEW, "地図で見る", "場所を地図の上で見る", _S.MISSING,
       detection_keywords=("地図", "マップ", "地図上"), nearest_supported_id="view.list",
       limitation="地図は表示できません"),
    _c("view.heatmap", _L.VIEW, "濃淡で分布を見る", "分布を色の濃さで見る", _S.MISSING,
       detection_keywords=("ヒートマップ", "色の濃さ", "色を濃く", "濃淡"),
       nearest_supported_id="view.bar_chart", limitation="濃淡の表示はできません"),
    _c("view.calendar", _L.VIEW, "カレンダーで見る", "月の形で見る", _S.MISSING,
       detection_keywords=("カレンダー", "月表示", "月ごとの表"),
       nearest_supported_id="view.list", limitation="カレンダー表示はできません"),
    _c("view.line_chart", _L.VIEW, "折れ線で見る", "変化を線で見る", _S.MISSING,
       detection_keywords=("折れ線",), nearest_supported_id="view.bar_chart",
       limitation="折れ線グラフは描けません"),

    # --- INTERACT: 画面で何をするか ---------------------------------
    _c("interact.check_off", _L.INTERACT, "1件ずつ済みにする",
       "終わったものを消していく", _S.IMPLEMENTED,
       detection_keywords=("ひとつずつ", "消して", "チェックできる")),
    _c("interact.edit", _L.INTERACT, "後から直す", "記録を編集する", _S.IMPLEMENTED),
    _c("interact.audio_mix", _L.INTERACT, "音を重ねて組み合わせる",
       "内蔵された複数の音を同時に鳴らして組み合わせる", _S.PARTIAL,
       detection_keywords=("音を組み合わせ", "音を重ね", "サウンドを組み合わせ"),
       limitation="内蔵音源の組み合わせまで対応しています。任意の音声素材の取り込みはまだできません"),
    _c("interact.filter", _L.INTERACT, "絞り込む", "条件で絞って見る", _S.MISSING,
       detection_keywords=("絞り込", "フィルタ"), nearest_supported_id="view.list",
       limitation="絞り込みはまだできません"),

    # --- EFFECT: 外へ何をするか（安全審査の対象） -------------------
    _c("effect.share", _L.EFFECT, "ほかの人へ送る・共有する", "外の相手へ渡す",
       _S.MISSING, safety=_F.SENSITIVE,
       detection_keywords=("共有", "シェア", "送って", "送信", "公開", "招待"),
       limitation="共有機能はまだありません"),
    _c("effect.notify", _L.EFFECT, "通知を出す", "時間や状態をきっかけに知らせる",
       _S.MISSING, safety=_F.SENSITIVE,
       detection_keywords=("通知", "リマインド", "お知らせして", "アラーム"),
       limitation="通知は送れません"),
    _c("effect.camera", _L.EFFECT, "カメラを使う", "その場で撮る", _S.MISSING,
       safety=_F.SENSITIVE, detection_keywords=("カメラ", "撮影"),
       limitation="カメラは使えません"),
    _c("effect.location", _L.EFFECT, "現在地を取得する", "いまどこかを知る", _S.MISSING,
       safety=_F.SENSITIVE, detection_keywords=("現在地", "位置情報", "GPS"),
       limitation="現在地は取得できません"),
    _c("effect.contacts", _L.EFFECT, "連絡先を読む", "アドレス帳を使う", _S.MISSING,
       safety=_F.SENSITIVE, detection_keywords=("連絡先", "アドレス帳"),
       limitation="連絡先は読めません"),
    _c("effect.payment", _L.EFFECT, "支払いを扱う", "お金のやり取りをする", _S.MISSING,
       safety=_F.SENSITIVE, detection_keywords=("決済", "課金", "支払い機能", "送金"),
       limitation="支払いは扱えません"),
    _c("effect.http", _L.EFFECT, "外部サービスへ接続する", "他のサービスと繋ぐ",
       _S.MISSING, safety=_F.SENSITIVE,
       detection_keywords=("API", "外部サービスと連携", "連携して"),
       limitation="外部サービスとは繋げません"),
    _c("effect.media_compose", _L.EFFECT, "音や画像を合成する",
       "素材を組み合わせて新しい音・画像を作る", _S.MISSING, safety=_F.SENSITIVE,
       detection_keywords=("組み合わせ", "合成"),
       limitation="音や画像を合成することはできません"),

    # --- SIMULATE: 時間経過・生成的な振る舞い -----------------------
    # **`SAFE` である。** 持っていないだけで、外部へ何かをするわけでは
    # ない。確認の対象は「外へ作用するもの」に限る（005 §3.1）。
    _c("simulate.loop", _L.SIMULATE, "時間を進める・ゲームとして動かす",
       "放っておいても状態が変わる", _S.IMPLEMENTED,
       detection_keywords=("ゲーム", "育て", "育成")),
)

SEMANTIC_CAPABILITIES: dict[str, CapabilityDefinition] = {c.id: c for c in _CATALOG}


def capability(capability_id: str) -> CapabilityDefinition | None:
    return SEMANTIC_CAPABILITIES.get(capability_id)


def capability_ids() -> tuple[str, ...]:
    return tuple(SEMANTIC_CAPABILITIES)


def is_known_capability(capability_id: str) -> bool:
    """**知らない ID を黙って通さない。**"""
    return capability_id in SEMANTIC_CAPABILITIES
