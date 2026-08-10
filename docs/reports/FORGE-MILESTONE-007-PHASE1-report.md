# FORGE-MILESTONE-007 第一段階 実施レポート — Cognitive Pipeline最小実装

**Ref:** FORGE-MILESTONE-007(第一段階、実装契約: Blueprint v1.3)
**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-15

Blueprint v1.3(過去版・Superseded Design Historyは不採用)に基づき、
既存`run_pipeline()`を一切変更せず、`run_cognitive_pipeline()`という
完全に独立したFacadeとして、Cognitive Pipelineの最小実装を行った。

---

## 0. 実装開始前に発見・修正した重大な不具合

作業着手時点で、`forge_ai`の既存80テストのうち**3件が既に失敗していた**
(並行して進んでいた実装作業の副作用)。原因は、6例対応のため
`DomainCategory`へ`TASK_MANAGEMENT`・`SURVEY`・`SCHEDULE`を追加した際、
`_BUILTIN_DOMAINS`(実際のDomain定義本体)への追加が漏れていたこと。
`DomainRegistry.get()`が黙って`GENERIC`へフォールバックしてしまい、
テストが失敗していた。**この3件を最優先で修正し、既存80テストの維持を
最初に回復した。** 3つのDomain定義(concepts/actionsを含む)を追加し、
件数変化を正しく反映するようテストも更新した(80→83件)。

---

## 1. 変更ファイル一覧

### 新規(Cognitive Pipeline専用)
```
forge_ai/contracts/cognitive_interfaces.py
forge_ai/core/orchestration/cognitive_types.py
forge_ai/core/orchestration/cognitive_context.py
forge_ai/core/orchestration/cognitive_dependencies.py
forge_ai/core/orchestration/outcomes.py
forge_ai/core/orchestration/errors.py
forge_ai/core/orchestration/pipeline_orchestrator.py
forge_ai/core/input_processing/normalizer.py
forge_ai/core/input_processing/ambiguity_detector.py
forge_ai/core/understanding/intent_recognizer.py
forge_ai/core/understanding/domain_classifier.py
forge_ai/core/understanding/world_builder.py
forge_ai/core/understanding/requirement_extractor.py
forge_ai/core/planning/application_planner.py
forge_ai/core/planning/template_selector.py
forge_ai/core/critic/design_critic.py
forge_ai/core/critic/revision_engine.py
forge_ai/core/confirmation/escalation_handler.py
（各ディレクトリの__init__.py）
```

### 変更(既存、後方互換な拡張のみ)
```
forge_ai/core/domain_model.py   — DomainCategory 3種追加+Domain定義本体(重大バグ修正)
forge_ai/core/intent_model.py    — Intent へ8フィールド追加(既定値あり)
forge_ai/core/world_model.py      — World へ Events/States/Permissions追加(既定値あり)
forge_ai/core/planner.py           — ScreenPlan/ApplicationPlan へフィールド追加(既定値あり)
forge_ai/core/pipeline.py           — run_cognitive_pipeline()を追加(run_pipeline()は無変更)
```

### テスト(新規+更新)
```
forge_ai/tests/test_input_processing.py(新規、9件)
forge_ai/tests/test_understanding.py(新規、17件)
forge_ai/tests/test_planning_and_critic.py(新規、14件)
forge_ai/tests/test_cognitive_orchestrator_integration.py(新規、12件)
forge_ai/tests/test_cognitive_pipeline_golden.py(新規、4件)
forge_ai/tests/test_domain_model.py(更新、既存2件→6件。4件はDomain拡張分)
```

---

## 2. 実装した範囲

Blueprint v1.3 Task1〜9の設計に対し、CEO指定18項目のうち以下を実装した。

1. Cognitive系の型・Protocol ✅(`cognitive_types.py`・`cognitive_interfaces.py`)
2. CognitiveContext ✅
3. CognitiveDependencies ✅
4. Outcomes(Success/NeedsConfirmation/Failedの3具体型) ✅
5. Error Model ✅
6. Input Normalization ✅(前後空白・全角記号の一部)
7. 簡易Ambiguity Detection ✅(missing_goal・privacy_safety_permissionの2分類)
8. 簡易Intent Recognition ✅(日本語キーワード辞書によるルールベース)
9. Domain Classification ✅(実スコアリング、全12 Domain対象)
10. World Model Construction ✅(Domain+Intent両方から構築)
11. Requirement Extraction ✅(**Meaning Modelを対象外とし2引数へ簡略化**、5分類)
12. Preliminary / Final Template Selection ✅(11 Template Family対応)
13. 簡易Application Planning ✅(単一画面、Empty State/Validation/Navigation付き)
14. 最小Design Critic ✅(4評価軸: Completeness/Simplicity/Empty State/Validation Coverage)
15. Revision Engine ✅(auto_fixableな指摘のみ自動修正)
16. CognitiveOrchestrator ✅(Legacy Protocol不使用、NotImplementedError非捕捉)
17. run_cognitive_pipeline() Facade ✅
18. Unit / Integration / Golden Test ✅(56件新規)

---

## 3. 未実装・既知の制限(正直な申告)

- **Meaning Model**: CEO指定18項目に含まれないため、今回は実装していない。
  Requirement Extractorは`(world, intent)`の2引数のみで動作する
  (Blueprint v1.3の3引数シグネチャとは異なる、意図的な第一段階の簡略化)。
- **Ambiguity Detectionの8分類中、実装済みは2分類のみ**
  (missing_goal・privacy_safety_permission)。missing_actor・
  missing_domain・missing_data・missing_action・conflicting_
  requirements・multiple_possible_templatesは、確実に判定できる
  ルールを今回は持たないため検出しない(検出漏れがありうる)。
- **Design Criticは14軸中4軸のみ**(Completeness/Simplicity/Empty State
  Quality/Validation Coverage)。Intent Fidelity・Domain Consistency・
  Navigation Coherence・Accessibility・Privacy等は今回評価しない。
- **複数画面のApplication Planning**: 現状は常に単一画面(`main`)を
  生成する。`navigation_edges`は常に空。
- **`CognitiveOrchestrator.__init__`にproviderパラメータが無い**:
  Blueprint v1.3 Task3.2の疑似コードは`provider`を受け取るが、第一段階の
  全コンポーネントがルールベースでLLMを一切呼ばないため、実装時に
  この引数を省略した(未使用の引数を残すより正直な選択と判断した)。
  `Compiler`のみ、内部で`MockProvider`(決定的)を使う。
- **6例以外の入力**: 日本語キーワード辞書は6例を中心に構築しており、
  それ以外の入力(英語・6例と無関係な話題等)はGenericへ落ちるか、
  Ambiguity Detection的中せず低精度になる可能性が高い。

---

## 4. 実際に動く入力例と生成結果概要(実行結果、事実)

6例すべてで`CognitivePipelineSuccess`に到達することを、実際に実行して
確認した。

| 入力 | Domain | Template | 画面数 | Critic | Quality |
|---|---|---|---|---|---|
| 買い物リストを作りたい | shopping | checklist | 1 | release_ready=True, score=1.00 | 1.00 |
| 今日のタスクを管理したい | task_management | checklist | 1 | release_ready=True, score=1.00 | 1.00 |
| 日記を記録したい | diary | memo | 1 | release_ready=True, score=1.00 | 1.00 |
| 簡単なアンケートを作りたい | survey | form | 1 | release_ready=True, score=1.00 | 1.00 |
| 予定を管理したい | schedule | calendar | 1 | release_ready=True, score=1.00 | 1.00 |
| 在庫を管理したい | inventory | tracker | 1 | release_ready=True, score=1.00 | 1.00 |

例(買い物リストを作りたい)の詳細:
```
title: 買い物リストを作りたい
screen: name=main, purpose=買い物リストを作りたい
  key_elements=(item, price, quantity, store)
  required_actions=(add_item, remove_item, mark_purchased, set_budget)
  empty_state_message=まだitemがありません。追加してください。
  validation_rules=(主要な入力欄が空のまま追加操作をしても、エラー表示はせず何もしないこと。,)
unassigned_requirements=('item'のデータを保持できること。, 主要な操作がキーボード操作のみでも完了できること。)
decision_trace: 2件(cognitive_intent_recognition, domain_classification)
```

---

## 5. 全テスト結果(実行結果、事実)

```
$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 139 tests in 0.036s
OK

$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.029s
OK (skipped=17)
```

## 6. 既存80テストが維持されている証拠

作業開始直後の実行で、修正前の状態が「Ran 80 tests」「FAILED
(failures=3)」であったことを実際に確認した(0章の不具合)。修正後、
該当3テストの原因(Domain定義漏れ)を解消し、影響した
`test_all_five_named_domains_plus_generic_exist`のみ、拡張後の実態
(9 Domain)に合わせて`test_all_eight_named_domains_plus_generic_exist`
へ改名・更新した(既存の期待値を弱めたのではなく、意図的なDomain拡張を
正しく反映させた)。それ以外の既存テスト関数は1つも削除・弱体化して
いない。既存ファイル(test_compiler.py・test_contracts.py・
test_meaning_and_intent.py・test_pipeline.py・test_planner.py・
test_provider_and_prompt.py・test_quality_engine.py・
test_repair_engine.py・test_world_model.py)は無変更で全合格している。

## 7. Backend / Flutter / Nativeが無変更である証拠

```
$ find backend/app/ai/native -name "*.py" -newer docs/tasks/task035.md
(該当なし)

$ (Dartファイル全件のbrace整合性チェック)
Dart issues: 0

$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.029s
OK (skipped=17)   ← 前回セッションから件数・結果とも無変化
```
`backend/app/ai/runtime/prompt_pipeline.py`等、M005のコードは一切
参照・変更していない(forge_ai/側のみで完結する第一段階のため)。

---

## 8. 次に改善すべき3点

1. **Ambiguity Detectionの分類拡充**: 現状2分類(missing_goal・
   privacy_safety_permission)のみ。特にmissing_domain・
   conflicting_requirementsは、6例以外の実運用input(複数要求を含む
   文等)で必要性が高まると想定される。
2. **Template Selectionのスコア均衡ケースの精査**: 「買い物リストを
   作りたい」で、checklistとtrackerが同点(3.0)になり、辞書の登録
   順で偶然checklistが勝っている(0章と同種の、テストして初めて
   見つかる類の潜在的な脆さ)。actionキーワードの再整理を推奨する。
3. **複数画面Application Planningへの拡張**: 現状は常に単一画面。
   M006が定義する「画面ごとの責務分離」を本格的に活かすには、
   Domainの複雑さに応じて複数画面(例: 一覧画面+詳細画面)を生成する
   ロジックが必要(navigation_edgesも今回は常に空)。
