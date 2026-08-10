# ADR-013: `differs_from_preliminary` Needs a Graded Notion of "Significantly Different"

**Status:** Proposed（設計フェーズ、未実装。Runtime挙動は今回変更していない）
**Ref:** Template Selector監査(2026-07-21、CEO報告「household_budget欠落」
調査を発端に発見)

---

## Context

`docs/adr/ADR-008-preliminary-final-template-selection-split.md`は、
「Final選択がPreliminary候補と**著しく異なる**場合」の再計画を、
Cognitive Revisionと同じカウンタ・上限を共有する、という設計を決定
した。

しかし実際の実装(`TemplateSelection.differs_from_preliminary:
bool`、`forge_ai/core/orchestration/cognitive_types.py`)は、
「Preliminary候補に含まれるかどうか」という**真偽値**でしかなく、
ADR-008が本来意図していたはずの「著しく異なる」という**程度**の
判断を一切表現できていない。

`TemplateSelector.select_final()`(`forge_ai/core/planning/
template_selector.py`)は、`score_by_template`という、Templateごとの
スコアを既に算出している。1位のTemplateがPreliminary候補の外に
あったとしても、そのスコアが2位以下を大差で上回っている場合(=
Final Selectorが強い根拠を持って決定している場合)と、僅差の
偶然の逆転にすぎない場合とを、現状の実装は区別しない。

2026-07-21のTemplate Selector監査(household_budget欠落の調査)で、
14 Domain全てを実際に検証した結果、現時点でこの区別が無いことに
起因する実害(無駄な確認要求)は確認されなかった。しかし、この監査
自体が「Preliminary候補の精度を継続的に手動でメンテナンスし続ける」
ことに依存しており、ADR-008自身の`Revisit Conditions`も「再計画が
頻発するようになったら、まずPreliminary精度を見直す」ことを促して
いる——つまり、**Preliminary側の精度に頼る現在の緩和策には限界が
あり、Final Selector側の確信度を直接使う、より根本的な解決策を
検討する価値がある**、というのが本ADRの提起である。

`docs/adr/ADR-007-confidence-must-affect-control-flow.md`は、
Domain Classification等の`overall_confidence`について、「Confidence
は制御フローに実際に影響を与えるべきであり、閾値ベースの段階的な
扱い(0.8以上=継続、0.5〜0.8=仮設計、0.5未満=原則確認)とする」と
いう、確立された設計哲学を既に持っている。本ADRは、この哲学を
Template Selectionの「Preliminary/Final不一致」という別の場面へも
一貫して適用することを提案する。

---

## Decision(提案、未実装)

**`TemplateSelection`へ、`differs_from_preliminary`という真偽値に
加えて、不一致の「深刻度」を表す情報を追加し、`pipeline_
orchestrator.py`が、深刻度に応じて異なる扱いをできるようにする。**

### 提案する深刻度の算出方法

`score_by_template`(既存フィールド、変更不要)から、1位と2位の
スコア差を「決定マージン」として算出する。

```python
def selection_margin(score_by_template: tuple[tuple[str, float], ...]) -> float:
    """1位と2位のスコア差。値が大きいほど、Final Selectorの決定が
    僅差の偶然ではなく、明確な根拠に基づくことを示す。"""
    ranked = sorted(score_by_template, key=lambda kv: kv[1], reverse=True)
    if len(ranked) < 2:
        return float("inf")
    return ranked[0][1] - ranked[1][1]
```

この`margin`を使い、ADR-007と同じ「段階的な扱い」の哲学に沿って、
以下のような分岐を設ける(閾値は暫定案、ADR-007と同様「実運用データ
に基づく再調整が前提」とする)。

| margin | 扱い(提案) |
|---|---|
| 大(例: 2.0以上) | Preliminaryとの不一致があっても、Final Selectorの決定を採用し、再計画(Cognitive Revision)を経ずに継続する |
| 小(2.0未満) | 現状通り、Cognitive Revisionへ回す(不一致の合成Critic Issueとして扱う、ADR-008の既存設計を維持) |

**重要な設計上の注記**: Template Selectorの`score_by_template`は
確率・0〜1の信頼度ではなく、加点式のスコア(action一致で+3.0、
entity一致で+1.0等)であるため、ADR-007の0.5/0.8という閾値を
そのまま数値的に流用することはできない。本ADRが提案する閾値
(margin 2.0)は、Template Selection独自の採点体系に合わせた、
**別個の閾値**であり、ADR-007の哲学(段階的な扱い、閾値はCEO承認の
もとで調整可能)を踏襲しつつ、具体的な数値は独立して検討する必要が
ある。

---

## Alternatives

- **現状維持(真偽値のまま、案A=最小変更案)**: 2026-07-21監査の
  時点では実害が無いため、直ちに変更する必要は無いという判断も
  合理的である。ただし、Domain数が増える・Preliminary精度の
  継続的な手動メンテナンスコストが無視できなくなった場合に、
  改めて本ADRの提案を実装することを想定する。
- **Preliminary Pattern Candidates自体を廃止し、Final Selectorの
  スコアだけで完結させる**: 却下(検討はしたが不採用として記録)。
  ADR-008が明記する通り、Preliminary Pattern CandidatesはDomain
  Registryの`recommended_patterns`という、Application Planning
  以前に分かる有用なヒントを活用する仕組みであり(Rule Before
  Prompt、ADR-003)、Final Selectorのスコアだけに一本化すると、
  この「早い段階で分かることを早く使う」という利点が失われる。
- **`margin`ではなく、1位のスコアの絶対値だけを見る**: 却下。
  スコアの絶対値は、entity数・action数等、プロンプトの詳細度に
  依存して変動するため、「他候補との相対的な差」の方が「決定的
  かどうか」をより安定して表現できると判断した。

---

## Consequences(実装する場合の影響、未実装のため仮定)

- `TemplateSelection`へ新しいフィールド(例:
  `mismatch_severity: Literal["decisive", "ambiguous"]`、または
  `margin: float`そのもの)を追加する必要がある。既存の
  `differs_from_preliminary: bool`フィールド自体は後方互換のため
  維持し、新フィールドを追加する形にする(既存の呼び出し元・
  テストを壊さない)。
- `pipeline_orchestrator.py`の`while final_selection.differs_from_
  preliminary:`ループの先頭に、`margin`に基づく早期`break`分岐を
  追加する必要がある。
- 新しい閾値(`margin`の具体的な値)の妥当性を検証するテストが
  新たに必要になる。ADR-007と同様、「閾値変更にはCEO承認を要件と
  する」という運用ルールを踏襲すべきである。
- `test_planning_and_critic.py`の既存テスト(特に「Preliminary/
  Final不一致→Cognitive Revision」を前提にしたテスト)が、新しい
  分岐によって挙動が変わらないか、実装時に全て再確認する必要が
  ある。

---

## Migration(移行方法の提案)

1. **Phase 0(今回、本ADRのみ)**: 設計提案のみ。Runtime変更なし。
2. **Phase 1(将来、CEO承認後)**: `TemplateSelection`へ新フィールド
   (後方互換な追加)を導入し、`selection_margin()`ヘルパーを
   `template_selector.py`へ実装する。この時点ではまだ
   `pipeline_orchestrator.py`の分岐は変更しない(新フィールドの
   値が実際の運用でどう分布するかを、まずログ・トレースで観察する
   段階)。
3. **Phase 2(観察結果を踏まえ、CEO承認後)**: 実際のデータに基づき
   閾値を確定し、`pipeline_orchestrator.py`へ早期`break`分岐を
   追加する。この段階で、既存の「Preliminary/Final不一致→
   Cognitive Revision」を前提にしたテストを、新しい分岐を踏まえて
   更新する。
4. 各Phaseの完了後、本ADRの`Status`を`Proposed`から`Accepted`
   (Phase 1完了時)・`Implemented`(Phase 2完了時)へ更新する。

---

## Revisit Conditions

- Preliminary Pattern Candidatesの手動メンテナンス(Domain追加の
  たびに`_DOMAIN_TO_PRELIMINARY`を更新する運用、2026-07-21の
  監査・completeness checkで一定の安全網は整備済み)が、Domain数の
  増加により継続困難になった場合、本ADRのPhase 1以降へ着手する
  ことを検討する。
- 逆に、Preliminary精度の手動メンテナンスで十分に不一致が発生
  しない状態が今後も継続する場合(2026-07-21時点でまさにこの状態)、
  本ADRは`Proposed`のまま据え置いて構わない。
