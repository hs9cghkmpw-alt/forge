"""Capability Layer(FORGE-ARCHITECTURE-REVIEW-AND-IMPLEMENT-005 §32、
2026-08-13)。

`docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW.md` §6〜§9で採用した
Vertical Sliceの実装:

    Missing Capability Detection
      → Solution Hypothesis
      → User Correction
      → Revised Capability Spec

**この層がやらないこと(重要)**:

* Capabilityを**自動生成しない**。Registryは人手管理の静的テーブルで
  あり、AIは読むだけで書き換えられない(レビュー §3.2 / §5)。
  Flutterは動的コード実行ができないため、AIにWidgetを作らせる方式は
  そもそも成立しない。
* LLMを一切呼ばない。`conversation_policy.py`と同じく純粋関数の集まり
  であり、同じ入力なら常に同じ出力になる。
* 実装していないものを「できる」と言わない(レビュー F3)。Registryに
  無いものは`supported=False`のまま扱い、会話でも正直にそう伝える。

**3層に分けた理由**(レビュー §3.1): 構想は`text` `number` `chart`
`map` `notification`を同じ平面に並べていたが、これらは抽象度が違う
(`number`は型、`chart`は表示、`notification`は権限の要るOS機能)。
同じRegistryへ入れると依存関係が表現できず、安全なものと危険なものが
混在する。3層に分けると、**EffectCapabilityだけが安全審査の対象**に
なり、粒度の議論も終わる。

    DataCapability   : 何を記録するか   (text/number/date/choice/bool)
    ViewCapability   : どう見せるか     (list/card/grid/chart/tabs)
    EffectCapability : 外へ何をするか   (share/notify/camera/location…)

`supported`は`app/ai/validators/schema_validator.py`のWidget Registry
(v1.8で19種)と1:1で対応させて手で維持する。**Registryを増やす際は
Validator・Runtime・ここの3箇所を同時に更新すること**(TD37: 登録漏れで
4種のWidgetが描画不能だった実バグ)。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

__all__ = [
    "CAPABILITY_QUESTION_KEY_PREFIX",
    "CAPABILITY_REGISTRY",
    "Capability",
    "CapabilityLayer",
    "CorrectionTarget",
    "SolutionHypothesis",
    "build_hypothesis",
    "capability_by_id",
    "classify_correction",
    "detect_capabilities",
    "has_buildable_gap",
    "missing_capabilities",
    "CapabilityTurn",
    "CapabilityTurnKind",
    "resolve_capability_turn",
    "revise_hypothesis",
]


class CapabilityLayer(str, Enum):
    """Capabilityの層。安全審査の対象は`EFFECT`だけである。"""

    DATA = "data"
    VIEW = "view"
    EFFECT = "effect"


@dataclass(frozen=True)
class Capability:
    """1つのCapabilityの定義(静的、人手管理)。"""

    id: str
    layer: CapabilityLayer
    label_ja: str
    """ユーザーへ見せる日本語。内部IDをそのままUIへ出さない
    (§9で実際に起きた「「Shopping」「Diary」」の再発防止)。"""

    supported: bool
    """Forgeが**実際に**作れるかどうか。Widget Registryに実装がある場合のみ`True`。"""

    widget_types: tuple[str, ...] = ()
    """対応するForge LanguageのWidget型(`supported=True`の場合のみ意味を持つ)。"""

    requires_confirmation: bool = False
    """実行前にユーザーの確認が要るか。EffectCapabilityのみ`True`になりうる
    (指示書:「ユーザーが欲しいと言ったから」だけで自動的に危険Capabilityを
    実行可能にしない)。"""

    detection_keywords: tuple[str, ...] = ()
    """このCapabilityが要求されたと判定する語。決定的なsubstringマッチング
    (`forge_ai/core/lexicon.py`と同じ手法。形態素解析は使わない)。"""

    nearest_supported_id: str | None = None
    """`supported=False`のとき、代わりに提案できる実装済みCapability。
    `None`なら代替が無い(その場合は正直に「できない」と言う)。"""


def _cap(*args, **kwargs) -> Capability:
    return Capability(*args, **kwargs)


# ---------------------------------------------------------------------------
# Capability Registry(静的・人手管理)
#
# `supported=True`のものは、Widget Registry v1.8(19種)に実装がある。
# `supported=False`のものは「よく要求されるが、まだ作れない」もので、
# **検出のためだけに**列挙している——実装済みだと偽らないための一覧である。
# ---------------------------------------------------------------------------
_REGISTRY: tuple[Capability, ...] = (
    # --- Data(安全。何を記録するか) ---------------------------------
    _cap("data.text", CapabilityLayer.DATA, "文字の記録", True, ("text_field",),
         detection_keywords=("メモ", "名前", "タイトル", "内容")),
    _cap("data.number", CapabilityLayer.DATA, "数値の記録", True, ("text_field", "slider"),
         detection_keywords=("金額", "値段", "点数", "回数", "体重", "サイズ", "個数")),
    _cap("data.date", CapabilityLayer.DATA, "日付の記録", True, ("date_field",),
         detection_keywords=("日付", "いつ", "期限", "何日")),
    _cap("data.choice", CapabilityLayer.DATA, "選択肢からの記録", True, ("choice_field",),
         detection_keywords=("カテゴリ", "種類", "分類", "選択肢")),
    _cap("data.bool", CapabilityLayer.DATA, "済/未済の記録", True, ("checkbox", "checklist"),
         detection_keywords=("チェック", "済み", "完了したか")),
    # 未実装のData。
    _cap("data.photo", CapabilityLayer.DATA, "写真の記録", False,
         detection_keywords=("写真", "画像", "撮った"), nearest_supported_id="data.text"),
    _cap("data.audio", CapabilityLayer.DATA, "音声の記録", False,
         detection_keywords=("録音", "音声で残"), nearest_supported_id="data.text"),

    # --- View(安全。どう見せるか) -----------------------------------
    _cap("view.list", CapabilityLayer.VIEW, "一覧で見る", True, ("list", "record_list_view", "checklist"),
         detection_keywords=("一覧", "リストで見", "並べて")),
    _cap("view.grid", CapabilityLayer.VIEW, "タイル状に見る", True, ("record_list_view",),
         detection_keywords=("タイル", "グリッド")),
    _cap("view.bar_chart", CapabilityLayer.VIEW, "棒グラフで見る", True, ("bar_chart",),
         detection_keywords=("棒グラフ", "グラフで", "グラフにして")),
    _cap("view.tabs", CapabilityLayer.VIEW, "タブで切り替える", True, ("tab_view",),
         detection_keywords=("タブ", "切り替え")),
    # 未実装のView。§33の例(釣果を地図で)はここに当たる。
    _cap("view.map", CapabilityLayer.VIEW, "地図で見る", False,
         detection_keywords=("地図", "マップ", "地図上"), nearest_supported_id="view.list"),
    _cap("view.heatmap", CapabilityLayer.VIEW, "濃淡で分布を見る", False,
         detection_keywords=("ヒートマップ", "色の濃さ", "色を濃く", "濃淡"),
         nearest_supported_id="view.bar_chart"),
    _cap("view.calendar", CapabilityLayer.VIEW, "カレンダーで見る", False,
         detection_keywords=("カレンダー", "月表示", "月ごとの表"), nearest_supported_id="view.list"),
    _cap("view.line_chart", CapabilityLayer.VIEW, "推移を折れ線で見る", False,
         detection_keywords=("折れ線", "推移をグラフ", "変化をグラフ"),
         nearest_supported_id="view.bar_chart"),

    # --- Effect(安全審査の対象。外へ何をするか) ---------------------
    # いずれも未実装。**実装されても自動では許可しない**——
    # `requires_confirmation=True`により、既存のCONFIRM Policyへ直結する。
    _cap("effect.share", CapabilityLayer.EFFECT, "ほかの人へ送る・共有する", False,
         requires_confirmation=True,
         detection_keywords=("共有", "シェア", "送って", "送信", "公開", "招待")),
    _cap("effect.notify", CapabilityLayer.EFFECT, "通知を出す", False,
         requires_confirmation=True,
         detection_keywords=("通知", "リマインド", "お知らせして", "アラーム")),
    _cap("effect.camera", CapabilityLayer.EFFECT, "カメラを使う", False,
         requires_confirmation=True,
         detection_keywords=("カメラ", "撮影")),
    _cap("effect.location", CapabilityLayer.EFFECT, "現在地を取得する", False,
         requires_confirmation=True,
         detection_keywords=("現在地", "位置情報", "GPS")),
    _cap("effect.contacts", CapabilityLayer.EFFECT, "連絡先を読む", False,
         requires_confirmation=True,
         detection_keywords=("連絡先", "アドレス帳")),
    _cap("effect.payment", CapabilityLayer.EFFECT, "支払いを扱う", False,
         requires_confirmation=True,
         detection_keywords=("決済", "課金", "支払い機能", "送金")),
    _cap("effect.http", CapabilityLayer.EFFECT, "外部サービスへ接続する", False,
         requires_confirmation=True,
         detection_keywords=("API", "外部サービスと連携", "連携して")),
)

CAPABILITY_REGISTRY: dict[str, Capability] = {c.id: c for c in _REGISTRY}


def capability_by_id(capability_id: str) -> Capability | None:
    return CAPABILITY_REGISTRY.get(capability_id)


# ---------------------------------------------------------------------------
# 検出
# ---------------------------------------------------------------------------


def detect_capabilities(text: str) -> tuple[Capability, ...]:
    """発話から、要求されているCapabilityを決定的に列挙する。

    **完全な自然言語理解ではない**(このセッション全体の方針どおり、
    形態素解析ライブラリという新規依存は追加しない)。検出漏れは
    「今までどおりの経路を通る」だけであり、誤検出だけが害になるため、
    キーワードは**その語が出たら要求とみなして良いもの**に絞ってある。

    Registry定義順で返す(同じ入力なら常に同じ順序)。
    """
    if not text:
        return ()
    lowered = text.lower()
    found: list[Capability] = []
    for capability in _REGISTRY:
        if any(keyword.lower() in lowered for keyword in capability.detection_keywords):
            found.append(capability)
    return tuple(found)


def missing_capabilities(capabilities: tuple[Capability, ...]) -> tuple[Capability, ...]:
    """`supported=False`のものだけを返す。

    ここで返るものは**まだ作れない**。呼び出し側は、これを
    「作れるふり」に使ってはならない(レビュー F3)。
    """
    return tuple(c for c in capabilities if not c.supported)


# ---------------------------------------------------------------------------
# Solution Hypothesis
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SolutionHypothesis:
    """Forgeが「こういう形なら作れます」と提示する仮説。

    レビュー §3.4: 「違う」の曖昧さは、**Forgeが出した仮説の構造**で
    受け止める。仮説がdata/view/effectsに分かれているから、ユーザーの
    否定がどこに向いているかを分類できる(`classify_correction()`)。
    """

    # 各層は「その層で検討対象になっているCapability全部」を持つ。
    # 実装済みかどうかで分けずに1つのタプルへ入れるのが要点である。
    data: tuple[Capability, ...] = ()
    view: tuple[Capability, ...] = ()
    effects: tuple[Capability, ...] = ()

    spec_notes: tuple[str, ...] = ()
    """ユーザーが言った、**Platform Capabilityでは表せない仕様の詳細**。

    §37の区別の受け皿である。「脈拍も記録したい」の「脈拍」は、Forgeの
    能力(数値を記録できる)を1つも増やさない——増えるのは**このToolが
    何を記録するか**という仕様である。ここへ入れておかないと、
    ユーザーが確かに言ったことが、BUILDへ届かないまま消える。

    Platform Capabilityと混ぜないために、別のフィールドにしている。
    ここに何が入っても`missing`は変わらない(能力の不足ではないため)。
    """

    revision: int = 0
    """User Correctionによって作り直された回数。無限ループ防止に使う
    (レビュー F2: 仮説も3回で打ち切る)。"""

    @property
    def missing(self) -> tuple[Capability, ...]:
        """まだ作れないもの。**全層から毎回導出する**。

        FORGE-USER-GUIDED-SELF-EXTENSION-006 指摘2で見つかった実バグの
        修正(2026-08-13)。以前`missing`は**フィールドとして保存**されて
        おり、`revise_hypothesis()`が訂正対象層のMissingで全体を置換して
        いた。その結果:

            初期「写真を記録して地図で見たい」→ missing=[data.photo, view.map]
            訂正「違う、色の濃さで見たい」    → missing=[view.heatmap]
                                                       ^^ data.photo が消滅

        原因は「導出できる値をフィールドとして保存し、部分的に更新した」
        ことであり、`missing`の更新漏れではない。**保存をやめれば、
        更新漏れという不具合の形そのものが無くなる**。層を差し替えれば
        Missingは自動的に整合する。

        「保持が既定」という原則を、層の中身だけでなくMissing状態にも
        成立させるための構造上の担保である。
        """
        return tuple(
            c for c in (self.data + self.view + self.effects) if not c.supported
        )

    @property
    def buildable(self) -> tuple[Capability, ...]:
        """今すぐ作れるもの(Data + View)。ユーザーへ提示する形はこれ。"""
        return tuple(c for c in (self.data + self.view) if c.supported)

    def is_empty(self) -> bool:
        return not (self.data or self.view or self.effects)

    def to_message(self) -> str:
        """会話の1ターンとして出す日本語。専用画面へは倒さない
        (指示書4章と同じ方針)。

        **できないことを先に、正直に言う**。そのあとで、作れる形を出す。
        「作れるふりをしてから実は作れない」という順序にはしない。
        """
        parts: list[str] = []
        if self.missing:
            names = "・".join(c.label_ja for c in self.missing)
            parts.append(f"{names}は、今のForgeではまだ作れません。")

        buildable = [c.label_ja for c in self.buildable]
        if buildable:
            parts.append("代わりに、" + "・".join(buildable) + "ができる形なら作れます。")

        # Semantic分解が「もっと近い代替」を知っている場合、それを添える
        # (FORGE-USER-GUIDED-SELF-EXTENSION-006 §30・§59)。
        # 「地図で濃淡」は4つのPrimitiveが要るが、同じ困りごとに答える
        # 「場所ごとの集計」は1つで足りる——この差を黙っていると、
        # ユーザーは「できない」としか受け取れない。
        # **勝手に代替版を作らず、短く確認する**(§59)。
        hint = self._closer_alternative_hint()
        if hint:
            parts.append(hint)

        confirm_needed = [c.label_ja for c in self.effects if c.requires_confirmation]
        if confirm_needed:
            parts.append("(" + "・".join(confirm_needed) + "は、作る前に確認させてください。)")

        parts.append("この形で進めますか？違うところがあれば教えてください。")
        return "".join(parts)

    def _closer_alternative_hint(self) -> str:
        """`semantic_capability`の分解を使い、より少ない不足で成立する
        代替があれば一言添える。分解表に無ければ何も言わない
        (**知らないことを、それらしく言わない**)。"""
        from app.ai.runtime.semantic_capability import (  # noqa: PLC0415 — 循環import回避
            SEMANTIC_LABELS_JA,
            decompose,
        )

        for gap in self.missing:
            decomposition = decompose(gap.id)
            if decomposition is None:
                continue
            alternative = decomposition.nearest_alternative()
            if alternative is None:
                continue
            label = SEMANTIC_LABELS_JA.get(alternative[0])
            if label:
                return f"({label}なら、もう少しで作れるようになります。)"
        return ""

    def to_build_note(self) -> str:
        """BUILDへ渡す`build_brief`へ追記する一文
        (FORGE-USER-GUIDED-SELF-EXTENSION-006 §16、2026-08-13)。

        **これが無いと、ユーザーが「それでいい」と言って合意した内容が
        生成へ一切反映されない**。訂正の往復で仕様を育てても、Compilerへ
        届かなければProductとしては未完成である(§16はこの接続をE2Eで
        確認せよと明示している)。

        `to_message()`と別にしているのは、宛先が違うから:
        `to_message()`はユーザーへの問いかけ、こちらは生成器への指示である。
        作れないもの(`missing`)は**書かない**——Compilerに作れないものを
        指示しても、実現できないか、実現したふりになるだけである。
        """
        parts: list[str] = []
        buildable = [c.label_ja for c in self.buildable]
        if buildable:
            parts.append("ユーザーと合意した形: " + "・".join(buildable) + "。")
        if self.spec_notes:
            # ユーザーが言った具体的な要望を、そのままCompilerへ渡す。
            parts.append("ユーザーの追加要望: " + " / ".join(self.spec_notes) + "。")
        return "".join(parts)


_MAX_HYPOTHESIS_REVISIONS = 3


def has_buildable_gap(hypothesis: SolutionHypothesis | None) -> bool:
    """仮説の提示を**会話の1ターンとして出すべきか**。

    MISSINGがEffectだけの場合は`False`を返す。理由:

    既存のCONFIRM Policy(`conversation_policy.requires_confirmation()`)が、
    共有・送信・削除などを**既に**捕まえて確認へ倒している。同じ発話に
    対してCapability層も「共有はできません」と割り込むと、確認と仮説が
    二重に出て会話が壊れる。**安全判定が先、Capabilityの話は後**という
    順序を、ここで明示的に固定する(50セッションのうち3件——
    `schedule_shared`・`share_1`・`risky_1`——がこれに当たり、実際に
    走らせて確認した)。

    Data/Viewの不足(地図・カレンダー・写真など)は安全とは無関係なので、
    そちらだけが仮説として会話に出る。

    **正直な既知の制限(TECH_DEBT)**: 共有系は「確認は取るが、実際には
    まだ実装が無い」状態のままである。確認文自体を「できないこと」に
    合わせて書き換えるのは、指示書001 §4で定めたCONFIRMの意味を変える
    ことになるため、この Vertical Slice の範囲外とした。
    """
    if hypothesis is None:
        return False
    return any(c.layer is not CapabilityLayer.EFFECT for c in hypothesis.missing)


def build_hypothesis(text: str) -> SolutionHypothesis | None:
    """発話からSolution Hypothesisを組み立てる。

    **`None`を返す条件が設計の要**(レビュー §6「既存経路に一切触れない」):
    MISSINGが1つも無ければ`None`を返し、呼び出し側は今までどおりの
    BUILD経路へ進む。つまりこの機能は、**作れないものを頼まれたときにだけ**
    会話へ現れる。既存の50セッションの挙動は変わらない(回帰テスト済み)。
    """
    detected = detect_capabilities(text)
    missing = missing_capabilities(detected)
    if not missing:
        return None

    # 各層には「検出されたもの(未実装含む)+ 代替」をまとめて入れる。
    # `missing`は保存せず、層から導出する(指摘2の修正、上記docstring参照)。
    substitutes: list[Capability] = []
    for gap in missing:
        if gap.nearest_supported_id is None:
            continue
        alternative = CAPABILITY_REGISTRY.get(gap.nearest_supported_id)
        if alternative is not None and alternative not in detected and alternative not in substitutes:
            substitutes.append(alternative)

    combined = detected + tuple(substitutes)
    return SolutionHypothesis(
        data=tuple(c for c in combined if c.layer is CapabilityLayer.DATA),
        view=tuple(c for c in combined if c.layer is CapabilityLayer.VIEW),
        effects=tuple(c for c in combined if c.layer is CapabilityLayer.EFFECT),
    )


# ---------------------------------------------------------------------------
# User Correction
# ---------------------------------------------------------------------------


class CorrectionTarget(str, Enum):
    """ユーザーの「違う」が、仮説の**どの部分**に向いているか
    (レビュー §3.4、構想§30-Dへの回答)。"""

    DATA = "data"
    VIEW = "view"
    EFFECT = "effect"
    PROBLEM = "problem"
    """そもそも困りごとの理解が違う。これだけは会話を巻き戻す。"""

    ACCEPTED = "accepted"
    """否定ではなく、提案を受け入れた。"""

    UNCLEAR = "unclear"
    """「違う」ことは分かるが、どこがかは分からない。聞き返す。"""


_ACCEPT_KEYWORDS: tuple[str, ...] = (
    "それでいい", "それで良い", "でいい", "で良い", "いいね", "いいよ", "お願い",
    "はい", "うん", "ええ", "そうそう", "その感じ", "そんな感じ", "大丈夫",
    "ok", "オッケー", "進めて", "それで",
)

# 「〜も追加したい」のように、**何かを足したい**ことを示す語。
# §10が「addition marker」を独立した信号として挙げているとおり、
# これはCapability語の有無とは別の軸である。
#
# **なぜ語彙を足すだけでは解けないか**: 「いいけど脈拍も追加したい」は
# Correctionだが、「脈拍」はCapability Registryに無い。ここで「脈拍」を
# キーワードへ足すのは対症療法である——次は「血糖値」で同じことが起きる。
#
# 正しい理解は§37の区別にある。「脈拍」は**Product Spec**(記録する項目の
# 名前)であって、**Platform Capability**(数値を記録できるか)ではない。
# Forgeは既に数値を記録できるので、必要な能力は増えていない。増えたのは
# **このToolの仕様**である。したがって、追加マーカーがあれば「Dataへの
# 訂正」と分類し、名詞そのものは`spec_notes`(下記)へ保持する。
_ADDITION_MARKERS: tuple[str, ...] = (
    "も追加", "も記録", "も残", "も入れ", "も見", "も欲しい", "も要る", "も必要",
    "追加したい", "追加して", "足したい", "足して", "増やしたい",
)

# 肯定の中に**変更意図**が混ざっていることを示す語。
# 「うん、地図でいい」は合意だが、「うん、でも地図じゃなくて一覧がいい」は
# 訂正である。この差を作っているのは肯定語ではなく、この対比語である。
_CONTRAST_MARKERS: tuple[str, ...] = (
    "でも", "けど", "けれど", "ただ", "しかし", "その代わり", "かわりに", "代わりに",
)

_PROBLEM_KEYWORDS: tuple[str, ...] = (
    "そもそも", "そういうことじゃない", "そうじゃなくて", "やりたいのは", "困ってるのは",
)

_NEGATION_KEYWORDS: tuple[str, ...] = (
    "違う", "ちがう", "じゃない", "ではなく", "でなく", "いらない",
)


# 「〜したい」「〜だけ」等、**目的を述べ直している**ことを示す語。
# Capabilityが1つも検出できなかった否定文が、これらを含むなら、
# ユーザーは見せ方ではなく**やりたいこと自体**を言い直している。
_GOAL_RESTATEMENT_MARKERS: tuple[str, ...] = (
    "したい", "しよう", "ほしい", "欲しい", "たいのは", "だけ", "ではなくて",
    "本当は", "やりたい", "決めたい", "知りたい",
)

# 否定語そのものを除いた残りが、この文字数未満なら「情報が無い」と扱う。
# 「違う」「ちがう」だけの返事を、目的の言い直しと誤認しないため。
_MIN_RESTATEMENT_LENGTH = 6


def _restates_a_goal(lowered: str) -> bool:
    """否定に加えて、やりたいことの言い直しが含まれているか。"""
    remainder = lowered
    for negation in _NEGATION_KEYWORDS:
        remainder = remainder.replace(negation, "")
    remainder = remainder.strip("、。 　.")
    if len(remainder) < _MIN_RESTATEMENT_LENGTH:
        return False
    return any(marker in remainder for marker in _GOAL_RESTATEMENT_MARKERS)


def classify_correction(text: str, hypothesis: SolutionHypothesis) -> CorrectionTarget:
    """ユーザーの返答を、仮説のどの部分への訂正かに分類する。

    **判定は「語の出現」ではなく「態度(stance)」から始める**
    (FORGE-USER-GUIDED-SELF-EXTENSION-006 指摘3の修正、2026-08-13)。

    以前は`detect_capabilities()`を先に見ていたため、肯定文にCapability語が
    含まれるだけで訂正へ倒れていた。実測した誤分類:

        「うん、地図でいい」      → VIEW(訂正)   ← 本当は合意
        「はい、その地図の感じで」  → VIEW(訂正)   ← 本当は合意
        「そうそう、一覧で大丈夫」  → VIEW(訂正)   ← 本当は合意

    原因は**語の出現と変更意図を同一視していた**ことである。
    「うん、地図でいい」の「地図」は**合意の対象**であって変更要求では
    ない。ACCEPT判定を先頭へ動かすだけでは足りない——それだと
    「うん、でも地図じゃなくて一覧がいい」まで合意になってしまう。

    したがって3段階で判定する:

        1. 態度   : 否定か、肯定か、どちらでもないか
        2. 対比   : 肯定の中に変更意図(「でも」等)があるか
        3. 対象   : 変更意図があるとき、どの層への訂正か

    否定を肯定より先に見るのは、「そうじゃない」のように**肯定語を
    部分文字列として含む否定**があるためである。
    """
    lowered = (text or "").lower()

    # 明示的なProblem語は最優先(態度以前に、話の対象が違う)。
    if any(k in lowered for k in _PROBLEM_KEYWORDS):
        return CorrectionTarget.PROBLEM

    negated = any(k in lowered for k in _NEGATION_KEYWORDS)
    affirmed = any(k in lowered for k in _ACCEPT_KEYWORDS)
    contrasted = any(k in lowered for k in _CONTRAST_MARKERS)

    # 肯定のみ(対比なし)。Capability語が含まれていても、それは
    # **合意の対象**であって変更要求ではない。
    if affirmed and not negated and not contrasted:
        return CorrectionTarget.ACCEPTED

    detected = detect_capabilities(text)
    if detected:
        # 変更意図がある(否定・対比・あるいは単に別のことを言っている)。
        # 複数層が検出された場合、外側(影響が大きい方)を優先する。
        for layer, target in (
            (CapabilityLayer.EFFECT, CorrectionTarget.EFFECT),
            (CapabilityLayer.VIEW, CorrectionTarget.VIEW),
            (CapabilityLayer.DATA, CorrectionTarget.DATA),
        ):
            if any(c.layer is layer for c in detected):
                return target

    if any(marker in lowered for marker in _ADDITION_MARKERS):
        # 何かを足したいことは分かるが、それがCapability Registryに
        # 無い場合(「脈拍も追加したい」)。**分からないから聞き返す**の
        # ではなく、**記録する項目への訂正**だと分かっている。
        # 名詞はProduct Specとして`revise_hypothesis()`が保持する。
        return CorrectionTarget.DATA

    if negated:
        # 否定はあったが、Capabilityは1つも検出できなかった。ここで
        # `PROBLEM`と`UNCLEAR`を分ける必要がある(§39 Case C と Case D)。
        #
        # **語彙リストに「そうじゃない」を足すのでは解けない**。
        # 実際に両者を分けているのは語ではなく**構造**である:
        #
        #   Case C「そうじゃない。子供の送り迎えの担当だけ決めたい」
        #       → 否定 + **やりたいことの言い直し**
        #   Case D「違う」
        #       → 否定のみ。何が違うのかの情報が無い
        if _restates_a_goal(lowered):
            return CorrectionTarget.PROBLEM
        return CorrectionTarget.UNCLEAR

    if affirmed:
        # 肯定 + 対比だが、変更先のCapabilityが分からない
        # (例:「うん、でもちょっと違うんだよね」)。聞き返す。
        return CorrectionTarget.UNCLEAR

    return CorrectionTarget.UNCLEAR


# 「も」「追加」等は**足したい**という意味であり、置き換えではない。
# 「違う」「じゃなくて」は置き換えである。この区別が無いと、
# 「脈拍も記録したい」で既存の項目が全部消える(§39 Case B)。
_ADDITIVE_MARKERS: tuple[str, ...] = ("も記録", "も残", "も入れ", "も見", "も欲しい", "追加", "足して", "increase")
_REPLACING_MARKERS: tuple[str, ...] = ("違う", "ちがう", "じゃなくて", "ではなく", "でなく", "やめて", "いらない")


def _spec_note_from(text: str) -> str:
    """発話から、Compilerへ渡す仕様メモを取り出す。

    「いいけど脈拍も追加したい」の「いいけど」は、こちらの提案への
    相槌であって仕様ではない。前置きを落として要望だけ残す。
    句読点までの相槌を落とすだけの決定的な処理であり、要約ではない
    (落とせなければ全文をそのまま残す——情報は失わない)。
    """
    note = (text or "").strip()
    for separator in ("、", "。", ","):
        head, found, tail = note.partition(separator)
        if not found or not tail.strip():
            continue
        lowered = head.lower()
        is_preamble = any(k in lowered for k in _ACCEPT_KEYWORDS + _CONTRAST_MARKERS + _NEGATION_KEYWORDS)
        if is_preamble and len(head) <= 8:
            note = tail.strip()
            break
    # 「いいけど〜」のように句読点が無い場合、対比語で切る。
    for marker in _CONTRAST_MARKERS:
        prefix, found, tail = note.partition(marker)
        if found and len(prefix) <= 4 and tail.strip():
            note = tail.strip()
            break
    return note


def _is_additive_correction(text: str, layer: CapabilityLayer) -> bool:
    """この訂正が「追加」か「置き換え」か。

    明示的な語があればそれに従う。無い場合は層ごとの既定へ倒す:

    * `DATA`は**追加**が既定。記録したい項目を1つ挙げたからといって、
      他の項目を捨てたい人はまずいない。
    * `VIEW`は**置き換え**が既定。見せ方は普通どちらか一方である。
    * `EFFECT`は**置き換え**が既定(安全側。作用を勝手に増やさない)。
    """
    lowered = (text or "").lower()
    if any(marker in lowered for marker in _REPLACING_MARKERS):
        return False
    if any(marker in lowered for marker in _ADDITIVE_MARKERS):
        return True
    return layer is CapabilityLayer.DATA


def revise_hypothesis(
    hypothesis: SolutionHypothesis, text: str, target: CorrectionTarget
) -> SolutionHypothesis | None:
    """訂正を反映した新しい仮説(Revised Capability Spec)を返す。

    `None`を返す場合:

    * `target`が`PROBLEM`: 仮説を直すのではなく、会話を巻き戻すべき
      (呼び出し側がNeed Modelの作り直しへ倒す)。
    * 訂正回数が上限に達した: 無限ループを避ける(レビュー F2)。
      既存の`QuestionStrategy`のEscalationと同じ考え方である。

    **該当する層だけを差し替える**。ユーザーが「見せ方が違う」と言った
    ときに、記録する項目まで作り直さない——それは訂正ではなく作り直しで
    あり、ユーザーがまだ言っていないことを勝手に変えることになる。
    """
    if target is CorrectionTarget.PROBLEM:
        return None
    if hypothesis.revision >= _MAX_HYPOTHESIS_REVISIONS:
        return None
    if target in (CorrectionTarget.ACCEPTED, CorrectionTarget.UNCLEAR):
        return hypothesis

    detected = detect_capabilities(text)
    layer = {
        CorrectionTarget.DATA: CapabilityLayer.DATA,
        CorrectionTarget.VIEW: CapabilityLayer.VIEW,
        CorrectionTarget.EFFECT: CapabilityLayer.EFFECT,
    }[target]
    replacements = tuple(c for c in detected if c.layer is layer)
    if not replacements:
        # Capabilityとしては何も変わらないが、**ユーザーは確かに何かを
        # 言っている**。Product Specの詳細として保持する(§37)。
        # これが無いと「脈拍も」がBUILDへ届かず、黙って消える。
        note = _spec_note_from(text)
        if layer is CapabilityLayer.DATA and note and note not in hypothesis.spec_notes:
            return replace(
                hypothesis,
                spec_notes=hypothesis.spec_notes + (note,),
                revision=hypothesis.revision + 1,
            )
        return hypothesis
    additive = _is_additive_correction(text, layer)

    # 差し替え先も未実装だった場合(§33の「地図」→「色を濃く」=ヒートマップ)、
    # **できないものが1つ減ったふりをしない**。未実装のものも層へ残し、
    # 代替があればそれも並べる。`missing`は層から導出されるので、
    # ここで別途更新する必要は無い(指摘2の修正)。
    substitutes: list[Capability] = []
    for gap in (c for c in replacements if not c.supported):
        if gap.nearest_supported_id is None:
            continue
        alternative = CAPABILITY_REGISTRY.get(gap.nearest_supported_id)
        if alternative is not None and alternative not in replacements and alternative not in substitutes:
            substitutes.append(alternative)

    updated = replacements + tuple(substitutes)
    existing = {
        CapabilityLayer.DATA: hypothesis.data,
        CapabilityLayer.VIEW: hypothesis.view,
        CapabilityLayer.EFFECT: hypothesis.effects,
    }[layer]
    if additive:
        # 「脈拍**も**記録したい」は追加であって置き換えではない。既にある
        # ものを消さずに足す(§39 Case B)。重複は定義順を保ったまま除く。
        merged: list[Capability] = list(existing)
        for capability in updated:
            if capability not in merged:
                merged.append(capability)
        updated = tuple(merged)

    changes: dict[str, object] = {"revision": hypothesis.revision + 1}
    if layer is CapabilityLayer.DATA:
        changes["data"] = updated
    elif layer is CapabilityLayer.VIEW:
        changes["view"] = updated
    else:
        changes["effects"] = updated
    return replace(hypothesis, **changes)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 会話への接続(FORGE-ARCHITECTURE-REVIEW-AND-IMPLEMENT-005 §32)
# ---------------------------------------------------------------------------

CAPABILITY_QUESTION_KEY_PREFIX = "capability_gap:"


class CapabilityTurnKind(str, Enum):
    """Capability層が、この会話ターンで何をすべきか
    (FORGE-USER-GUIDED-SELF-EXTENSION-006 §13のState Machine)。"""

    NONE = "none"
    """何もしない。通常の会話へそのまま進む(既存経路は無変更)。"""

    PRESENT = "present"
    """仮説を提示する(初回、または訂正を反映した改訂版)。"""

    CLARIFY = "clarify"
    """「違う」とだけ言われた。仮説は**捨てずに**保持し、短く1問だけ聞く(§14)。"""

    REWIND = "rewind"
    """「そもそも違う」。Problem理解まで巻き戻す(§15)。"""

    ACCEPT = "accept"
    """合意。BUILDへ進む(§16)。"""


@dataclass(frozen=True)
class CapabilityTurn:
    """`resolve_capability_turn()`の戻り値。

    Engine(`conversation_engine.py`)はこれを`ConversationStepResult`へ
    翻訳し、Router(`routers/ai.py`)がSessionへ永続化する。この層自体は
    Sessionを書き換えない(純粋関数のままにしておくため)。
    """

    kind: CapabilityTurnKind
    message: str = ""
    question_key: str = ""
    hypothesis: SolutionHypothesis | None = None
    target: CorrectionTarget | None = None


def _missing_key(hypothesis: SolutionHypothesis) -> str:
    return CAPABILITY_QUESTION_KEY_PREFIX + ",".join(c.id for c in hypothesis.missing)


def _clarify_question(hypothesis: SolutionHypothesis) -> str:
    """「違う」だけのときに聞く、短い1問(§14)。

    「どこが違いますか？」という丸投げにしない——それはユーザーに
    Forgeの内部構造を考えさせている。**こちらが出した仮説の軸**を
    そのまま二択にして返す。答えるのに考える必要がないのが良い質問である。

    質問攻めにも戻さない: 聞くのは1問だけで、その後は
    `asked_question_keys`に記録されるため繰り返さない。
    """
    has_data = bool(hypothesis.data)
    has_view = bool(hypothesis.view)
    if has_data and has_view:
        return "記録する内容と、見せ方だと、どちらを変えたいですか？"
    if has_view:
        return "見せ方を変えたいですか？それとも記録する内容の方ですか？"
    return "どんなふうに変えたいか、一言で教えてもらえますか？"


CLARIFY_QUESTION_KEY = CAPABILITY_QUESTION_KEY_PREFIX + "clarify"


def resolve_capability_turn(
    latest_user_text: str,
    current_hypothesis: SolutionHypothesis | None,
    asked_question_keys: tuple[str, ...],
) -> CapabilityTurn:
    """Stateful User Correction Loopの中核
    (FORGE-USER-GUIDED-SELF-EXTENSION-006 §13、2026-08-13)。

    **これが以前の`next_capability_turn()`と決定的に違う点**:
    前回の仮説(`current_hypothesis`)を受け取り、**それに対する訂正**
    として解釈する。以前は毎回`build_hypothesis(latest_user_text)`で
    最新発話から作り直していたため、訂正されていない層の文脈が失われて
    いた(§11-12の指摘。実測で再現済み:「魚とサイズと場所を記録して
    地図で見たい」→「違う、色を濃く」で`data`が空になった)。

    Sessionは書き換えない。何をすべきかを返すだけで、永続化は呼び出し側
    (Router)が行う——`conversation_policy.py`と同じく、この層は
    純粋関数の集まりに保つ。
    """
    # --- 仮説がまだ無い: 初回提示するかどうか --------------------------
    if current_hypothesis is None:
        hypothesis = build_hypothesis(latest_user_text)
        if not has_buildable_gap(hypothesis):
            return CapabilityTurn(CapabilityTurnKind.NONE)
        presented = [k for k in asked_question_keys if k.startswith(CAPABILITY_QUESTION_KEY_PREFIX)]
        if len(presented) >= _MAX_HYPOTHESIS_REVISIONS:
            return CapabilityTurn(CapabilityTurnKind.NONE)
        key = _missing_key(hypothesis)
        if key in asked_question_keys:
            return CapabilityTurn(CapabilityTurnKind.NONE)
        return CapabilityTurn(
            CapabilityTurnKind.PRESENT, message=hypothesis.to_message(),
            question_key=key, hypothesis=hypothesis,
        )

    # --- 仮説を提示済み: 今の発話は「それへの返事」である --------------
    target = classify_correction(latest_user_text, current_hypothesis)

    if target is CorrectionTarget.ACCEPTED:
        # §39 Case E: 同じ仮説を再提示せず、BUILDへ進む。
        return CapabilityTurn(
            CapabilityTurnKind.ACCEPT, hypothesis=current_hypothesis, target=target
        )

    if target is CorrectionTarget.PROBLEM:
        # §15: Capabilityの差し替えではなく、困りごとの理解から作り直す。
        return CapabilityTurn(CapabilityTurnKind.REWIND, target=target)

    if target is CorrectionTarget.UNCLEAR:
        # §14: 仮説を**捨てない**。既に一度聞いていれば、もう聞かない
        # (質問攻めにしない)——その場合は通常の会話へ戻す。
        if CLARIFY_QUESTION_KEY in asked_question_keys:
            return CapabilityTurn(CapabilityTurnKind.NONE, target=target)
        return CapabilityTurn(
            CapabilityTurnKind.CLARIFY, message=_clarify_question(current_hypothesis),
            question_key=CLARIFY_QUESTION_KEY, hypothesis=current_hypothesis, target=target,
        )

    revised = revise_hypothesis(current_hypothesis, latest_user_text, target)
    if revised is None:
        # 訂正上限。無理に正解へ辿り着こうとせず、通常の会話へ戻す(F2)。
        return CapabilityTurn(CapabilityTurnKind.NONE, target=target)
    if revised is current_hypothesis:
        # その層に新しい要求が見つからなかった。聞き返す。
        if CLARIFY_QUESTION_KEY in asked_question_keys:
            return CapabilityTurn(CapabilityTurnKind.NONE, target=target)
        return CapabilityTurn(
            CapabilityTurnKind.CLARIFY, message=_clarify_question(current_hypothesis),
            question_key=CLARIFY_QUESTION_KEY, hypothesis=current_hypothesis, target=target,
        )

    return CapabilityTurn(
        CapabilityTurnKind.PRESENT, message=revised.to_message(),
        question_key=_missing_key(revised), hypothesis=revised, target=target,
    )
