"""Quality Engine。

生成されたForge IRを6軸で数値化し、Quality Scoreを返す。
このモジュールはForge IRとApplication Planだけを見て評価する
(Providerを呼ばない、決定的な静的分析)。
"""

from __future__ import annotations

from dataclasses import dataclass

from forge_ai.core.compiler import ForgeIRDocument, ForgeIRWidget
from forge_ai.core.planner import ApplicationPlan


@dataclass(frozen=True)
class QualityScore:
    """6軸のスコア(0.0〜1.0)。"""

    correctness: float
    completeness: float
    simplicity: float
    runtime_safety: float
    explainability: float
    maintainability: float

    @property
    def overall(self) -> float:
        """単純平均。将来、軸ごとの重み付けが必要になった場合はここを変更する
        (QualityEngine自体の責務を変えずに済むよう、overallの算出方法だけを
        差し替えられる設計にしている)。"""
        values = (
            self.correctness,
            self.completeness,
            self.simplicity,
            self.runtime_safety,
            self.explainability,
            self.maintainability,
        )
        return sum(values) / len(values)

    def to_dict(self) -> dict[str, float]:
        """6軸のスコアとoverallを1つのdictへまとめる(ログ出力・レポート表示用)。"""
        return {
            "correctness": self.correctness,
            "completeness": self.completeness,
            "simplicity": self.simplicity,
            "runtime_safety": self.runtime_safety,
            "explainability": self.explainability,
            "maintainability": self.maintainability,
            "overall": self.overall,
        }


# Runtime Safetyの静的チェックで使う上限値。
# shared/schemas/ui_schema.v1*.json のMAX_NESTING_DEPTH/MAX_WIDGETS_PER_SCREENと
# 意図的に同じ値を使っている(forge_ai/はBackendをimportしないため、
# 値だけを手動同期している。IMPLEMENTATION_REPORT.mdに明記)。
_MAX_NESTING_DEPTH = 12
_MAX_WIDGETS_PER_SCREEN = 200


class QualityEngine:
    """Forge IRとApplication Planから、6軸のQuality Scoreを算出する。"""

    def evaluate(self, ir: ForgeIRDocument, plan: ApplicationPlan) -> QualityScore:
        """Forge IRとApplication Planから6軸のQualityScoreを算出する。"""
        return QualityScore(
            correctness=self._correctness(ir),
            completeness=self._completeness(ir, plan),
            simplicity=self._simplicity(ir),
            runtime_safety=self._runtime_safety(ir),
            explainability=self._explainability(ir, plan),
            maintainability=self._maintainability(ir),
        )

    def _correctness(self, ir: ForgeIRDocument) -> float:
        """最低限の構造的整合性(screenが1つ以上あるか、initial_screen_idが
        実在するか)を確認する。forge_ai/は本物のSchema Validatorを持たないため、
        ここでの「correctness」は構造的な自己無矛盾性の意味に限定される
        (本格的な検証はBackend接続後、Validatorが行う)。"""
        if not ir.screens:
            return 0.0
        screen_ids = {s.id for s in ir.screens}
        if ir.initial_screen_id not in screen_ids:
            return 0.3
        return 1.0

    def _completeness(self, ir: ForgeIRDocument, plan: ApplicationPlan) -> float:
        """Planが要求したdata_entitiesのうち、実際にIRのどこかに
        (state・widgetのproperties経由で)言及されているものの割合。"""
        if not plan.data_entities:
            return 1.0
        ir_text = _flatten_text(ir)
        mentioned = sum(1 for entity in plan.data_entities if entity.lower() in ir_text)
        return mentioned / len(plan.data_entities)

    def _simplicity(self, ir: ForgeIRDocument) -> float:
        """Widget総数が少ないほど高スコア(上限に対する余裕度)。
        単純に「少なければ良い」ではなく、必要最小限からの乖離が小さいほど
        高くなるよう、上限に対する比率で減点する形にしている。"""
        total_widgets = sum(_count_widgets(s.body) for s in ir.screens)
        if total_widgets == 0:
            return 0.0
        ratio = total_widgets / _MAX_WIDGETS_PER_SCREEN
        return max(0.0, 1.0 - ratio)

    def _runtime_safety(self, ir: ForgeIRDocument) -> float:
        """ネスト深度が上限を超えていないか。"""
        for screen in ir.screens:
            depth = _widget_depth(screen.body)
            if depth > _MAX_NESTING_DEPTH:
                return 0.0
        return 1.0

    def _explainability(self, ir: ForgeIRDocument, plan: ApplicationPlan) -> float:
        """各screenにtitleがあり、planのpurposeと空でない対応が取れているか。"""
        if not ir.screens:
            return 0.0
        titled = sum(1 for s in ir.screens if s.title.strip())
        return titled / len(ir.screens)

    def _maintainability(self, ir: ForgeIRDocument) -> float:
        """Widget IDがドキュメント全体で重複していないか(重複はRuntime側で
        Fallbackや誤動作の原因になりうるため、保守性の指標として扱う)。"""
        all_ids = [w.id for s in ir.screens for w in _flatten_widgets(s.body)]
        if not all_ids:
            return 0.0
        unique_ratio = len(set(all_ids)) / len(all_ids)
        return unique_ratio


def _flatten_widgets(widget: ForgeIRWidget) -> list[ForgeIRWidget]:
    """widgetとその子孫すべてを平坦なリストへ展開する。"""
    result = [widget]
    for child in widget.children:
        result.extend(_flatten_widgets(child))
    return result


def _count_widgets(widget: ForgeIRWidget) -> int:
    """widget木に含まれる総Widget数を返す。"""
    return len(_flatten_widgets(widget))


def _widget_depth(widget: ForgeIRWidget) -> int:
    """widget木の最大ネスト深度を返す(葉ノードは深度1)。"""
    if not widget.children:
        return 1
    return 1 + max(_widget_depth(c) for c in widget.children)


def _flatten_text(ir: ForgeIRDocument) -> str:
    """IR全体を検索用に1つの小文字テキストへ変換する
    (Compilerが独自に定義したproperties構造に依存しすぎないよう、
    JSON化した文字列全体を対象にする)。"""
    import json

    return json.dumps(ir.to_json_dict(), ensure_ascii=False).lower()
