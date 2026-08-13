"""Declarative Capability Definition
(FORGE-USER-GUIDED-SELF-EXTENSION-006 §55・§56、2026-08-13)。

`docs/spec/FORGE-SELF-EXTENSION-ARCH-REVIEW-v2.md` §5-B / §10 / §11 の実装。

---

## これは何か

**新しいCapabilityを、コードではなくデータとして追加する仕組み**である。

    Capability Definition = 既存Runtime Primitiveの合成の宣言

Dartを1行も生成しない。生成されるのは「どのPrimitiveをどう組み合わせるか」
という宣言だけで、それを決定的なValidatorが検査する。

## なぜこれが安全なのか(§34のThreat Modelへの回答)

任意コード生成が危険なのは、**実行されるから**である。ここで生成される
のは実行コードではなく、既存の検証済みPrimitiveへの参照リストである。
したがって:

* 任意コード実行 — 起きない。新しい実行経路が1つも増えない
* Supply-chain — 起きない。依存を追加できない(参照先はPrimitive IDのみ)
* 権限昇格 — `EFFECT`を含む定義は`COMPOSED`へ昇格できない(下記)
* Prompt injection によるCapability捏造 — Registryに無いIDは**拒否**する

隔離(Sandbox)が要らないのは、隔離すべき実行が無いからである。
必要なのはスキーマ検証と参照整合性検査だけで、それはこのファイルが行う。

## この仕組みの上限(意図的な安全弁)

**Runtime Primitiveの集合が、表現できるものの上限を決める**。
定義データをいくら書いても、`view.spatial`が実装されない限り地図は
描けない。「定義を書けば何でも増える」設計にはしていない(v2 §6)。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.ai.runtime.semantic_capability import (
    PRIMITIVE_REGISTRY,
    PrimitiveKind,
    RuntimePrimitive,
)

__all__ = [
    "CapabilityDefinition",
    "DefinitionRejected",
    "TrustLevel",
    "ValidationOutcome",
    "validate_definition",
]


class TrustLevel(str, Enum):
    """生成物と長期検証済みCoreを同じ扱いにしない(§25、v2 §10)。"""

    CORE = "core"
    """人間が実装し、長期運用されているもの。"""

    COMPOSED = "composed"
    """既存Primitiveの合成のみで、必要なPrimitiveがすべて実装済み。

    **これは「定義として成立した」という意味であって、「本番で使える」
    という意味ではない**(指摘5)。本番利用の可否は
    `ValidationOutcome.production_usable`が答える——Compiler接続と
    描画確認まで揃って初めて`True`になる。""" 

    CANDIDATE = "candidate"
    """定義は妥当だが、必要なPrimitiveがまだ実装されていない。
    **利用不可**。何が足りないかを記録しておくためだけに存在する。"""

    REJECTED = "rejected"
    """検証に落ちた。利用不可。"""


@dataclass(frozen=True)
class CapabilityDefinition:
    """新しいCapabilityの宣言。**データであってコードではない**。"""

    id: str
    label_ja: str
    primitive_ids: tuple[str, ...]
    version: str = "1.0"
    """`major.minor`(§26)。Primitive追加はminor、意味変更はmajor。
    生成済みToolは使用時のmajorをpinする。定義はデータなので、
    rollbackはpinを戻すだけで済む——ビルドが要らない。"""

    origin: str = "generated"
    """`human` / `generated`。Trust判定の材料。"""


@dataclass(frozen=True)
class DefinitionRejected:
    """なぜ受け入れられなかったか。**理由を必ず持たせる**——
    「駄目でした」だけでは、次に何を直せばよいか分からない。"""

    code: str
    detail: str


@dataclass(frozen=True)
class ValidationOutcome:
    definition: CapabilityDefinition
    trust: TrustLevel
    rejections: tuple[DefinitionRejected, ...] = ()
    missing_primitives: tuple[RuntimePrimitive, ...] = ()
    widget_types: tuple[str, ...] = field(default_factory=tuple)

    # --- 状態を1つのbooleanで表さない(指摘5の修正、2026-08-13)--------
    #
    # 以前は`usable`という1つのプロパティで
    # 「定義として妥当」と「実際のTool生成に使える」を同時に表していた。
    # `COMPOSED`なら`usable=True`になるため、**Compiler未接続・描画未確認の
    # ものが「利用可能」と読める契約**になっていた。テスト自身が
    # `compile_definition`の不在を確認しているのに、契約はそれと矛盾していた。
    #
    # 段階を分けて、それぞれ**別の根拠で**答えられるようにする。
    # 曖昧な1語より、答えられないことを答えられないと示す方が安全である。

    @property
    def definition_valid(self) -> bool:
        """定義の形式・参照が妥当か(拒否理由が無いか)。"""
        return not self.rejections

    @property
    def primitives_available(self) -> bool:
        """必要なRuntime Primitiveがすべて実装済みか。"""
        return self.definition_valid and not self.missing_primitives

    @property
    def compiler_supported(self) -> bool:
        """Compilerがこの定義を選んでForge Languageへ落とせるか。

        **現時点では常に`False`**。定義を消費する経路(Solution Shape)が
        まだ無い。ここを`True`にしてよいのは、実際に接続して
        E2Eで確認した時だけである(TD58)。
        """
        return False

    @property
    def runtime_verified(self) -> bool:
        """この合成で実際に描画されることを確認したか。

        **現時点では常に`False`**。個々のWidget(`bar_chart`等)の
        描画実績はあるが、**この合成としての**描画は確認していない。
        「部品が動くから合成も動くはず」は確認ではない。
        """
        return False

    @property
    def production_usable(self) -> bool:
        """本番のTool生成に使ってよいか。

        全段が揃って初めて`True`になる。**今はどの定義もここへ到達しない**
        ——それが正しい状態である(§56の基準に照らして未達だから)。
        """
        return (
            self.primitives_available
            and self.compiler_supported
            and self.runtime_verified
        )

    def explain(self) -> str:
        if self.rejections:
            return "; ".join(f"{r.code}: {r.detail}" for r in self.rejections)
        if self.missing_primitives:
            names = "・".join(p.label_ja for p in self.missing_primitives)
            return f"定義は妥当だが、{names}がRuntimeに未実装のため使用できない"
        return (
            "既存Primitiveの合成として成立する"
            "(ただしCompiler未接続・合成としての描画未確認のため、本番利用は不可)"
        )


# 1つの定義が参照してよいPrimitiveの上限。Capability爆発(§28)と、
# 「super_map_everything」のような巨大Capabilityの両方を防ぐ。
_MAX_PRIMITIVES_PER_DEFINITION = 6


def validate_definition(definition: CapabilityDefinition) -> ValidationOutcome:
    """定義を決定的に検査し、Trust Levelを決める。

    検査順序に意味がある。**まず存在を疑い、次に安全を見て、
    最後に実装状況を見る**:

    1. 未知のPrimitive参照 → 拒否(§45: AIが言ったから存在するとは扱わない)
    2. `EFFECT`を含む → 拒否。外部作用は合成で自動獲得させない(§8)
    3. 空・過大 → 拒否(§28 Granularity)
    4. `VIEW`をまったく含まない → 拒否(描けないものはCapabilityではない)
    5. 未実装Primitiveを含む → `CANDIDATE`(利用不可、記録のみ)
    6. すべて実装済み → `COMPOSED`(利用可)
    """
    rejections: list[DefinitionRejected] = []

    unknown = [pid for pid in definition.primitive_ids if pid not in PRIMITIVE_REGISTRY]
    if unknown:
        # §45: Local AIが`view.quantum_map`のような存在しないものを提案しても、
        # Platform Truthは Registry 側にある。捏造は必ずここで止まる。
        rejections.append(DefinitionRejected(
            "unknown_primitive", f"Registryに存在しないPrimitive: {', '.join(unknown)}"
        ))
        return ValidationOutcome(definition, TrustLevel.REJECTED, tuple(rejections))

    primitives = tuple(PRIMITIVE_REGISTRY[pid] for pid in definition.primitive_ids)

    effects = [p for p in primitives if p.kind is PrimitiveKind.EFFECT]
    if effects:
        # 外部作用は「合成したら手に入る」ものではない。安全審査を経て
        # 人間が実装・許可するものである(§8 Product Correctness ≠ Security)。
        rejections.append(DefinitionRejected(
            "effect_not_composable",
            f"外部作用({', '.join(p.label_ja for p in effects)})は合成では獲得できない",
        ))

    if not primitives:
        rejections.append(DefinitionRejected("empty", "Primitiveが1つも指定されていない"))
    elif len(primitives) > _MAX_PRIMITIVES_PER_DEFINITION:
        rejections.append(DefinitionRejected(
            "too_broad",
            f"Primitiveが多すぎる({len(primitives)}個)。"
            "再利用できない巨大Capabilityになっている(§28)",
        ))

    if primitives and not any(p.kind is PrimitiveKind.VIEW for p in primitives):
        rejections.append(DefinitionRejected(
            "no_view", "表示手段(VIEW)を含まない。ユーザーからは何も見えない"
        ))

    if rejections:
        return ValidationOutcome(definition, TrustLevel.REJECTED, tuple(rejections))

    missing = tuple(p for p in primitives if not p.implemented)
    widget_types = tuple(dict.fromkeys(w for p in primitives for w in p.widget_types))

    if missing:
        return ValidationOutcome(
            definition, TrustLevel.CANDIDATE, (), missing, widget_types
        )
    return ValidationOutcome(definition, TrustLevel.COMPOSED, (), (), widget_types)
