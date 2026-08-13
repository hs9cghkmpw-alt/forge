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
    "next_capability_turn",
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

    data: tuple[Capability, ...] = ()
    view: tuple[Capability, ...] = ()
    effects: tuple[Capability, ...] = ()
    missing: tuple[Capability, ...] = ()
    revision: int = 0
    """User Correctionによって作り直された回数。無限ループ防止に使う
    (レビュー F2: 仮説も3回で打ち切る)。"""

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

        buildable = [c.label_ja for c in (self.data + self.view)]
        if buildable:
            parts.append("代わりに、" + "・".join(buildable) + "ができる形なら作れます。")

        confirm_needed = [c.label_ja for c in self.effects if c.requires_confirmation]
        if confirm_needed:
            parts.append("(" + "・".join(confirm_needed) + "は、作る前に確認させてください。)")

        parts.append("この形で進めますか？違うところがあれば教えてください。")
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

    supported = tuple(c for c in detected if c.supported)
    # 未実装のものについて、代替として提案できる実装済みCapabilityを補う。
    substitutes: list[Capability] = []
    for gap in missing:
        if gap.nearest_supported_id is None:
            continue
        alternative = CAPABILITY_REGISTRY.get(gap.nearest_supported_id)
        if alternative is not None and alternative not in supported and alternative not in substitutes:
            substitutes.append(alternative)

    combined = supported + tuple(substitutes)
    return SolutionHypothesis(
        data=tuple(c for c in combined if c.layer is CapabilityLayer.DATA),
        view=tuple(c for c in combined if c.layer is CapabilityLayer.VIEW),
        effects=tuple(c for c in detected if c.layer is CapabilityLayer.EFFECT),
        missing=missing,
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
    "それでいい", "それで良い", "でいい", "で良い", "いいよ", "お願い", "はい", "うん", "ok", "オッケー", "進めて",
)

_PROBLEM_KEYWORDS: tuple[str, ...] = (
    "そもそも", "そういうことじゃない", "そうじゃなくて", "やりたいのは", "困ってるのは",
)

_NEGATION_KEYWORDS: tuple[str, ...] = (
    "違う", "ちがう", "じゃない", "ではなく", "でなく", "いらない",
)


def classify_correction(text: str, hypothesis: SolutionHypothesis) -> CorrectionTarget:
    """ユーザーの返答を、仮説のどの部分への訂正かに分類する。

    判定順序に意味がある:

    1. `PROBLEM`(困りごとの理解自体が違う)を最優先で見る。ここが
       違うなら、data/viewをいくら差し替えても無駄だから。
    2. 次に、発話から**新しいCapabilityが検出できるか**を見る。
       検出できた層が、訂正の対象である——ユーザーは「違う」だけでなく
       「こうしたい」を言っていることが多く、そちらの方が情報量が多い。
    3. 否定語だけで、どこがかが分からない場合は`UNCLEAR`。聞き返す。
    4. 否定語も新Capabilityも無ければ`ACCEPTED`。

    `hypothesis`を引数に取るのは、将来「提示した内容と照らして判定する」
    余地を残すため。現時点では層の特定にのみ使う。
    """
    lowered = (text or "").lower()

    if any(k in lowered for k in _PROBLEM_KEYWORDS):
        return CorrectionTarget.PROBLEM

    detected = detect_capabilities(text)
    if detected:
        # 複数層が検出された場合、外側(影響が大きい方)を優先する。
        for layer, target in (
            (CapabilityLayer.EFFECT, CorrectionTarget.EFFECT),
            (CapabilityLayer.VIEW, CorrectionTarget.VIEW),
            (CapabilityLayer.DATA, CorrectionTarget.DATA),
        ):
            if any(c.layer is layer for c in detected):
                return target

    if any(k in lowered for k in _NEGATION_KEYWORDS):
        return CorrectionTarget.UNCLEAR

    if any(k in lowered for k in _ACCEPT_KEYWORDS):
        return CorrectionTarget.ACCEPTED

    return CorrectionTarget.UNCLEAR


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
        return hypothesis

    supported_replacements = tuple(c for c in replacements if c.supported)
    new_missing = tuple(c for c in replacements if not c.supported)

    # 差し替え先も未実装だった場合(§33の「地図」→「色を濃く」=ヒートマップ)、
    # **できないものが1つ減ったふりをしない**。新しいMISSINGとして扱い、
    # 代替があればそれを提案する。
    substitutes: list[Capability] = []
    for gap in new_missing:
        if gap.nearest_supported_id is None:
            continue
        alternative = CAPABILITY_REGISTRY.get(gap.nearest_supported_id)
        if alternative is not None and alternative not in substitutes:
            substitutes.append(alternative)

    updated = supported_replacements + tuple(substitutes)
    changes: dict[str, object] = {"missing": new_missing, "revision": hypothesis.revision + 1}
    if layer is CapabilityLayer.DATA:
        changes["data"] = updated
    elif layer is CapabilityLayer.VIEW:
        changes["view"] = updated
    else:
        changes["effects"] = replacements
    return replace(hypothesis, **changes)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 会話への接続(FORGE-ARCHITECTURE-REVIEW-AND-IMPLEMENT-005 §32)
# ---------------------------------------------------------------------------

CAPABILITY_QUESTION_KEY_PREFIX = "capability_gap:"


def next_capability_turn(
    latest_user_text: str, asked_question_keys: tuple[str, ...]
) -> tuple[str, str] | None:
    """会話の1ターンとして出すべきCapabilityの話があれば`(文面, key)`を返す。

    無ければ`None`——その場合、呼び出し側は**今までどおりの経路**へ進む
    (レビュー §6「既存経路に一切触れない」)。

    `question_key`に不足Capability名を含めるのが要点である。既存の
    `asked_question_keys`(同じUnknownを繰り返し聞かないための仕組み、
    指示書001 §5)をそのまま再利用できる:

    * 同じ不足(例: 地図)を二度提示しない。
    * ユーザーが「違う、色を濃く」と訂正すると、不足が
      `view.heatmap`へ変わる=**別のkey**になるため、訂正後の仮説は
      ちゃんと1回提示される。
    * 提示回数が`_MAX_HYPOTHESIS_REVISIONS`に達したら打ち切る
      (レビュー F2:「違う」ループが終わらない事態を防ぐ)。無理に
      正解へ辿り着こうとせず、通常の会話へ戻す。

    判定は最新の発話のみを見る。会話全体を見ると、訂正後も最初の
    「地図」という語が残っているため、訂正が反映されない。
    """
    hypothesis = build_hypothesis(latest_user_text)
    if not has_buildable_gap(hypothesis):
        return None

    presented = [k for k in asked_question_keys if k.startswith(CAPABILITY_QUESTION_KEY_PREFIX)]
    if len(presented) >= _MAX_HYPOTHESIS_REVISIONS:
        return None

    key = CAPABILITY_QUESTION_KEY_PREFIX + ",".join(c.id for c in hypothesis.missing)
    if key in asked_question_keys:
        return None
    return hypothesis.to_message(), key
