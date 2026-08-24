"""Semantic Design Critic — **意味の階層が成立しているか**を見る
(FORGE-R1-CLOSURE-015 §3・§10、2026-08-17)。

---

## なぜ既存のDesign Criticと別なのか

`DesignCritic`は`ApplicationPlan`を見る。`style_role`はその後の
Compilerが付けるので、**まだ存在しない**。順序を入れ替えるとPlanの
評価がCompilerに依存することになるので、入れ替えない。

そこで「生成されたForge Documentを見る」評価をここに置き、既存の
Reportへ**軸を1つ足す形で合流させる**。

## roleが「ある」ことを評価しない

これが要点である。

```
❌ style_roleが存在する → PASS
```

では、**10個すべてが`metric.primary`でもPASS**してしまう。それは
「一番大事なものが10個ある」という状態で、Designとしては失敗である。
階層が消えているのに、機械は「意味が付いている」と満足する。

だから見るのは3つ:

1. **存在**   — 重要な場所に意味が付いているか
2. **妥当性** — その意味がその場所に合っているか
3. **階層**   — 強い意味が乱立していないか

## 決定的である

AIを呼ばない。同じ文書なら常に同じ結果を返す。**「美しい」を測って
いるのではない**——測っているのは、意味の構造が破綻していないか
という、機械的に判定できる事実だけである(§10.1)。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from forge_ai.core.orchestration.cognitive_types import CriticIssue

__all__ = [
    "SemanticDesignFinding",
    "VisualStructureEvidence",
    "evaluate_semantic_design",
]

# **同一画面で1つだけ**であるべき役割。2つ以上あれば階層が消える。
_SINGULAR_ROLES: frozenset[str] = frozenset({"metric.primary", "button.primary"})

# 意味が付いていないと困るWidget。**画面の骨格になるもの**に限る
# ——全Widgetに強制すると、区切り線にまで意味を書かせることになる。
_ROLE_EXPECTED_TYPES: frozenset[str] = frozenset({
    "metric_view", "section_header", "record_list_view", "button", "tab_view",
})

# お金の向きと、状態の良し悪しを**兼用しない**。
#
# 支出はエラーではない。同じ赤で塗ると「使ったこと自体が失敗」という
# 意味になる。Design Language V1がこの2つを別の語彙にしているのは
# そのためで、生成物でも混ざっていないことを見る。
_FINANCE_ROLES: frozenset[str] = frozenset({"finance.income", "finance.expense"})
_STATE_ROLES: frozenset[str] = frozenset({"state.success", "state.danger", "state.warning"})

# 面を持ち上げすぎていないか。**全部を持ち上げると階層が消える**
# (`surface.elevated`のavoid_whenがまさにそう言っている)。
_ELEVATED_ROLE = "surface.elevated"
_MAX_ELEVATED = 2


@dataclass(frozen=True)
class VisualStructureEvidence:
    """生成物の**構造についての決定的な事実**(§10)。

    「美しさを測った」ものではない。名前を`VisualQuality...`にしなかった
    のはそのためである——測れていないものを測ったことにしない。

    ただし`UNKNOWN`のまま置くよりはよい。ここにある数値は、後から
    「どういう構造の生成物が受け入れられたか」を突き合わせるための、
    機械的に再現できる事実である。
    """

    primary_metric_count: int = 0
    primary_action_count: int = 0
    semantic_role_count: int = 0
    distinct_role_count: int = 0
    hierarchy_depth: int = 0
    role_coverage_ratio: float = 0.0
    """意味が付いていてほしいWidgetのうち、実際に付いている割合。"""

    elevated_surface_count: int = 0
    duplicated_singular_roles: tuple[str, ...] = ()
    finance_state_conflict: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "primary_metric_count": self.primary_metric_count,
            "primary_action_count": self.primary_action_count,
            "semantic_role_count": self.semantic_role_count,
            "distinct_role_count": self.distinct_role_count,
            "hierarchy_depth": self.hierarchy_depth,
            "role_coverage_ratio": round(self.role_coverage_ratio, 3),
            "elevated_surface_count": self.elevated_surface_count,
            "duplicated_singular_roles": list(self.duplicated_singular_roles),
            "finance_state_conflict": self.finance_state_conflict,
        }


@dataclass(frozen=True)
class SemanticDesignFinding:
    """評価結果。既存Criticと同じ`CriticIssue`の語彙で話す。"""

    score: float
    issues: tuple[CriticIssue, ...] = ()
    evidence: VisualStructureEvidence = field(default_factory=VisualStructureEvidence)

    @property
    def has_blocking_issue(self) -> bool:
        return any(i.severity == "high" for i in self.issues)


def _walk(widget: dict, depth: int = 1):
    yield widget, depth
    for child in widget.get("children", []) or ():
        yield from _walk(child, depth + 1)


def _duplicated_singular_roles(
    per_screen: "list[tuple[str, list[tuple[dict, int]]]]",
) -> dict[str, dict[str, int]]:
    """1画面に2つ以上ある**単一であるべきrole**を、画面ごとに返す。

    **文書全体では数えない**(FORGE-017A §14)。別々の画面がそれぞれ
    主KPIを1つ持つのは正しい設計であり、画面が増えるほど誤検知が
    増える形にしてはいけない。
    """
    result: dict[str, dict[str, int]] = {}
    for screen_id, widgets in per_screen:
        counts: dict[str, int] = {}
        for widget, _ in widgets:
            role = widget.get("style_role")
            if isinstance(role, str) and role in _SINGULAR_ROLES:
                counts[role] = counts.get(role, 0) + 1
        duplicated = {role: n for role, n in counts.items() if n > 1}
        if duplicated:
            result[screen_id] = duplicated
    return result


def _bound_field(widget: dict) -> str | None:
    """そのWidgetが**どの値を見せているか**。無ければ`None`。"""
    for key in ("value_field", "field", "label_field"):
        value = widget.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _finance_state_conflicts(
    per_screen: "list[tuple[str, list[tuple[dict, int]]]]",
) -> tuple[str, ...]:
    """**同じ値**にお金の向きと状態の良し悪しが両方付いている箇所。

    ---

    ## 「同じ文書に両方ある」を誤りにしていた（FORGE-017A §14）

    以前は`finance.*`と`state.*`が同じ文書に現れるだけで指摘していた。
    しかし家計簿アプリは、**正当に両方を使う**。

        finance.expense  … 支出（お金が出ていく向き）
        state.danger     … 予算を超えた（状態が悪い）

    これは兼用ではなく、**別々のことを別々の語彙で言っている**——
    015 §9が求めた姿そのものである。それを弾いていた。

    本当の誤りは「支出を危険として塗る」こと、つまり**同じ値**に
    両方の意味を持たせることである。Widgetは`value_field`等で
    「どの値を見せているか」を持っているので、そこで判定する。

    値の結び付きが分からないWidget（`value_field`が無い）は
    **判定しない**——分からないものを誤り側へ倒すと、また誤検知になる。
    """
    conflicts: set[str] = set()
    for _, widgets in per_screen:
        finance_fields: set[str] = set()
        state_fields: set[str] = set()
        for widget, _ in widgets:
            role = widget.get("style_role")
            field_name = _bound_field(widget)
            if not isinstance(role, str) or field_name is None:
                continue
            if role in _FINANCE_ROLES:
                finance_fields.add(field_name)
            elif role in _STATE_ROLES:
                state_fields.add(field_name)
        conflicts |= finance_fields & state_fields
    return tuple(sorted(conflicts))


def _issue(category: str, severity: str, evidence: str, fix: str) -> CriticIssue:
    return CriticIssue(
        category=category, severity=severity, evidence=evidence,
        recommended_fix=fix, affected_component="forge_document", auto_fixable=False,
    )


def evaluate_semantic_design(document: dict) -> SemanticDesignFinding:
    """生成されたForge Documentの**意味の階層**を評価する。

    AIを呼ばない。同じ文書なら常に同じ結果になる。
    """
    # **画面ごとに見る**(FORGE-017A §14)。
    #
    # 以前は全画面のWidgetを1つの配列へ潰してから数えていた。そのため
    #
    #     一覧画面に metric.primary が1つ
    #     詳細画面に metric.primary が1つ
    #
    # という**正しい設計**が「metric.primaryが2個ある」として弾かれて
    # いた。指摘文自身が「metric.primaryは**画面で**1つだけにする」と
    # 書いているのに、数えるのは文書全体だった。
    #
    # 画面が増えるほど誤検知が増えるので、複数画面のアプリを作るほど
    # Criticが役に立たなくなる形だった。
    per_screen: list[tuple[str, list[tuple[dict, int]]]] = []
    for index, screen in enumerate(document.get("screens", []) or ()):
        body = screen.get("body")
        if isinstance(body, dict):
            screen_id = str(screen.get("id") or f"screen[{index}]")
            per_screen.append((screen_id, list(_walk(body))))

    widgets: list[tuple[dict, int]] = [w for _, ws in per_screen for w in ws]

    roles = [w.get("style_role") for w, _ in widgets if isinstance(w.get("style_role"), str)]
    role_counts: dict[str, int] = {}
    for role in roles:
        role_counts[role] = role_counts.get(role, 0) + 1

    expected = [w for w, _ in widgets if w.get("type") in _ROLE_EXPECTED_TYPES]
    covered = [w for w in expected if isinstance(w.get("style_role"), str)]
    coverage = (len(covered) / len(expected)) if expected else 1.0

    duplicates_by_screen = _duplicated_singular_roles(per_screen)
    duplicated = tuple(sorted({role for roles_ in duplicates_by_screen.values() for role in roles_}))
    elevated = role_counts.get(_ELEVATED_ROLE, 0)
    conflicting_fields = _finance_state_conflicts(per_screen)

    evidence = VisualStructureEvidence(
        primary_metric_count=role_counts.get("metric.primary", 0),
        primary_action_count=role_counts.get("button.primary", 0),
        semantic_role_count=len(roles),
        distinct_role_count=len(role_counts),
        hierarchy_depth=max((d for _, d in widgets), default=0),
        role_coverage_ratio=coverage,
        elevated_surface_count=elevated,
        duplicated_singular_roles=duplicated,
        finance_state_conflict=bool(conflicting_fields),
    )

    issues: list[CriticIssue] = []
    penalties = 0.0

    for screen_id, roles_ in sorted(duplicates_by_screen.items()):
        for role, count in sorted(roles_.items()):
            # **これが「roleがあるだけ」を弾く判定である。**
            issues.append(_issue(
                "semantic_design", "high",
                f"画面'{screen_id}'に'{role}'が{count}個ある",
                f"{role}は1画面に1つだけにする。残りは補助的な役割へ落とす",
            ))
            penalties += 0.4

    if not roles:
        issues.append(_issue(
            "semantic_design", "high",
            "style_roleが1つも無い",
            "見出し・一覧・主要操作に意味的役割を付ける",
        ))
        penalties += 0.5
    elif coverage < 0.8:
        issues.append(_issue(
            "semantic_design", "medium",
            f"骨格Widgetの{int((1 - coverage) * 100)}%に意味的役割が無い",
            "metric_view/section_header/record_list_view/button/tab_viewへroleを付ける",
        ))
        penalties += 0.2

    if elevated > _MAX_ELEVATED:
        issues.append(_issue(
            "semantic_design", "medium",
            f"surface.elevatedが{elevated}箇所ある",
            "持ち上げる面を絞る。全部を持ち上げると階層が消える",
        ))
        penalties += 0.2

    for field_name in conflicting_fields:
        issues.append(_issue(
            "semantic_design", "medium",
            f"'{field_name}'に finance.* と state.* の両方が付いている",
            "支出はエラーではない。同じ値にお金の向きと状態の良し悪しを兼用しない",
        ))
        penalties += 0.2

    return SemanticDesignFinding(
        score=max(0.0, 1.0 - penalties), issues=tuple(issues), evidence=evidence,
    )
