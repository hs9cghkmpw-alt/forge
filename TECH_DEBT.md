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
- **Provider未実装**: TD15参照。**2026-08-10更新: geminiのみ実装済み**(未検証)。openai/claude/oss/forge_aiは引き続き未実装。
- ~~**Native AI未接続**: TD16参照。~~ → **解消済み(2026-08-10確認)**。
  TD16本文参照。
- ~~**Repair Loop Stub**: TD17参照。~~ → **本番経路では呼ばれている、
  ただし実際に修正できるのは限定的なパターンのみ(2026-08-11確認)**。
  TD17・TD32参照(以前は本番でも一度も修正できていなかった実バグを
  発見・修正した)。

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

## TD15. AI Provider(5種)がすべて未実装スタブ → **一部解消・実機確認済み(2026-08-10、Geminiのみ)**

FORGE-MILESTONE-002/003。`backend/app/ai/foundation/providers.py`の
OpenAI/Claude/Gemini/OSS/ForgeAIの5 Providerは、いずれも
`complete_structured()`を呼ぶと`NotImplementedError`を送出していた
(`tests/test_ai_runtime.py`の`test_all_foundation_provider_stubs_raise`で
5件とも確認済み)。

**今は困っていない理由**: 意図的な設計(禁止事項「AI実装したふり」を
避けるため)。`ProviderRouter`によるルーティング(選択)ロジックは
実際に動作するが、選んだ先のProviderを実際に呼び出す部分だけが
未実装という状態を明確に切り分けている。

**将来困る条件**: 実際にAI生成機能をユーザーへ提供するには、
最低1つのProviderを実装する必要がある。

**対応方針(当初)**: `docs/spec/NATIVE_AI_ROADMAP.md`参照。CEO承認を得た上で、
まず`forge_ai/`(既に世界理解〜設計までは実装済み)を`ForgeAIProvider`へ
接続することを推奨する。

**2026-08-10 FORGE-AI-CONNECT-001での対応**: CEOから「無料で使える外部AI
接続を先に」という明示的な指示を受け、`NATIVE_AI_ROADMAP.md`が推奨していた
`forge_ai/`経由の接続ではなく、**`GeminiProvider`を先に実装した**
(Google AI Studioの無料枠を想定。理由: forge_aiのCognitive Engineは
それ自体が決定的なルールベース実装であり実LLMではないため、「本物のAIに
繋ぐ」という当初の目的に対しては、外部LLM APIを直接繋ぐ方が早い)。
新規の外部Pythonパッケージは追加せず、既存の`httpx`でGemini REST APIを
直接呼ぶ実装にした。

現状: `mock`・`gemini`の2つが実際に動作する。`openai`/`claude`/`oss`/
`forge_ai`(Provider名としての、Engineとの接続)の4つは、依然として
`NotImplementedError`を送出する未実装スタブのまま。

**2026-08-10 追記: CEOの実際のAPIキーで実機確認済み。** CEOから
Google AI Studioで取得した実際のAPIキーを共有してもらい(このセッション内で
`backend/.env`へ設定、コミットはしていない)、以下を実際に実行して確認した。

- `GeminiProvider`単体で、実際のGemini APIから構造化JSON応答を受け取れる
  こと(例: `{"title": "買っとこ！買い物メモ"}`)。
- 既定モデル`gemini-2.0-flash`は`429`(無料枠のトークン上限0)、
  `gemini-2.5-flash`/`gemini-2.5-flash-lite`は`404`(新規ユーザー提供終了)
  で失敗することを実際に確認し、`gemini-flash-latest`(常に最新版を指す
  エイリアス)へ既定モデルを変更したところ成功した。
- `uvicorn`で実際にBackendを起動し、`POST /api/v1/ai/generate`へ
  `generation_options.provider: "gemini"`を指定して実際にHTTPリクエストを
  送り、`status: "success"`・`diagnostics.provider_used: "gemini"`・
  Forge Language準拠のJSON文書(Validator通過)が返ることを確認した
  (「買い物リストを作って」→checklistアプリ、「旅行の持ち物チェック
  リストを作って」→checklistアプリ、いずれも成功)。

**分かった課題(新規、TD番号は付けず記録のみ)**: 「旅行の持ち物チェック
リスト」という入力に対し、実際に生成されたチェックリストの中身が
「京都旅行」「沖縄旅行」「温泉旅行」のような**旅行先の候補**になっており、
本来期待される「パスポート」「着替え」のような**持ち物**にはなっていなかった。
Gemini自体は正しく応答しているが、forge_aiのCognitive Engine側の
Domain/Template解釈(travel domainの扱い方)に、今回初めて実データで
見えた改善余地がある。今回はGemini接続の検証が目的のため、この中身の
精度改善には着手していない。

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
      どちらの設計にするか未決定 → **記述が古くなっていた点を訂正(2026-08-11)**

**2026-08-11追記**: 「今は困っていない理由: どちらもまだ実際には
呼ばれない(Stub/Mock)」という下記の記述は、**もう実態と合っていない**
ことを実コードで確認した(FORGE-AI-QUALITY-001の一環)。

`backend/app/ai/runtime/prompt_pipeline.py`(実際に`/api/v1/ai/generate`
が呼ぶ本番経路)は、`forge_ai.repair.repair_engine.RepairEngine`を
**実際にimportして呼び出している**(357〜362行目、Validator不合格時に
`self._max_repair_attempts`回まで実行)。テスト
(`backend/tests/test_ai_runtime.py`の`test_invalid_then_repaired_
then_valid`・`test_repair_exhausted_still_invalid_raises_forge_
validation_error`・`test_quality_reevaluated_after_repair`)も既に
この本番経路を対象に書かれている。Stubのままなのは、下記で言及されている
`backend/app/ai/runtime/repair.py`の`AIRepair` Protocol
(`raise NotImplementedError`)だけであり、これは`run_cognitive_pipeline`
(forge_aiの経路、現在の唯一の本番経路)ではなく、使われていない旧
Legacy Protocol側の実装である。

この訂正を踏まえると、下記「対応方針」(RepairEngineの実績を土台に
`repair.py`側もハイブリッド設計へ寄せる)は**既に実質的に達成済み**
とみなせる(`repair.py`側のStub自体は、使われていないコードとして
残っている——別途削除するかは判断が必要、TD項目としては起票しない)。

**今回スコープ外にしたこと**: `RepairEngine._try_fix()`が実際に
決定的修正できるのは`missing_app_title`・`empty_checklist_state`の
2カテゴリのみ(`forge_ai/repair/repair_engine.py`参照)。これ以外の
Validator不合格理由(未知のWidget type等)は、Repair試行回数を使い切って
そのままエラーになる。実際にどのカテゴリの不合格が多く発生している
かを実機で計測していないため、今回は追加のパターン対応は見送った。

---

以下、2026-08-10以前の元の記述(履歴として残す)。

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

## TD20. Native AI出力の安全性検査(Output Safety)が未設計(→ M005) → **解消済み(2026-08-11実機確認)**

**2026-08-11追記**: この項目は既に実装・実機確認済みだったにも
関わらず、本文に「解消済み」マーカーを付け忘れていたため訂正する
(TD17と同種の記述漏れ、他のTD項目を精査する過程で発見)。
`backend/app/ai/runtime/output_safety.py`(`OutputSafetyChecker`)を
新設し、`routers/ai.py`から呼び出すよう配線した。実際に「クレジット
カード番号を保存するアプリ」を実Gemini APIへ依頼し、生成された
app titleに含まれる`"クレジットカード番号"`・`"カード番号"`を
`safety_report`(`safe: false`、high severity)が正しく検出することを
2026-08-10・2026-08-11の両方で実機確認した。詳細な実装内容・検証
記録はCHANGELOG.md Task049参照。以下は当初(未実装だった時点)の
記述をそのまま残す。

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

## TD21. Prompt Injection対策が明示的に設計されていない(→ M005) → **解消済み(2026-08-10実機確認)**

**2026-08-11追記**: TD20と同じ理由で「解消済み」マーカーを付け忘れて
いたため訂正する。`forge_ai/prompt/injection_guard.py`
(`PromptInjectionGuard`)を新設し、薄いAdapter
(`backend/app/ai/runtime/injection_scan.py`)経由で`routers/ai.py`から
呼び出すよう配線した(検出のみ、ブロックはしない設計)。実際に
Gemini経由で`Ignore previous instructions`+`developer modeを有効に
して`を含むリクエストを送り、`injection_report.detected=true`
(`status`は`success`のまま継続)を2026-08-10に実機確認した。詳細は
CHANGELOG.md Task049参照。以下は当初(未実装だった時点)の記述を
そのまま残す。

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

## TD22. IntentIR/PlanIR/Templateスキーマにバージョン管理が無い(→ M005) → **解消済み(2026-08-11)**

**2026-08-11追記**: TD20/TD21と同じ理由で「解消済み」マーカーを
付け忘れていたため訂正する。`IntentIR`・`PlanIR`
(`backend/app/ai/foundation/interfaces.py`)・`Template`
(`backend/app/ai/runtime/template_engine.py`)へ、既定値付きの
`schema_version: str = "1.0"`を追加した(既存呼び出し元への後方互換を
保ったまま)。Migration機構自体は実装していない(2つ目のバージョンが
実際に必要になった時点で設計する、という下記の元の対応方針どおり)。
詳細はCHANGELOG.md Task049参照。以下は当初(未実装だった時点)の
記述をそのまま残す。

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

## TD23. HTTP層(FastAPI/Pydantic)がClaude環境で一度も実行できていない → **解消済み(2026-08-10)**

**2026-08-10追記**: `pip install -r requirements.txt`が実際にこの
環境で成功するようになり(TECH_DEBT.md記載当時と異なりネットワークが
使えた)、`uvicorn app.main:app`を実際に複数回起動し、
`POST /api/v1/ai/generate`・`GET /health`等へ実際にHTTPリクエストを
送って動作確認した(FORGE-AI-CONNECT-001、`docs/reports/
FORGE-AI-CONNECT-001-report.md` 9章参照)。`_is_json_syntax_error()`を
含むexception_handlers.pyも実際に例外パス込みで動作している
(Geminiの`429`/`404`エラーが正しく`RuntimeError`経由でエラーレスポンスに
変換されることを確認済み)。以下は解消前の記述として残す。

---

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

---

## TD24. Domain内の複数Conceptに「意味的な重要度」の区別が無い → **travelのbelongings/accommodation/itineraryケースは解消済み(2026-08-11)、選定メカニズムを一般化済み**

**2026-08-11追記**: CEO指示「すべてお願い」を受け対応した。
`application_planner.py`へ`_prioritize_explicitly_mentioned_concepts()`を
追加し、`"belongings"`が`intent.required_concepts`に実際に含まれる
場合のみ先頭へ優先する、許可リスト方式(travel domain以外への影響
無し)で対応。加えて、この過程で`forge_ai`自身のGolden Test
(`test_success_cases_do_not_leak_raw_concept_identifiers_as_initial_items`)
が、`compiler.py`の`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`テーブルに
`"belongings"`のエントリが無いことによる別の実バグ(内部識別子の
raw leak)を検出したため、`("パスポート", "着替え", "歯ブラシ",
"充電器")`を追加して解消した。

実際にGemini APIで再検証し、「パスポート」「着替え」「歯ブラシ」
「充電器」が正しく生成されることを確認した(forge_ai/backend
テストスイート917 passed, 12 skippedも維持)。

**残る限界**: この解決策は`"belongings"`という個別Conceptへの
対応であり、「Domain内の複数Conceptから、文の主題を汎用的に
選び出す」という根本課題自体は未解決のまま(下記は当初の記述)。

---

FORGE-AI-CONNECT-001の実機確認(2026-08-10、実際のGemini APIで
「旅行の持ち物チェックリストを作って」を試して発見)。

`forge_ai/core/planning/application_planner.py`の
`primary_concept = data_entities[0] if data_entities else "item"`は、
`data_entities`の**先頭要素**を無条件に「主概念」として扱う。
`data_entities`(`base_data_entities`)は
`forge_ai/core/understanding/world_builder.py`で
`domain.typical_concepts`の**定義順そのまま**から作られる
(`CognitiveWorldBuilder.build()`)。

「旅行の持ち物チェックリストを作って」という入力では、`intent.
required_concepts`に`destination`(「旅行」由来)と`belongings`
(「持ち物」由来、2026-08-10に追加)の両方が正しく含まれるにも
関わらず、`data_entities[0]`は常に`destination`になる(TRAVEL domainの
`typical_concepts`定義順で`destination`が先頭のため)。この結果、
Compile段階のPrompt(`build_compile_prompt`)が「destinationの具体例」を
求める形になり、実際にGemini APIで生成させたところ「京都旅行」
「沖縄旅行」「温泉旅行」という**旅行先**が生成され、期待される
「パスポート」等の**持ち物**にはならなかった(実際に確認した実例)。

**今は困っていない理由**: 影響はtravel domainの「持ち物」系リクエストに
限定される(他13 Domainでは同種の問題を確認していない、確認もしていない)。
Gemini接続自体・Validator・Repair等のパイプラインは正しく動作しており、
「生成される中身の妥当性」という品質面の課題である。

**将来困る条件**: 他のDomainでも、同一Domain内に複数のConceptがあり、
かつユーザーの入力がそのうち特定の1つだけを強く意図している場合
(例: 「家計簿の固定費だけ管理したい」等)、同様に「関係ない方の
Conceptが主役として選ばれる」問題が起こりうる。

**対応方針(未着手)**: `data_entities`の先頭を、Domain定義順ではなく
`intent.required_concepts`の中で「より具体的・特徴的な一致」を
した順(例: 汎用的すぎる一致(destinationの元キーワード「旅行」は
Domain判定そのものに使われる語であり、Concept固有性が低い)より、
Domain判定に使われた語とは別の語で一致したConcept(例:
「持ち物」→belongings)を優先する、等)へ並べ替えることを検討する。
ただし、この並べ替えロジックは`application_planner.py`の
`base_data_entities`という、**全15 Domain共通の基盤ロジック**であり、
変更するとtravel以外のDomainの挙動にも影響しうる。今回は
`forge_ai`の既存Golden Test(390件)への影響を確認する余裕が
無かったため、着手を見送った。着手する場合は、既存Golden Test全件と
新規のtravel/belongings向けGolden Testの両方が通ることを確認してから
マージすること。

---

**2026-08-11(2回目)追記(FORGE-AI-QUALITY-001)**: CEOが選んだ4方向の
うちの1つ「『主役となる概念』の選び方自体を直す」に対応した。

実際に全15 Domainの`typical_concepts`定義を1件ずつ精査した結果、
「先頭Conceptが単なるDomain判定のトリガーで、主役には不向き」という
問題を持つのはtravelの`"destination"`のみであると確認できた
(他14 Domainは、先頭Conceptがそのまま主役として自然な設計になっている)。
そのため、「言及された概念を無条件に優先する」という、より汎用的な
アルゴリズムへの全面刷新は見送った——実際に試した結果、"price"・
"quantity"のような「主役の属性に過ぎない概念」が、単に言及された
というだけで誤って主役に昇格しうることを確認したため(`compiler.py`
冒頭が指摘する既知の制限そのもの)。

代わりに、`_PREFER_AS_PRIMARY_WHEN_MENTIONED = ("belongings",)`という
travel専用のConcept名直書き許可リストを、`DomainConcept.
primary_candidate: bool = True`という一般的なDomain定義側のメタデータへ
置き換えた(`domain_model.py`参照)。**選定ルール自体**(「Domain判定の
トリガーになっただけの概念より、実際に言及された別概念を優先する」)は
据え置きつつ、**メカニズム**を一般化した: 将来、別のDomainで同種の
問題が見つかった場合、`application_planner.py`を一切変更せず、該当
Conceptに`primary_candidate=False`を宣言するだけで対応できる。

この変更により、travel domainで新たに2ケースが解消した(以前は
`"destination"`が固定的に主役になっていたため、静的テーブルに
`"destination"`のエントリしか無く、以下は生の識別子が漏れていた)。

| プロンプト | 修正前 | 修正後(実機・実Gemini API確認) |
|---|---|---|
| 「ホテルと観光地を管理したい」 | `destination`が主役(無関係な旅行先が生成される可能性) | `accommodation`が主役 → `['グランドホテル京都 (宿泊先)', '清水寺 (観光地)', ...]` |

`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`(`compiler.py`)へ`accommodation`・
`itinerary`・`expense`のエントリも追加した(昇格したConceptがテーブルに
無いと生の識別子が漏れる、という同種の問題を防ぐため。実際に
`test_success_cases_do_not_leak_raw_concept_identifiers_as_initial_items`
が「ホテルと観光地を管理したい」で検出した)。

`forge_ai/tests/test_planning_and_critic.py`へ3件の回帰テストを追加
(demoteされるケース・何も言及が無ければ変わらないケース・
`primary_candidate`を宣言していない既存Domainではメカニズム自体が
no-opであることの確認)。forge_ai全408件・backend込み全947件が
回帰なしで通ることを確認した上で、実際に`uvicorn`+実Gemini APIで
3プロンプト(持ち物・ホテル/観光地・旅行計画のみ)を再実行し、
いずれも意図した具体的な内容が生成されることを確認した。

---

## TD25. Flutter音声入力(speech_to_text)が実機・実ブラウザで一度も検証できていない

FORGE-AI-CONNECT-001(2026-08-11)、CEO「すべてお願い」を受けて実装。
`frontend/lib/features/app_generation/presentation/providers/
voice_input_provider.dart`(`VoiceInputController`、`speech_to_text`
パッケージへの薄いラッパー)と、`home_screen.dart`の`_VoiceInputButton`
(マイクボタン、`StatefulWidget`)を新規実装した。

**今は困っていない理由(困っていない、ではなく「まだ実害が顕在化して
いない」という意味)**: Claudeのサンドボックスには、Flutter SDK・
マイクデバイス・ブラウザの音声認識APIのいずれも存在しない。そのため、
以下がすべて未検証である。

- `speech_to_text: ^7.0.0`という指定が、`flutter pub get`で実際に
  解決可能か(バージョン番号は公式ドキュメントの記載に基づく推測)。
- `SpeechToText.initialize()`/`.listen()`の実際のAPIシグネチャ
  (`onError`/`onStatus`/`onResult`のコールバック引数の型、
  `SpeechRecognitionError.errorMsg`・`SpeechRecognitionResult.
  recognizedWords`/`.finalResult`等のフィールド名)が、実際にpub.devで
  解決されるバージョンと一致するか。
- Chrome等のブラウザで、実際にマイク権限プロンプトが出て、音声が
  正しく文字起こしされるか。

**プラットフォームの制約**: このアプリは`android/`・`ios/`という
ネイティブプロジェクトフォルダを一度も`flutter create`で生成しておらず
(`frontend/web/`のみ存在)、今回もこれらのフォルダは作成していない。
そのため音声入力は**Web(Chrome等)でのみ動作する想定**であり、
ネイティブアプリとしてビルドした場合は動作しない
(`AndroidManifest.xml`のRECORD_AUDIO権限・`Info.plist`の
NSMicrophoneUsageDescription等が無いため)。

**将来困る条件**: CEO環境で`flutter pub get`を実行した際に依存解決が
失敗する、または`flutter run -d chrome`実行時にAPIシグネチャ不一致で
コンパイルエラーになる可能性がある。

**対応方針**: CEO環境で`flutter pub get`→`flutter run -d chrome`を実行し、
結果(エラーメッセージ含む)を共有してもらう。コンパイルエラーが出た場合、
エラー内容から実際のAPIシグネチャとのズレを特定して修正する
(`GETTING_STARTED.md`のトラブルシューティング参照)。

---

## TD26. Checklist系Domain(10種)のCompile段階が、Providerの応答をtitle以外
すべて捨てていた → **解消済み・実機確認済み(2026-08-11)**

FORGE-AI-QUALITY-001(2026-08-11)、CEO「生成できるアプリのクオリティを
最大限にしたい」→「色々なジャンルで実際に生成→不具合を見つけて直す」を
選択したことを受けて発見・修正。

**発見の経緯**: 実際にGemini APIへ11ジャンルのプロンプトを投げて出力を
確認したところ、以下のように、依頼内容に関係なく常に同じ初期データが
返ってくる不具合を再現した。

| プロンプト | 修正前の出力 |
|---|---|
| 「満足度アンケートを作って」 | `['最初の質問']` |
| 「週間スケジュールを管理するアプリを作って」 | `['定例ミーティング']` |
| 「毎日の勉強記録をつけたいアプリを作って」 | `['英語', '資格試験の勉強', '読書']` |

**根本原因**: `forge_ai/core/compiler.py`の`Compiler.compile()`が、
Provider(Gemini)の応答から`title`しか読み取っておらず、チェックリストの
初期項目は`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT`という静的な決め打ちテーブル
(`primary_concept`名→固定の例値タプル)からしか作られていなかった。
このテーブルは「先頭のkey_elementが何の概念か」だけを見るため、依頼内容の
具体的な違い(「満足度アンケート」と「習い事の満足度アンケート」)を一切
反映できない。

この`Compiler`(Checklist単一画面形状)は、`pipeline_orchestrator.py`の
`SUPPORTED_DOMAIN_CATEGORIES`(`forge_ai/core/ir/ir_generator.py`の
`_ENTITY_DEFINITIONS`のキー)に含まれない、以下10 Domainすべてで使われる
(残る5 Domain=diary/inventory/household_budget/fishing_log/habit_trackingは
`forge_ai/core/ir/`の新経路のため対象外・元々問題なし)。

`shopping・hospital・attendance・task_management・survey・schedule・
child_growth・study・travel・generic`

**修正内容**:
1. `forge_ai/prompt/prompt_builder.py`の`build_compile_prompt()`: system
   textへ「依頼内容に即した具体的なexample_items(2〜4件)を提案すること」
   という指示を追加。
2. `backend/app/ai/runtime/forge_ai_provider_bridge.py`の
   `_RESPONSE_SCHEMAS["compile"]`へ、任意項目として`example_items`
   (`array<string>`)を追加(`required`には含めない。MockProvider・既存の
   実LLM未接続テストは`example_items`を返さないため、その場合は既存の
   静的テーブル→生の識別子という順序へ安全にフォールバックする)。
3. `forge_ai/core/compiler.py`の`Compiler.compile()`: Providerが
   `example_items`(空でない文字列のリスト)を返した場合、静的テーブルより
   優先して使うよう変更。不正な形(非リスト・非文字列要素)は無視して
   フォールバックする防御的な実装にした。

**検証**: `forge_ai/tests/test_compiler.py`へ`TestCompilerProviderExample
Items`(4件、優先順位・空リスト時のフォールバック・キー欠如時の
フォールバック・不正な形の防御を検証)を追加。既存の全テスト
(forge_ai 408件・backend込み944件)が回帰なしで通ることを確認した上で、
実際に`uvicorn`+実Gemini APIで再実行し、修正後の出力を確認した。

| プロンプト | 修正後の出力 |
|---|---|
| 「満足度アンケートを作って」 | `['サービス全体の満足度を教えてください', 'スタッフの接客対応はいかがでしたか？', '今後も当サービスを利用したいと思いますか？']` |
| 「週間スケジュールを管理するアプリを作って」 | `['月曜 10:00 - チーム定例ミーティング', '水曜 14:00 - プロジェクト進捗確認', '金曜 17:00 - 週次振り返りミーティング']` |
| 「毎日の勉強記録をつけたいアプリを作って」 | `['英検1級対策 - 公式問題集 1章〜3章完了', '基本情報技術者試験 - 過去問道場 午前50問演習', 'Pythonプログラミング学習 - 基礎文法セクション終了']` |

**既知の制限**: `example_items`は依然として「チェックリストの初期項目」
という単一の粒度でしか使われない。TD24で既に指摘した「item/price/
quantity/storeのような、本来複数属性を持つ1件のデータをChecklistの複数行
として扱ってしまう」という、より根本的なCompilerの構造的制約(Task
#10「primary_concept選定アルゴリズムの汎用的な再設計」の範囲)自体は
未解消のまま。

---

## TD27. 「通院記録」「勤怠」がhospital/attendance Domainへ分類されず、
diary Domainへ誤分類されていた → **解消済み・実機確認済み(2026-08-11)**

FORGE-AI-QUALITY-001(2026-08-11)、TD26と同じ実機プローブで発見。

**根本原因**: `forge_ai/core/lexicon.py`の`CONCEPT_KEYWORDS`に、「通院」
(hospitalの`appointment`概念)・「勤怠」(attendanceの`status`概念)に
対応するエントリが無かった。一方`ACTION_KEYWORDS`の「記録」→
`add_entry`(diaryのaction)だけは一致してしまうため、Domain Classification
(`understanding/domain_classifier.py`)がConcept一致0件・Action一致のみで
diaryをprimary_domainに選んでしまっていた(「Action一致のみでは
confidenceに上限を課す」設計はあるが、他Domainが完全に0点のままだと
それでも勝ってしまう)。結果、診療記録・勤務記録という明確な意図が
あるにもかかわらず、確認も無く汎用日記アプリとして生成されていた。

**修正内容**: `lexicon.py`の`CONCEPT_KEYWORDS`へ`("通院", "appointment")`・
`("勤怠", "status")`を追加。「毎日」「写真」のような汎用語と異なり、
「通院」「勤怠」は日常会話の他文脈でまず使われない語であるため、
既存の「見送り」判断とは事情が異なると判断した。

**修正後の実際の挙動(意図的にdiary誤分類ではなくなっただけで、
即Success化はしない)**:
- 「通院記録を管理するアプリを作って」→ hospital domainへ正しく分類され、
  既存のPrivacy確認フロー(利用者の同意確認)へ合流するようになった。
- 「勤怠を記録するアプリを作って」→ attendance domainへ正しく分類され、
  「status」概念がattendance/task_managementで共有されているという
  既存の既知の僅差競合(`出席と欠席を記録したい`と同種)により、
  Domain確認を求めるようになった。

**検証**: `forge_ai/tests/test_v03_domain_inference_golden.py`の
`CONFIRMATION_CASES`へ2件追加し、実際のreasonコードが一致することを
自動テスト化した。加えて、`test_hospital_and_attendance_domain_specific_
prompts_are_no_longer_misclassified_as_diary`を新設し、reasonだけでなく
primary_domainがhospital/attendanceになっていること自体を直接検証する
(reasonの一致だけでは「diaryのままだが別の理由でconfirmationになった」
というケースを見逃しうるため)。既存の全テスト(forge_ai 408件)が回帰
なしで通ることを確認した上で、実際に`uvicorn`+実Gemini APIで再実行し、
上記の挙動を確認した。

---

## TD28. Design Criticの評価軸がM006 14軸中8軸のみだった → **10軸へ拡張(2026-08-11)**

FORGE-AI-QUALITY-001(2026-08-11)、CEOが選んだ4方向のうち
「Design Criticの評価範囲を広げる」に対応した。

**追加した2軸**:
* **Action Completeness**: `key_elements`(データ)を持つ画面が、
  `required_actions`を1つも持たない(=見るだけで何も操作できない)
  場合、high/blockingとして指摘する。
* **State Completeness**: (1) `ApplicationPlan`全体で`data_entities`が
  1件も無い場合はhigh/blocking、(2) 画面の`key_elements`に、
  `plan.data_entities`へ含まれない値(孤立したデータ)がある場合は
  medium/non-blockingとして指摘する。

**選定基準(正直な申告)**: 残り4軸(Domain Consistency・Error
Recovery・Explainability・Runtime Safety)は見送った。`DesignCritic.
evaluate()`は`plan`・`template_selection`・`requirements`の3引数しか
受け取らず、これらはDomain定義・実際のエラーハンドリング文言の意味・
Runtime実行結果といった、この3引数だけでは機械的に判定できない情報を
要するため。シグネチャを広げる設計変更(呼び出し元
`pipeline_orchestrator.py`・既存テストへの影響範囲)は今回のスコープ
外とした。

**正直な申告その2**: `CognitiveApplicationPlanner`の現在の実装では、
`required_actions`が空になることは実質無く(必ず`("add_item",)`等へ
fallbackする)、単一画面Planでは`screen.key_elements`と
`plan.data_entities`は常に一致する(`data_entities`がそのまま
`key_elements`に代入されるため)。そのため、追加した2軸は現時点では
**ほぼ常に満点**になる——既存のNavigation Coherence軸(単一画面時は
常に満点)と同種の、将来の拡張(複数画面Plan・Action 0件になりうる
経路)に備える防御的な評価軸という位置づけである。

**検証**: `forge_ai/tests/test_planning_and_critic.py`へ4件の回帰テスト
(データありでAction無し→blocking/データ無しでAction無し→非該当/
data_entities空→blocking/孤立したkey_element→medium非blocking)を
追加。forge_ai全411件・backend込み全951件が回帰なしで通ることを確認
した上で、実際に`uvicorn`+実Gemini APIで「買い物リストを作って」を
再実行し、Design Criticの評価軸追加後もSuccess経路が正常に動作する
ことを確認した(意図しない副作用でrelease_readyが崩れていないことの
裏付け)。

---

## TD29. Template Selectorの選定結果がCompile段階へ渡されておらず、実質死んでいた → **"form"のみ解消済み(2026-08-11)**

FORGE-AI-QUALITY-001(2026-08-11)、CEOが選んだ4方向のうち
「Widget・Templateの種類を増やす」を調査した過程で発見した、最も
影響範囲の大きい不具合。

**発見の経緯**: `TemplateSelector`(`forge_ai/core/planning/
template_selector.py`)は、11種類のTemplate名(checklist/form/tracker/
calendar/memo/crud/dashboard/catalog/detail_list/wizard/generic)から、
Domain別のPreliminary候補・Dominant action一致・Data lifecycle一致に
基づく本格的なスコアリング・tie-break処理で1つを選ぶ、既に十分な
作り込みがされた実装だった。実際に「満足度アンケートを作って」で
`final_template_selection`のDecision Traceを見ると、正しく`template=
form`が選ばれていた。**にもかかわらず**、`pipeline_orchestrator.py`が
`deps.compiler.compile()`を呼ぶ箇所(12. Forge IR Compilation)で、
この選定結果(`context.template_selection.template`)を一切引数として
渡していなかった。結果、`Compiler.compile()`は選ばれたTemplate名を
知りようがなく、常にChecklist単一画面(text_field+button+checklist)を
組み立てていた——Template Selectorのスコアリング・tie-break・
Preliminary/Final不一致時の再計画ループは、**実際の出力に何の影響も
与えていない、事実上の死にコードだった**。

**今は困っていない理由(だった)**: Validator・Repair・Critic等の
パイプラインは正しく動作しており、生成自体は失敗しない。「Templateが
実際の構造に反映されない」という、生成される中身の豊かさに関わる
品質面の課題だった。

**修正内容**: `Compiler.compile()`へ`template: str = "checklist"`
引数を追加し、`pipeline_orchestrator.py`から`context.template_
selection.template`を渡すよう変更した。`template=="form"`の場合のみ、
新設`_compile_form_template()`(2画面: 入力画面+送礼画面、`heading`→
`card`→`form`→`text_field`*N、送信で`navigate`)へ分岐する。この形状は
**新規発明ではなく**、既にWidget Registry v1.1〜1.2で実装・テスト
済みの`backend/app/ai/generators/templates/form_template.py`
(`build_form_template`)・`frontend/lib/features/app_generation/data/
datasources/templates.dart`(`buildFormTemplate`、Mock Generator用)と
**完全に同じ構造**を採用した(新しいWidget構成パターンを増やさない、
既存の実績あるShapeへ意図的に合わせる設計判断)。

**残り9種(tracker/calendar/memo/crud/dashboard/catalog/detail_list/
wizard/generic)は未対応のまま**。実際に選ばれる頻度が高いのは
"form"(survey/hospital)・"checklist"(shopping/task_management等、
既存動作)であり、"tracker"系Domain(household_budget等)は
`forge_ai/core/ir/`という別経路(Template Selectorを経由しない)で
既に十分な品質を確保できている。残りの候補(calendar/memo/crud/
dashboard/catalog/detail_list/wizard)は、実際にどのDomain・入力で
最終的に選ばれるかを確認しないまま実装すると過剰設計になりうるため、
今回は"form"のみに絞った。

**検証**: `forge_ai/tests/test_compiler.py`へ`TestCompilerFormTemplate`
(8件: 既定挙動が変わらないこと・2画面構成・form/heading/card Widget
使用・質問ごとのtext_field生成・version="1.2"・submit_actionの
navigate先・JSON直列化・実際のBackend Validatorでの検証)を追加。
`forge_ai/tests/golden_cognitive/04_survey.json`(Golden Test)を
`ir_valid_screens: 1→2`へ意図的に更新した(実際の出力が変わった
ことを正しく反映)。forge_ai全415件・backend込み全959件が回帰なしで
通ることを確認した上で、実際に`uvicorn`+実Gemini APIで「満足度
アンケートを作って」を再実行し、実際のサービス改善アンケートらしい
3つの質問文がそれぞれ独立したtext_fieldとして生成され、実際の
Backend Validatorに通り(`valid: true`)、Design Criticが
`release_ready=true`になることを確認した。

---

## TD30. AI生成アプリの実行時Stateをローカル永続化した設計上のトレードオフ(2026-08-11新設)

FORGE-AI-QUALITY-001(2026-08-11)、CEO「これを、ほんとにアプリストアで
人気レベルのアプリをつくれるようなクオリティにするにはどうしたらいい？
考えて考えて疑って考えて疑って考えてから実装して」への対応。

**発見の経緯**: 「app store品質」に必要な要素を洗い出す過程で、
`ForgeStateStore`(`frontend/lib/json_ui/runtime/forge_state_store.dart`)
がメモリ内Mapのみで一切永続化しておらず、`ForgeScreenView`
(`forge_renderer.dart`)が画面を開くたびに文書の初期値から`ForgeRuntimeState`
を新規構築していることを実コードで確認した(`KNOWN_ISSUES.md`の
「AI生成アプリの状態はアプリ再起動で消える」に既に記録されていた、
意図的なスコープ外だった項目)。生成したチェックリスト・家計簿等の
アプリが、閉じるたびに入力内容ごと消える設計では実用アプリとして
成立しないと判断し、最優先で対応した。

**採用した設計と、あえてやらなかったこと**:

* ROADMAP.mdが元々想定していた「Backendの`apps`/`app_versions`テーブル
  + Supabase」というサーバー側・マルチデバイス同期の永続化は、
  Supabaseアカウント作成等CEO側の作業(このセッションでは実行不能な
  外部サービス連携)が必要なため見送った。
* 代わりに、既存の`SavedForgeApp`(アプリ定義)保存と同じ
  `shared_preferences`(端末ローカルのみ)を使い、実行時State
  (`{appId: {screenId: {stateKey: {type, value}}}}`という1つのJSON
  Blob)として保存する方式にした。既存の`_appsKey`/`_historyKey`と
  同じ「1キーへ全体をまとめて読み書きする」パターンを踏襲した(既知の
  制限も同じ: 件数が大きく増える場合はsqlite等への移行が必要、
  `SharedPreferencesAppLibraryRepository`冒頭のコメント参照)。
* 保存タイミングは「State変化のたび(`notifyListeners()`)に
  fire-and-forgetで書き込む」方式にした。`await`せず結果を待たない
  ため、理論上は「書き込みが完了する直前にアプリが強制終了された場合」
  にその1回分だけ失われうるが、書き込み自体はミリ秒オーダーで
  即座に発行されるため、実用上のリスクは小さいと判断した(既存の
  `ChangeNotifier`ベースの同期的な設計を維持するため、ここを
  `await`する非同期化はより大きな変更になり見送った)。
* text_fieldの1文字ごとの入力(`onChanged`)は、既存の設計どおり
  `notify: false`で書き込まれるため、保存の対象にならない(未確定の
  下書き入力まで毎回保存することを避ける、既存の意図を活かした)。

**残る限界(正直な申告)**:
* サーバー側保存・複数端末間の同期は依然未着手。
* 保存されるJSON Blobのサイズに上限を設けていない(既存の
  `_appsKey`/`_historyKey`と同じ既知の制限)。
* この作業環境にDart/Flutter SDKが無いため、**一切実行できていない**
  (構文の目視レビュー・括弧バランスの機械チェックのみ実施)。新規
  Unit Test 2ファイル(`forge_state_persistence_test.dart`・
  `shared_preferences_app_library_repository_test.dart`)を追加したが
  未実行。CEO環境での`flutter test`実行が必須(詳細は
  `KNOWN_ISSUES.md`参照)。

---

## TD31. Gemini無料枠のレート制限(429)が、生のGoogle側エラーJSONのまま表示されていた(2026-08-11解消)

FORGE-AI-QUALITY-001(2026-08-11)、CEO「アプリストアで人気レベルの
アプリをつくれるようなクオリティにするには」対応の一環。多数の
プロンプトを`uvicorn`+実Gemini APIへ連続送信して信頼性面の問題を
探す中で実際に再現した。

**発見**: 無料枠のレート制限(実測: 短時間に約20回程度でGoogle側の
制限に達する。Google側の都合で変わりうる)に達すると、
`GeminiProvider.complete_structured()`が`httpx.HTTPStatusError`を
そのまま`RuntimeError`のメッセージへ埋め込むため、ユーザー(または
Flutter側でエラー表示を見る利用者)には
`"RESOURCE_EXHAUSTED"`・`"generativelanguage.googleapis.com"`のような、
Google API固有の英語の技術用語がそのまま見えてしまっていた。

**修正**: `providers.py`の`GeminiProvider.complete_structured()`で、
`status_code == 429`の場合のみ、原因と対処法が一目でわかる日本語の
文言(「Gemini APIの無料枠の利用上限に達しました。しばらく時間を
おいてから、もう一度お試しください。」)を先頭に出すよう変更した。
生のGemini応答は末尾に残しており、デバッグ時の手がかりは失っていない。
それ以外のHTTPエラー(400・403等)は、既存の挙動(status codeと
レスポンス本文をそのまま含める)のまま変更していない。

**検証**: `backend/tests/test_gemini_provider.py`へ回帰テスト1件を
追加(429時に日本語の案内文言・元のstatus code・元のGoogle側エラー
コードの両方が含まれることを確認)。全テスト(960件)が回帰なしで
通ることを確認した上で、実際に多数のプロンプトを連続送信して429を
実際に発生させ、修正前後のエラーメッセージを比較した。

---

## 補足: TD17(Repair Engine)の記述を訂正

Repair EngineのSection(TD17)を参照。「今は困っていない理由: どちらも
まだ実際には呼ばれない(Stub/Mock)」という記述が、実際には
`prompt_pipeline.py`が`forge_ai.repair.repair_engine.RepairEngine`を
本番経路で呼び出しているという実態と合っていなかったため、TD17本文へ
2026-08-11追記として訂正した(削除はせず、旧記述は履歴として残した)。

---

## TD32. Repair Loopは本番経路で呼ばれていたが、フィールド名の取り違えにより実際は一度も修正できていなかった(2026-08-11解消)

FORGE-AI-QUALITY-001(2026-08-11)。TD17の記述訂正(「Repair Engineは
Stubで呼ばれない」という記述が古かった)を確認する過程で、より深刻な
実バグを発見した。

**発見の経緯**: TD17を訂正する際、「では実際に何かを修正できているか」
を裏取りしようとして`RepairEngine._try_fix()`(既知2パターン:
`"missing_app_title"`・`"empty_checklist_state"`)の判定文字列が、
`backend/app/ai/validators/schema_validator.py`の実際の`Category`
enum(`"syntax"`/`"schema"`/`"semantic"`/`"runtime_safety"`の4値のみ)
のどれとも一致しないことに気づいた。

**根本原因**: `backend/app/ai/runtime/forge_ai_adapter.py`の
`to_repair_issues()`が、`ForgeAIRepairIssue.category`へ
`ValidationIssue.category`(4値の大分類)を渡していた。しかし
`RepairEngine._try_fix()`が判定に使いたかったのは、具体的な識別名
(`ValidationIssue.rule`、実際の値は`"string_length"`・`"required"`・
`"identifier_format"`等)だった。この2つのフィールドを取り違えていた
ため、**Repair Loop自体は本番経路で毎回呼ばれていたが(TD17参照)、
実際にはどのValidator不合格も一度も修正できず、常に
`repair_attempts`を使い切ってそのままエラーになる設計だった**
(Gemini API呼び出しが1回無駄になるだけで、ユーザーへの結果は
「Repairが無かった場合」と同じ)。

加えて、`"missing_app_title"`・`"empty_checklist_state"`という2つの
「既知パターン」自体、実際の`schema_validator.py`を確認したところ
**どちらも実在するルールではなかった**ことも判明した: `app.title`が
無い(keyごと欠落)こと自体はエラーにならない(`app`セクション自体が
任意)。checklistが0件であること自体もエラーにならない(買い物リストが
空で始まるのは正常)。おそらく`forge_ai/`単体の開発時に、実際のBackend
Validatorのルール名を確認せず仮に置いたパターンが、そのまま残っていた
と考えられる。

**修正内容**:
1. `to_repair_issues()`: `category=e.category.value` →
   `category=e.rule`へ修正。
2. `RepairEngine._try_fix()`: `"missing_app_title"`は
   (forge_ai自身のテストがAdapterを経由せず直接構築するケースとの
   後方互換のため)残しつつ、実際に発生しうる`"string_length"`
   ルール(`/app/title`パスに限定、他のフィールドの`string_length`
   エラーと誤って混同しないようpathで絞り込み)への対応を追加した。
   実在しない`"empty_checklist_state"`パターンは削除した。

**検証**: `forge_ai/tests/test_repair_engine.py`・
`backend/tests/test_forge_ai_adapter.py`へ、実際の`schema_validator.py`
(モックではなく本物の関数)が生成する不合格文書を使った回帰テストを
追加(空タイトルの文書を実際に`validate_forge_document()`へ通し、
`to_repair_issues()`が正しく`"string_length"`を返すことを確認)。
全テスト(962件)が回帰なしで通ることを確認した。

**残る限界**: `"string_length"`(app.title)以外の実際のValidator
ルール(`"required"`・`"identifier_format"`・`"type"`等)は、依然
決定的な自動修正の対象になっていない。これらの多くはAI生成JSON側の
構造的な不具合(例: checklist widgetにstate_refが無い)であり、
何を正しい値にすべきかを安全に推測できないため、今回は対応を見送った
(不用意に「直したつもり」で別の不具合を埋め込むリスクの方が大きいと
判断)。実際にどのルールが本番でどれだけの頻度で発生するかを計測して
いないため、次にどのパターンへ対応すべきかの優先順位付けもできていない。
