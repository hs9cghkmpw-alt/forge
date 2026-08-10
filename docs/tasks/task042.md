# Task042 — ADR-007実装(Task042-1: ConfidenceRecord・overall_confidence導入、Task042-2 Phase B: Shadow Judgment)

**Status: Evaluation Phase Complete(2026-07-22、CEO承認)。**
Task042-1・Task042-2 Phase B(Shadow Judgment)・Evaluation Reportまで
完了し、ここでTaskを終了する。Phase C(実際の判定ロジック置換)は
開始しない(理由は`FORGE-TASK042-2-EVALUATION-REPORT.md`・
ADR-007の追記参照)。後続は独立したTask043
(「Confidence Model Review」、設計レビューのみ)として引き継ぐ。

## 依頼内容

Task041完了後、CEOから「次はADR-007の実装に着手してほしいが、いきなり
コード変更は行わず、まず現状調査を実施してほしい」という依頼を受けた。
調査結果(`FORGE-TASK042-ADR007-INVESTIGATION-PLAN.md`)をTask042-1〜3の
3段階に分けて提示したところ、CEOから以下の調整指示を受けた。

1. Task042-1(ConfidenceRecord・overall_confidence導入、観測のみ)は
   そのまま進める。
2. Task042-2は、ADRの0.5/0.8への単純置換ではなく、「overall_confidence
   を導入しつつ既存シグナル(intent confidence・domain coverage・
   score margin)を内部要素として残し、比較実験できる状態を作る」という
   移行案を優先する。
3. Task042-3(複数ApplicationPlan候補保持)は、Planner・Critic・
   Orchestrator・DecisionTrace全てに影響する規模の大きい仕事のため、
   独立したマイルストーン(M008等)として切り出すかを改めて判断する。

着手順として「1. Task042-1実装 → 2. CEOレビュー → 3. Task042-2の詳細
設計 → 4. Task042-3の切り出し判断」という順序が承認された。本Taskは
このうち1(Task042-1の実装)を行う。

## 行ったこと

- `forge_ai/core/orchestration/cognitive_types.py`へ`ConfidenceRecord`
  (`value`・`basis`)・`OverallConfidence`(`intent_confidence`・
  `domain_confidence`必須、`entity_confidence`・`planning_confidence`・
  `template_confidence`は任意で`None`許容、`.value`は`available_
  components`の単純平均)を新設した。
- `forge_ai/core/orchestration/confidence.py`(新規ファイル)へ
  `compute_overall_confidence(intent, classification)`を実装した。
  既存の`Intent.confidence`・`DomainClassification.domain_coverage`
  ・`score_margin`から`OverallConfidence`を組み立てる。
- `pipeline_orchestrator.py`のDomain Classification直後へ、
  `overall_confidence_observation`という**新しいDecisionTrace
  ステージ**を追加した。**この値はどの`if`分岐にも使わず、
  `_should_escalate_for_low_confidence()`・`_is_low_risk_
  reversible()`は導入前と全く同じ引数・ロジックのまま変更していない**
  ことを、コードを直接確認して検証済み。
- `test_confidence_model.py`(新規、14件)を追加し、`ConfidenceRecord`
  ・`OverallConfidence`・`compute_overall_confidence()`の単体テストと、
  実際のPipeline実行を通じて「観測ステージがDecisionTraceに記録される
  が、既存のSuccess/Confirmation判定には影響しない」ことを確認する
  end-to-endテストを追加した。
- **発見・修正した問題**: 新しいDecisionTraceステージの追加により、
  `test_cognitive_pipeline_complex_golden.py`(複雑入力6例の
  Golden Test)が、`decision_trace_stages`リストの不一致で6件全て
  失敗する状態になっていた。実際にPipelineを再実行し、
  `decision_trace_stages`以外のフィールド(domain・template・
  entities・actions・critic_release_ready等)が1つも変わっていない
  ことを個別に確認した上で、6件のgolden JSONファイルを、新しい
  ステージを含む正しい内容へ更新した(このテスト自体のエラー
  メッセージが想定している「意図した変更であれば更新する」という
  手順に従った)。

## 変更理由

CEO承認済みの段階計画(Task042-1〜3)のうち、最初の段階を実装した。
「観測のみ、制御フローに一切影響しない」という方針を徹底することで、
既存の確認要求/Success判定ロジックへの回帰リスクを最小化しつつ、
Task042-2で必要になる`overall_confidence`という値そのものを、
実際のPipeline実行を通じて検証可能な状態にした。

## 既存挙動への影響

**無し(意図的)。** `_should_escalate_for_low_confidence()`・
`_is_low_risk_reversible()`は1行も変更していない。追加した
`overall_confidence_observation`というDecisionTraceステージは、
新しい観測情報を1件追加するだけであり、既存のどの分岐にも読まれない。

Golden Test(`test_v03_domain_inference_golden.py`36件・
`test_cognitive_pipeline_complex_golden.py`6件)を全て再実行し、
Domain・Template・Success/Confirmationの判定結果が1件も変わって
いないことを確認した(6件のgolden JSONについては、`decision_trace_
stages`という「新しいステージが追加されたことそのものを記録する」
フィールドのみを、意図した変更として更新した)。

## テスト結果

```
$ python3 -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 374 tests in 0.259s
OK

$ python3 -O -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 374 tests in 0.300s
OK

$ python3 -m unittest discover -s backend/tests -p "test_*.py"
Ran 400 tests in 0.052s
OK (skipped=35)
```

## 次の一手

CEOレビューを経て、Task042-2(overall_confidenceを既存の3信号モデルと
並行して比較実験できる状態を作る、単純置換ではない移行案)の詳細設計へ
進む。Task042-3(複数ApplicationPlan候補保持)を独立したマイルストーンへ
切り出すかどうかも、あわせて判断する。

## 追記(2026-07-21、同日中の拡張)

CEOからTask042-1のレビュー結果として承認を受け、Task042-2の詳細設計へ
進む前に、以下の追加対応を依頼された。

> DecisionTraceへoverall_confidenceを記録する際、overall_confidence・
> available_components・intent_confidence・domain_confidence・basisを
> まとめて追跡できるようにしてほしい(Task042-2での比較実験のため、
> 制御フローには使わない)。

`DecisionTrace`へ`confidence_observation: OverallConfidence | None =
None`という新しいフィールドを追加し、`overall_confidence_
observation`ステージのDecisionTraceが、`OverallConfidence`
オブジェクトそのものを保持するようにした。これにより、`reason`という
自由記述文字列を構文解析することなく、`trace_entry.confidence_
observation.value`・`.available_components`・`.intent_confidence`・
`.domain_confidence`・各`.basis`へ直接アクセスできる。既存の
DecisionTrace構築箇所は、新フィールドが既定値`None`を持つため、全て
無変更のまま動作する(後方互換)。

`test_confidence_model.py`へ4件追加(計18件)。forge_ai全378件・
backend全400件が引き続き合格(`-O`有無双方で確認済み)。

このあと、Task042-2の詳細設計(`FORGE-TASK042-2-DESIGN-PROPOSAL.md`)
を別途提出した。

## 追記2(2026-07-21、Phase B実装完了)

CEOからTask042-2設計提案が承認され、Phase B(`ShadowJudgment`追加・
Golden Test比較レポート)の実装指示を受けた。以下を実施した。

- `forge_ai/core/orchestration/confidence.py`へ`ThresholdsUsed`
  (現行モデル・Shadowモデル双方の閾値を構造化データとして保持)・
  `compute_legacy_escalation_reasons()`(現行モデルの判定理由を
  列挙する関数、後述のリファクタリングにより`_should_escalate_for_
  low_confidence()`と同じロジックを共有)・`classify_risk()`
  (5+1分類のrisk_classification)・`ShadowJudgment`・
  `compute_shadow_judgment()`を追加した。
- `pipeline_orchestrator.py`の`_should_escalate_for_low_confidence()`
  を、`compute_legacy_escalation_reasons()`を呼ぶだけの薄いラッパーへ
  リファクタリングした。**この関数が返す`bool`値は、リファクタリング
  前と一字一句同じ閾値・同じ条件から導出されるため、完全に同じ**
  (既存挙動への影響なし、全テストで確認済み)。
- `DecisionTrace`へ`shadow_judgment`フィールドを追加し、
  `overall_confidence_observation`ステージへ`ShadowJudgment`を
  そのまま記録するようにした(制御フローには一切使わない、
  `if _should_escalate_for_low_confidence(...)`は`shadow_judgment`・
  `overall_confidence`のどちらも参照しない)。
- `test_confidence_model_comparison.py`(新規、12件)を追加。境界値
  専用テスト11件(overall_confidence=0.49/0.50/0.79/0.80、intent低
  domain高、intent高domain低、score_marginのみ低い、全信号高い/低い、
  閾値の記録・カスタム閾値の実験可能性)と、Golden Test全42件を
  実際にPipelineへ通して比較する報告テスト1件。
- **比較結果(Golden Test 42件)**: 一致件数42/42(一致率100%)。
  36件が`both_continue`、6件が`both_escalate`。不一致は0件だった。
  risk_classificationは`high_confidence`29件・`medium_band`7件・
  `multiple_signals_low`6件で、単独の信号だけが低いケース
  (`*_only_low`)は今回のGolden Test corpusには1件も無かった。
  詳細は`FORGE-TASK042-2-SHADOW-COMPARISON-REPORT.md`参照。

テスト結果: forge_ai 390件(`-O`有無双方)・backend 400件、全て合格。
Golden Test(v0.3の36件・複雑入力6件)は、Success/Domain/Template等の
既存の期待値を一切変更していない(Shadow結果を理由に変更しない、
というCEO指示を遵守)。

## 追記3(2026-07-22、比較データの訂正)

Task042-2 Evaluation Report作成のため、Shadow結果の分布(intent_
confidence・overall_confidence等)を詳しく分析する過程で、
**`test_confidence_model_comparison.py`の`_all_golden_prompts()`に
実在するバグを発見した**。

`test_cognitive_pipeline_complex_golden.CASES`は`{ケース名: 実際の
入力文}`という辞書であり、`.items()`は`(ケース名, 入力文)`という
順序のタプルを返す。一方`test_v03_domain_inference_golden.
SUCCESS_CASES`は`(入力文, Domain名)`という順序。以前の実装は、この
2つを単純に連結して`for text, domain in prompts:`のように分解して
いたため、**複雑入力6件については、実際の日本語入力ではなく
`"01_shared_shopping"`のようなケース名の文字列そのものを`run_
cognitive_pipeline()`へ渡していた**。

このケース名文字列は、Domain語彙と一致せず`generic`へ分類され、
「低リスクGeneric仮設計」という既存の許容ルールにより、たまたま
`CognitivePipelineSuccess`へ到達していたため、テスト自体はエラーに
ならず「合格」していた。しかし、実際に比較していたのは意図した
入力ではなかった。

**修正内容**: `complex_golden._load_golden(case_name)`から実際の
`"domain"`フィールドを読み、`(実際の日本語入力, 実際のDomain)`という
正しい順序のタプルへ揃えた。

**修正後の比較結果(再掲)**: 一致件数42/42(一致率100%は変わらず)。
ただし内訳は`both_continue`が42件全てとなり(以前の`both_escalate`
6件は、バグにより生じた見せかけの結果だった)、risk_classification
は`high_confidence`35件・`medium_band`7件で、`*_only_low`・
`multiple_signals_low`は0件になった。**現在のGolden Test corpusは、
低confidence・確認要求が必要な領域を一切カバーしていない**ことが
判明した(境界値テスト(`TestShadowJudgmentBoundaryValues`)で
別途補っている)。

`FORGE-TASK042-2-SHADOW-COMPARISON-REPORT.md`を訂正後の数値で
再生成した。forge_ai全390件(`-O`有無双方)・backend全400件、
引き続き全て合格。
