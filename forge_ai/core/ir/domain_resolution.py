"""Domain Resolution(FORGE-QUALITY-AI-INDEPENDENCE-003 Phase B、
2026-08-12)。TD45の解決。

**解いていた問題**: 「毎日の血圧を記録したい」と話すと、Domain分類が
`diary`(Curated Domain)を返し、**Curatedが存在するというだけで
無条件に採用**されていた。結果、手作りの日記定義
(タイトル / 本文 / 気分 / 日付)がそのまま使われ、収縮期・拡張期・
脈拍を持たない「血圧記録アプリ」が生成されていた。

Conversation Engineが正しくNeedを理解しても、ここで意味を壊せば
Forge全体として失敗する(指示書8章)。

**根本原因(監査で判明)**: `domain_classifier.py`には既に
`_ACTION_ONLY_CONFIDENCE_CAP = 0.5`という仕組みがあり、
「**Conceptが1件も一致せず、Actionだけが一致してDomainが決まった**」
場合にconfidenceへ上限を課していた。実測すると:

    「日記をつけたい」      → matched_concepts=["日記"]  conf=1.00
    「出費を記録したい」    → matched_concepts=[...]      conf=0.67
    「毎日の血圧を記録したい」→ matched_concepts=[]        conf=0.50
    「読んだ本を記録したい」  → matched_concepts=[]        conf=0.50

つまり「そのDomainの概念語が1つも出てきていないのに、『記録する』と
いう**動詞だけ**が一致した」状態が、誤解決そのものだった。判定に
必要な情報は既にコード内にあり、`pipeline_orchestrator.py`が
それを**見ずに**Curatedを採用していただけである。

**したがって新しい閾値(マジックナンバー)は導入していない**。既存の
`matched_concepts`が空かどうか、という既にある意味をそのまま使う。

**採用しなかった案**: 「Curatedと合成の両方を作って比較する」
(指示書10章のADAPT_CURATED含む)。Curated候補の妥当性を測るためだけに
毎回LLM呼び出しが1回増え、しかも「どちらが良いか」を機械的に判定する
基準が別途必要になる。今回は、**既に存在する信号だけで誤解決を
止められる**ことが実測で分かったため、複雑な比較機構は導入していない
(指示書10章「複雑化するだけなら導入しない」)。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

__all__ = ["DomainResolution", "SolutionSource", "resolve_domain_source"]


class SolutionSource(str, Enum):
    """このNeedに対して、どこから解の骨格を得るか。"""

    CURATED = "curated"
    """`ir_generator.py`の手作りEntity定義を使う(人手で調整済み、
    Golden Testで固定されている高品質な骨格)。"""

    GENERATED = "generated"
    """`entity_synthesizer.py`がNeedから合成する。Curatedが
    そのNeedを満たせない場合に選ぶ。"""


@dataclass(frozen=True)
class DomainResolution:
    source: SolutionSource
    reason: str
    """なぜそう決めたか。Decision Traceへ載せ、誤解決の追跡に使う
    (指示書6章と同じ「判断根拠を残す」方針)。"""

    semantic_fit: bool = False
    """そのDomainの**概念語**がユーザーの発話に実際に現れたか。
    指示書9章の`semantic_fit`に対応する。"""


def resolve_domain_source(
    domain_category: str,
    *,
    is_curated: bool,
    matched_concepts: tuple[str, ...],
    matched_actions: tuple[str, ...],
    can_generate: bool,
) -> DomainResolution:
    """Curatedを使うか、合成するかを決定的に決める。

    引数はすべて**既にPipelineが持っている事実**であり、新たなLLM
    呼び出しを一切必要としない。

    * `is_curated` — そのDomainにCurated定義が存在するか。
    * `matched_concepts` — 分類時に実際に一致した**概念語**
      (「日記」「家計簿」等)。空 = 名前の上で一致していない。
    * `matched_actions` — 一致した**動詞**(「記録する」等)。
    * `can_generate` — 合成経路が使えるか(Synthesizer未注入なら`False`)。

    判定:

    1. Curatedが無い → `GENERATED`(従来どおり)。
    2. Curatedがあり、概念語が一致している → `CURATED`
       (人手で調整済みの骨格の方が良い)。
    3. Curatedがあるが**概念語が1件も一致していない**(動詞だけで
       選ばれた)→ `GENERATED`。**ここがTD45の修正点**。
    4. ただし3の場合でも合成が使えないなら、`CURATED`へ退避する
       ——Curatedが不適合でも、何も作れないよりはましだからである
       (この場合は理由へその旨を明記する)。
    """
    if not is_curated:
        return DomainResolution(
            SolutionSource.GENERATED,
            f"'{domain_category}'にCurated定義が無いため合成する",
        )

    if matched_concepts:
        return DomainResolution(
            SolutionSource.CURATED,
            f"'{domain_category}'の概念語({', '.join(matched_concepts[:3])})が"
            "発話に現れており、手作り定義が適合する",
            semantic_fit=True,
        )

    if not can_generate:
        return DomainResolution(
            SolutionSource.CURATED,
            f"'{domain_category}'の概念語は一致していないが"
            "(動詞のみの一致)、合成経路が使えないためCuratedで代替する",
        )

    matched = ", ".join(matched_actions[:3]) or "(なし)"
    return DomainResolution(
        SolutionSource.GENERATED,
        f"'{domain_category}'の概念語が1件も一致しておらず、動詞({matched})"
        "だけで選ばれたDomainであるため、Curatedを使わず発話から合成する",
    )
