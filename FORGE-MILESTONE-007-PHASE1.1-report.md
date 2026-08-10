# FORGE-MILESTONE-007 Phase 1.1 実施レポート — 契約精度・品質評価・UX改善

**Ref:** M007 Phase 1 Minimal Cognitive Slice(Phase 1.1修正)
**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-16

CEOの実物監査(139/265件全合格の確認込み)で指摘された7点を修正した。
新しいDomain・大規模機能は追加せず、既存の最小実装の契約精度・品質
評価・ユーザー体験の改善に限定した。

---

## 1. 変更ファイル一覧

```
forge_ai/core/pipeline.py                              — provider契約復元、名称訂正
forge_ai/core/orchestration/pipeline_orchestrator.py     — 名称訂正、tie-break呼び出し、combined confidence
forge_ai/core/orchestration/cognitive_types.py            — CriticReport拡張、domain_coverageプロパティ
forge_ai/contracts/cognitive_interfaces.py                  — select_final()シグネチャ変更
forge_ai/core/planning/template_selector.py                  — 明示的tie-break実装
forge_ai/core/planning/application_planner.py                 — data要件の割当バグ修正、Validation UX改善
forge_ai/core/critic/design_critic.py                           — 7軸評価、mandatory blocking、evaluated/unevaluated
forge_ai/core/critic/revision_engine.py                          — Validation UX改善
forge_ai/core/understanding/requirement_extractor.py              — Validation UX改善(5要件へ分割)
forge_ai/tests/test_cognitive_orchestrator_integration.py           — Provider契約テスト・Confidence組合せテスト追加
forge_ai/tests/test_planning_and_critic.py                            — Tie-breakテスト・Criticテスト追加
```

---

## 2. 修正した契約差分

### 2.1 実装位置づけの訂正(指摘1)
「Blueprint v1.3の実装」という表現を撤回し、**M007 Phase 1 Minimal
Cognitive Slice**へ統一した(`pipeline.py`・`pipeline_orchestrator.py`の
docstring、本レポート)。実装済み13段階(Meaning Modelを除く)であることを
明記し、Blueprint v1.3準拠部分と意図的な簡略化を分離して記載した。

### 2.2 Provider契約の回復(指摘2)
```diff
- def run_cognitive_pipeline(raw_input, *, domain_registry=None, dependencies=None)
+ def run_cognitive_pipeline(raw_input, provider=None, *, domain_registry=None, dependencies=None)
```
`provider`省略時は決定的な`MockProvider`を使う(既定動作維持)。
明示的に渡した場合、`Compiler`へ実際に注入される。

### 2.3 Template Selection tie-break(指摘3)
```diff
- def select_final(self, plan: ApplicationPlan) -> TemplateSelection
+ def select_final(self, plan: ApplicationPlan, preliminary_candidates: tuple[str, ...] = ()) -> TemplateSelection
```
同点時、(1)Preliminary候補内優先→(2)Dominant action一致数→
(3)Data lifecycle一致数→(4)generic、の順で決定的に解決する。

### 2.4 Validation UXの改善(指摘4)
1要件("エラーにせず何もしない")を5要件へ分割し、「空のまま追加操作」
(既存M005教訓、静かに無視してよい)と「必須項目を満たさない送信」
(理由表示・入力保持・修正方法明示・フォーカス移動)を明確に区別した。

### 2.5 Critic/Qualityスコアの誤解防止(指摘5、A案採用)
```diff
  class CriticReport:
      release_ready: bool
      score: float  # 後方互換のため維持
      issues: tuple[CriticIssue, ...] = ()
+     implemented_checks_score: float = 0.0
+     coverage_ratio: float = 0.0
+     evaluated_axes: tuple[str, ...] = ()
+     unevaluated_axes: tuple[str, ...] = ()
```
未割当のmandatory要件がある場合、Privacy要件が未割当の場合は
`release_ready=True`にしない。Accessibility(mandatory=False)は
未割当でもblockingにしない。単一画面のnavigation不要と、複数画面での
navigation_edges欠落を区別した。

### 2.6 Confidenceの分離(指摘6)
`DomainClassification.confidence`(=`domain_coverage`プロパティを追加)・
`intent.confidence`(intent_extraction_confidence)・`score_margin`の
3指標を、Orchestrator内の`_should_escalate_for_low_confidence()`が
明示的に組み合わせる(単一指標のみでの判定を廃止)。

---

## 3. 追加テスト一覧

- `TestProviderContract`(3件): 既定Provider・明示的Provider呼び出し・
  2つの異なるProviderの独立差し替え。
- `TestCombinedConfidenceAssessment`(5件): 高coverage/高margin/高intent
  confidenceでは確認不要、いずれか低い場合は確認要求、margin=0でも
  coverageが高ければ過剰確認しない、等。
- `test_shopping_tie_is_resolved_by_preliminary_candidates_not_registration_order`・
  `test_tie_break_falls_through_to_dominant_action_when_not_in_preliminary`・
  `test_backward_compatible_call_without_preliminary_candidates_still_works`
  (Template Selection tie-break、3件)。
- `TestDesignCritic`に6件追加: mandatory未割当のblocking・non-mandatory
  未割当の非blocking・Privacy未割当のblocking・単一画面のnavigation不要・
  複数画面のnavigation_edges欠落検出・evaluated/unevaluated軸の追跡。

合計17件新規(139→156件)。

---

## 4. Forge AI全テスト結果

```
$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 156 tests in 0.028s
OK
```

## 5. Backend全テスト結果

```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.026s
OK (skipped=17)
```
前回セッションから件数・結果とも無変化。

---

## 6. 6入力例の出力差分

| 入力 | Domain/Template(変化なし) | score(旧→新) | coverage_ratio(旧→新) | release_ready | issues |
|---|---|---|---|---|---|
| 買い物リストを作りたい | shopping/checklist | 1.00→0.93 | (無し)→0.50 | True | 0→1 |
| 今日のタスクを管理したい | task_management/checklist | 1.00→0.93 | (無し)→0.50 | True | 0→1 |
| 日記を記録したい | diary/memo | 1.00→0.93 | (無し)→0.50 | True | 0→1 |
| 簡単なアンケートを作りたい | survey/form | 1.00→0.93 | (無し)→0.50 | True | 0→1 |
| 予定を管理したい | schedule/calendar | 1.00→0.93 | (無し)→0.50 | True | 0→1 |
| 在庫を管理したい | inventory/tracker | 1.00→0.93 | (無し)→0.50 | True | 0→1 |

Domain・Templateの判定結果自体は変化していない(6例とも引き続き
CognitivePipelineSuccessへ到達)。買い物リストのTemplate Selectionは、
以前は登録順で偶然checklistが選ばれていたが、今回`rationale`に
「Preliminary候補内で絞り込み -> checklist」という明示的な理由が
記録されるようになった。

## 7. Critic/Qualityスコアが1.00ではなくなった理由

7評価軸の実装済みスコア(`implemented_checks_score`)は0.93(以前の
0軸→1.00とほぼ同じ計算だが、Accessibility要件が未割当のまま残るため
0.5点相当が加わり、平均が下がった)。`coverage_ratio=0.50`は、
M006が定義する14評価軸のうち7軸のみを実際に評価したことを正直に示す
(以前はこの指標自体が存在せず、`score=1.00`が「アプリ全体の品質」で
あるかのように見えていた)。`release_ready=True`は維持されている
(Accessibility要件はmandatory=Falseのため、blockingにはしていない)。

---

## 8. Provider差し替えが機能する証拠

```python
class _CountingProvider:
    def __init__(self):
        self.call_count = 0
    def complete(self, prompt):
        self.call_count += 1
        return MockProvider().complete(prompt)

provider = _CountingProvider()
outcome = run_cognitive_pipeline("買い物リストを作りたい", provider)
# provider.call_count >= 1 であることを実際に確認済み(test_explicit_provider_is_actually_invoked)
```
2つの異なるProviderインスタンスをそれぞれ独立に渡しても、互いに
混同されず正しく呼び出されることも確認した
(`test_two_different_providers_can_be_swapped_independently`)。

---

## 9. Backend / Flutter / Native無変更である証拠

```
$ find backend/app/ai/native -name "*.py" -newer docs/tasks/task036.md
(該当なし)

$ (Dartファイル全件のbrace整合性チェック)
Dart issues: 0

$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.026s
OK (skipped=17)   ← 前回から件数・結果とも無変化
```

---

## 10. 今回のスコープ外(CEO指示どおり)

複数画面化・Meaning Model追加には進んでいない。これらはPhase 1.1の
次のステップとして残す。
