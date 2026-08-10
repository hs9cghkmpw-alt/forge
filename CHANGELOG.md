# CHANGELOG

バージョンではなくTaskごとに記録する(`docs/tasks/`と対応。詳細な差分は各taskNNN.mdを参照)。

## Task044 — FORGE-UI-REFRESH-002: Sparkleブランド・ダーク生成中画面（2026-08-10）

CEOから新しいUIモックアップ画像(✦マークのSparkleロゴ、紫→青グラデーション、
「AIが考えている最中」向けのダーク画面、チェックリスト形式の生成中演出)が
共有され、「あなたの最善で選んでよし。エラーは都度解消してくれ」という
指示を受けたため、確認を挟まず実装した。

### 追加
- `frontend/lib/shared_widgets/forge_sparkle_mark.dart`(新規)。モックアップの
  "✦"ロゴを、実際の画像アセットが無いため`CustomPainter`でベクター描画する
  Widget。新規アセット・新規パッケージ依存は追加していない。
- `ForgeTheme`(`forge_theme.dart`)へ、ホーム画面・生成中画面専用の
  ダークパレット(`consoleBackground`等)と、ブランドグラデーション
  (`gradientStart`/`gradientEnd`/`brandGradient`)を追加。すべての新規配色は
  WCAG AAコントラスト比を計算した上で選定した(ファイル内コメント参照)。
  既存の`background`/`ink`/`accent`等は変更・削除していない。

### 変更
- `home_screen.dart`: ダーク配色化、`ForgeMark`→`ForgeSparkleMark`、
  送信ボタンのグラデーション化、`forgeExampleItems`を使ったクイック候補
  チップの追加(「例を見る」→「もっと例を見る」に改名、Bottom Sheet自体は
  変更なし)。**音声入力は引き続き未実装のため、モックアップにあるマイク
  アイコンは採用していない**(実装していない機能をあるように見せない、
  というFORGE v0.2 P5の既存方針を踏襲)。
- `generation_flow_screen.dart`: 生成中画面(`_GeneratingView`)を、
  1行だけのメッセージ切り替えから、全段階を並べたチェックリスト表示
  (完了=チェック、現在=スピナー、未到達=薄いドット)へ変更し、ダーク配色
  にした。完成画面(`_CompletionView`)はSparkleロゴ・グラデーションボタンに
  更新したが、配色自体は既存のlightなテーマのまま据え置いた(CEO提示
  モックアップ自体が画面ごとに意図的に配色を切り替えているため、
  `MaterialApp`全体のダークモード切り替えとしては実装していない)。
  確認画面(`_ConfirmationView`)・エラー画面(`_GenerationErrorView`)は
  未変更。
- テスト3件(`test/features/.../home_screen_test.dart`・
  `test/e2e/kids_checklist_generation_flow_test.dart`・
  `test/e2e/survey_form_validation_flow_test.dart`)を、上記の文言変更・
  新規チップによる`find.text()`の曖昧化に合わせて更新した(過去の
  FORGE-UI-REFRESH-report.md 2章と同じ種類の問題を、今回は実装と
  同じセッション内で先回りして修正した)。

### 既知の未達成事項
- Claudeのサンドボックスに Flutter/Dart SDK が無いため、`flutter analyze`・
  `flutter test`・`flutter build`のいずれも実行できていない
  (実行結果は一度も見ていない)。実装は既存パターン(既存の
  `RUNTIME-003`ボタン幅バグの回避パターン等)を踏襲し、括弧・波括弧の
  対応関係やimportの整合性は手動で確認したが、**CEO環境での実行結果
  待ち**。詳細は`docs/reports/FORGE-UI-REFRESH-002-report.md`参照。

## Task043 — Confidence Model Review（設計レビューのみ、コード変更なし）（2026-07-22）

Task042をEvaluation Phase Completeとして終了したことを受け、後続の
設計課題を独立したTaskとして開始した。今回はコード変更を一切行わず、
設計レビュー資料のみを作成した。

- confidenceとuncertaintyを概念として分離できるか検討した。
- `score_margin`の扱いについて3案(overall_confidenceへ統合・独立
  シグナルとして保持・第三要素として扱う)を比較した。
- 低confidence領域のGolden Test候補(intentのみ低い・domainのみ低い・
  score_marginのみ低い・privacy由来・permission由来・ambiguous
  entity由来を含む)を提案した。
- Task042-3(複数候補保持)との責務分離を、confidence・
  uncertainty・multiple candidate planningの3観点で整理した。

詳細は`docs/tasks/task043.md`・`FORGE-TASK043-CONFIDENCE-MODEL-
REVIEW.md`参照。

## Task042 — ADR-007実装 Task042-1: ConfidenceRecord・overall_confidence導入（2026-07-21）

**Status: Evaluation Phase Complete(2026-07-22)。Phase Cは開始しない。
後続はTask043として独立させた。**

ADR-007(Confidence Must Affect Control Flow)の実装第1段階。
`ConfidenceRecord{value, basis}`・`OverallConfidence`(intent/domain
confidence必須、entity/planning/template confidenceは将来拡張用に
任意)を新設し、`compute_overall_confidence()`で計算した値を
DecisionTraceへ**観測専用**で記録するようにした。既存の確認要求判定
ロジック(`_should_escalate_for_low_confidence()`等)は1行も変更して
いない。

新しいDecisionTraceステージの追加により、Golden Test6件が
`decision_trace_stages`の不一致で失敗する状態を発見し、他のフィールド
(Domain・Template・Success判定等)が一切変わっていないことを確認した
上で、golden fileを意図した変更として更新した。

CEOから、Task042-2は「ADRの閾値への単純置換ではなく、既存シグナルを
内部要素として残しつつ比較実験できる状態を作る」方針が明示されており、
次はその詳細設計に進む。Task042-3(複数ApplicationPlan候補保持)は
規模が大きいため、独立マイルストームとして切り出すかを別途判断する。

詳細は`docs/tasks/task042.md`・`FORGE-TASK042-ADR007-INVESTIGATION-
PLAN.md`参照。

**追記(同日)**: CEOレビューでTask042-1が承認され、Task042-2着手前の
追加対応として、`DecisionTrace`へ`confidence_observation`
(`OverallConfidence`オブジェクトそのもの)を保持するフィールドを
追加した(`reason`文字列を構文解析せずに`overall_confidence`・
`available_components`・`intent_confidence`・`domain_confidence`・
各`basis`へ直接アクセスできるようにするため)。テスト4件追加(計18件)。
続けてTask042-2の詳細設計(単純置換ではなく、Shadow Judgmentによる
比較可能な移行案)を`FORGE-TASK042-2-DESIGN-PROPOSAL.md`として提出、
コード変更はまだ行っていない。

**追記2(同日、Phase B実装完了)**: 設計提案が承認され、
`ShadowJudgment`(現行モデルとoverall_confidenceモデルの判定・
不一致分類・risk_classification・thresholds_usedを構造化して保持)を
実装した。`_should_escalate_for_low_confidence()`は、判定ロジックの
実体を`confidence.compute_legacy_escalation_reasons()`へ切り出した
薄いラッパーへリファクタリングしたが、**返す`bool`値は完全に同一**
(全テストで確認済み)。Golden Test全42件を実際にPipelineへ通した
比較の結果、**一致率100%**(不一致0件)だった。詳細は
`docs/tasks/task042.md`・`FORGE-TASK042-2-SHADOW-COMPARISON-
REPORT.md`参照。forge_ai 390件・backend 400件、全て合格。

**追記3(2026-07-22、比較データの訂正)**: Evaluation Report作成中に、
比較対象抽出コードのタプル順序バグ(複雑入力6件で実際の入力文の
かわりにケース名文字列を使っていた)を発見・修正した。一致率100%
という結論は変わらないが、修正後は42件全てが`high_confidence`/
`medium_band`に分類され、**低confidence領域は現在のGolden Test
corpusで一切検証できていない**ことが判明した。詳細は
`docs/tasks/task042.md`追記3参照。

## Task041 — Template Selector監査・CI統合・完全性チェック・設計改善提案（2026-07-21）

**Status: 実装済み・CI実行待ち**(`forge-ai-test`がGitHub Actions上で
実際に成功したことを確認するまで完了扱いにしない)。

CEOから`household_budget`のPreliminary/Final不一致(確認要求ループ)の
報告を受け調査した結果、報告された不具合は既にFORGE v0.3時点で修正
済みであることが判明した(CEOの手元のワークツリーが古い状態だった)。
この説明にCEOが納得した上で、「同種の再発防止」を本命として以下を
実施した。

- `DomainCategory`全14カテゴリと`_DOMAIN_TO_PRELIMINARY`を監査し、
  未登録が無いことを確認した。golden test 36件全てが1件も
  Preliminary/Final不一致を起こさないことも確認した。
- `household_budget`固有の回帰テスト4件・全Domain登録監査テスト
  1件を追加した。
- `_DOMAIN_TO_PRELIMINARY`の完全性を、**モジュール読み込み時に自動
  検証する**仕組みを追加した(欠落があれば`import`の瞬間に
  `RuntimeError`、テストの実行有無に依存しない。当初
  `AssertionError`を使っていたが、`python -O`実行下でも無効化
  されないことを型としてより明確に示すため、CEO指摘によりRuntime
  Errorへ修正した——実際には明示的な`raise`文だったため`-O`による
  無効化は元々発生していなかったが、型名の誤解を避けるための修正)。
- `forge_ai/tests/`(360件)がCIから一度も実行されていなかったことを
  発見し、`.github/workflows/ci.yml`へ`forge-ai-test`ジョブを新設
  した。
- `differs_from_preliminary`が真偽値であり「著しく異なる」という
  程度を表現できていないという設計ギャップについて、
  `docs/adr/ADR-013-template-selection-mismatch-severity.md`として
  設計改善案(未実装、Runtime変更なし)をまとめた。

詳細は`docs/tasks/task041.md`・`FORGE-TEMPLATE-SELECTOR-AUDIT-
report.md`・`FORGE-TEMPLATE-SELECTOR-CI-HARDENING-report.md`・
`FORGE-TEMPLATE-SELECTOR-CI-HARDENING-PATCH1-report.md`参照。

## Task040 — Forge UI刷新: CEO提示モックアップへのUI反映（2026-07-17）

CEOが提示したUIモックアップ(ホーム画面→「例を見る」→入力反映→生成中→
完成→生成されたアプリ、の6ステップフロー)を、実際のForge Flutterアプリへ
反映した。生成の仕組み(Mock/HTTP Repository・Renderer・Runtime)自体は
変更していない。

### 状況
作業開始時点で、テーマ・ホーム画面・例選択Bottom Sheet・生成フロー画面が
既に2026-07-16付でモックアップに合わせて更新済みだった。本セッションでは
これらを検証した上で、UI変更によって実際に壊れていた既存E2Eテスト2件を
発見・修正した。

### 修正内容
`test/e2e/kids_checklist_generation_flow_test.dart`・
`test/e2e/survey_form_validation_flow_test.dart`が、いずれも旧UI
(「これで作る」ボタン→Confirm画面→「この内容で作ります」ボタン)を
前提にしたまま残っており、新しいHomeScreen(Confirm画面を経由せず直接
GenerationFlowScreenへ進む設計)に対して実行すると確実に失敗する状態
だった。新しいUI操作(直接入力→丸い送信ボタン→生成中画面→完成画面→
「アプリを開く」)に合わせて更新した。Mock Generatorが受け取る文言・
返す結果は変更していない。

### 本セッションで発見・修正した自己修正
`survey_form_validation_flow_test.dart`の編集時、置換範囲の指定が
不十分で旧内容の末尾が重複して残ってしまった(brace/paren数の機械的な
確認で発見)。該当部分を削除して修正した。

### 未実行の検証(正直な申告)
Claudeのサンドボックスに Dart SDK が無いため、`flutter analyze`・
`flutter test`とも一度も実行できていない。CEO環境での実行が必須。

### 既知の状態
`confirm_screen.dart`・`generated_app_screen.dart`が新フローから
参照されなくなり孤立している(削除はしていない)。詳細は
`FORGE-UI-REFRESH-report.md`参照。

## Task039 — FORGE-MILESTONE-007 Phase 1.2: Meaning Model導入（2026-07-16）

Meaning ModelをCognitive Pipelineへ正式接続し、複雑な修飾条件
(共有・写真/気分・期限/優先度・在庫低下・回答後一覧・毎週月曜日)を
含む6入力の意味を構造化して、Requirement Extraction・Application
Planning・Decision Traceへ実際に反映した。複数画面化・新規Domainには
進んでいない。

### 実装内容
- `SemanticUnit`/`ExtractedMeaning`(Cognitive専用、Legacy
  `meaning_model.py`とは別型)を新設。
- `CognitiveMeaningExtractor`を実装(Actor/Entity/Action/Constraint/
  Preference/Temporal/State/Evidence spanを決定的なキーワード辞書で抽出)。
- `RequirementExtractorProtocol.extract()`をBlueprint本来の3引数
  (meaning, world, intent)へ復元。
- `Requirement.derived_from`(既定値"world")を新設し、Meaning由来の
  要件を区別。
- `ApplicationPlanner`が、Meaning由来のmandatory要件のtarget_ref/
  operation_refを実際にdata_entities/required_actionsへ反映するよう拡張。
- `DesignCritic`へ`intent_meaning_fidelity`軸(8軸目)を追加。

### 実装中に発見・修正した設計上の問題
Meaning由来かどうかを区別せず全てのmandatory要件のtarget_ref/
operation_refを自動反映すると、Phase 1.1で検証した「Planへ実際に
反映されていない要件はunassignedのままになる」という機械判定機能が
無意味になってしまう問題を発見した。`derived_from`フィールドを追加し、
Meaning由来の要件のみを自動反映の対象とすることで解決した。

### 検証
```
Forge AI tests: 192 PASS(既存164件維持+新規28件)
Backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定の複雑入力6例・既存6例、計12例全てで`CognitivePipelineSuccess`
に到達し、Meaning由来の情報が実際にPlanへ反映されることを確認した。

## Task038 — FORGE-MILESTONE-007 Phase 1.1(残修正)実物監査対応（2026-07-16）

CEOがForge AI 156件・Backend 265件の全合格を確認した上で、Meaning
Model・複数画面化へ進む前の残修正4点(Preliminary/Final不一致判定の
一元化・Decision Trace記録・Requirement割当の実データ判定・
Privacy/Accessibility方針統一)を求めた。**独立監査の結果、4点とも
既に正しく実装・テスト済みであることを確認した。**

### 確認結果
1. `TemplateSelector.select_final()`が`differs_from_preliminary`を
   自ら設定しており、Orchestrator側の上書きは存在しない。Revision
   ループも`while`文で不一致が続く限り繰り返す設計になっている。
2. `preliminary_template_selection`・`final_template_selection`・
   `design_critic`・`cognitive_revision`の4段階全てでDecision Trace
   が記録されている。
3. `Requirement.target_ref`/`operation_ref`(後方互換)が追加され、
   `ApplicationPlanner`が文字列の偶然一致ではなく機械的な参照整合性
   のみで割当判定していることを、専用テストで確認した。
4. `design_critic.py`のdocstringと実装が、Privacy mandatory/
   Accessibility mandatory=high・blocking、Accessibility
   non-mandatory=medium・non-blockingという方針で完全に一致している。

### 本セッションで発見・修正した軽微な冗長コード
Cognitive Revisionループ内で`design_critic.evaluate()`が同一入力に
対して連続2回呼ばれ、2回目の結果が使われていなかった(決定的な
Criticのため動作結果への影響は無いが、無駄な呼び出し)。削除した。

### 検証
```
Forge AI tests: 164 PASS(前回156件から8件増加)
Backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定6例全てで、Domain/Template判定・release_ready=Trueを維持し、
Decision Trace件数が2件→5件(Template Selection・Critic・
Revisionの記録追加分)に増えたことを確認した。

## Task037 — FORGE-MILESTONE-007 Phase 1.1: 契約精度・品質評価・UX改善（2026-07-16）

CEOの実物監査(139/265件全合格を確認済み)で指摘された7点を修正した。
新しいDomain・大規模機能は追加せず、既存Minimal Sliceの契約精度・
品質評価・ユーザー体験の改善に限定した。

### 修正内容
1. 実装位置づけを「Blueprint v1.3の実装」から「M007 Phase 1 Minimal
   Cognitive Slice」へ訂正(Meaning Model未実装、実装済み13段階を明記)。
2. `run_cognitive_pipeline()`へ`provider`を正式な引数として復元し、
   Compilerへ実際に注入されることをテストで確認した。
3. Template Selectionの同点解決を、Preliminary候補優先→Dominant
   action一致数→Data lifecycle一致数→genericの順で決定的にした
   (辞書登録順への暗黙の依存を解消)。
4. Validation既定を「エラーにせず何もしない」1件から、空入力時の
   無視(既存M005教訓)と、必須項目未達成時の理由表示・入力保持・
   修正方法明示・フォーカス移動という5件へ分割した。
5. `CriticReport`へ`implemented_checks_score`・`coverage_ratio`・
   `evaluated_axes`・`unevaluated_axes`を追加し、score=1.00がアプリ
   全体の品質1.00を意味しないことを明示した。未割当のmandatory要件・
   Privacy要件はrelease_readyをblockingし、単一画面のnavigation不要と
   複数画面でのnavigation_edges欠落を区別した。
6. `intent_extraction_confidence`・`domain_coverage`・`score_margin`の
   3指標を明示的に組み合わせるHuman Confirmation判定へ変更した。

### 実装中に発見した実バグ
「data」カテゴリの要件が常に未割当扱いになっており、指摘5の
mandatory-blockingルールを適用すると6例全てが`NeedsConfirmation`へ
落ちてしまう問題を発見した。実際には単一画面のkey_elementsが
data_entities全てを含むため実質的に充足されており、
`application_planner.py`の割当判定漏れが原因だった。修正済み。

### 検証
```
Forge AI tests: 156 PASS(既存139件維持+新規17件)
Backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定6例全てで、Domain/Template判定結果を変えずに
`CognitivePipelineSuccess`へ到達し、Critic/Qualityスコアが正直な値
(implemented_checks_score=0.93、coverage_ratio=0.50)になることを確認した。

## Task036 — FORGE-MILESTONE-007 第一段階実装: Cognitive Pipeline最小実装（2026-07-15）

`docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md` v1.3を実装契約として、
既存`run_pipeline()`を無変更のまま、`run_cognitive_pipeline()`という
独立したFacadeでCognitive Pipelineの最小実装を行った。

### 実装開始前に発見・修正した重大な不具合
着手時点でforge_ai/既存80テストのうち3件が失敗していた。原因は
`DomainCategory`へTASK_MANAGEMENT/SURVEY/SCHEDULEを追加した際、
対応する`Domain`定義本体(`_BUILTIN_DOMAINS`)への追加が漏れていた
ため。3つのDomain定義を追加し修正した(最優先で対応)。

### 新規実装(18項目)
Cognitive型・Protocol・Context・Dependencies・Outcomes(3型Union)・
Error Model・Input Normalization・簡易Ambiguity Detection(2分類)・
簡易Intent Recognition(日本語キーワード辞書)・Domain Classification
(実スコアリング)・World Model Construction(Domain+Intent)・
Requirement Extraction(第一段階簡略化、2引数)・Preliminary/Final
Template Selection(11 Family対応)・簡易Application Planning・
最小Design Critic(4軸)・Revision Engine・CognitiveOrchestrator・
run_cognitive_pipeline() Facade・Unit/Integration/Golden Test(56件)。

### 検証(実行結果)
```
forge_ai tests: 139 PASS(既存80件維持+新規56件+Domain拡張3件)
backend tests: 265(248 PASS + 17 SKIP、無影響)
```
CEO指定6例(買い物・タスク管理・日記・アンケート・予定・在庫)全てで
`CognitivePipelineSuccess`に到達することを実際に実行して確認した。

### 既知の制限
Meaning Model未実装(Requirement Extractorは2引数)。Ambiguity
Detection・Design Criticは一部の分類/評価軸のみ実装。複数画面
Application Planning未対応。詳細は`FORGE-MILESTONE-007-PHASE1-report.md`
参照。

## Task035 — FORGE-MILESTONE-007 PREPARATION 実物監査(4回目)対応(8点修正、v1.3)（2026-07-15）

CEOが、前回の7点修正(Legacy/Cognitive分離・M006認知順序・Requirements
入力・Preliminary/Final分離・Facade分離)を承認した上で、Outcome生成
API・依存注入API・段階数・Confidence計算・文書整合性に実装ブロッカーが
残っていることを指摘した。以下8点を修正し、Blueprintをv1.3として
全面書き直した。**新規コードは追加していない。**

### 修正内容
1. `CognitivePipelineOutcome`(Union型エイリアス)へ`.success(...)`等の
   メソッド呼び出しをする疑似コードを撤回。対応する具体的なdataclassを
   直接構築する形へ修正(型として成立しない疑似コードだった)。
2. `CognitivePipelineSuccess`を`context`・`ir`・`initial_quality`の
   3フィールドへ簡素化し、`CognitiveContext`と情報を重複保持しない
   設計へ変更。
3. `CognitiveDependencies`を専用dataclassとして定義し、`**`展開
   (dataclassは非対応)をやめ、単一引数として渡す設計へ修正。
4. 段階数を「14 Transformation Stage + 1 Terminal Outcome(M004側)+
   3 M005 Post-processing Stage」へ最終確定。「16段階」という表記を
   撤回し、`FORGE_COGNITIVE_ARCHITECTURE_V2.md`・関連図2件・ADR-008を
   一括更新した。
5. `DomainClassification`に安全性条件(全スコア0→Generic確定、同点→
   score_margin=0.0)を追加。confidenceの2定義案を比較し、Intentの
   情報をどれだけ説明できたかを測る式を採用(単純な相対比較は過大評価
   リスクがあるため却下)。raw_score/normalized_scoreを区別する
   `DomainCandidate`型を新設。
6. Preliminary/Final Template Selection不一致時の再計画を、Cognitive
   Revisionへ一本化(同じ入力でPlannerを再実行する設計は、決定的な
   実装なら無意味なため撤回)。
7. `NotImplementedError`をCognitiveOrchestrator内で捕捉しない設計へ
   変更し、Provider障害が`CognitivePipelineFailed`(planning_error相当)
   へ誤って吸収されないことを保証した。
8. Blueprint・報告書を全面書き直し、旧設計の記述を本文から分離して
   14章(設計の変遷、Superseded Design History)へ集約した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task034 — FORGE-MILESTONE-007 PREPARATION 実物監査(3回目)対応(7点修正)（2026-07-15）

CEOが、前回の4点修正(Facade分離・Outcome3型Union・Quality責務・
Error mapping)を承認した上で、既存Legacy Protocolへ無理に合わせる形で
M006とM004の不一致を解決していた点を指摘し、実装開始承認を保留した。
以下7点の追加修正を行った。**新規コードは追加していない。**

### 修正内容
1. Legacy Protocol(既存、無変更)とCognitive Protocol(新規、
   `CognitiveIntentRecognizerProtocol`等)を完全に分離(Task4)。
2. M006の認知順序(Intent→Domain→World→Meaning)を、Legacy Protocolの
   都合で変更せず維持(Task3.3)。
3. `CognitivePlannerProtocol.plan()`にrequirementsを必須引数として
   追加し、渡し忘れを型レベルで防止(Task3.3・4.2)。
4. Preliminary Pattern CandidatesをOrchestratorが明示的に呼び出す
   独立ノードへ変更(Application Planner内部への隠蔽を廃止、Task3.3、
   ADR-008一部訂正、`docs/diagrams/01`・`07`を更新)。
5. `DomainClassification`を、Intent由来のconcept/actionと各Domainの
   実際の一致度に基づくスコアリング契約へ全面書き換え。
   `score_margin`フィールドを追加(Task4.3)。
6. `CognitiveWorldBuilderProtocol.build(classification, intent)`が
   DomainとIntentの両方からWorldを構築する契約へ変更(Task4.4)。
7. Boolean Feature Flag・「provider_error等」・「Thin Wrapper化」・
   「7つの新設サブディレクトリ」(実際は6つ)等の古い記載を本文から
   削除・訂正。

### 本セッションでの追加発見
Preliminary Pattern Candidatesを独立ノード化した結果、M004側の段階数が
13→14へ増加し、M006本体の「全16段階」という記載と、更新後の図
(17ノード)との間に新たな数の不一致が生じた。CEO確認事項として提示した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task033 — FORGE-MILESTONE-007 PREPARATION 実物監査対応(4点修正)（2026-07-15）

CEOがImplementation Blueprintを実コードと突き合わせて監査し、
ディレクトリ構成・Immutable Context・単一Orchestrator・依存規則・
段階Migration・テスト方針は承認の上、実装開始前に4点の修正を求めた。
**新規コードは追加していない。**

### 修正内容
1. `needs_confirmation`を既存`PipelineResult`(7フィールド必須)へ
   ダミー値経由で変換する設計を撤回。`run_pipeline()`(既存、無変更)
   とは別に`run_cognitive_pipeline() -> CognitivePipelineOutcome`
   (Success/NeedsConfirmation/Failedの3独立dataclass Union)という
   新Facadeへ分離した。Boolean Feature Flag方式は撤回(ADR-009新設)。
2. 既存Protocol(`IntentBuilderProtocol.build()`等)が`process(context)`
   統一メソッドを持たないことを確認し、Orchestrator疑似コードを
   実際のメソッド名で呼ぶ形へ書き直した。
3. Initial Quality(M004、Repair前)/Final Quality(M005、Repair後の
   既存実装済みロジック)の責務分担を明記した。
4. 「未捕捉CognitiveErrorはprovider_error等へ分類される」という不正確な
   記述を、既存`prompt_pipeline.py`の実際の例外捕捉順序
   (NotImplementedError→provider_error、それ以外の Exception→
   planning_error)に基づき訂正した。ConfirmationRequiredが例外として
   Orchestrator外へ漏れないよう、主要経路を例外を使わない直接returnへ
   変更した。

### 本セッションでの追加発見
既存`IntentBuilderProtocol.build(meaning, world)`のシグネチャと、
M006 3章の掲載順(Intent Recognition→Domain→World→Meaning)の間に
実行順序の食い違いがあることを発見し、Task3の疑似コードでデータ依存に
従った実行順(Domain→World→Meaning→Intent)へ明確化した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task032 — FORGE-MILESTONE-007 PREPARATION: Implementation Blueprint（2026-07-15）

M006(Cognitive Architecture v2.0、CEO承認済み)を実装可能な設計へ
落とし込む「Implementation Blueprint」を作成した。**新規コードは
0行(Python/Dartとも無変更)。**

### 成果物
- `docs/spec/FORGE_M007_IMPLEMENTATION_BLUEPRINT.md`(新規、約710行)。
  Task1(ディレクトリ設計)〜Task9(Migration Plan)の9タスクを全て記述。
- `docs/diagrams/10_m007_dependency_graph.md`(新規、依存図)。

### 設計の要点
- **既存ファイルは一切移動しない**: `forge_ai/core/`直下の既存7ファイル
  (domain_model/world_model/meaning_model/intent_model/planner/
  compiler/pipeline)は位置を変えず、M006の新規認知能力は
  `core/`配下の新設7サブディレクトリ(input_processing/understanding/
  planning/critic/confirmation/orchestration、+既存core/)へ追加する。
- **Cognitive Context**: Immutable(frozen dataclass)、`with_*`
  メソッド経由でのみ「更新」(実質は新インスタンス生成)。
- **Pipeline Orchestrator**: 16段階の実行順序を知る唯一のコンポーネント。
  各モジュールは互いを呼ばず、依存規則(Task5)で同階層間の直接import
  も禁止する。
- **Feature Flag方式のMigration**: `run_pipeline()`へ
  `use_cognitive_pipeline: bool = False`を追加するのみとし、既定Falseに
  より既存M005・既存80テストへの影響をゼロにする設計とした。
  Rollbackはフラグを触らないだけで完了する。
- **Error Model**: forge_ai/側`PlanningError`とM005側
  `pipeline_errors.PlanningError`が名前は同じだが別クラスであることを
  明記し、階層関係(段階レベル詳細 vs HTTPカテゴリ集約)として設計した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task031 — FORGE-MILESTONE-006 実物監査(2回目)対応(4点修正)（2026-07-15）

CEOがM006成果物(main spec・ADR7件・図9件・例6件)を実物監査し、Hybrid
方式・Decision Trace・Cognitive Revision/Schema Repair分離・M004/M005
責務境界は承認の上、正式確定前に4点の文書修正を求めた。**新規コードは
追加していない(設計文書のみ)。**

### 修正内容
1. Cognitive Pipelineの段階数不一致(「全16段階」と記載しながら実際は
   14段階)を解消。Design Critic後に「Cognitive Revision」「Human
   Confirmation / Escalation」を独立段階として追加し、真の16段階へ統一。
2. Confidence/Ambiguityの優先順位を統一。「Privacy/Safety/Permission
   関連HIGH ambiguity→confidence不問で必ず確認」「Domain confidence
   <0.5→原則確認」「低リスクかつ可逆的な場合のみGeneric仮設計」という
   3段階順位へ整理し、旧来の矛盾する2閾値(0.3/0.5)を0.5/0.8の2閾値へ
   簡素化。
3. Ambiguity Detection失敗時の「ambiguities=()で楽観継続」を廃止し、
   `detection_status="failed"`/`overall_severity="unknown"`を新設。
   Privacy/Health/Welfare等は確認・安全停止、低リスク時のみwarning付き
   限定継続へ分岐。
4. Application Planning/Template Selectionの隠れた循環依存を解消。
   Application Planningの内部フェーズとして「Preliminary Pattern
   Candidates」を新設し、Template Selectionを「Final Template
   Selection」として再定義(ADR-008新設)。不一致時の再計画はCognitive
   Revisionとカウンタを共有し、新たな独立ループを作らないことを明記。

### 本セッションでの追加確認
ADR新設(7→8件)に伴う表記漏れ2箇所(0章・21章)を発見・修正した。

### 検証
```
Backend tests: 265(248 PASS + 17 SKIP)
Forge AI tests: 80 PASS
```
無影響を再確認。`backend/app/ai/native/`・Flutter・M005も無変更。

## Task030 — FORGE-MILESTONE-006: Cognitive Architecture v2.0 設計（2026-07-15）

「M006で扱う『Forgeがどう考えるか』を実装前に設計・固定する」という
Architecture Design Onlyの依頼に基づき、以下を新規作成した。
**新規コードは0行(Python/Dartとも無変更)。**

### 成果物
- `docs/spec/FORGE_COGNITIVE_ARCHITECTURE_V2.md`(新規、約960行):
  Cognitive Pipeline(16段階、各9項目で定義)・Domain Model(12 Domain、
  保存方式比較)・World Model(Events/States/Permissions追加)・Meaning
  Model・Requirement Extraction・Planner・Template Selection(11
  Template Family)・Design Critic(14評価軸)・Self-Revision Loop
  (Schema Repairとの責務分離)・LLM使用方針(全16段階の分類)・
  Confidence Model・Decision Trace・Learning-Ready Design・Failure
  Modes(14種)・M004/M005責務境界・Native扱い・3方式比較(Rule-Based/
  LLM中心/Hybrid、Hybrid採用)・完了条件・自己レビュー。
- `docs/adr/ADR-001`〜`ADR-007`(7件): Hybrid採用・Domain Before UI・
  Rule Before Prompt・Cognitive RevisionとSchema Repairの分離・
  Decision Trace必須化・Provider Independence維持・Confidence の
  制御フロー反映、それぞれの理由・却下案・影響・見直し条件。
- `docs/diagrams/01`〜`09`(Mermaid、9件): Cognitive Pipeline・Module
  Responsibility・Runtime Call Sequence・Decision Trace Flow・
  Revision Loop・Domain Knowledge Flow・Template Selection Flow・
  Confidence Escalation Flow・M004/M005 Boundary。
- `docs/examples/01`〜`06`(6件): 買い物リスト・家計簿・日記・満足度
  アンケート・福祉支援記録・病院予約。福祉支援記録は、Privacy起因の
  HIGH Ambiguityによりパイプラインが確認要求で停止する例として
  意図的に選定した(他5例はApplication Planまで到達)。

### 検証
新規コードを追加していないため、Python(backend 265件・forge_ai 80件)・
Flutterとも無影響。実行して確認した。

## Task029 — FORGE-MILESTONE-005 実物監査(3回目)対応（2026-07-14）

CEOがCEO環境で`Ran 265 tests / FAILED (failures=2)`を報告。原因は、
前回追加したFix 1(Engine/Provider許可リスト化)により、未知の
engine/provider文字列がPydantic入力層で拒否されるようになった結果、
2件の既存テストが「許可リスト導入前の古い経路」を期待したままに
なっていたこと。**コード本体は変更していない**(テストの期待値・
名前・コメントのみ修正)。

### 修正
- `test_unsupported_engine_returns_error_envelope` →
  `test_unknown_engine_string_is_rejected_by_pydantic_before_reaching_pipeline`
  へ改名。期待値を`category=planning_error`から
  `category=request_error, sub_reason=schema_invalid, HTTP 422`へ修正。
- `test_unregistered_provider_returns_provider_error` →
  `test_unknown_provider_string_is_rejected_by_pydantic_before_reaching_pipeline`
  へ改名。同様に`category=provider_error, sub_reason=unavailable`から
  `category=request_error, sub_reason=schema_invalid, HTTP 422`へ修正。
- `test_unimplemented_provider_returns_provider_error`(`provider=
  "openai"`)を、`status_code=503`・`sub_reason=unavailable`まで
  明示的に検証するよう強化。

### 確定した契約
```
未知のengine/provider文字列 → request_error / schema_invalid / HTTP 422
既知だが未実装のprovider     → provider_error / unavailable / HTTP 503
```

### 検証(統一済み件数)
```
Backend tests: 265(248 PASS + 17 SKIP、Claude環境)
Forge AI tests: 80 PASS
python -m compileall backend forge_ai: exit code 0
```
`docs/reports/FORGE-MILESTONE-005-report.md`を、過去3回の監査を
通じて蓄積した古い件数表記(255/9件等)を整理した最終版へ全面更新した。

## Task028 — FORGE-MILESTONE-005 実物監査(2回目)対応（2026-07-14）

CEOがHTTP層を含めて実機検証(Backend 255/255・HTTP 9/9・forge_ai 80/80・
Python compile PASS)した上で、正式完了前に3点の修正+軽微な修正1点を
指摘された。

### Fix 1: Engine/Providerの公開HTTP APIレベルでの許可リスト化
`GenerationOptionsDTO`の`engine`/`provider`を`str`から`Literal`へ変更。
`engine: Literal["forge_ai"] | None`、
`provider: Literal["mock", "openai", "claude", "gemini", "oss"] | None`。
Router内部の`ProviderRouter`は`native`/`local`/Provider名としての
`forge_ai`を後方互換のため引き続き解決できるが、HTTP経由ではこれらを
受理しない(Pydanticが422で弾く)。

### Fix 2: Plan変換時の情報消失(unclassified_diagnostics)を修正
`plan_ir_from_application_plan()`の戻り値を`PlanIR`から
`PlanConversionResult(plan_ir, warnings)`へ変更。以前は
presentation conceptと判定してdata_neededから除外した要素の警告を
変数に貯めるだけでどこにも返していなかった。`Diagnostics`・
`DiagnosticsDTO`へ`conversion_warnings`を追加し、HTTPレスポンス経由で
確認できるようにした。

### Fix 3: HTTP公開APIのmax_repair_attempts上限を2回に制限
`Field(default=None, ge=0, le=10)`だったものを`le=2`へ修正。M005契約
「Repair最大2回・Validator最大3回」との矛盾を解消。0/1/2は許可、
3以上はHTTP入力層で422になる(境界テストを追加)。

### 軽微な修正
`prompt_pipeline.py`・`forge_ai_adapter.py`の冒頭docstringが「このファイル
だけがforge_aiを直接importする」という、実コードと矛盾する(両ファイルとも
forge_aiを直接importする)自己矛盾した記述だったため、正確な記述へ修正した。

### 変更したテスト
- `test_forge_ai_adapter.py`: `PlanConversionResult`型変更に伴い
  `TestPlanAdapter`の6件を`result.plan_ir.X`形式へ更新、新規2件
  (`warnings`が返ることの確認)を追加(計18件)。
- `test_http_api.py`: Fix1(3件)・Fix3(3件)・Fix2(1件)の新規7件を追加
  (計17件、Claude環境ではfastapi未インストールのためスキップ継続)。

### 検証
```
$ python -m unittest discover -s backend/tests -p "test_*.py"
Ran 265 tests in 0.025s
OK (skipped=17)

$ python -m unittest discover -s forge_ai/tests -p "test_*.py"
Ran 80 tests in 0.015s
OK
```
248件(backend、HTTP17件を除く)+80件(forge_ai)=328件を実行・全合格
確認した。HTTP17件はCEO環境での再実行が必要(前回9件は実機PASS済み、
今回追加した7件は未検証)。

## Task027 — FORGE-MILESTONE-005: Backend AI Integration Implementation（2026-07-14）

Adapter Contract v1.1に基づき、M004(forge_ai/)とM005(backend/app/ai/
runtime/)を実際に接続する実装を行った。

### 新規/変更ファイル
- `backend/app/ai/runtime/forge_ai_adapter.py`(新規): Intent/Plan/
  RepairIssue/RepairResult/Quality の5つのAdapter関数。CEO指摘4
  (actions_needed固定)・5(key_elements誤分類)への対応を含む。
- `backend/app/ai/runtime/forge_ai_provider_bridge.py`(新規):
  `ForgeAIProviderBridge`。forge_ai.AIProvider Protocolを満たしながら
  M005のLLMAdapterへ委譲する。
- `backend/app/ai/foundation/providers.py`(変更): `MockLLMAdapter`を
  新規実装(指示書「実装するProviderはMockのみ」)。他4 Provider
  (OpenAI/Claude/Gemini/OSS)はStubのまま維持。
- `backend/app/ai/foundation/interfaces.py`(変更): `PlanIR`へ
  `unassigned_actions: tuple[str, ...] = ()`を後方互換で追加。
- `backend/app/ai/runtime/provider_router.py`(変更): `mock`を登録
  (8名前目)、`default_provider_name()`を`"forge_ai"`から`"mock"`へ修正。
- `backend/app/ai/runtime/pipeline_errors.py`(新規): Error Contract
  5分類(+ HTTPリクエスト層用の`request_error`)の例外階層。
- `backend/app/ai/runtime/prompt_pipeline.py`(全面書き換え): 旧
  Protocol注入方式を廃止し、Facade方式
  (`forge_ai.core.pipeline.run_pipeline()`を1回呼ぶ)へ全面改訂。
  Repair Loop(`RepairEngine(provider, max_iterations=1)`)・
  Repair後Quality再評価を実装。
- `backend/app/schemas/ai.py`(全面書き換え): Request/Response/
  Error Envelopeのpydanticモデル。
- `backend/app/routers/ai.py`(全面書き換え): `POST /api/v1/ai/generate`
  をPromptPipeline経由の実装へ更新。
- `backend/app/exception_handlers.py`(新規): `RequestValidationError`・
  `ForgeAIPipelineError`・`Exception`の3種の例外ハンドラ。共通Error
  Envelopeへ統一。JSON構文エラー(400)とスキーマエラー(422)を
  `type == "json_invalid"`で判定。
- `backend/app/main.py`(変更): 例外ハンドラの登録。
- `scripts/verify.ps1`(変更): `pip install -r requirements.txt`
  ステップを追加(HTTPテストがfastapi/pydantic無しでは自己スキップ
  するため、CEO環境で実際にテストが走るようにする)。

### 新規テスト(実行・検証済み、HTTPのみ未検証)
- `backend/tests/test_forge_ai_adapter.py`(新規16件、実行・全合格): 
  Adapter関数群の単体テスト。CEO指摘4・5の回帰テストを含む。
- `backend/tests/test_ai_runtime.py`(PromptPipeline部分を全面書き換え):
  `unittest.mock`でrun_pipeline/validate_forge_document/RepairEngine/
  QualityEngineを制御し、Facade呼び出し1回・Repair Loop・二重ループ
  防止(`max_iterations=1`の検証)・Quality再評価を検証。
- `backend/tests/test_http_api.py`(既存、1箇所の実装ミスを修正):
  `test_unsupported_engine_returns_error_envelope`が期待していた
  HTTP 200を422へ修正(実際のルーター実装は`ProviderError`以外
  すべて422を返すため、200という期待値が誤りだった)。

### 実行結果(事実)
```
$ python -m unittest discover -s backend/tests -p "test_*.py"  # repoルートから
Ran 255 tests in 0.022s
OK (skipped=9)
```
9件はHTTPテスト(`test_http_api.py`)で、fastapi/pydanticがClaude
環境に無いため自己スキップした(エラーではない)。それ以外の246件は
実行・全合格を確認した。

### 未検証事項(正直な申告)
- HTTP層(`schemas/ai.py`・`routers/ai.py`・`exception_handlers.py`・
  `main.py`・`test_http_api.py`)は、Claude環境に`fastapi`・`pydantic`が
  インストールできない(ネットワーク不可、実際に`pip install`を
  試行し失敗を確認済み)ため、**一度も実行できていない**。
  構文は`ast.parse`で静的に確認したのみ。
- JSON構文不正(400)とスキーマ不正(422)の判定
  (`_is_json_syntax_error`、`type == "json_invalid"`という判定基準)
  は、Pydantic v2の一般的な既知の挙動に基づく推測であり、実行確認
  できていない。CEO環境での実機確認が必要。

## Task026 — Adapter Contract v1.1(CEO実コード監査の6指摘に対応）（2026-07-14）

CEOが`ADAPTER_CONTRACT_V1.md`(v1.0)を実コードと突き合わせて監査し、
「Concrete type flow: FAIL」「Pipeline ownership: FAIL」を含む判定を
受けた。以下6点を修正した。**新規コードは追加していない(文書修正のみ)。**

### 最重要修正(FAIL判定の解消)
1. **型境界の修正**: `forge_ai.Compiler.compile()`が`ApplicationPlan`
   しか受け取れず、v1.0の「ApplicationPlan→PlanIR変換→Compilerへ渡す」
   という設計は型エラーになることを、実際にソースを確認して認めた。
   CEO推奨の「粗粒度Facade方式」(`forge_ai.core.pipeline.run_pipeline()`
   を1回だけ呼ぶ)へ全面的に設計変更した。この関数は既に存在しており、
   新規実装は不要だった。
2. **パイプライン所有者の一本化**: M004(`run_pipeline()`)を認知・
   設計パイプラインの唯一の所有者とし、M005(`PromptPipeline`)は
   HTTP/Provider選択/Validator/Repair制御/エラー変換/Diagnostics/
   Response整形に責務を限定した。

### その他の修正
3. Forge IR境界を「dict[str, Any]の型一致」ではなく「Validator合格
   済みdictのみ」へ訂正。
4. `Intent.required_actions`を`actions_needed=()`固定で破棄していた
   問題を修正。`PlanIR`に`unassigned_actions`フィールドを追加する
   必要性を明記(次フェーズの実装課題)。
5. `key_elements`を無条件で`data_needed`へ写す設計を修正し、
   データ実体/ユーザー操作/画面表現概念の3分類方針を追加。
6. HTTP Contractで`engine`(forge_ai)と`provider`(mock等)を分離し、
   Provider既定値を`"forge_ai"`から`"mock"`へ修正。
7. HTTPエラーコードを400(JSON構文不正のみ)/422(スキーマ・型・
   意味的失敗)へ統一。

### 検証
新規コードを追加していないため、Python 224件(backend)+80件
(forge_ai)は無影響。実行して合格を再確認した。

## Task025 — FORGE-MILESTONE-005: Backend AI Integration Adapter Contract（2026-07-14）

CEOロードマップ(M004完了→M005 Adapter Contract→M005実装→M006 Pipeline→
M007 LLM Adapter→M008 Repair→M009 Quality→M010 Native AIβ)に基づき、
M005実装の前段としてAdapter Contractを設計した。**実装は一切行っていない
(設計のみ)。**

### 成果物
`docs/spec/ADAPTER_CONTRACT_V1.md`(新規、約580行)。以下を含む。

- **Shared Types決定**(5ペア): Intent(Adapter変換)・Plan/ScreenPlan
  (Adapter変換)・Forge IR(dictで既に共通、Adapter不要)・RepairResult
  (Adapter変換)・QualityScore/CriticResult(Adapter変換)。
- **設計フェーズで発見した重要なリスク**: forge_ai.RepairEngine(内部で
  最大2回リトライ)をそのままM005のAIRepairとして使うと、M005外側の
  リトライ(最大2回)と掛け合わさり、最大4回の修復試行が発生する
  「二重ループ問題」を発見した。共通指示書6.5節「修正回数の上限」を
  静かに破る実装ミスになりかねない箇所であり、実装着手前に発見できた。
  対応方針(forge_ai.RepairEngineをmax_iterations=1で構築する)を記録した。
- **Error Contract**: 5分類(validation/planning/provider/runtime/
  unexpected)+HTTPステータス対応+provider_errorのsub_reason細分化。
- **Provider Contract**: forge_ai.AIProvider(Prompt型)とM005の
  LLMAdapter(文字列+schema)の関係を整理。後者を実LLM接続の正規契約とし、
  前者はBridge経由で接続する設計とした(統合しない)。
- **HTTP Contract**: `POST /api/v1/ai/generate`のRequest/Response/
  Error/Version形式。
- **Validator Position**: 既存`prompt_pipeline.py`の実装済みフロー
  (Repair前後で必ず検証、Criticより必ず先)を正式な契約として確定。
- **Sequence Diagram**: Conceptual Flow・Runtime Call Sequence・
  Dependency Diagram・Adapter Boundaryの4種類。

### 検証
新規コードを追加していないため、Python 224件(backend)+80件
(forge_ai)は無影響。実行して合格を再確認した。

## Task024 — Forge AI Architecture v1.0 修正(CEOレビュー3点対応)（2026-07-14）

CEOによる`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`実物監査を受け、
確定前に3点を修正した。新規コードは追加していない(文書修正のみ)。

### 修正内容
1. **接続図の分離**: 「概念的な処理順序」と「実行時の呼び出し方向」が
   1つの図に混在していた問題を修正。Conceptual Pipeline(5.1)・
   Runtime Call Graph(5.2)・Source-code Dependency Direction(5.3)の
   3種類へ分離した。実行時の基本方向はM005(Backend AI Integration)が
   M004(Forge AI Core)を呼び出す構造であることを明記(以前は逆方向に
   読める図だった)。実際に`grep`でM005→M004のimportがまだ存在しない
   (未接続)ことを確認した上で図を作成した。
2. **過去記録へのM005読み替え注記**: `docs/DECISIONS.md`(D50〜D55、
   ブロック注記+各見出しへ`(→ M005)`タグ)・`TECH_DEBT.md`(TD20〜TD22、
   同様)・`docs/reports/FORGE-MILESTONE-004-report.md`(冒頭に注記)・
   `CHANGELOG.md`(Task019、注記)へ、歴史的記録を変更せず注記のみ追加した。
3. **ADR Statusの精緻化**: 「Status: FROZEN」を「Status: ACCEPTED —
   RESPONSIBILITY BOUNDARIES FROZEN」「Interface Contract: PROVISIONAL」
   へ修正。Intent/Plan/Forge IRの共有型・M004↔M005 Adapter API・HTTP API
   契約・エラー伝播形式・Provider実装方式の5点を、未凍結(実装時に
   決定する)項目として明示した(6.1章新設)。

### 検証
新規コードを追加していないため、Python 224件(backend)+80件
(forge_ai)は無影響。実行して合格を再確認した。

## Task023 — Forge AI Architecture v1.0 (Architecture Freeze)（2026-07-14）

CEOレビュー「M004は実装マイルストーンではなく、Architecture Freeze
マイルストーンとして整理してください」に基づき対応した。

### 実施内容
- `docs/spec/FORGE_AI_ARCHITECTURE_V1.md`(新規、ADR)を作成し、以下を確定。
  - **M004 = forge_ai/(Forge AI Core)のみ**。旧「FORGE-MILESTONE-004:
    Native AI Phase-1」は**M005(Backend AI Integration)**として正式に読み替え。
  - `backend/app/ai/native/`は**M006以降・Experimental**とし、
    CEO承認なしに変更しないことを確定。
  - 実際のファイルタイムスタンプ調査による時系列(forge_ai/: 7/12、
    backend/app/ai/runtime/第1波: 7/13早朝、第2波: 7/13午前、
    backend/app/ai/native/: 7/13午前、第2波の直後)を記録。
  - 責務境界図(forge_ai/ vs backend/app/ai/runtime/ vs
    backend/app/ai/native/)を作成。
  - 接続図(User → forge_ai → backend runtime → Validator → Forge
    Runtime)を作成。現時点では**全区間が未接続**であることを明記。
- `backend/app/ai/runtime/README.md`・`backend/app/ai/native/README.md`
  を更新し、新しいマイルストーン番号(M005・M006以降)を反映。
- `docs/spec/NATIVE_AI_STATUS_NOTE.md`・`forge_ai/docs/DESIGN_DECISIONS.md`
  (D7)を更新し、番号重複が解消されたことを記録。

### 過去記録の扱い
CHANGELOG.md Task019・docs/DECISIONS.md D50〜D55・TECH_DEBT.md
TD20〜TD22・`docs/reports/FORGE-MILESTONE-004-report.md`は書き換えず、
歴史的記録として残した(本ADRを正典として参照する運用へ変更)。

### 新規コードは無し
本Taskは設計文書(ADR)の作成のみであり、`forge_ai/`・
`backend/app/ai/runtime/`・`backend/app/ai/native/`のPythonコードは
一切変更していない。

## Task022 — FORGE-MILESTONE-004: Forge AI v0.1 (Cognitive Engine) 正式提出（2026-07-14）

「FORGE-MILESTONE-004を開始してください。Domain Model・World Model・
Meaning Model・Intent Model・Plannerを実装してください」という依頼を
受けた。この依頼内容と完全に一致する実装(`forge_ai/`)が既に存在し
80テスト全合格の状態だったため、ゼロから再実装せず、既存実装を
検証・強化した上でM004の正式提出物として採用した(詳細は
`forge_ai/docs/DESIGN_DECISIONS.md` D6)。

### 重要な発見: 「FORGE-MILESTONE-004」という名前の重複
`docs/reports/FORGE-MILESTONE-004-report.md`という、同じ名前で
異なる内容(2026-07-13付「Native AI Phase-1（Intent Engine）」、
`backend/app/ai/runtime/`拡張、D50〜D55・TD20〜TD22で記録済み)の
報告書が既に存在することを確認した。前回のFORGE-MILESTONE-003.1で
このファイル群を「由来不明」と報告していたが、実際には正規の記録が
あったため、その報告を訂正した。

### 実施内容
- `forge_ai/`全ソースファイル(20件)のimport文を再監査し、LLM SDK・
  Flutter・Backend APIへの依存が無いことを再確認。
- `py_compile`で構文エラー0件、`ast`静的解析で型ヒント・Docstring
  100%を再確認。
- 80件のUnit Testを再実行し、全件合格を再確認。
- `docs/spec/NATIVE_AI_STATUS_NOTE.md`を更新(訂正を含む)。

### 未解決のまま残した点
- `forge_ai/`と「Native AI Phase-1」(`backend/app/ai/runtime/`)の
  統合方針、および名前の重複整理はCEO判断事項として残す。
- `backend/app/ai/native/`の由来は依然未確認。

## Task021 — FORGE-MILESTONE-003.1 CEO実機再検証フィードバック対応（2026-07-13）

CEOがCEO環境で実際に`flutter analyze`(PASS)・`flutter build web`(PASS)・
`flutter test`(2件失敗)・`scripts/verify.ps1`(Python exit 9009)を
検証した結果を受けて対応した。

### 修正
- `ForgeStateStore._coerce()`: 「対象キーが存在しない場合、valueの
  実行時型から新規State作成する」という分岐を削除。Forge Languageの
  契約上、state_refは事前宣言されている前提であり、存在しないキーへの
  `set_value`/`set_state`は`ActionResultKind.invalidTarget`として
  失敗すべきだった。この分岐により、CEO実機の`flutter test`で
  `action_result_kind_test.dart`の2件(`set_value`単体・composite経由)が
  失敗していた。既存の`write()`呼び出し箇所が全てこの分岐に依存して
  いないことを確認した上で削除。
- `scripts/verify.ps1`: `python`を固定で呼んでいたため、`py`のみが
  PATHにある環境でexit code 9009(コマンドが見つからない)になっていた。
  `py`を優先し、無ければ`python`にフォールバックする方式へ変更。

### 未検証事項
- 上記修正後の`flutter test`・`scripts/verify.ps1`の実際の再実行は、
  Claude環境にFlutter SDK・PowerShellが無いため行えていない。
  修正内容は手動トレースで期待結果と一致することを確認済み。
  CEO環境での再検証が必要。

## Task020 — FORGE-MILESTONE-003.1 CEOレビュー対応（2026-07-13）

FORGE-MILESTONE-003.1レポートへのCEOレビュー(6項目+メタ指摘)に対応した。

### 修正
- レポート内の確率的表現(「十中八九」)を削除し、「最も可能性が高い仮説」
  という断定しない表現へ統一。
- `ActionResult`に`ActionResultKind`(success/noOp/invalidTarget/
  invalidSource/validationError/runtimeError)を追加し、全8 Action種別
  (navigate/go_back/set_value/toggle_state/reset_state/add_item/
  submit_form/composite)がこの共通enumへ収束するよう統一した。
  既存の`success`/`reason`フィールドは後方互換のため無改変。
  `test/json_ui/runtime/action_result_kind_test.dart`(新規15件)で検証。
- `scripts/verify.ps1`: 最終サマリーをPASS/FAIL/WARNINGの3区分にし、
  `flutter devices`チェックを追加(Chrome未検出時は`-RunChrome`を
  安全にWARNINGスキップ)。
- `backend/tests/test_golden_mock_generator.py`・`tests/golden/*.json`
  (12カテゴリ)を新設。Mock Generator出力を凍結し、変更を即検出する
  Golden Testを追加(実際に1文字改変して検出することを確認済み)。
- `backend/app/ai/runtime/README.md`・`backend/app/ai/native/README.md`
  を新設し、Experimental/Not connectedのステータスをディレクトリ単位で明示。

### 分離
- Native AI / MILESTONE-004関連の話題をM003.1レポートから分離し、
  `docs/spec/NATIVE_AI_STATUS_NOTE.md`として独立させた
  (CEOレビュー「別章ではなく別Issue・別Taskとして切り離す」に対応)。

### テスト
- Python: 224件(既存221件 + Golden Test 3件)、実行・全合格を確認。
- Dart: 新規15件(action_result_kind_test.dart)、Claude環境では未実行。

## Task019 — FORGE-MILESTONE-004: Native AI Phase-1（Intent Engine）（2026-07-13）

> **【2026-07-14注記】** 「FORGE-MILESTONE-004」は現在「M005: Backend AI
> Integration」として読み替える。正典は`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`。

CEO実測(Flutter Test 223 PASS、Runtime基盤完成)を前提に、Forge Native AIの
土台(PHASE1〜9、いずれも設計・Stubのみ、AI推論は未実装)を構築した。
今回はPython(backend/)のみ変更し、Flutter/Dartは一切変更していない。

### 既存資産との重複を避けた設計判断(詳細はDECISIONS.md D50〜D54)
- `IntentIR`(既存)を拡張(entities/platform/complexity/category/
  output_type追加)。新しいIntent型は作らず、後方互換性を維持した。
- `IntentParser`(新規)を、既存`AIPlanner`とは別に追加。`AIPlanner`は
  変更していない。
- `Template`/`TemplateRegistry`(新規): 既存3 Template(checklist/memo/
  form)を構造化メタデータでカタログ化。新規Template実装は追加していない。
- `TemplateSelector`(新規、Stub)。
- `ProviderRouter`へ`native`/`local`エイリアスを追加(新規Provider実装は
  追加していない)。
- `NativeAIRuntime`(新規): 全構成要素を束ねるbundle。
  `is_fully_stubbed()`で「動いたふり」をしていないことを機械的に検証可能。

### テスト
- `tests/test_native_ai_phase1.py`(新規27件)、実行・全合格。
- 既存の`test_all_five_providers_registered`を`test_all_seven_provider_names_registered`
  (7件)へ更新(エイリアス追加に伴う、カバレッジ拡張目的の変更)。
- Python合計: backend 221件・forge_ai 80件、実行・全合格を確認。

### ドキュメント
- `docs/spec/AI_RUNTIME.md`更新。`TECH_DEBT.md` TD20〜TD22追加
  (Output Safety・Prompt Injection・IRバージョニングの未設計を記録)。

### 未実施
- 実際のAI推論(全コンポーネントがStubのまま)。
- Flutter側の変更・検証(今回はPythonのみ)。

## Task018 — FORGE-MILESTONE-003.3: add_item_regression_test.dart 誤検知修正（2026-07-13）

CEO実測(backend Python 192 PASS・forge_ai 80 PASS・flutter analyze警告0・
flutter build web PASS・Chrome起動PASS)のうち、`flutter test`1件のみ失敗。
`add_item_regression_test.dart`の「空白のみ入力」テストが、
`expect(find.text('   '), findsNothing)`でチェックリスト誤追加を判定していたが、
Flutterの`find.text()`はTextField内部のEditableTextの現在値ともマッチするため、
`emptySource`時にクリアされず残る入力欄自身の`"   "`を誤検出していた
(Runtimeの誤りではなくテストコードの誤検知)。判定方法を`ListTile`件数の
前後比較へ変更し修正した。変更対象は当該テストファイルのみ。

## Task017 — FORGE-MILESTONE-003.2: verify.ps1 Encoding Fix（2026-07-13）

CEO実機で`scripts/verify.ps1`が文字化けにより構文エラーで起動しなかった
問題を修正した。**今回はverify.ps1(および関連するREADME記述)のみを
変更し、他は一切変更していない。**

- **根本原因(実際にバイト列を検証して確定)**: ファイルはBOM無しの
  正しいUTF-8だったが、Windows PowerShell 5.1はBOM無し`.ps1`を
  システムのANSIコードページ(日本語Windowsでは既定Shift_JIS)で
  読み込むため、UTF-8の日本語部分が文字化けし構文エラーになった。
- **修正**: `verify.ps1`から日本語を排し英数字のみのメッセージへ変更、
  UTF-8 BOM付きで保存する二重対策を実施。
- `README.md`の該当セクションへ、上記の原因と対策を明記。

## Task016 — FORGE-MILESTONE-003.1: Runtime State Contract Fix & Final Quality Closure（2026-07-13）

CEO実機でChrome起動・複数カテゴリ操作を実施した結果、8カテゴリで生成
成功を確認した一方、家計簿カテゴリの追加操作で`add_item_failed`という
Runtime Errorが実機発生した。根本原因を特定・修正し、全12カテゴリの
Action契約を監査、検証スクリプトを新設した。

### PHASE1〜2: add_item_failedの根本原因と修正
- **根本原因**: 生成JSON自体は完全に正しかった(実際に生成・Validator確認済み)。
  `ForgeStateStore.addChecklistItem()`が、「target/sourceのState参照が
  無効(契約違反)」と「sourceのテキストが空(ユーザーが未入力のまま追加を
  押しただけの正常操作)」を同じ`false`として返し、Dispatcherが両方を
  同一の`add_item_failed` ERRORとしてログしていたことが原因と判断した。
- `AddChecklistItemOutcome`列挙型(`added`/`emptySource`/`targetMissing`/
  `sourceMissing`)を新設し、正常操作(空入力)ではERRORを出さず、
  契約違反のみをERROR扱いにするよう修正した(全カテゴリ共通の一般契約
  として修正。家計簿だけの特別扱いはしていない)。

### PHASE3〜6: 契約監査・テスト
- `backend/tests/test_all_categories_action_contract.py`(新規4件):
  全12カテゴリについて、Validatorとは独立したロジックでAction参照の
  実在性・型一致を再検証。
- `frontend/test/json_ui/add_item_regression_test.dart`(新規4件)・
  `forge_state_store_test.dart`拡張: add_itemの全4アウトカムを単体・
  E2Eレベルで検証。

### PHASE8: Web警告の整理
- `web/index.html`: `mobile-web-app-capable`タグ追加、明示的な
  `viewport`タグを削除(Flutter Webが自動挿入するため、明示すると
  Chrome Console警告が出ることをWeb検索で確認)。
- `flutter/lifecycle channel`警告はFlutter Engine自体の既知の起動時
  タイミング警告(複数の無関係プロジェクトで同一報告を確認)であり、
  コード側での対応不可と判断・文書化。

### PHASE9〜10: 技術的負債
- TD18(Noto Font未同梱)・TD19(計算アプリ等がGeneric fallbackへ落ちる
  実態)を`TECH_DEBT.md`へ追加。

### PHASE12: 検証スクリプト
- `scripts/verify.ps1`・`scripts/verify.bat`新設。Python Test〜
  flutter build webまでを1コマンドで実行し、失敗しても止まらず
  最後にサマリー表示する。Claude環境では未実行(README.md参照)。

### テスト
- Python: 192件(188 + 4新規)、実行・全合格を確認。
- Dart: 静的カウントで新規8件追加。Claude環境では未実行。

## Task015 — FORGE-MILESTONE-003: Analyzer Zero → Chrome Verification → Native AI Foundation（2026-07-12）

CEO実測(Python 167 PASS・**Flutter Test 212 PASS**・Web Build PASS・
Runtime/Chrome/Mock Generator/Language v1.2/Widget v1.1/E2E 全PASS)を受けて、
残る`flutter analyze`警告3件の解消と、Forge Native AI Foundationの構築を行った。

### PHASE1: Analyzer完全ゼロ対応
- `forge_runtime_state.dart`: 未使用import(`forge_form_validator.dart`)を
  自動検出ツールで発見・削除。
- `ForgeStateStore({})`(8箇所、`forge_state_store_test.dart`・
  `forge_action_dispatcher_test.dart`)・`readChecklist`のswitch式・
  `_validationErrors`関連2箇所・`v1_1_widgets_test.dart`の`state ?? {}`に、
  Map/Setの構文的あいまいさを避けるための明示的型引数を追加。

### PHASE6〜9: AI Runtime Foundation(backend/app/ai/runtime/）
- `prompt_pipeline.py`(新規): Natural Language → Intent → Plan → JSON →
  Validator → Critic → Repair → Final JSON のフローを実装。
  `planner.py`・`critic.py`・`repair.py`・`context_builder.py`・
  `provider_router.py`(いずれも既存、責務定義+Stubのみ)と組み合わせる。
- `tests/test_ai_runtime.py`(新規、21件): 型の重複防止・Stubが例外無く
  成功しないことの確認・ProviderRouterの実ルーティング・
  PromptPipelineのRepair Loop(最大試行回数)を検証。

### PHASE10: ドキュメント
- `docs/spec/AI_RUNTIME.md`・`PROMPT_PIPELINE.md`・`NATIVE_AI_ROADMAP.md`新設。

### テスト
- Python: 188件(167 + 21新規)、実行・全合格を確認。
- Dart: CEO実測212件PASS(Claude環境では未実行)。

### 既知の未達成事項
- PHASE1修正後の`flutter analyze`結果はClaude環境で未検証。
- Native AI(forge_ai/との接続)は未実装(意図通り、TD16参照)。

## Task014 — FORGE-MILESTONE-003: Stateful Runtime Foundation（2026-07-11）

Forge Language v1.2を新設(v1.0/v1.1は無改変で凍結維持)。State Store・
Action Dispatcher・Form Validationを正式なRuntime契約として導入した。

### 追加(Language v1.2)
- State型`number`。
- Action型5種: `set_state`/`toggle_state`/`reset_state`/`submit_form`/`composite`
  (v1.0/v1.1の`navigate`/`go_back`/`set_value`/`add_item`は維持)。
- `text_field`/`checkbox`への`validation`プロパティ(6ルール種別)。

### 追加(Dart Runtime、`json_ui/runtime/`新設)
- `ForgeStateStore`: 単一のState Store。汎用read/write + 型別便利メソッド。
- `ForgeActionDispatcher`: 全Actionの一元的な入口。`ActionResult`を返す。
  composite最大10件・ネスト最大3段。
- `ForgeFormValidator`: 6種の検証ルールを実装。

### 変更
- `ForgeRuntimeState`: 内部実装をRuntime層への委譲に置き換えた
  (既存の公開APIは無改変)。
- `forge_renderer.dart`: `navigationDepth`による無限遷移防止、診断ログ
  (`ForgeLogger`)を追加。
- `widget_registry_v1_1.dart`: checkboxはtoggle_state経由に統一、formの
  送信ボタンはsubmit_form経由に変更(Validation実行の要)、text_field/
  checkboxにエラーメッセージ表示を追加。
- Mock Generator(Python/Dart both): Survey Templateのコメント欄に
  `max_length` validationを追加(v1.1→v1.2へバージョン更新)。

### テスト
- Python: 135 → **167件**(v1.2 Schema/Action 32件を追加)。
- Dart: 165 → **211件(静的カウント予測。実行未検証)**。State Store・
  Action Dispatcher・Form Validator単体テスト(40件)、State Binding Widget Test
  (5件)、Survey Form ValidationのE2Eテスト(1件)を新規追加。

### 既知の未達成事項
- 今回追加・変更した全コードについて、Claude環境では`flutter analyze`・
  `flutter test`・`flutter build web`のいずれも実施できていない。

## Task013 — FORGE-MILESTONE-002.2: Web Platform Files Inclusion（2026-07-11）

CEOがFORGE-MILESTONE-002.1提出物で`flutter build web`を実行したところ、
`frontend/web/`が存在せず`This project is not configured for the web`で
失敗した(ZIP内に`frontend/web/`が無いことも確認された)。方針を修正し、
`web/`一式をClaude側で追加した。

### 追加(新規、`frontend/web/`)
- `index.html`・`manifest.json`: Flutter公式ドキュメント
  (`docs.flutter.dev/platform-integration/web/initialization`、Flutter 3.44.0
  向け記述として確認)を根拠に手書き。`flutter_bootstrap.js`は含めていない
  (`flutter build web`がビルド時に自動生成することを公式ドキュメントで確認済み)。
- `favicon.png`・`icons/Icon-192.png`・`icons/Icon-512.png`・
  `icons/Icon-maskable-192.png`・`icons/Icon-maskable-512.png`:
  Pillowで生成した有効なPNGファイル(ForgeThemeのaccent色+「F」)。

### 方針の変更点
- 従来「プラットフォームファイルは捏造しない」としていた方針を、`web/`に限り
  変更した。理由は`docs/development/FLUTTER_VALIDATION.md`に明記(`.metadata`
  等の不透明なSDK内部情報とは異なり、`web/index.html`・`manifest.json`は
  公開されたテンプレートであり、Web検索で現行版を確認できたため)。
- `android/`・`ios/`・`windows/`・`linux/`・`macos/`・`.metadata`は
  引き続きCEO環境での生成が必要(方針変更なし)。

### 差分監査
- `pubspec.yaml`・`analysis_options.yaml`・`lib/main.dart`・既存テスト・
  Language/Runtime/Validator/AI Foundationのコードは1バイトも変更していない
  ことを確認した(`frontend/web/`配下のみ新規追加)。
- Python 135件を再実行し、無影響であることを再確認した。

### 既知の未達成事項
- 実際に`flutter build web`が成功するかはClaude環境で検証できていない。

## Task012 — FORGE-MILESTONE-002.1: Analyze Zero-Issue Fix & Final Closure（2026-07-11）

CEO実機実測(Python 135/135 PASS・**Flutter Test 166/166 PASS**・Web Build PASS・
`flutter analyze` 3 issues found)を受けて、残る3件のみを最小修正した。

### 修正
- `mock_generation_datasource.dart:47`: `prefer_const_constructors`。
  `FormTemplateParams(...)`の引数が全てcompile-time constantだったため
  `const`化した(`questions`リストにも明示的型引数`<FormQuestion>[...]`を付与)。
- `mock_app_generation_repository.dart:27`: `inference_failure_on_instance_creation`。
  `Future.delayed(...)` → `Future<void>.delayed(...)`(戻り値未使用のため`void`が正しい)。
- `v1_1_widgets_test.dart:94`: `inference_failure_on_collection_literal`。
  空リスト`[]` → `<String>[]`(string_list state値としての実際の型に合わせた)。
- Task 4監査で発見した同種1件: `forge_document.dart`の`?? const []`にも
  明示的型引数`<String>[]`を追加(念のための対応、影響範囲は限定的)。
  他に`Future.delayed(`の無型引数呼び出しは無いことを確認済み。

### 既知の未達成事項
- 上記4件の修正により`flutter analyze`が`No issues found!`になるはずだが、
  Claude環境にDart SDKが無く実行できていない。CEO再実行での確認が必要。

## Task011 — FORGE-MILESTONE-002: Forge Language v0.3 + AI Foundation（2026-07-11）

CEOから「Checklist専用デモからの卒業」を目的とした一括マイルストーンとして依頼。
途中報告無しで完遂した(依頼書の方針通り)。

### 判明した事実(CEO実機実測、依頼書冒頭で共有)
- FORGE-RUNTIME-003完了報告: `flutter analyze` No issues found!、
  `flutter test` 103/103 PASS、Chrome実機でHome→Confirm→Generated Screen→
  チェックリスト操作まですべて成功。Mock Mode成功。

### PHASE1: Forge Language v1.1(6 Widget追加)
- `shared/schemas/ui_schema.v1.1.json`新設。v1.0(凍結)は変更せず、
  heading/checkbox/card/list/divider/formの6種を追加。
- Widget追加に伴いAction/State型は追加していない(既存4種/4型で表現)。

### PHASE2: Runtime再編
- `widget_registry_core.dart`新設(Registry機構をWidget実装から分離)。
- `widget_registry_v1_1.dart`新設(v1.1の6 Widget実装)。
- v1.0の6 Widget実装(`widget_registry.dart`)はロジック無変更。
- 新Widget追加時、既存ファイルに触れず新規ファイル+登録1行で完結する手順を確立
  (`docs/spec/RUNTIME_SPEC.md`)。

### PHASE3: Validator拡張
- `schema_validator.py`をv1.0/v1.1の2バージョン対応へ書き換え。
  v1.0文書がv1.1専用Widgetを使うと不合格になる(version gating)。
  既存120件のテストは無改変のまま全て合格を維持。

### PHASE4: Template System
- `docs/spec/TEMPLATE_SPEC.md`。Checklist(既存を再構成)・Memo(新規)・
  Form(新規、2画面・navigate実演・card実演)の3Template。

### PHASE5: Mock Generator v2
- Python/Dart双方をTemplate方式へ書き換え。家事/アンケート/メモの3
  カテゴリを追加(計12カテゴリ)。既存9カテゴリの出力は完全に無変更
  (回帰テストで確認)。

### PHASE6: AI Foundation(設計のみ)
- `backend/app/ai/foundation/interfaces.py`: IntentPlanner/ProductPlanner/
  LanguageGenerator/RepairEngine/Critic/PluginRouter/Memory/Conversation/
  PromptBuilder/LLMAdapterのProtocol定義。
- `backend/app/ai/foundation/providers.py`: OpenAI/Claude/Gemini/OSS/
  ForgeAIの5Providerスタブ(全て`NotImplementedError`)。

### テスト
- Python: 97 → **135件**(v1.1 Widget 23件・Mock Generator v2 10件・
  AI Foundation 5件を追加)。
- Dart: 95 → **165件(静的に数え上げた予測値。D36参照)**。最終検証パスで
  `mock_generator_renderer_contract_test.dart`(FORGE-RUNTIME-002由来)に
  sealed classの非網羅switchという実バグ(v1.1 Widget型がswitch式に
  反映されておらず、コンパイルエラーになる状態)を発見・修正し、
  対象カテゴリも8→11種類へ拡張した(`docs/DECISIONS.md` D36)。
  いずれもClaude環境では未実行、CEO環境での`flutter test`実行で確定値を確認する必要がある。

### ドキュメント
- 新設: `docs/spec/LANGUAGE_SPEC.md`・`RUNTIME_SPEC.md`・`TEMPLATE_SPEC.md`・
  `AI_SPEC.md`。
- 更新: `README.md`・`docs/ROADMAP.md`・`docs/DECISIONS.md`・`TECH_DEBT.md`。

### 既知の未達成事項
- 今回追加した全コードの`flutter analyze`/`flutter test`/Chrome実機確認は
  Claude環境で未実行。CEO確認が必須(FORGE-MILESTONE-002-report.md参照)。

## Task010 — FORGE-RUNTIME-003: Infinite Width Button Constraint Fix（2026-07-11）
### 修正(根本原因)
- `core/theme/forge_theme.dart`: `elevatedButtonTheme.minimumSize`を
  `Size.fromHeight(56)`(実質`Size(double.infinity, 56)`)から`Size(0, 56)`へ。
  Row内の`ElevatedButton`が`BoxConstraints forces an infinite width`で
  描画に失敗していた根本原因(CEO実機のスタックトレースで確定)。
- `home_screen.dart`: 送信ボタンを`SizedBox(width: double.infinity)`で
  明示的に全幅化(テーマ側の暗黙の全幅化が無くなったため)。
### 追加
- `test/json_ui/button_layout_regression_test.dart`(Button×8レイアウト
  シナリオの回帰テスト)。
### 訂正
- FORGE-RUNTIME-002で行った3つの修正(内側Columnのmain AxisSize・
  ListTileへのKey付与・GestureDetectorからIconButtonへの変更)は、
  **今回の根本原因ではなかった**ことが確定した。無条件に元へ戻してはいないが
  (それぞれ独立して妥当な改善のため)、「原因修正」ではなく「付随改善」として
  記録を訂正した(`docs/DECISIONS.md` D26追記・D29参照)。
### 既知の未達成事項
- 修正後の`flutter analyze`/`flutter test`/実機Chrome確認はClaude環境で未実行。

## Task009 — FORGE-RUNTIME-002: Generated Screen Rendering Fix（2026-07-11）
### 修正
- `widget_registry.dart`の`_buildChecklist`: 内側Columnに`mainAxisSize: min`を
  明示、各ListTileに`ValueKey`を付与、leadingを`GestureDetector+Icon`から
  `IconButton`へ変更(CEO実機で確認された「本文空白」「RenderBox例外らしき
  ログ」への対応。根本原因は完全なスタックトレースが無く断定していない)。
### 追加
- `test/e2e/kids_checklist_generation_flow_test.dart`(Home→Confirm→生成→
  チェックリスト操作までの1本のテスト)。
- `test/.../mock_generator_renderer_contract_test.dart`(8カテゴリ×8観点=64件、
  「Schemaとして有効」だけでなく「現行Rendererで描画可能」を検証)。
- `docs/spec/MOCK_GENERATOR_CONTRACT.md`(Python/Dart版Mock Generatorの
  期待構造を固定。機械比較で差分0件を確認)。
### 判明した事実(CEO実機実測)
- Mock Modeでのナビゲーション(Home→Confirm→Generated Screen遷移)は成功。
  MOCKバッジ表示・Backend接続エラー無し、いずれも確認済み。
- Generated Screenの本文(チェックリスト)が空白で表示される不具合を確認。
- Console/PowerShellログに「Cannot hit test a render box that has never
  been laid out」に類するRenderBox関連の出力を確認(完全なスタックトレース
  は未取得)。
### 既知の未達成事項
- 修正後の`flutter analyze`/`flutter test`/実機Chrome確認はClaude環境で未実行。
- 根本原因の完全な特定には至っていない(3点の対処療法的修正を適用)。
- TD10(Python/Dart二重管理)は今回も解消済みにしていない。

## Task008 — FORGE-RUNTIME-001: Runtime Mock Mode & First Interactive Experience（2026-07-11）
### 追加
- `core/config/app_config.dart`(`mockMode`設定、既定でBackend不要)。
- `core/utils/forge_logger.dart`(構造化ロギング、新規パッケージ依存なし)。
- `data/datasources/mock_generation_datasource.dart`(Mock GeneratorのDart移植)。
- `data/repositories/mock_app_generation_repository.dart`。
- 画面右上のMOCK/LIVE Badge(`main.dart`、Flutter標準`Banner`を流用)。
- `test/.../mock_generation_datasource_test.dart`(実質23件のテストケース)。
- `docs/development/FLUTTER_VALIDATION.md`にMock Mode節を追記。
### 変更
- `data/repositories/app_generation_repository_impl.dart` →
  `http_app_generation_repository.dart`(`HttpAppGenerationRepository`に改名)。
  エラーメッセージを簡潔化(開発者向け詳細はログへ)。
- `presentation/providers/app_generation_provider.dart`: Http/Mockの
  DI切り替えに対応。
- `generated_app_screen.dart`: 生成中もAppBar(戻るボタン)を表示。
- `confirm_screen.dart`: ボタン連打防止。
- `README.md`: セットアップ手順をCEO実測ベースへ更新、Mock/Live切替方法を追記。
### 既知の未達成事項
- 今回追加した変更後の`flutter analyze`/`flutter test`はClaude環境で未実行。
  CEOの再実行結果待ち。
- Mock Generatorのロジックは引き続きPython/Dartの二重管理(TECH_DEBT.md TD10)。

## Task007 — FORGE-MERGE-005: Flutter Analyze Zero-Issue Fix（2026-07-11）
### 修正
- `home_screen.dart`・`confirm_screen.dart`・`forge_renderer.dart`の
  `MaterialPageRoute`3箇所に明示的な型引数`<void>`を付与
  (CEO実機の`flutter analyze`で検出されたWarning 3件への対応)。
  Repository全体を`MaterialPageRoute`で検索し、この3箇所以外に無いことを確認済み。
### 判明した事実(CEO実機実測)
- `flutter test`: **7/7 PASS**(FORGE-MERGE-003〜004で追加した全テストが合格)。
- `flutter analyze`: Error 0、Warning 3(`MaterialPageRoute`型引数、上記で対応)。
### 既知の未達成事項
- 修正後の`flutter analyze`/`flutter test`はClaude環境で未実行。CEOの再実行結果待ち。
- 現行テストスイートはNavigator.pushの実遷移を直接検証していない(技術的負債として記録)。

## Task006 — FORGE-MERGE-004: Flutter Analyze Fix & Repository Completion（2026-07-11）
### 修正
- `home_screen.dart`: 非推奨の`withOpacity(0.6)`を`withValues(alpha: 0.6)`へ置換
  (CEO実機の`dart analyze`/`flutter analyze`で検出されたinfo 1件への対応)。
- `test/features/.../home_screen_test.dart`: `find.text()`によるTextField内容確認を
  `TextField.controller.text`の直接確認へ変更(finderの一意性が断定できなかったため)。
- `ci.yml`: Flutterバージョン指定を根拠のない暫定値(3.22.0)からCEO実機の
  実測値(3.44.5)へ更新。
### 追加
- `docs/development/FLUTTER_VALIDATION.md`(プラットフォーム構成方針・パス/シェル
  注意事項・検証履歴)。
- `docs/reports/`(過去レポートFORGE-MERGE-001〜003の永続保存)。
### 判明した事実(CEO実機実測)
- 環境: Flutter 3.44.5 / Dart 3.12.2 / Windows 10 / `C:\forge_verify\frontend` / cmd.exe。
- `flutter clean`・`flutter pub get`・`dart analyze`・`flutter analyze`は成功
  (info 1件のみ)。
- `flutter test`は、テスト未反映の旧ローカルRepositoryで実施されたため、
  7件のテスト自体の合否は未検証のまま。
- Web/Windows Buildはプラットフォーム未生成のため未実施(Windowsは追加で
  Visual Studio C++ Desktop開発ツールも未導入)。
### 訂正した過去の記述
- FORGE-MERGE-003で最有力候補としていた`package_config.json`解決エラー説は、
  裏付ける証拠が得られなかった。
- Analysis Server crashは、ASCIIパス+cmd.exe経由の実行で再現しなくなった
  (原因はパス文字種・シェルの一方または両方の可能性が高いが未確定)。
  詳細は`docs/reports/FORGE-MERGE-003-report.md`冒頭の訂正注記を参照。

## Task005 — FORGE-MERGE-003: Flutterプロジェクトとしての成立性（2026-07-11）
### 追加
- `frontend/analysis_options.yaml`(新設。flutter_lintsを実際に有効化)。
- `frontend/test/`配下にテスト3ファイル・7件(smoke_test.dart・home_screen_test.dart・
  forge_fallback_widget_test.dart)。
### 判明した事実
- CEO実測により、`frontend/`が一度も`flutter create`を通っていないことが確定
  (android/ios/windows/linux/macos/web/.metadataがすべて欠如)。
- `flutter analyze`がFormatExceptionでAnalysis Server crash、`flutter test`は
  テスト不在、`flutter build windows`はDesktop Project未構成で失敗。
### 既知の未達成事項
- FormatExceptionの根本原因は未確定(優先順位付き候補のみ)。CEOからの追加情報
  (エラー全文・スタックトレース)待ち。
- `windows/`等プラットフォームフォルダの生成は意図確認待ちのため未実施。

## Task004 — FORGE-MERGE-002: Foundation Hardening（2026-07-11）
### 追加
- Validatorテストを26件→97件へ拡張(`test_schema_validator_extended.py`)。
- `docs/spec/RENDERER_API.md`(Renderer公開API一覧・互換性ポリシー)。
- `docs/spec/LANGUAGE_FREEZE.md`(Language versioning方針)。
- `TECH_DEBT.md`(技術的負債8項目)。
### 修正
- `widget_registry.dart`: Row内の全widgetを一律Expandedにしていた不具合を修正
  (text_fieldのみExpanded)。
- `forge_renderer.dart`: const付与漏れ1件。
### 既知の未達成事項
- `flutter analyze`/`flutter test`はClaude環境で未実行(Dart SDK無し)。CEO確認必須。

## Task003 — FORGE-MERGE-001: Prototype統合と最初の縦の一本（2026-07-11）
### 追加
- Forge Language v1(`shared/schemas/ui_schema.v1.json`)を確定。
- Validator(`schema_validator.py`)・Mock Generator(`mock_generator.py`)を新設。
- `POST /api/v1/ai/generate` エンドポイント。
- Flutter Runtime(`json_ui/`: schema/widget_registry/renderer)。
- Prototype v0.1.3のHome/Confirm画面を移植、Tool画面をGeneratedAppScreenへ置換。
- `docs/DECISIONS.md`・`KNOWN_ISSUES.md`(リポジトリ直下)を新設。
### 修正
- Inspiration Cards 8種類のうち6種類が生成ロジック未対応だった不具合(3→8カテゴリへ拡張)。
- `confirm_screen.dart`の古い音声入力言及コメントを削除。
- `docs/AI.md`のSchema例を実装したv1に合わせて修正。
### 既知の未達成事項
- Dart/FastAPI層はClaude環境で未実行。

## Task001〜Task002 — Foundation初期構築（2026-07-07、Claude以前の作業）
### 追加
- Clean Architecture / Feature First / レイヤードアーキテクチャに基づく
  ディレクトリ構成一式。
- `docs/`配下の設計文書6件(README/Architecture/API/Database/AI/Roadmap)。
- FastAPI最小構成(`/health`のみ)・Flutter最小構成(プレースホルダー画面)。
- `.ai/`・`.agents/`・`PROMPTS/`・`docs/tasks/`・`docs/prompts/`。
### 備考
本CHANGELOGはTask003(FORGE-MERGE-001)の監査時点で遡って記録したものであり、
Task001・Task002当時にリアルタイムで書かれたものではない。詳細は
`docs/tasks/task001.md`・`task002.md`を参照。
