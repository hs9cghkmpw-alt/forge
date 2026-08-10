# TECH_DEBT.md

## KNOWN_ISSUES.mdとの違い

- **KNOWN_ISSUES.md**: 今、ユーザーまたは開発者が実際に困る/困りうる制約
  (例: Dart未検証、Androidエミュレータの接続先設定)。
- **TECH_DEBT.md**(本ファイル): 今は動作を妨げていないが、意図的な近道であり、
  将来の変更コストを増やす可能性がある設計・実装判断。「今すぐ直す必要はないが、
  忘れずに記録しておくべきもの」。

各項目には「今は困っていない理由」と「将来困る条件」を明記する。

---

## 解消済み

- **Analyzer Warning(3件: Unused import・List inference・Map inference)**:
  FORGE-MILESTONE-003(Analyzer Zero → Chrome Verification → Native AI
  Foundation)で修正した。`forge_runtime_state.dart`の未使用import
  (`forge_form_validator.dart`)を削除し、`ForgeStateStore({})`等の
  型推論があいまいな箇所(Map/Setの構文的あいまいさ)へ明示的な型引数を
  追加した。CEO環境での`flutter analyze`実行結果待ち(未検証、
  FORGE-MILESTONE-003-report.md参照)。

- **TD16(Native AI未接続)**: `docs/spec/ADAPTER_CONTRACT_V1.md`(v1.1、
  CEO実コード監査済み)のADRに基づき実装済みであることを2026-08-10の
  実ファイル監査(pytest実行含む)で確認した。詳細はTD16本文(下記)へ
  移動した記録を参照。本項目はこの時点で本CHANGELOGへ記録されていなかった
  (TECH_DEBT.mdの記述が実コードより古いままだった)ため、ここに追記する。

---

## 残課題(継続、PHASE12時点。2026-08-10実ファイル監査により一部更新)

- **TD10**: Python/Dart Mock Generator二重管理(継続、解消済み扱いにしない)。
- **Provider未実装**: TD15参照。
- ~~**Native AI未接続**: TD16参照。~~ → **解消済み(2026-08-10確認)**。
  TD16本文参照。
- **Repair Loop Stub**: TD17参照。

---

## TD1. ValidatorがJSON Schemaファイルとロジックを二重管理している

`shared/schemas/ui_schema.v1.json` と `backend/app/ai/validators/schema_validator.py`
の`_check_schema()`系関数は、内容的に同じ制約を別々に(JSONとPythonで)記述している。

**今は困っていない理由**: `jsonschema`パッケージが未導入(DECISIONS.md D9)。
テストは97件とも実際に合格しており、現時点で2つの定義がズレている形跡は無い。

**将来困る条件**: Widget/Action/State型が増えるたびに、両方を手で同期し続ける必要がある。
同期を1箇所忘れると、Schema上は禁止されているはずの文書がValidatorを通ってしまう
(またはその逆)というサイレントな不整合が起こりうる。

**対応方針**: CEO環境で`pip install jsonschema`が可能になった時点で、
`_check_schema()`を`jsonschema.validate()`呼び出しに置き換える(D9に記載済み)。

---

## TD2. ForgeRuntimeStateがchecklist専用の操作を直接持っている

`toggleChecklistItem()`/`deleteChecklistItem()`/`addChecklistItem()`が
汎用状態コンテナである`ForgeRuntimeState`に直接生えている
(docs/spec/RENDERER_API.md 3.3節でExperimentalと明記済み)。

**今は困っていない理由**: v1のステートフルWidgetはchecklistのみ。

**将来困る条件**: 別のステートフルWidget(例: 日付選択・スライダー)が
追加されるたびに、同じパターンで専用メソッドを`ForgeRuntimeState`へ
追加し続けると、このクラスが肥大化し単一責任の原則から外れていく。

**対応方針**: 2つ目のステートフルWidgetを追加するタイミングで、
Widget種別ごとに操作を切り出す設計(例: 各Widgetが自分の操作クラスを持つ)への
移行を検討する。1つ目(checklist)だけでは判断材料が不足しているため、今回は据え置く。

---

## TD3. RenderContextが存在せず、引数の受け渡しが個別引数になっている

`docs/spec/RENDERER_API.md` 1章参照。現状は4引数(BuildContext/ForgeRuntimeState/
ForgeWidgetRegistry/再帰コールバック)で収まっており可読性の実害は無い。

**将来困る条件**: テーマ上書き・Plugin解決器・デバッグフラグ等、渡すべき文脈が
増えた時点で引数リストが膨張する。

---

## TD4. Backend `ai/` モジュールが domain/usecases 層を経由していない

`backend/app/ai/generators/mock_generator.py`・`validators/schema_validator.py`は、
`backend/app/domain/`(entities/repositories/usecases)を一切使わず、
`routers/ai.py`から直接呼ばれている。一方Frontend側の`features/app_generation/`は
domain/data/presentationの3層をきちんと踏んでいる。

**今は困っていない理由**: Mock Generatorは単純な純粋関数であり、
Clean Architectureの層分けをする実益が薄い(過剰設計になる)。

**将来困る条件**: 本物のAI Compilerに差し替える際、リトライ・複数モデル切り替え・
ログ記録等の「アプリケーション固有ロジック」が必要になった時点で、
現状のフラットな構造では収まりが悪くなる可能性がある(実施レポート Task 7参照)。

---

## TD5. checklist項目(item)のID重複がValidatorで検出されない

`backend/tests/test_schema_validator_extended.py`の
`test_duplicate_checklist_item_id`で意図的に確認済み(現状は合格してしまう)。
Widget IDの重複検査は対象がWidgetツリーのみで、State内部のchecklist itemは対象外。

**今は困っていない理由**: Mock Generatorは`item_{連番}`で確実に一意なIDを生成する。

**将来困る条件**: 本物のAIやRepair Engineが、うっかり同じIDのitemを2つ生成した場合、
Runtime側の`toggleChecklistItem`/`deleteChecklistItem`が「最初に見つかった方」ではなく
両方に作用する、または意図しない方に作用する可能性がある(Dart側real_id一致判定は
`item.id == itemId`で全件走査するため、同id複数件があると複数件同時に更新されうる)。

**対応方針**: Validatorに`duplicate_checklist_item_id`ruleを追加する(Widget ID重複と
同様の仕組みを流用できる、小さな変更)。次回のValidator強化タイミングで対応候補とする。

---

## TD6. `row`のExpanded付与がtext_field決め打ちのヒューリスティックになっている

FORGE-MERGE-002 Task 2で修正した箇所(`widget_registry.dart`の`_buildRow`)。
「`text_field`だけはExpandedで包む」という判定を関数内にハードコードしている。

**今は困っていない理由**: 現状row内に置かれる「伸びるべきWidget」はtext_fieldのみ。

**将来困る条件**: 他のWidget種別が増え、「これも伸びてほしい」という要求が
出てきた時点で、同じ判定をWidgetごとに追加し続けることになる。Schemaに
明示的な`flex`/`grow`のようなレイアウトヒントを持たせる設計への移行を検討する
(Language変更を伴うため、今回のスコープ外)。

---

## TD7. `string_list` State型を消費するWidgetが無い

`docs/spec/LANGUAGE_FREEZE.md` 7.1節で詳述。今回はWidget追加が禁止のため
未対応。次にWidgetを追加するタイミングでの検討事項として申し送る。

---

## TD8. Validatorのversion検査が単一バージョン固定

`docs/spec/LANGUAGE_FREEZE.md` 5章参照。v2を作る時点で、
`_check_schema()`のversion分岐をリファクタリングする必要がある。

---

## TD9. Flutter Testが実際のNavigator遷移を検証していない

FORGE-MERGE-005で判明。現行7件のテスト(smoke/home_screen/forge_fallback_widget)は
いずれも`Navigator.push`を実際にトリガーする操作(送信ボタンを押す等)を含まない。
Home→Confirm、Confirm→GeneratedApp、Runtime内画面遷移の実際の動作は、
テストスイートでは直接検証されていない。

**今は困っていない理由**: FORGE-MERGE-005でCEO実機の`flutter test`は7/7 PASSしており、
既存の範囲では問題が無い。

**将来困る条件**: Navigator関連の変更(例: 今回のMaterialPageRoute型引数追加のような
一見安全な変更)を行った際、実際の遷移が壊れていないかをテストで機械的に
確認できない。目視確認またはCEOでの実機確認に頼ることになる。

**対応方針**: 次のテスト追加のタイミングで、`Navigator.push`をトリガーし
`find.byType(ConfirmScreen)`等で遷移先画面の表示を確認するテストを追加する
(Riverpodのモック化が必要な`GeneratedAppScreen`への遷移は除き、
`HomeScreen`→`ConfirmScreen`のような単純な遷移から着手するのが妥当)。

---

## TD10. Mock GeneratorがPython版とDart版で二重管理になっている

FORGE-RUNTIME-001 Task 3(DECISIONS.md D21)。
`backend/app/ai/generators/mock_generator.py` と
`frontend/lib/features/app_generation/data/datasources/mock_generation_datasource.dart`
は、意図的に同じキーワード・カテゴリ・出力構造を持つ、別言語での実装。

**今は困っていない理由**: 両方にテストがあり(Python 33件、Dart 95件)、
現時点では同期が取れていることを確認済み。FORGE-RUNTIME-002で
`docs/spec/MOCK_GENERATOR_CONTRACT.md`を新設し、9カテゴリの期待構造・
Widget type一覧・item ID規則を固定した上で、Python版とDart版を
プログラムで機械比較し、差分が0件であることを確認した(2026-07-11時点)。

**このステータス(TD10)は解消済みにしない。** 二重管理という構造そのものは
今回も残っている。次にカテゴリ・キーワードを変更する際は、
`docs/spec/MOCK_GENERATOR_CONTRACT.md`を必ず一緒に更新し、可能であれば
再度機械比較すること。

**将来困る条件**: カテゴリ追加・キーワード変更等を行う際、片方だけ更新して
もう片方を忘れるリスクがある。

**対応方針**: 本物のAIに置き換わった時点で、Python版のMock Generatorは
不要になる可能性が高い(Dart版はMock Modeの主要な用途として残る)。
それまでの間は、変更時に両ファイルへの変更を1つのDECISIONS.mdエントリで
まとめて記録する運用とする。

---

## TD11. Rendererの例外保護は「構築時」のみで「レイアウト/hit-test時」を保護しない

FORGE-RUNTIME-002の調査で判明。`buildForgeWidget()`のtry/catchは、
Widget構築(`build()`メソッド相当の同期的なWidgetツリー組み立て)中の
例外だけを捕まえる。今回発生したような、レイアウト計算やhit-test
(タップ判定)の段階で起こる例外は、build()呼び出しの外側(Flutterの
描画パイプライン)で発生するため、現在のtry/catchでは捕まえられない。

**今は困っていない理由**: FORGE-RUNTIME-002 Task 3/4で、具体的な原因
候補(内側Columnのmain AxisSize不整合、リストWidgetのKey欠如、
非標準的なGestureDetector+Icon構成)に対処療法的な修正を行った。

**将来困る条件**: 別の未知Widget構成や、将来Widgetが追加された際、
同種のレイアウト時例外が再発する可能性がある。build()時の例外保護
(Fallback)だけでは、この種の問題を自動的には防げない。

**対応方針**: Flutterの`ErrorWidget.builder`をアプリ全体でカスタマイズし、
レイアウト/描画時の例外もある程度キャッチしてFallback相当の表示に
倒す仕組みを検討する(現状は個別のWidget実装を頑健にすることで
対処している)。Widget追加が解禁されるタイミングで再検討する。

---

## TD12. Card Widgetの単独利用シナリオが無い

FORGE-MILESTONE-002 D33参照。Language/Validator/Runtime全層で実装・
テスト済みだが、実際に使われているのはForm Template内(質問群を囲む)のみ。

**今は困っていない理由**: Form Templateでの利用により、実装自体の
正しさ(Schema検証・描画)はテストで確認できている。

**将来困る条件**: 「実装されているが実質使われていないコード」が
増えると、どれが本当に必要かの判断が難しくなる。

**対応方針**: 次にCategoryを追加する際、Cardを主役にできる自然な
ユースケース(例:「プロフィールカードを作って」)が無いか検討する。
一定期間(目安: 次のマイルストーン)経っても使い道が増えない場合は、
Deprecated化を検討する(LANGUAGE_FREEZE.md 6章の手順に従う)。

---

## TD13. Validatorのversion別Widget許可リストが、バージョンが増えるたびに大きくなる

`WIDGET_TYPES_BY_VERSION`辞書は、v1.2・v1.3…と増えるたびに新しいキーが
必要になる。現状(2バージョン)では問題無いが、バージョンが増えると
このパターンの見通しが悪くなる可能性がある。

**今は困っていない理由**: 現状2バージョンのみで、辞書は小さい。

**将来困る条件**: バージョンが5個・10個と増えた場合。

**対応方針**: 「各バージョンで追加されたWidget集合」を個別に持ち、
「そのバージョン以下の集合の累積和」を動的に計算する形へ変更することを、
3つ目のバージョンを追加するタイミングで検討する。

---

## TD12. number State型に対応する編集用Widgetが無い

FORGE-MILESTONE-003。`number`型のStateは宣言・Validator検証(`min`/`max`)
まで対応したが、それを実際に編集できるWidget(例: 数値専用の入力欄、
スライダー等)は今回追加していない(禁止事項「未依頼Widgetの大量追加」)。

**今は困っていない理由**: 現在のTemplate(Checklist/Memo/Form)はnumber型の
Stateを生成しない。`min`/`max`ルールはSchema・Validator・Runtime全層で
実装済みだが、実際に使われる経路がまだ無い。

**将来困る条件**: 将来「年齢を入力してください」のような数値入力を伴う
Templateやカテゴリを追加する際、text_fieldをnumber型に流用するか、
専用のWidgetを追加するかを判断する必要がある。

**対応方針**: 次にnumber入力が必要なTemplateを追加するタイミングで判断する。
TD7(string_list、v1.1で`list` Widgetにより解消済み)と同じパターンで、
先にWidgetを追加してから使うのではなく、実際の需要が生じた時点で追加する。

---

## TD13. compositeの途中失敗時にロールバックしない

FORGE-MILESTONE-003。`composite` Actionの実行中にstepが失敗した場合、
それより前のstepの結果(State変更)は元に戻らない(仕様として意図的にそう
設計した。`docs/spec/RUNTIME_CONTRACT_V1_2.md` 3.3節)。

**今は困っていない理由**: 現在Mock Generatorはcomposite Actionを生成しない
(手書きJSONでのみ使われる想定)。テストでもこの挙動を明示的に検証済み。

**将来困る条件**: 「複数のStateを同時に、全部成功するか全部失敗するかの
どちらかにしたい」というAtomicなComposite操作が必要になった場合、
現在の設計では対応できない。

**対応方針**: 実際にAtomic性が必要なユースケースが出てきた時点で、
`ForgeStateStore`にトランザクション的なスナップショット/ロールバック機構を
追加するかを検討する。今は推測で先行実装しない。

---

## TD14. formがformを入れ子にするケースをActionDispatcherが辿らない

FORGE-MILESTONE-003。`ForgeActionDispatcher._collectValidatableFields()`は
column/row/cardの中は再帰的に辿るが、form の中にさらに form が
ネストされているケースは辿らない(意図的な制限。`forge_action_dispatcher.dart`
のコメント参照)。

**今は困っていない理由**: Schema上form-in-formは禁止していないが、
Mock Generatorも生成せず、実用上の必要性が無い。

**将来困る条件**: 将来「ウィザード形式の入れ子フォーム」のようなものが
必要になった場合、この制限に当たる。

**対応方針**: 実際の需要が生じるまで対応しない。Validator側でform-in-formを
明示的に禁止するかどうかも、その時点で判断する(現状はSchema上許可されて
いるが、Runtime側が対応していないという食い違いがある点は認識しておく)。

---

## TD15. AI Provider(5種)がすべて未実装スタブ

FORGE-MILESTONE-002/003。`backend/app/ai/foundation/providers.py`の
OpenAI/Claude/Gemini/OSS/ForgeAIの5 Providerは、いずれも
`complete_structured()`を呼ぶと`NotImplementedError`を送出する
(`tests/test_ai_runtime.py`の`test_all_foundation_provider_stubs_raise`で
5件とも確認済み)。

**今は困っていない理由**: 意図的な設計(禁止事項「AI実装したふり」を
避けるため)。`ProviderRouter`によるルーティング(選択)ロジックは
実際に動作するが、選んだ先のProviderを実際に呼び出す部分だけが
未実装という状態を明確に切り分けている。

**将来困る条件**: 実際にAI生成機能をユーザーへ提供するには、
最低1つのProviderを実装する必要がある。

**対応方針**: `docs/spec/NATIVE_AI_ROADMAP.md`参照。CEO承認を得た上で、
まず`forge_ai/`(既に世界理解〜設計までは実装済み)を`ForgeAIProvider`へ
接続することを推奨する。

---

## TD16. Native AI(forge_ai/)とbackend/app/ai/runtime/が未接続 → **解消済み(2026-08-10確認)**

**解消済み。** 以下は当初(未接続だった時点)の記述をそのまま残す。

`forge_ai/`(FORGE PROJECT AI実装チーム キックオフ指示書で構築)と
`backend/app/ai/runtime/`(今回構築)は、概念的に対応する型を持ちながら
(`forge_ai`の`Intent`/`ApplicationPlan` vs `runtime`の`Intent`(=`IntentIR`)/
`Plan`(=`PlanIR`))、実際にはコード上で繋がっていない。

**今は困っていない理由**: 両者ともまだAI推論を含まないため、
接続していないことによる実害が無い。

**将来困る条件**: Native AI接続時、2つの型システムをどう統合するかを
決めないまま進めると、`backend/app/ai/runtime/`が`forge_ai/`を
importするための変換コード(アダプタ)が場当たり的に増えていく可能性がある。

**対応方針(当初)**: `docs/spec/NATIVE_AI_ROADMAP.md` 2章に移行ステップを記録した。
型統合の具体的な方法はCEO承認が必要な設計変更と位置づけ、今回は決定していない。

**2026-08-10 実ファイル監査による解消確認**:
`docs/spec/ADAPTER_CONTRACT_V1.md`(v1.1、「CEO実コード監査済み」と明記)の
ADRに基づき、型統合ではなく**Facade方式のAdapter層**(ADR 1.1節)として
実装済みであることを、実ファイル読み取りと`pytest`実行の両方で確認した。

- `backend/app/ai/runtime/forge_ai_adapter.py`: `forge_ai.Intent`/
  `ApplicationPlan`/`RepairResult`/`QualityScore`を`IntentIR`/`PlanIR`/
  `CriticResult`等へ変換する関数群(診断・ログ用途、ADR 1.1節「粗粒度
  Facade」の原則により`forge_ai/`内部処理を駆動しない設計)。
- `backend/app/ai/runtime/forge_ai_provider_bridge.py`: `forge_ai.
  AIProvider` Protocolを満たしつつ内部で`LLMAdapter`へ委譲する
  `ForgeAIProviderBridge`。
- `backend/app/ai/runtime/prompt_pipeline.py`: `forge_ai.core.pipeline.
  run_cognitive_pipeline()`を1回呼ぶ形で、本番生成経路として実際に
  接続されている(ADR 7.2節のFacade方式Sequenceどおり)。
- `backend/app/routers/ai.py`: 上記`PromptPipeline`をHTTPエンドポイントから
  呼び出しており、型統合ではなくAdapter経由で末端まで配線されている。
- テスト: `backend/tests/test_forge_ai_adapter.py`ほか、`forge_ai`関連の
  Adapter/Bridge/PromptPipelineテスト18件が実際に`pytest`でPASS
  (2026-08-10実行確認)。`backend`+`forge_ai`合算で908 passed, 12 skipped。

型システム自体の統合(2つの`Intent`型を1つにする等)は行っていない
(ADR 2.1〜2.3節「決定: Adapter変換、統合不要」のとおり、意図的にFacade方式を
選び、型統合はしない設計判断)。これはギャップではなく、ADRで明示的に
却下された代替案(ADR 8.2節)であるため、TD16としては解消済みとする。

**ADR 8.3節に記載された、今回もまだ設計していない将来拡張点(TD16とは別、
現時点でも未着手)**: Streaming応答、Cost/Token計測、Multi-provider
fallback、Caching、`CriticResult.issues`の実質化、`forge_ai.Planner`の
`navigation_edges`計算。これらは新規のTD項目として管理する価値があるが、
今回のセッションでは追跡番号を割り当てず、本節に記録するに留める。

---

## TD17. Repair Engineが「決定的な既知パターン修正」と「AI委任」の
      どちらの設計にするか未決定

`forge_ai/repair/repair_engine.py`(既に実装済み)は、既知2パターンのみ
決定的に修正し、Provider呼び出しは「件数を尋ねるだけ」の軽い使い方をしている。
一方`backend/app/ai/runtime/repair.py`の`AIRepair` Protocolは、
`repair()`1回の呼び出しでAIが直接修正案を返すことを前提にした設計に見える
(Stubのため実際の動作は未確認)。この2つの設計思想の違いを、
今回明示的にすり合わせていない。

**今は困っていない理由**: どちらもまだ実際には呼ばれない(Stub/Mock)。

**将来困る条件**: Native AI接続時、「Repair EngineはAIに丸投げするのか、
決定的な既知パターン+AIのハイブリッドにするのか」を決めないまま
実装を始めると、後で設計をやり直すことになる。

**対応方針**: `docs/spec/NATIVE_AI_ROADMAP.md`に記載した通り、
`forge_ai/`のRepairEngineの実績(既知パターン優先、AI委任は最小限)を
土台に、`backend/app/ai/runtime/repair.py`側もハイブリッド設計へ
寄せることを推奨する(CEO承認が必要な設計方針の確認)。

---

## TD18. Noto Fontを同梱していない(日本語の一部文字で「見つからない文字」警告)

FORGE-MILESTONE-003.1 PHASE9。Chrome Consoleに
"Could not find a set of Noto fonts to display all missing characters"
という警告が出ることをCEO実機で確認した。Flutter Webは既定でシステム
フォント/Google Fonts CDNへ依存しており、環境によっては一部の文字
(絵文字・稀少な漢字等)が正しく表示されない場合がある。

**対象文字**: 現時点でどの文字が実際に表示崩れを起こしているかは、
警告メッセージからは特定できていない(具体的な文字コードポイントの
一覧はConsoleに出ていない)。今回生成される9カテゴリのMock文書は
常用漢字・ひらがな・カタカナの範囲に収まっており、実際に文字が
欠落して見える具体的な報告は無い。

**実害**: 現時点で確認されているのは警告ログのみ。実際に文字が
「表示されない」という実害の報告はCEO実機確認では出ていない。

**推奨フォント**: Noto Sans JP(Google Fonts、Apache License 2.0で
商用・改変・再配布とも問題無いことをライセンス条文レベルで確認する
必要がある。今回は未確認)。

**ライセンス確認事項**: Apache License 2.0であることは一般に知られているが、
実際にNoto Sans JPのライセンスファイルを確認し、フォントサブセット化
(使用文字だけを抽出して同梱)を行う場合の扱いも含めて確認する必要がある
(今回未実施)。

**バンドルサイズ**: Noto Sans JPフルセットは数十MB規模になりうる
(日本語の文字数の多さのため)。サブセット化しない場合、Webアプリの
初回読み込みサイズに大きく影響する。サブセット化する場合はビルド
パイプラインへの追加が必要。

**今回対応しなかった理由**: 「フォントファイルを成果物へ無断で巨大追加
しない」「ライセンスを確認せず追加しない」「オフライン実行可能性を維持
する」という制約の下、上記ライセンス確認・サブセット化検討・
バンドルサイズ評価をすべて今回のセッション内で完了させることは
時間的に困難と判断し、次フェーズへ正式に持ち越すこととした。

**導入フェーズ**: 実際に「特定の文字が表示崩れしている」という具体的な
実害が確認された時点、またはNative AI接続でアプリの多様性が増し
稀少文字の使用頻度が上がった時点で優先度を上げる。

---

## TD19. 「計算アプリ」等、Calculator的なリクエストにCalculator専用構造が無い

FORGE-MILESTONE-003.1 PHASE10。CEO実機で「計算アプリつくって」という
入力を試したところ、Mock Generatorは生成に成功した(ログ上はSUCCESS)。
ただし、この入力はどのカテゴリキーワードにも一致しないため、
**Generic fallback(`generate_forge_document`の最終分岐)** へ落ち、
入力テキストそのものをタイトルにした空のChecklistテンプレート
(項目「最初のアイテム」1件のみ)が生成されている。**実際に四則演算等を
行うCalculator機能は一切生成されていない。**

**現状仕様として妥当か**: 「生成自体は失敗しない(クラッシュしない)」
という意味では妥当だが、ユーザーが期待した「計算アプリ」とは
似ても似つかないものが出てくるため、UXとしては誤解を招く。

**Native AI接続後に対応予定か**: 対応予定である。ただし今回のセッションで
CalculatorのためのWidget追加・Language仕様追加は行っていない
(禁止事項「Calculator Widget追加」「Language仕様の無断追加」に従った)。
Native AI(forge_ai/接続後)であれば、既存のtext_field/text/button語彙の
組み合わせ、またはnumber State型(v1.2で追加済み)を使って、決定的な
Mock Generatorでは実現しづらい「入力に応じた動的な計算式」を、
AIが都度設計することが期待できる。

**対応方針**: 今回は「Generic fallbackへ落ちている」という事実を
正直に記録するに留める。Mock Generatorへ Calculator専用テンプレートを
追加するかどうかは、CEO承認が必要な設計判断(新しいTemplateの追加)と
位置づける。

---

> **【2026-07-14 注記、Architecture Freeze】** 以下TD20〜TD22は、当時
> 「FORGE-MILESTONE-004: Native AI Phase-1」という名前の依頼で発見・
> 記録された技術的負債である。この名前は現在「**M005: Backend AI
> Integration**」として正式に読み替えられている(M004は`forge_ai/`のみを
> 指す)。番号整理・責務境界の正典は`docs/spec/FORGE_AI_ARCHITECTURE_V1.md`
> を参照すること。以下の記録内容そのものは変更していない。

## TD20. Native AI出力の安全性検査(Output Safety)が未設計(→ M005)

FORGE-MILESTONE-004 PHASE11レビューで発見。現在のValidatorは構造的整合性
(型・参照・再帰深度等)のみを検査し、生成された文書の「意味」が
安全かどうかは検査していない。例えば、個人情報を不必要に収集する
Formや、誤解を招く選択肢を持つUIが、構造的には完全に合法な
Forge Language文書として生成されうる。

**今は困っていない理由**: 現時点で実際にAI推論を行うProviderが
1つも実装されていない(全てStub)ため、この種の出力は発生し得ない。

**将来困る条件**: Native AI(またはOpenAI/Claude等のProvider)が
実際に接続され、ユーザーの自由な自然言語入力から文書を生成するように
なった時点で、この種の安全性検査が無いまま出力をそのままRuntimeへ
渡すことになる。

**対応方針**: `AICritic`(既存Protocol)の責務を拡張し、品質だけでなく
安全性(過剰な個人情報収集の検出等)も評価するか、専用の
Output Safety Checkerを新設するかを、Native AI接続の設計時に
CEO承認のもと決定する。

---

## TD21. Prompt Injection対策が明示的に設計されていない(→ M005)

FORGE-MILESTONE-004 PHASE11レビューで発見。`PromptBuilder`
(forge_ai/既存)は文字列連結を避けた構造化Promptを生成するため、
最も単純な形のInjection(ユーザー入力をsystem指示へ直接混入させる)は
構造的に起きにくい。ただし、ユーザー入力(`context`フィールド経由)
自体に「これまでの指示を無視して」のような指示文が含まれていた場合、
実際のLLM Providerがどう反応するかは、Provider実装依存であり、
Forge側で明示的なサニタイズ・検出を行う仕組みはまだ無い。

**今は困っていない理由**: 実推論を行うProviderが無いため実害が無い。

**将来困る条件**: 実際のLLM Provider接続後、ユーザー入力に
Prompt Injectionと疑われる文字列が含まれるケースへの対応方針
(検出して拒否する/無視して処理を続ける/ログに残す等)を決めていないと、
初回接続時に場当たり的な対応になりかねない。

**対応方針**: Native AI接続の設計時に、`IntentParser`/`AIPlanner`の
入力層でのサニタイズ方針をCEO承認のもと決定する。

---

## TD22. IntentIR/PlanIR/Templateスキーマにバージョン管理が無い(→ M005)

FORGE-MILESTONE-004 PHASE11レビューで発見。Forge Language(JSON)は
v1.0/v1.1/v1.2という明確なバージョニングと後方互換性ポリシー
(`docs/spec/LANGUAGE_FREEZE.md`)を持つが、`IntentIR`/`PlanIR`/`Template`
といったAI Runtime側の中間表現には、同様のバージョン管理が無い。
将来これらの型のフィールドを変更する際、どのProviderがどのバージョンの
IRを前提にしているかを判定する仕組みが無い。

**今は困っていない理由**: 実装(推論)が無いため、複数バージョンのIRが
同時に存在する状況が発生しない。

**将来困る条件**: 複数のProvider実装(Native AI・OpenAI等)が同時に
稼働し、それぞれが異なる時期に開発された場合、IRのバージョン不一致による
不具合が起こりうる。

**対応方針**: 実際に2つ目のProvider実装に着手するタイミングで、
Forge LanguageのFreeze方針を参考に、IntentIR/PlanIR/Templateへも
バージョニングを導入するかどうかを検討する。

---

## TD23. HTTP層(FastAPI/Pydantic)がClaude環境で一度も実行できていない

FORGE-MILESTONE-005実装。`backend/app/schemas/ai.py`・
`backend/app/routers/ai.py`・`backend/app/exception_handlers.py`・
`backend/app/main.py`・`backend/tests/test_http_api.py`は、いずれも
fastapi・pydanticに依存する。Claudeのサンドボックスにはこれらが
インストールされておらず(ネットワーク不可、実際に`pip install`を
試行し失敗を確認済み)、これらのファイルは`ast.parse`による構文確認
以外、一度も実行できていない。

**今は困っていない理由**: `PromptPipeline`・Adapter関数群という
「呼び出される側」の純粋なPythonロジックは、Python単体テスト
(246件)で実際に実行・検証済みである。HTTP層は薄い皮であり、
ロジックの誤りというより「配線」の誤りが起こりうる箇所である。

**将来困る条件**: CEO環境で`pip install -r requirements.txt`実行後、
`uvicorn app.main:app --reload`または`pytest`を実行した際に、
import エラー・Pydanticモデルの構文誤り・FastAPIのルーティング誤りが
発見される可能性がある。特に`_is_json_syntax_error()`
(JSON構文エラーを`type == "json_invalid"`で判定するロジック)は、
Pydantic v2の一般的な既知の挙動に基づく推測であり、実際のバージョンで
異なる可能性がある。

**対応方針**: CEO環境で`scripts/verify.ps1`(`pip install`ステップを
追加済み、D63参照)を実行し、実際に`test_http_api.py`が実行される
ことを確認する。もし`_is_json_syntax_error()`の判定が外れていた場合、
その関数だけを修正すればよいよう、判定ロジックを1箇所に切り出してある
(`backend/app/exception_handlers.py`)。
