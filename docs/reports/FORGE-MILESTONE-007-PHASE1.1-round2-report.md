# FORGE-MILESTONE-007 Phase 1.1(残修正)実施レポート

**Ref:** M007 Phase 1 Minimal Cognitive Slice(Phase 1.1、2回目監査対応)
**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-16

CEOがForge AI 156件・Backend 265件の全合格を確認し、Provider契約・
Confidence分離・Validation UX・Criticカバレッジ・Template tie-breakの
方向性を承認した上で、Meaning Model・複数画面化へ進む前の残修正4点を
求めた。**本セッションでの独立監査により、4点とも既に正しく実装済み
であることを確認した。** 追加で、監査中に見つけた軽微な冗長コードを
1件修正した。

---

## 1. 変更ファイル一覧

```
forge_ai/core/orchestration/pipeline_orchestrator.py   — 冗長なCritic再評価呼び出しを削除(本セッションの修正)
```

上記1ファイルの軽微な修正を除き、指摘4点は既に別セッションで正しく
実装・検証済みであることを、本セッションで独立に確認した(詳細は
2章)。参考として、4点の実装が含まれるファイルは以下。

```
forge_ai/core/planning/template_selector.py           — 指摘1: differs_from_preliminaryの一元化
forge_ai/core/orchestration/pipeline_orchestrator.py    — 指摘1・2: Orchestrator側の上書き削除、Decision Trace追加
forge_ai/core/orchestration/cognitive_types.py           — 指摘3: target_ref/operation_ref追加
forge_ai/core/understanding/requirement_extractor.py      — 指摘3: target_ref/operation_refを実際に設定
forge_ai/core/planning/application_planner.py               — 指摘3: 実データに基づく割当判定
forge_ai/core/critic/design_critic.py                          — 指摘4: Privacy/Accessibility方針の統一
forge_ai/tests/test_cognitive_orchestrator_integration.py        — 指摘1のRegression Test
forge_ai/tests/test_planning_and_critic.py                        — 指摘3・4のRegression Test
```

---

## 2. 独立監査で確認した内容(指摘ごと)

### 指摘1: Preliminary/Final不一致判定の責務集約 — 確認: 正しく実装済み

`TemplateSelector.select_final()`が`differs_from_preliminary=best_template
not in preliminary_candidates`を自ら設定しており(該当ファイル167行目)、
`CognitiveOrchestrator`側の`dataclasses.replace()`による上書きは存在
しないことを確認した(grep検索で0件)。Revision後の再選択(2箇所)も
同じ`select_final()`を経由するため、判定は毎回フレッシュに行われる。

Orchestratorの制御フローも`if`ではなく`while final_selection.
differs_from_preliminary:`というループになっており、不一致が続く限り
Revisionを繰り返し、上限到達時のみ`NeedsConfirmation`(reason=
`preliminary_final_mismatch_exhausted`)へ抜けることを確認した。

**監査中に発見した軽微な冗長コード**: Cognitive Revisionループ内で
`design_critic.evaluate()`が同一の`plan`/`template_selection`に対して
連続2回呼ばれており(2回目の呼び出し結果はどこにも使われない、
純粋な無駄呼び出し)、削除した(本セッションで修正、動作結果への
影響は無い。DesignCriticは決定的なため2回目も同じ結果を返すのみ)。

### 指摘2: Template Selection・Critic・RevisionをDecision Traceへ記録 — 確認: 正しく実装済み

`preliminary_template_selection`・`final_template_selection`・
`design_critic`・`cognitive_revision`の4段階全てで`context.
with_decision()`が呼ばれていることを確認した。実際に「買い物リストを
作りたい」を実行し、`final_template_selection`のDecision Trace内容が
「選択Template・同点候補・Preliminary候補・tie-break規則・却下候補・
スコア」を全て含むことを実行結果で確認した(3章参照)。

### 指摘3: Functional/Data/Validation Requirementの割当判定を実データに基づかせる — 確認: 正しく実装済み

`Requirement`へ`target_ref`/`operation_ref`(既定値`None`、後方互換)が
追加され、`RequirementExtractor`が実際にこれらを設定していることを
確認した。`ApplicationPlanner`の割当判定が、`target_ref in
data_entities`・`operation_ref in required_actions`という機械的な
参照整合性のみに基づき、description文字列の内容は一切見ていないことを
コードレベルで確認した。

`test_description_string_coincidence_alone_does_not_cause_false_
assignment`が、descriptionに実在するentity名("item")を含めつつ
`target_ref=None`とした要件が正しく未割当のままになることを検証して
おり、実際に実行して合格を確認した。

### 指摘4: Docstring・方針の統一 — 確認: 正しく実装済み

`design_critic.py`冒頭のdocstringが「Privacy mandatory未割当:
high/blocking」「Accessibility non-mandatory未割当: medium/
non-blocking」「Accessibility mandatory=True未割当: high/blocking
(Privacyと同じ扱い)」という、CEO指定の方針と完全に一致する記述に
なっていることを確認した。実装コード(153〜170行目)も、
`unassigned_mandatory_accessibility`の有無で分岐し、この方針通りに
`severity`・`has_blocking_issue`を設定していることを確認した。

---

## 3. 追加Regression Test一覧(既存、独立監査で内容を確認)

**指摘1(`test_cognitive_orchestrator_integration.py`、
`TestPreliminaryFinalMismatchAcrossRevisions`、3件)**:
- `test_mismatch_persists_across_revision_when_final_never_converges`:
  常にPreliminary候補外を返すFake Selectorで、`NeedsConfirmation`
  (reason=`preliminary_final_mismatch_exhausted`)へ到達し、Successには
  ならないことを確認。
- `test_mismatch_resolves_to_false_once_converged_within_preliminary`:
  1回目は候補外、Revision後(2回目)は候補内に収束するFakeで、
  `differs_from_preliminary=False`となりSuccessへ到達することを確認。
- `test_shared_revision_limit_reached_results_in_needs_confirmation`:
  `revision_attempt >= max_revision_attempts`に実際に到達している
  ことを確認。

**指摘3(`test_planning_and_critic.py`、4件)**:
- `test_functional_requirement_with_missing_action_is_unassigned_and_blocks_critic`
- `test_functional_requirement_with_present_action_is_assigned`
- `test_data_requirement_with_missing_entity_is_unassigned`
- `test_description_string_coincidence_alone_does_not_cause_false_assignment`

**指摘4関連(`test_planning_and_critic.py`)**:
- `test_mandatory_accessibility_unassigned_is_high_and_blocking`

合計164件(前回156件から8件増加)。

---

## 4. Forge AI全テスト結果

```
$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 164 tests in 0.071s
OK
```

## 5. Backend全テスト結果

```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.035s
OK (skipped=17)
```
前回セッションから件数・結果とも無変化。

---

## 6. Revision後もTemplate不一致が残るケースの実行結果

`test_mismatch_persists_across_revision_when_final_never_converges`を
実行し、常にPreliminary候補外(`wizard`)を返すFake Selectorに対して、
`CognitivePipelineNeedsConfirmation(reason='preliminary_final_mismatch_
exhausted')`が返り、`CognitivePipelineSuccess`には一切ならないことを
確認した(実行結果: 合格)。

## 7. Template tie-breakがDecision Traceへ記録された実例

実際に「買い物リストを作りたい」を実行し、`final_template_selection`
段階のDecision Traceが以下を記録していることを確認した。

```
[final_template_selection]
  decision: template=checklist
  reason: actions=['add_item', 'remove_item', 'mark_purchased', 'set_budget'],
    data_entities=['item', 'price', 'quantity', 'store'], validation_count=5,
    scores上位=[('checklist', 4.0), ('tracker', 4.0), ('generic', 0.1)]
    | tie-break: 同点(score=4.00): ('checklist', 'tracker')
    / Preliminary候補('checklist', 'form')内で絞り込み -> checklist
```

## 8. Functional/Data/Validation Requirementの割当判定例

「日記を記録したい」の実行結果で、`unassigned_requirements`に
Accessibility要件のみが残り、Functional/Data要件は(対応するAction/
Entityが実際にPlanへ反映されているため)正しく割当済みと判定される
ことを確認した。

```
unassigned_requirements = ('主要な操作がキーボード操作のみでも完了できること。',)
```

---

## 9. Backend / Flutter / Native無変更である証拠

```
$ find backend/app/ai/native -name "*.py" -newer docs/tasks/task037.md
(該当なし)

$ (Dartファイル全件のbrace整合性チェック)
Dart issues: 0

$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.035s
OK (skipped=17)
```

---

## 10. 6入力例の結果(変化なし、Decision Trace件数のみ増加)

| 入力 | Domain/Template | differs_from_preliminary | release_ready | Decision Trace件数 |
|---|---|---|---|---|
| 買い物リストを作りたい | shopping/checklist | False | True | 5 |
| 今日のタスクを管理したい | task_management/checklist | False | True | 5 |
| 日記を記録したい | diary/memo | False | True | 5 |
| 簡単なアンケートを作りたい | survey/form | False | True | 5 |
| 予定を管理したい | schedule/calendar | False | True | 5 |
| 在庫を管理したい | inventory/tracker | False | True | 5 |

Domain/Template判定結果自体は前回から変化していない。

---

## 11. 今回のスコープ外(CEO指示どおり)

Meaning Model・複数画面化には進んでいない。
