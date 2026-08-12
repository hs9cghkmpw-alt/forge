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
- **Widget Registry(2026-08-11更新)**: CEO承認によりForge Language
  Freeze運用を解除し、`choice_field`/`bar_chart`(TD34)・
  `date_field`/`tab_view`(TD36)を追加。Widget型は14種→18種。単一
  画面を`tab_view`によるタブ構成へ更新した。真の複数画面CRUDは、
  Runtime側の制約(画面をまたいだState共有が無い)により見送った、
  TD36参照。Python側・Dart側とも実機検証済み(TD37でFlutter SDKを
  実際に取得・実行できることが判明し、`typeNameOf()`の網羅的switch式
  にケース追加漏れがあったため4種のWidgetが一度も描画できていな
  かった重大なバグを発見・修正した)。全Dartテスト435件・Pythonテスト
  1024件が通ることを確認済み。KNOWN_ISSUES.mdの「Flutter SDK不在」
  制約は解消済み(セットアップ手順を記録)。
- ~~**新規発見(2026-08-11)**: TD35。~~ → **解消済み(2026-08-11)**。
  `backend/.env`を実際に読み込むコードがどこにも無く、Gemini接続が
  必要なDomain(Legacy/checklist系)は常に失敗していた
  (household_budget等IR系Domainはそもそも決定的でGeminiを呼ばない
  ため、たまたま「動いているように」見えていた)。`main.py`へ
  `load_dotenv()`を追加して解消。TD35本文参照。

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

---

## TD33. record_list系Domain(3種)のchoice型Field(カテゴリ・気分等)が、有効な選択肢を一切示さないまま送信させ、高確率で入力を弾いていた(2026-08-11解消)

FORGE-AI-QUALITY-001(2026-08-11)、CEO「がっつしバグ全部探して潰して」
対応の一環。IR経由(record_list形状)で生成されるDomain
(household_budget/inventory/diary)を実際にGemini APIで生成し、
生成されたJSONの中身を1フィールドずつ確認する過程で発見した。

**発見**: `household_budget`の「カテゴリ」・`inventory`の「カテゴリ」・
`diary`の「気分」は、いずれも`choice`型Field(あらかじめ決められた
選択肢からのみ選べるはずのField)として`record_schemas`に正しく
宣言されているにも関わらず、実際の入力Widgetはplaceholderが
Fieldラベルのみ(例:「カテゴリ」)の、ただの`text_field`だった。

**根本原因**: Widget Registryが凍結されており、ドロップダウン等の
専用Widgetを新設できないという既存の制約(`FORGE-IR-V1-PROPOSAL.md`)
自体は正しい設計判断だが、その代替として「有効な選択肢をどこにも
示さない」ままにしていたのは見落としだった。実際にDart Runtime側の
`ForgeFieldValueParser._parseChoice()`
(`frontend/lib/json_ui/validation/forge_field_value_parser.dart`)を
確認したところ、`options.contains(raw)`という**厳密な完全一致検査**
だった。つまり「食費」以外の表記(「食費だ」「Food」「食費 」等)は
送信時に`invalidChoice`として拒否される仕様であり、UIには選択肢の
手がかりが一切無いまま、素直な入力の大半が初回submitで弾かれる
設計になっていた(エラーメッセージ自体には選択肢が含まれるが、
それは送信して失敗した**後**にしか分からない)。

**修正**: `forge_ai/core/ir/forge_language_compiler.py`の
`_build_field_inputs()`で、`FieldType.CHOICE`のFieldに限り、
placeholderへ選択肢を埋め込むよう修正した(例: 「カテゴリ」→
「カテゴリ(食費・交通費・娯楽・その他)」)。新しいWidget型は
追加していない(既存の`text_field`+`placeholder`プロパティのみで
実現)。作成用フォーム・編集用フォームの両方がこの共有関数を通るため、
両方に反映される。

**検証**: `forge_ai/tests/test_forge_language_compiler.py`へ回帰
テスト2件(choice型Fieldのplaceholderに全選択肢が含まれること・
choice以外のFieldのplaceholderが変わっていないこと)を追加。全テスト
(964件)が回帰なしで通ることを確認した上で、実際に`uvicorn`+実Gemini
APIで`household_budget`・`inventory`・`diary`の3 Domainを再生成し、
いずれも選択肢がplaceholderへ正しく反映されていることを確認した。

**残る限界**: これはあくまで「テキストとして選択肢を見せる」という
最小限の緩和であり、実際にタップで選べるドロップダウン/チップ選択の
ような体験には及ばない。Widget Registryの拡張(専用のchoice Widget
追加)は、今回のスコープ(既存Widget内での改善)を超えるため見送った。

**追記(同日、同種の問題をdate型Fieldでも発見・修正)**: `choice`型と
同じ調査の過程で、`date`型Field(例: 家計簿記録の「日付」)も同様に
placeholderがFieldラベルのみ(「日付」)で、`ForgeFieldValueParser.
_parseDate()`が要求する厳密なISO 8601形式(YYYY-MM-DD)がどこにも
示されていないことに気づいた。choiceほど致命的ではない(YYYY-MM-DD
自体は広く知られた書式のため)が、同じ理由・同じ修正方針で
placeholderへ「日付(YYYY-MM-DD)」のように形式を含めるよう修正した。
回帰テストを追加し、全テスト(965件)が通ることを確認した。

**さらに追記(2026-08-11、TD34でこの「残る限界」自体を解消)**: 上記の
「専用Widget追加はスコープ超過」という制約は、`docs/spec/
LANGUAGE_FREEZE.md`のWidget追加凍結運用に基づくものだった。CEOへ
この制約の実態(正式な凍結宣言は一度も無かったこと)と、それにより
生じている具体的な実害(household_budgetの「収支をグラフで見たい」
という既存の例文が実現不可能な約束になっていること)を報告し、
凍結解除の承認を得た。TD34で`choice_field`(本物のドロップダウン)を
実装し、このplaceholder応急処置を置き換えた。

---

## TD34. Widget Registryが14種のまま(text/checkboxレベルの表現力しか無く、製品自身の例文すら実現不可能)だった → **choice_field/bar_chartの2種を追加(2026-08-11)**

FORGE-AI-QUALITY-001(2026-08-11)。CEOから「いまの生成できるアプリは
テキストとチェックボックスぐらいの機能しか持たせられないってこと?
これはツールをそれぐらいしかもってないから?ゴールはわかってる?」
という直接的な問いを受け、正直に調査・報告した内容が発端。

**発見**: Forge Language全体でWidget型はv1.0〜v1.5を通じて14種類
(`text`/`text_field`/`button`/`column`/`row`/`checklist`/`heading`/
`checkbox`/`card`/`list`/`divider`/`form`/`record_list_view`/
`section_header`)のみで、画像・グラフ・カレンダー・地図・スライダー・
ドロップダウン・アニメーションのいずれも存在しなかった。決定的だった
のは、`frontend/lib/features/app_generation/presentation/widgets/
example_picker_sheet.dart`が提示するオンボーディング例文そのものに
「収入や支出を記録して、月ごとの収支をグラフで見たい」という一文が
含まれていたこと——**製品自身が謳う例が、製品自身のWidget語彙では
文字通り実現不可能だった**(グラフに相当するWidgetが1つも無い)。

**根本原因**: `docs/spec/LANGUAGE_FREEZE.md`の「Widgetは追加しない」
という運用方針。ただし実際に同ドキュメントを読み直すと、2章の
Freeze条件(実RuntimeでのFlutter `flutter analyze`確認・全Widget
セットの実描画確認・`string_list`設計課題の解消)がいずれも未達成の
まま、1章に明記された通り**一度も正式に凍結宣言されていなかった**。
つまり「変更してはいけない確定ルール」ではなく、「まだ検証していない
という理由で、これまで誰も踏み込まなかった未確定の状態」だった。

**CEOの判断**: この事実確認を報告した上でWidget追加を提案したところ、
「凍結宣言をすべて解除します。ひきつづきすすめて。」と明示的な承認を
得た。

**対応**: 新規パッケージ依存を追加せず、Flutter標準Widgetのみで
実現できる2種を追加した(`backend/app/ai/validators/schema_validator.py`
にVersion "1.6"として新設、`WIDGET_TYPES_V1_6_ADDITIONS`)。

* `choice_field`: 決まった選択肢から1つを選ぶ入力
  (`DropdownButtonFormField`で実装)。TD33のplaceholder応急処置
  (`text_field`に選択肢の文字列を埋め込むだけ)を置き換える、本来
  あるべき専用Widget。ユーザーが自由文字列を打鍵できない構造その
  ものにより、`ForgeFieldValueParser._parseChoice()`が要求する
  完全一致を保証する(誤入力自体が起こりえない)。
* `bar_chart`: `record_list`の数値Fieldを棒グラフで可視化する
  (1 Record = 1本の棒)。月ごとの合計等の**集計は行わない**、
  Phase1の最小実装(指示書の制約と同じ精神: 需要が実証されていない
  機能の先行実装を避ける)。

**変更ファイル(Python側、テスト・実機検証まで完了)**:

* `backend/app/ai/validators/schema_validator.py` — Version "1.6"を
  新設。`choice_field`(`options`: 1〜20件・重複禁止の文字列配列、
  `state_ref`必須)・`bar_chart`(`state_ref`は`record_list`型必須、
  `value_field`/`label_field`は`state_ref`が指す`record_schemas`の
  実在するFieldであること、`value_field`はtype=numberであることまで
  検査する——`record_list_view.display_fields`より踏み込んだ検査)の
  Schema検証・意味検証を追加。`input_types`(form_without_input警告
  用)へ`choice_field`を追加。
* `backend/tests/test_schema_validator_v1_6.py`(新規、21件)。
* `forge_ai/core/ir/forge_language_compiler.py` — `_build_field_inputs()`
  でCHOICE型Fieldを`choice_field`Widgetとして出力するよう変更(TD33の
  placeholder応急処置を削除)。新設`_build_bar_chart_widget()`で、
  数値Fieldを持つEntity(fishing_log/household_budget/reading_log/
  inventoryの4 Domain。habit_tracking/todo/diaryは数値Fieldを持たない
  ため対象外)の一覧直後に`bar_chart`を追加。`label_field`は
  CHOICE型Fieldを優先(無ければSTRING型)。出力Versionを"1.5"から
  "1.6"へ更新。
* `forge_ai/tests/test_forge_language_compiler.py` — 既存の
  Widget構成アサーション6件を新しい構成へ更新(削除ではなく、意図した
  設計変更への追従。特に「3 Domainで一貫した構成」という前提自体が
  崩れた——数値Fieldの有無でWidget構成が意図的に分岐するようになった
  ため、その旨をテストのdocstringに明記した)。新規テストクラス
  `TestForgeLanguageCompilerWidgetVocabularyExpansion`(12件、
  bar_chartの対象Domain判定・value_field/label_field選定・
  household_budgetの「グラフで見たい」要求への回帰テストを含む)。

**検証**: 全Pythonテスト995件(985既存+新規、TD34分のみで33件追加)が
回帰なしで通ることを確認。さらに`uvicorn`起動+HTTP経由で
`household_budget`(「収入や支出を記録して、月ごとの収支をグラフで
見たい」という、まさに例文そのもののプロンプト)・`fishing_log`・
`inventory`を再生成し、いずれも`version: "1.6"`・`choice_field`
(有効なoptions付き)・`bar_chart`(正しいvalue_field/label_field)が
生成されたJSONへ反映されていること、HTTP/Validatorレイヤーが正しく
配線されていることを確認した(`habit_tracking`は数値Fieldを持たない
ため`bar_chart`が付かないことも確認済み、意図通り)。

**訂正(2026-08-11、TD35調査で判明)**: 上記の検証は当初「実際に
Gemini APIで生成した」と記録していたが、これは不正確だった。
household_budget等IR経由のDomainは`ForgeLanguageCompiler`が完全に
決定的(`domain_category`文字列のみから、Gemini呼び出し無しで
Forge Document全体を組み立てる)であるため、この検証は
**HTTP/Validatorレイヤーの配線確認としては有効だが、Gemini接続
そのものの確認にはなっていなかった**。詳細・真のGemini接続確認は
TD35参照。

**未検証(正直な申告)**: Flutter/Dart側
(`frontend/lib/json_ui/schema/forge_document.dart`への
`ForgeChoiceFieldWidgetNode`/`ForgeBarChartWidgetNode`追加、新規
`frontend/lib/json_ui/widget_registry/widget_registry_v1_6.dart`の
`buildChoiceField`/`buildBarChart`)は、このセッションを通じて
一貫している既知の制限の通り、Flutter SDKがサンドボックスに存在せず
`flutter analyze`・実機/実ブラウザでの描画確認が一切できていない。
既存Widget実装(`widget_registry_v1_1.dart`等)と同じパターン
(`AnimatedBuilder`+`ForgeRuntimeState`の`getString`/`setString`/
`getRecordList`)を踏襲し、コードレビューレベルでの整合性は確認したが、
実際にFlutterでコンパイル・描画されることは未確認。
`DropdownButtonFormField`は`value`パラメータ(新しい`initialValue`
ではなく)を使い、`pubspec.yaml`のDart SDK下限('>=3.3.0')に対して
より広いFlutterバージョンで動くよう配慮した。`bar_chart`は
`CustomPainter`ではなく素のLayout Widget(`Row`/`FractionallySizedBox`)
で組んだ(検証できない環境では、実績のある標準Widgetの組み合わせの
方がレビューで正しさを判断しやすいという判断)。

**残る限界(意図的にスコープ外)**:

* `bar_chart`は集計を行わない(1 Record = 1本の棒のまま)。
  「月ごとの収支」のような期間集計は、なお実現していない
  (Phase1の最小実装、需要が実証されていない機能の先行実装を避ける
  という指示書の一貫した方針)。
* 画像Widget(`image`)は追加していない。ストレージ戦略
  (ローカルbase64 vs クラウド)の製品判断が必要な上、新規パッケージ
  依存(`image_picker`相当)が要るため、CEOと未協議のまま独断で
  スコープに含めることは避けた。

---

## TD35. `backend/.env`のGEMINI_API_KEYが、実`uvicorn`プロセスでは一度も読み込まれていなかった(2026-08-11発見・解消)

TD34の実機検証中に偶然発見。当初「一部プロンプトだけHTTP経由で謎の
エラーになる」という現象として記録したが(下記「発見時の記録」)、
CEOから「バグは徹底的に無くして」という指示を受けて再調査し、
根本原因を特定・修正した。

**発見時の記録(当初の症状)**: 「やることリストを作って」「TODOを
管理するアプリ」等の一部プロンプトが、HTTP `/api/v1/ai/generate`
経由では常に`GEMINI_API_KEY が設定されていません`というエラーで
失敗する一方、同じ`uvicorn`プロセスでhousehold_budget等の別の
プロンプトは正常に成功していた。直接呼び出し・`TestClient`経由では
再現しなかった。

**真の根本原因**: 2つの独立した事実の組み合わせだった。

1. **`backend/.env`を実際に読み込むコードがどこにも存在しなかった**。
   `GETTING_STARTED.md`・`backend/.env.example`・
   `providers.py`のdocコメントはいずれも「`GEMINI_API_KEY`は
   `backend/.env`に書く」と案内しており、`requirements.txt`にも
   `python-dotenv`が依存として入っていたが、**`load_dotenv()`を
   呼び出す箇所が実装のどこにも無かった**。つまり`.env`ファイルへの
   記述は、実際のアプリ起動時には一切反映されておらず、利用者が
   別途OSの環境変数として明示的に`export`した場合のみ動作する、
   ドキュメントの案内と実態が食い違った状態になっていた。
2. **household_budget等IR経由の7 Domainは、そもそもGeminiを一切
   呼び出さない設計だった**。`pipeline_orchestrator.py`は対象
   Domain(`SUPPORTED_DOMAIN_CATEGORIES`)を`IRGenerator`→
   `ForgeLanguageCompiler`という経路へ通すが、この経路は
   `domain_category`文字列だけから完全に決定的にForge Document
   全体を組み立てる、純粋関数の連なりであり(`forge_language_
   compiler.py`にProvider/bridge参照は一切無いことをソース確認
   済み)、Gemini呼び出しは1回も発生しない。一方「やることリスト」
   は`GENERIC`Domainへ分類され、Legacy `Compiler.compile()`
   (`forge_ai/core/compiler.py`)を経由するため、こちらは実際に
   `provider.complete()`を呼ぶ(`forge_ai/core/pipeline.py`の
   `_default_cognitive_dependencies()`が明記: 「`compiler`のみ、
   実際に`provider.complete()`を呼び出す」)。

つまり「household_budget等が成功していた」のは、Gemini接続が
正しく機能していたからではなく、**それらのDomainがそもそもGemini
を必要としない決定的な経路だったから**であり、`.env`が読み込まれて
いない状態でも「成功」して見えていた。「やることリスト」だけが
実際にGeminiを呼ぼうとして、読み込まれていないキーの不在に
初めて突き当たっていた、というのが真相だった。

**この発見が意味すること(正直な訂正)**: TD34の「実際に`uvicorn`+
実Gemini APIで`household_budget`・`fishing_log`・`inventory`を
再生成し確認した」という検証記述は、HTTP/Validatorレイヤーが
正しく配線されていることの確認としては有効だが、**Gemini接続そのものの
確認にはなっていなかった**(そもそも呼んでいないため)。TD34で
実際にGemini接続まで検証できていたのは、pytest内の
`httpx.MockTransport`による単体テストと、このTD35調査で独立して
確認した`TestClient`経由の実接続確認のみである。

**修正**: `backend/app/main.py`の先頭(他のimportより前)へ
`load_dotenv(os.path.join(_BACKEND_DIR, ".env"))`を追加した
(`_BACKEND_DIR`は同ファイルが既存のsys.path解決ロジックで使っている
絶対パスをそのまま再利用、cwdに依存しない)。`load_dotenv()`は既定で
既存のOS環境変数を上書きしない(`override=False`)ため、本番デプロイ
環境で実際の環境変数として`GEMINI_API_KEY`が設定されているケースには
影響しない。

**検証**: 新規テスト2件(`backend/tests/test_main_env_loading.py`)
を追加。1件はサブプロセスで`GEMINI_API_KEY`をOS環境変数からは明示的に
除去した状態から`app.main`をimportし、実際に`.env`の内容が
`os.environ`へ反映されることを確認する(pytestの既存モジュール
キャッシュに影響しないよう、独立したサブプロセスで検証している)。
もう1件は`.env`の中身に依存しない、ソースコードレベルの軽量な回帰
テスト。全996件(回帰なし)を確認した上で、実際に`uvicorn`を
**手動でのexport無しの、まっさらなシェルから**起動し、以前は
確実に失敗していた「やることリストを作って」「TODOを管理するアプリ」
の両方が、実際にGemini経由の(毎回異なる)バラエティのある文言
(例:「牛乳とパンを買う」「明日の会議資料を準備する」)で成功する
ことを実機確認した。

---

## TD36. Widget Registryが16種のまま(全Domainが単一画面へ全機能を詰め込む構成)だった → **date_field/tab_viewの2種を追加、v1.7(2026-08-11)**

FORGE-AI-QUALITY-001(2026-08-11)。CEO「次になになにとか、思ってますとか、
いらない。全て実装してくれ。確認もしなくて良い、ゴールは示している。
つくってくれ。」という明示的な指示を受けて、TD34直後の会話で
「次に効果が大きいのは画像対応と、複数画面・ナビゲーション」と述べた
候補について、確認を挟まず実装を進めた。

**調査した結果、「複数画面によるNavigator遷移」は安全に実装できないと
判断した(重要な発見)**: Flutter Runtime(`forge_renderer.dart`)を
読んだところ、`ForgeScreenView`は画面遷移(`Navigator.push`)の
たびに**独立した新しい`ForgeRuntimeState`**を生成する設計になっている
(`_ForgeScreenViewState.initState()`)。つまり「一覧画面」の`records`
Stateと「追加画面」の`records`Stateは、同じ`state_ref`名を使っていても
実行時には別インスタンスであり、追加画面で`add_record`しても一覧画面
には反映されない(画面をまたいだState共有・戻り値の受け渡し機構が
存在しないため)。この制約を無視して素朴に複数`screens`へ分割すると、
「追加したはずのデータが一覧に出てこない」という、今の単一画面構成
より明確に劣化した、壊れたアプリを生成してしまう。Flutter SDKが
無くこの種の実行時の不具合を検証する手段が無いため、**確実に正しく
動くと言い切れない実装を、確認を求めず進めるべきではない**と判断し、
複数`screens`によるCRUD分割は見送った(スコープを都合よく小さくした
のではなく、根拠のある技術的判断——真の複数画面CRUDには、Runtime側に
画面をまたいだState共有、または画面遷移の戻り値受け渡し機構を新設する
必要があり、これは別途のマイルストーンとして扱うべき規模)。

**代わりに実装したもの**: 新規パッケージ依存を追加せず、既存の
Runtime設計(単一画面・単一State)の制約の中で、確実に安全と判断
できる2種を追加した(Version "1.7"新設)。

* `date_field`: カレンダー選択(Flutter標準の`showDatePicker()`)。
  TD33の「text_fieldのplaceholderへ『日付(YYYY-MM-DD)』という
  書式ヒントを埋め込む」応急処置を、choice_field(TD34)と同じ理由で
  専用Widgetへ置き換えた。誤った書式・実在しない日付の入力自体を
  構造的に防ぐ。
* `tab_view`: 「追加」「一覧」「編集」を`divider`区切りで縦に
  積み上げていた単一画面の構成を、タブ切り替え構成へ変更した。
  **`TabBarView`(内部で`PageView`を使う)は使っていない**——
  `ForgeScreenView`が画面全体を`SingleChildScrollView`で包んでおり、
  その内部では高さが無制限になるため、`TabBarView`をそのまま置くと
  典型的な「unbounded height」のレイアウトエラーになる(この種の
  実行時エラーはFlutter SDKが無い環境では検証できない)。代わりに、
  選択中のタブ1つの中身だけをその場に描画する自作の`_TabViewSwitcher`
  (素の`StatefulWidget`+`int`状態のみ、`TabController`/`vsync`すら
  使わない、最も検証しやすい構成)で実装した。

**変更ファイル(Python側、テスト・実機検証まで完了)**:

* `backend/app/ai/validators/schema_validator.py` — Version "1.7"を
  新設。`date_field`(`state_ref`/`label`必須、`placeholder`任意)・
  `tab_view`(`tab_titles`と`children`が同じ要素数の配列であること、
  各`children[i]`を再帰的にWidget Schema検証)を追加。`tab_view`を
  `CONTAINER_WIDGET_TYPES`へ加えることで、既存の`_walk_widgets`・
  `_widget_depth`(再帰探索・ネスト深度・Widget数上限のカウント)を
  そのまま再利用できるようにした——column/row/card/formと同じ
  「フラットなchildren配列を持つコンテナ」として設計したことによる。
* `backend/tests/test_schema_validator_v1_7.py`(新規、19件)。
* `forge_ai/core/ir/forge_language_compiler.py` — `_build_field_inputs()`
  でDATE型Fieldを`date_field`Widgetとして出力するよう変更(TD33の
  placeholder応急処置を削除)。`_compile_single_screen()`を、
  `divider`区切りの単一列から`tab_view`(3タブ)構成へ全面的に
  書き換えた。出力Versionを"1.6"から"1.7"へ更新。
* `forge_ai/tests/test_forge_language_compiler.py` — tab_view導入に
  伴い、Widget構成を直接検証していた既存テスト十数件を新しい構成
  (タブごとの中身)へ更新した(削除ではなく、意図した設計変更への
  追従。木構造のどこかにWidgetがあるかを調べる`_all_widgets`等の
  テストヘルパーを新設し、以後のテストが特定の階層構造に過度に
  依存しないようにした)。新規テストクラス
  `TestForgeLanguageCompilerV1_7WidgetVocabularyExpansion`(10件)。

**検証**: 全Pythonテスト1024件(回帰なし)を確認した上で、`uvicorn`
起動+HTTP経由で`household_budget`・`fishing_log`・`reading_log`
(誤分類でdiaryとして生成された、既知の別問題)を再生成し、
いずれも`version: "1.7"`・`tab_view`(3タブ、正しいtab_titles)・
`date_field`(正しいstate_ref/label)が実際に反映されていることを
確認した。

**未検証(正直な申告)**: Flutter/Dart側
(`forge_document.dart`への`ForgeDateFieldWidgetNode`/
`ForgeTabViewWidgetNode`追加、`forge_runtime_state.dart`の
`_findById`へのtab_view対応、新規
`frontend/lib/json_ui/widget_registry/widget_registry_v1_7.dart`の
`buildDateField`/`buildTabView`)は、この時点では「Flutter SDK不在の
ため未検証」と記録していたが、**実際には誤りだった**——TD37で
Flutter SDKを実際に取得・実行できることが判明し、検証した結果、
`typeNameOf()`の網羅的switch式にこの節で追加した4種のケースが
1つも登録されておらず、choice_field/bar_chart/date_field/tab_viewの
いずれも一度もRuntime上で描画できない状態だった(重大な実バグ、
TD37参照)。修正・実際の`flutter test`での動作確認込みで解消済み。
`tab_view`の実装方針(`TabBarView`を避けた理由)は上記の通り、
レイアウトエラーを避けるための意図的な設計判断であり、当てずっぽうでは
なかったことも実機で確認できた。

**残る限界(意図的にスコープ外、根拠つき)**:

* 真の意味での複数画面CRUD(一覧画面と追加/編集画面を独立した
  `screens`として行き来する)は実装していない。上記の通り、
  Runtime側に画面をまたいだState共有機構が無い限り、安全に実装
  できないため。
* 画像Widget(`image`)は今回も追加していない。ストレージ戦略
  (ローカルbase64 vs クラウド)の製品判断が必要な上、新規パッケージ
  依存(`image_picker`相当)が要る。加えて、現在のCurated Domain
  Library(7 Domain)には画像を持つFieldが1つも無く、追加しても
  使い道が無い(`child_growth`等、legacy Domainには"photo"概念が
  あるが、IR経由の対象外)。
* マップ・スライダーは未着手(新規パッケージ依存または高い実装
  リスクのため、確認無しで進めるべきではないと判断)。

---

## TD37. 「Flutter SDK不在のため未検証」という制約は、実は物理的制約ではなかった → **解消(2026-08-11)、検証した結果、4種のWidgetが一度も描画できない重大なバグを発見・修正**

FORGE-AI-QUALITY-001。CEO「出し惜しみせず、完璧を求めてくれ」という
指示を受け、これまで数多くのTD項目・報告で前提としてきた「Claudeの
サンドボックスにFlutter SDKが無いため未検証」という制約を、改めて
自分で調査し直した。

**発見**: `flutter.dev`・`github.com`・`pub.dartlang.org`はこの環境の
プロキシに拒否される(403)が、**`storage.googleapis.com`
(Flutter公式のリリース配布元)と`pub.dev`(パッケージ配布元)は
到達可能**だった。実際にFlutter SDK(stable、3.44.9、1.5GB)を
ダウンロード・sha256照合・展開し、`flutter pub get`(105個の依存
パッケージ全て解決)・`flutter analyze`・`flutter test`をすべて
実際に実行できた。つまりこの制約は「環境の物理的な制約」ではなく、
「誰も実際にダウンロードを試みていなかった」だけだった。セットアップ
手順は`KNOWN_ISSUES.md`に記録した(SDK自体はスクラッチパッド配下に
置いたため、セッションをまたいで永続しない——次回セッションでまた
同じ手順が必要)。

**実際に検証した結果、見つかった実バグ(最重要)**: `flutter analyze`を
実行したところ、`frontend/lib/json_ui/widget_registry/widget_registry_
core.dart`の`typeNameOf()`(`ForgeWidgetNode`のsealed class全派生型を
網羅する`switch`式で、`buildForgeWidget()`がRegistryから実際のBuilder
関数を引くために使う、Widget描画の入口そのもの)が
`non_exhaustive_switch_expression`というコンパイルエラーになっていた。
このセッションでTD34・TD36として追加した4種類のWidget
(`choice_field`・`bar_chart`・`date_field`・`tab_view`)を、
`ForgeWidgetNode`のサブクラスとしては追加していたが、**この`switch`式
へケースを追加し忘れていた**。

これは単なるコンパイルエラーというだけでなく、**実行時の意味としては
「この4種類のWidgetは、Forge Language文書としては正しく生成・
Validator合格するのに、Flutter Runtime側では一度も実際に描画できない
(型判定の時点で例外になる)」という、TD34・TD36の成果そのものを
無効化しかねない重大な実バグだった**。Backend側のPythonテスト
(schema_validator・forge_language_compiler)がいずれも「正しいJSONを
生成できているか」だけを検証しており、「そのJSONが実際にFlutterで
描画できるか」は検証範囲外だったため、pytestが990件超通っていても
この不具合には一切気づけなかった——これはPython側の検証とDart側の
検証が別の層を担っているという、このプロジェクトの構造上避けられない
限界であり、実際にFlutter側を動かすまで発見しようが無かった。

`typeNameOf()`に4件のケースを追加して修正した。同じ理由で
非網羅switchになっていたテスト専用の複製
(`test/features/app_generation/data/datasources/
mock_generator_renderer_contract_test.dart`の`_typeNameOf()`)も
同様に修正した。

**ついでに見つかった、このセッションとは無関係な既存バグ3件**
(実際に`flutter analyze`/`flutter test`を全体に対して実行した結果、
副次的に発見):

1. `frontend/lib/features/app_library/data/repositories/shared_
   preferences_app_library_repository.dart`の`loadRuntimeState()`
   (TD30、2026-08-11の別の作業で追加したコード)に型エラー
   (`dynamic`を`String`キーへ代入)があった。`Map<String,
   dynamic>.from()`で明示的に絞り込むよう修正。
2. `test/e2e/survey_form_validation_flow_test.dart`・
   `test/e2e/kids_checklist_generation_flow_test.dart`の2件が、
   `find.widgetWithText(ElevatedButton, 'アプリを開く')`という
   Finderを使っていたが、完成画面の「アプリを開く」ボタンは
   FORGE-UI-REFRESH(2026-08-10)で`DecoratedBox`+`InkWell`による
   グラデーションCTAへ再デザインされており、もう`ElevatedButton`
   ではなかった(このリデザイン後、一度も`flutter test`を実行できて
   いなかったため気づかれていなかった)。`find.text(...)`ベースの、
   具体的なWidget型に依存しないFinderへ修正。
3. `test/features/app_generation/presentation/screens/home_screen_
   test.dart`の1件が、Bottom Sheet内の5番目の例文をタップする際、
   既定のテストウィンドウサイズ(800×600)ではスクロールされておらず
   画面外でヒットテストに失敗していた。`tester.ensureVisible()`を
   追加。

**検証**: 全Dartテスト(Unit・Widget・E2E含め435件)が実際に通ることを
確認した(このセッションを通じて初めて到達した状態)。加えて、
TD34・TD36で追加した4種のWidgetそれぞれについて、新規Widget Test
(`test/json_ui/widget_registry/v1_6_v1_7_widget_vocabulary_expansion_
test.dart`、9件)を実際の`ForgeDocumentView`経由で描画・操作する形で
新設し、以下を実機(テスト上のRendererだが、初めてFlutter Engineが
実際に描画・レイアウトした結果)で確認した:

* `choice_field`: ドロップダウンとして描画され、選択→送信→Recordへの
  反映まで一連で動作する。
* `date_field`: タップすると実際に`DatePickerDialog`(Material標準)が
  開き、日付を選ぶとYYYY-MM-DD形式でstateへ反映される。
* `tab_view`: タブタイトルが表示され、選択中のタブの中身だけが描画
  される(TabBarViewのような「全タブ保持」ではないこと、設計方針
  通りに動いていることの確認)。タップで正しく切り替わる。
* `bar_chart`: Recordが無い間は何も描画せず(クラッシュしない)、
  Record追加後はtitle・ラベル・値が表示される。

Python側は全1024件、Dart側は全435件、合計1459件のテストが通ることを
このセッションの最終状態として確認した。

**この発見が示す教訓**: 「環境的な制約」だと思い込んでいたものは、
実際に一度も検証せずに数セッションにわたって前提として扱われ続けて
いた。CEOの「出し惜しみせず、完璧を求めてくれ」という指示が無ければ、
`choice_field`/`bar_chart`/`date_field`/`tab_view`という、このセッション
の主要な成果物4つが実際には一度も動かないまま「実装完了」として
報告され続けていた可能性が高い。今後、「サンドボックスでは検証
できない」という判断を下す前に、実際に到達性を確認すること
(`curl`で疎通確認する等)を徹底する。

## TD38. Widget Registryが18種のまま(範囲指定の数値入力が無く、`text_field`へ数字を手打ちさせるしかなかった) → **sliderの1種を追加、v1.8(2026-08-11)**

CEO「要は、一気に検証を進めたい。なので、壊れてる?って機能でもどんどん
追加してくれ。あとでなおす。」という明示的な指示を受けて着手した。
TD34(v1.6)・TD36(v1.7)と同じWidget Vocabulary Expansionの第3弾。

reading_logの「評価(5段階)」のような、上限・下限が決まった数値入力を
これまで`text_field`(自由入力+`pattern`バリデーション)で表現していた
——CEOの実機での入力体験としては、キーボードで"3"と打つより
スライダーを操作する方が明らかに自然な操作感である。

**実装内容**:

* `Field`(`ir_types.py`)へ`min_value`/`max_value`(両方`None`でない
  場合のみ意味を持つ)を追加。`ir_generator.py`の`_build_field()`が、
  両方設定されたNUMBER型Fieldに対しては数値パターンバリデーション
  ヒントを付けない(sliderの構造そのものが範囲外入力を防ぐため、
  choice_field/date_fieldと同じ設計方針)。
* reading_logの`rating`Fieldへ`min_value=1, max_value=5`を設定
  (Curated Domain Libraryが最初から持っていた「評価(5段階)」という
  ラベルと矛盾しない、根拠のある具体値)。
* `schema_validator.py`: `slider`Widget用のスキーマ検証を追加
  (`label`必須、`state_ref`が"number"型stateを指すこと、`min`/`max`が
  数値であること、`min < max`であること——bool値がPythonでは`int`の
  サブクラスであるため`min`/`max`に混入しないよう`isinstance(v, bool)`
  で明示的に弾く回帰テストも追加)。`backend/tests/
  test_schema_validator_v1_8.py`(14件)。
* `forge_language_compiler.py`の`_build_field_inputs()`へ、
  「NUMBER型かつmin_value/max_valueが両方設定されている」場合の
  分岐を追加。既存の`"number"`型state(v1.2で導入済みだが、これまで
  消費するWidgetが1つも無かった)をそのまま使い、新しいstate型は
  追加しない。`forge_ai/tests/test_forge_language_compiler.py`へ
  `TestForgeLanguageCompilerV1_8WidgetVocabularyExpansion`(6件)を追加。
* Dart側: `ForgeSliderWidgetNode`(`forge_document.dart`)、
  `buildSlider()`(`widget_registry_v1_8.dart`、Flutter標準の`Slider`、
  新規パッケージ依存なし)、`ForgeRuntimeState.setNumber()`
  (既存の`setString`/`setBoolean`と対称的な新規API)。

**TD37の教訓を踏まえた確認**: `widget_registry_core.dart`の
`typeNameOf()`(sealed classの網羅的switch式)へ、`ForgeSliderWidgetNode`
のクラス定義を書いた**直後**に対応するcaseを追加し、同じ理由で
複製を持つ`test/features/app_generation/data/datasources/
mock_generator_renderer_contract_test.dart`の`_typeNameOf()`・
`kRegisteredWidgetTypes`も同時に更新した。`flutter analyze`で
0エラーであることを確認済み(TD37のような「4種類とも一度も描画
できない」の再発が無いことの直接確認)。

新規Widget Test(`test/json_ui/widget_registry/
v1_8_widget_vocabulary_expansion_test.dart`、4件)で、実際に
`ForgeDocumentView`経由でsliderを描画し、ドラッグ操作でstateが
更新されること・フォーム送信でRecordへ反映されることを確認した。
Python側(`forge_ai/tests/test_forge_language_compiler.py`の
`test_slider_output_passes_the_real_backend_schema_validator`)でも、
実バックエンドの`validate_forge_document()`が生成物を受理することを
確認済み。

**既知の未解決課題(CEOから明示的に「あとでなおす」の許可を得ている軽微な見た目上の課題)**:
`ForgeRecordValidator.validate()`(`forge_record_validator.dart`)が、
Record保存時に値を必ず一度`.toString()`してから
`ForgeFieldValueParser.parse()`で再解析する実装になっているため、
sliderのdouble値(例: `5.0`)が文字列`"5.0"`を経由して再びdoubleへ
戻る(値そのものは正しくラウンドトリップするが、整数値であっても
`record_list_view`/`bar_chart`の表示が常に「5.0」のように末尾へ
".0"が付く)。機能的な破損ではなく表示上の見た目の課題のため、
このセッションでは修正を見送った。

## TD39. Curated Domain Library 7 Domainのうち、`todo`・`reading_log`の2つは、実機の分類パイプラインからは構造的に到達不可能だった(2026-08-11発見、未解消)

sliderのライブ検証(実際に`uvicorn`+実Gemini経由で`reading_log`
アプリを生成し、生成物にsliderが含まれることを確認する)を行おうと
した際に発見した、TD37と同種の「Python側テストでは検出できない、
層をまたいだ実バグ」。

`forge_ai/core/orchestration/pipeline_orchestrator.py`は、以下の1行で
IR経路(`IRGenerator`/`ForgeLanguageCompiler`、決定的生成)を使うかどうかを
判定する:

```python
domain_category_value = context.domain_classification.primary_domain.category.value
if domain_category_value in SUPPORTED_DOMAIN_CATEGORIES:
```

`SUPPORTED_DOMAIN_CATEGORIES`(`ir_generator.py`)は
`{"fishing_log", "household_budget", "habit_tracking", "todo",
"reading_log", "inventory", "diary"}`という7つの文字列だが、
`domain_category_value`の実体は`DomainCategory`(`domain_model.py`)
というEnumの`.value`であり、そのEnumには**`"todo"`にも
`"reading_log"`にも一致するメンバーが1つも存在しない**
(近い名前の`TASK_MANAGEMENT = "task_management"`はあるが、
"task_management" != "todo")。

つまり、`todo`/`reading_log`は、`IRGenerator`(`_ENTITY_DEFINITIONS`)
・`ForgeLanguageCompiler`・専用のPythonテスト群一式が存在し、
「Domain定義としては完成している」のに、**実際のプロンプト分類が
これらのカテゴリ値を返すことは構造的にあり得ない**ため、実機の
`/api/v1/ai/generate`を通じて生成されることが原理的に無い
(`domain_category`を明示的に渡すテスト・スクリプトからしか到達
できない)。

**実機確認**:
* 「読んだ本を記録して評価をつけたい」→ `diary`ドメインへ分類され、
  reading_log固有の`book_record`ではなく`diary_entry`スキーマが
  使われた(sliderも生成されない)。
* 「やることリストを管理したい」→ `record_schemas`を持たない
  (IR経路を通っていない=レガシー`Compiler`経路にフォールバック
  している)出力になった。

**影響**: v1.8で追加したslider Widgetの、Curated Domain Library内での
唯一のトリガー(reading_logの`rating`Field)が、この`reading_log`
Domain自体に実機到達できないため、**現状sliderは実機の生成パイプライン
からは一度も出力され得ない**(直接`IRGenerator().generate(plan,
domain_category="reading_log")`のようにDomain名を明示すれば、
Python側・Dart側とも正しく動作することは確認済み——TD38参照)。

**未解消の理由**: sliderの実装自体は指示された範囲(Widget Vocabulary
Expansion第3弾)であり、`todo`/`reading_log`を実機到達可能にするには
`DomainCategory`Enumへの新規メンバー追加+分類器(`core/understanding/`
配下のキーワード辞書等)への語彙追加という、別の作業範囲の変更が
必要になる。CEOの「あとでなおす」という許可の範囲内と判断し、この
セッションでは発見・記録のみに留めた。

**推奨される次の一手**: `DomainCategory`へ`READING_LOG = "reading_log"`・
`TODO = "todo"`(または`TASK_MANAGEMENT`を`SUPPORTED_DOMAIN_CATEGORIES`
側で`"todo"`に正規化する)を追加し、対応する分類キーワード
(「読書」「読了」「積読」/「やること」「タスク」等)を分類器へ
追加する。分類器の構造次第では影響範囲が広くなる可能性があるため、
着手前に`core/understanding/`配下の分類ロジックを読み込むこと。

## TD40. Forming Operation(UPDATE、生成後に会話で「育てる」)は設計のみで未実装 → **解消(2026-08-11、同日中)**

FORGE-PRODUCT-VISION-002(製品思想更新)対応。CEO指示書が要求する
「Held状態から会話に戻り、既存の道具を更新する」体験の中核だが、
バックエンドに一切存在しない(監査で確認、詳細は`docs/spec/
FORGE_PRODUCT_VISION_002_CONVERSATIONAL_ARCHITECTURE.md` A.4)。

**未実装の理由(技術的リスクの正直な申告)**: UPDATE操作は「既存の
Forge Document全体+変更要求」を入力に、更新済みのForge Document全体を
出力する必要がある。Forge DocumentのWidget木は`children`を持つ再帰的な
構造(`ForgeWidgetNode`のsealed class)であり、`GeminiProvider.
complete_structured()`が使う`responseSchema`(OpenAPI Schemaのサブセット、
`$ref`による自己参照未対応)で、無制限に再帰するWidget木を直接構造化
出力させられるかは**未検証**である。検証を経ずに実装だけ進めると、
TD37(4種のWidgetが一度も描画できていなかった)と同種の「実は一度も
動いていない機能」を生む危険が高いと判断し、実装を見送った。

設計候補2案(詳細はdesign doc B.4):
1. (推奨)Forge Document全体を書き換えさせず、`add_field`・
   `reorder_records`・`add_widget`・`change_property`という小さな
   Operationの集合(DSL)をLLMに選ばせる。DSLは非再帰的なフラット
   構造なので`responseSchema`との相性がよい。
2. `responseSchema`を使わず、Document全体を自由出力(JSON文字列+
   `json.loads()`)させる。Schema制約を失う代わりに再帰の制約から
   解放される。

いずれも「LLMに既存の構造化データを渡し、修正済みデータを受け取る」
という、このリポジトリに前例のない往復(`repair_engine.py`の`_try_fix()`
はLLMの応答を実際には使っていない決定的修正のみ、A.6参照)を新規実装
することになるため、次のセッションで小さく検証しながら進めることを
推奨する。

**追記(2026-08-11、同日中に解消)**: CEO「実装できたの？できるまで
やって」という指示を受け、上記「未検証」を実際に検証した。

**技術検証の結果**: `responseSchema`へ「type: object」とだけ渡して
`properties`を書かない形(再帰的なWidget木の型を事前に確定できない
ケース)を実際にGemini APIへ送ったところ、**その部分は空オブジェクト
`{}`で返ってくる**ことを実機で確認した(既存の構造化データを丸ごと
失う、深刻な失敗モード。懸念は正しかった)。一方、`responseSchema`を
一切送らず、`responseMimeType: application/json`のみでフリーフォームの
JSON生成を要求したところ、既存の再帰的な構造を正しく維持しながら
新しい要素を追加できることも実機で確認した——上記の設計候補2案のうち
「案2」を採用した。

**実装内容**: `GeminiProvider.complete_structured()`
(`backend/app/ai/foundation/providers.py`)を、`response_schema`が
空dict(`{}`)の場合に`responseSchema`自体を省略する形へ拡張(既存の
非空schema呼び出しの挙動は完全に無変更、回帰テストで確認済み)。
新規`backend/app/ai/runtime/forge_operation.py`の
`ForgeOperationEngine.apply_update()`が、既存Forge Document+変更要求を
受け取り、Validator不合格時は1回だけ「直前のエラー内容」をプロンプトへ
追記して再生成する(`MAX_UPDATE_ATTEMPTS = 2`、`prompt_pipeline.py`の
`MAX_REPAIR_ATTEMPTS`と同じ「無限リトライ禁止」の思想)。新規
`POST /api/v1/ai/update`エンドポイント追加。

**実機確認**: `uvicorn`+実Geminiで、`/converse`が生成した3件の
買い物チェックリスト(牛乳・食パン・卵)に対し、「よく買うものを
上に置きたい。カテゴリ分けもしたい。」という変更要求を`/update`へ
送った。1回目の応答はValidator不合格だったが、2回目(Repair往復1回)で
Validator合格した更新済みJSONが返り、既存3件のitemを正しく
`frequent_items`/`food_items`/`daily_items`という3つのchecklist
stateへ分割・再配置し、対応する3つの`add`ボタン(それぞれ異なる
`target_state_ref`)まで生成していることを確認した。指示書6・16・18章の
「よく買うものを上に置きたい」「カテゴリ分けしたい」という例そのものが、
実際に動作することを確認した。

新規Python 9件(`test_forge_operation.py`)・`GeminiProvider`の回帰
テスト2件(`test_gemini_provider.py`)追加。既存backend全テストと合わせ
633件、全てgreen。

## TD41. ConversationStoreはプロセス内メモリのみ(`ConfirmationStore`と同じ既知の制限、2026-08-11新設)

FORGE-PRODUCT-VISION-002対応で新設した`backend/app/ai/runtime/
conversation_store.py`は、`confirmation_store.py`と全く同じ設計
(プロセス内メモリ・TTL 30分・最大3ターン)を踏襲した。サーバー
再起動やマルチプロセス/マルチワーカー構成では会話セッションが失われる。
`confirmation_store.py`が既に同じ制限をTECH_DEBTとして記録済みであり、
新規の問題ではなく既存の設計方針をそのまま継承しただけである。将来
複数ワーカーで運用する場合、両Storeをまとめて Redis等の外部ストアへ
置き換えることを検討する。

## TD42. `/converse`と`/update`を結線(2026-08-11、同日中)、その過程で発見・修正した実バグ3件

CEO「自由度はどれくらいなのだろう？今最新で与えている情報を優先に
してほしい」という指示を受け、report.mdで「次の一手」としていた
「`/converse`内で新しい問題と既存ツールへの変更要求を判定する」を
実装した。

**実装**: `ConversationEngine.step()`が`has_existing_tool: bool`引数を
受け取るようになった(既定`False`、後方互換)。`True`の場合のみ
`next_action="update"`を選びうる(design doc B.3と同じ決定的上書き
ルール: `has_existing_tool=False`なのに"update"と自己申告してきても
鵜呑みにせずBUILDへ倒す)。`ConverseRequest`へ`current_document`
(任意)を追加、渡された場合のみHeld画面からの再開として扱う。
`/converse`ルーターは`update`と判定された場合、`ForgeOperationEngine.
apply_update()`(TD40)へそのまま委譲する。

**実機確認の過程で発見・修正した実バグ3件**(いずれもこのTD42の作業
自体が原因ではなく、実際にHTTPを叩いて初めて表面化した既存の穴):

1. **`/converse`のProvider呼び出しに例外処理が一切無かった**:
   `ConversationEngine(provider).step()`の呼び出しが、`PromptPipeline.
   run()`(既存の`/generate`系、内部で例外を`ProviderError`/
   `PlanningError`へ変換済み)や`ForgeOperationEngine.apply_update()`
   (内部で例外を捕捉し`UpdateResult(success=False, ...)`を返す)とは
   異なり、**一切の例外処理を経由せず素通りしていた**。実機で
   Gemini APIのレート制限(429)に遭遇したところ、`GeminiProvider`が
   用意した親切な日本語メッセージ(TD31対応)が失われ、汎用の
   `unhandled_exception_handler`(「予期しないエラーが発生しました」)
   まで落ちることを確認した。`app/routers/ai.py`の`converse()`で
   `try/except`を追加し、`ProviderError`(429/"利用上限"を含む
   メッセージなら`sub_reason="rate_limited"`)へ変換するよう修正した。
2. **`MockLLMAdapter`が JSON Schemaの`"number"`型を処理していなかった**:
   `_synthesize_field()`は`"array"`/`"integer"`/`"object"`のみ分岐して
   おり、`"number"`(浮動小数点)は素通りしてデフォルトの文字列分岐
   (`"mock_result"`)へ落ちていた。`ConversationEngine`の`NeedModel.
   confidence`フィールド(`{"type": "number"}`)がこれに該当し、
   呼び出し側の`float(raw.get("confidence", 0.0) or 0.0)`が
   `float("mock_result")`で`ValueError`になる実クラッシュを、
   `TestClient`経由の実機テストで発見した。`"number"`分岐を追加し
   `0.0`を返すよう修正(`"integer"`→`0`と対称的)。
3. **新規テストファイルが、他の無関係なテストを壊すテスト分離バグ**:
   `app.main`はプロセス内で1度しかimportされない(`sys.modules`
   キャッシュ)ため、Feature Flag Router(workspace/folder)の登録可否は
   「プロセスで最初に`app.main`をimportした時点の環境変数」で確定
   する。`test_workspace_router.py`・`test_folder_router.py`はそれぞれ
   自分のFlagを`os.environ.setdefault()`してからimportするが、新規
   `test_converse_and_update_http.py`がFlagを一切設定せず`app.main`を
   importしていたため、`unittest discover`のアルファベット順によっては
   このファイルが先に走り、後続の`test_workspace_router.py`等の
   `setdefault`が手遅れになる(Router自体が未登録のまま確定し、
   期待していた401が404になる)ことをフルスイート実行で発見した。
   同じ防御パターン(両Flagの`setdefault`)を新規ファイルへも追加して
   修正した。

**実機確認**: 修正後のコードで`uvicorn`を再起動し、`/converse`
(`current_document`付き、"よく買うものを上に置きたい。カテゴリ分けも
したい。")を再送したところ、エラー変換自体は正しく`provider_error`/
`rate_limited`/`retryable=true`へ分類されることを確認した——ただし
Gemini無料枠の**日次クォータ**そのものをこのセッションの検証作業
(このドキュメント全体を通じた多数のライブ呼び出し)で使い切っており
(`「You exceeded your current quota」`という文言が数分間の再試行を
挟んでも変化しなかったため、単なる分単位のレート制限ではなく日次上限と
判断)、「実際にGeminiがupdateを選ぶ」ところまでのライブE2E確認は
このセッション内では完了できなかった。

**代替の検証**: (a) 分岐ロジック自体は`test_conversation_engine.py`の
`TestConversationEngineUpdate`(4件、has_existing_tool=True/Falseの
両方を実際のFakeProviderで検証)で確認済み。(b)
`ForgeOperationEngine.apply_update()`自体は、TD40で既にライブGemini
経由でEnd-to-Endの成功(買い物リストのカテゴリ分割)を確認済みであり、
`/converse`から呼ばれる経路は同じ実装をそのまま再利用している。(c)
新規Python 20件(`test_converse_and_update_http.py`4件・
`test_mock_llm_adapter.py`4件・`test_conversation_engine.py`追加4件・
既存修正分)、既存backend全テストと合わせ645件、全てgreen。

正直な評価として、「実際のGeminiが会話の中で自発的にupdateを選ぶ」
という最後の1点だけは、クォータ回復後(翌日以降)に再確認することを
推奨する。

## TD43. Frontend統合: Home画面・Held画面を`/converse`・`/update`へ接続(2026-08-11、同日中)

CEO「自由度はどれくらいなのだろう？今最新で与えている情報を優先に
してほしい」という指示を受け、report.mdで「CEO確認が必要」として
保留していたフロントエンド統合(Home画面の文言変更、Inspiration
Cardsの遷移先変更)を、実際には指示書28章の確認事項リストのどれにも
当てはまらない可逆な変更だと判断し直し、実装した。

**実装内容**:
* `HomeScreen`: 見出しを「アイデアを入力するだけで、あなただけの
  アプリに。」から「最近、ちょっと困ってることある？」へ(design doc
  C.1、Space)。`_onSubmit()`の遷移先を`GenerationFlowScreen`(単発
  生成、無変更のまま残す)から新設`ConversationFlowScreen`
  (`/converse`、複数ターンの会話)へ変更。
* `GeneratedAppHostShell`: `StatelessWidget`→`StatefulWidget`化。
  `onDocumentUpdated`を渡した呼び出し元にのみ「ここを変える」ボタンを
  表示し、タップで`ConversationFlowScreen`(`currentDocument`付き、
  UPDATE専用モード)を開く。Home(保存済みアプリを開く経路)・My Apps
  画面の両方へ配線した(Held→Forming→Heldの入口、design doc C章)。
* 新規`ConversationFlowScreen`: ASK/BUILD/UPDATE/フォールバック
  confirmationの4分岐を1画面で扱う。既存の`GenerationFlowScreen`は
  無変更のまま残している(削除しない、可逆性優先)。
* 共有パーサー`generation_result_parsing.dart`を新設し、`Api
  AppGenerationRepository`・新設`ApiConversationRepository`の両方が
  同じ`GenerateResultDTO`解析ロジックを再利用する(重複させない)。

**Widget Testで発見・修正した実バグ(重要)**: `ConversationFlowScreen`が
`ConversationTurnRequest`(Riverpod `.family`のキャッシュキー)を
`build()`内で`_sessionId`(ASKレスポンス処理の副作用としてsetStateする
値)から毎回組み立て直していたため、ASKレスポンスを受け取った直後の
再描画で、**ユーザーがまだ何も送っていないのに、同じ発話でもう一度
`/converse`を呼んでしまう**(`sessionId`だけが変わり`==`が不一致に
なるため、Riverpodが新しいリクエストとして扱う)実バグを、Widget Test
実行で発見した。この余分な呼び出しの結果は`_handledCurrentTurn`
フラグにより画面には反映されないため、目視や手動テストでは気づけない
種類のバグだった——実際のGemini会話であれば、無駄な1往復を消費し、
Backend側の会話履歴(`ConversationStore`)にも本来無いはずの重複した
ユーザー発話が残ってしまう。

**修正**: `_sessionId`から毎回`ConversationTurnRequest`を組み立て直す
のをやめ、`_currentRequest`という「その時点で確定したリクエストの
スナップショット」を`_sendReply()`(ユーザーが実際に送信した瞬間)と
`initState()`でのみ更新する方式へ変更した。ASKレスポンス処理で
`_sessionId`をsetStateしても、次にユーザーが送信するまで`_current
Request`は変化しない。

**もう1つ、Widget Testで発見した実装上の注意点**: `enterText()`の
直後に同じフレームで`tap()`すると、テキスト変更が`_ReplyBar`の
送信ボタンの有効状態(`canSend`)へ反映されないまま`tap()`が空振り
することがあった(既存のE2Eテストにある「RotationTransitionの間は
pumpAndSettle禁止」と同種の、タイミング依存の落とし穴)。`enterText()`
と`tap()`の間に`pump()`を1回挟むことで解消した。

**テスト**: 新規Dart 8件(`api_conversation_repository_test.dart`6件・
`conversation_flow_screen_test.dart`2件)、既存E2E/Widget Testの修正
(Home画面の遷移先変更・文言変更に追従、`ensureVisible()`の適用漏れ
修正)を含め、Dart側全447件がgreen。`flutter analyze`は0エラー。

## TD44. `design_tokens`(配色テーマ)がCurated Domain Library(5 Domain)にしか適用されておらず、生成されるアプリの大半がFlutter既定のMaterial配色のままだった → **解消(2026-08-12)**

CEO「widgetの充実が良いのか、生成できるAIが良いのか、実際に作られる
アプリのクオリティをアプリストアにあるようなレベルにするにはどう
すればいいか、めちゃくちゃ考えて、多次元レベルで色々な角度から
疑って、これだ！って答えが出たら実装してみて」という指示への対応。

**分析(指示された「多次元での検討」の結果)**: Widget語彙(19種、
v1.8で拡充済み)・生成AIの賢さ(プロンプト・分類ロジック)・視覚的
デザイン品質、の3方向を比較した。

* Widget語彙は既に19種あり、「機能が足りない」ことが目に見える
  不具合として観測されていない(むしろTD39のように、既存Widgetを
  使う経路にすら到達できないDomainがある方が問題)。
* 生成AIの賢さ(Gemini呼び出しの精度)は本質的にセッションをまたいで
  改善し続けるべき対象だが、単一のコード変更で「これだ」と言える
  性質のものではない(効果測定にABテスト相当の運用が要る)。
* 一方、`QualityEngine`(`forge_ai/quality/quality_engine.py`)・
  `DesignCritic`(`forge_ai/core/critic/design_critic.py`)を実際に
  読むと、6軸+10軸のいずれも**構造的な自己無矛盾性**(画面がある、
  IDが重複しない、Actionがある等)しか評価しておらず、**視覚的な
  仕上がり**(配色・角丸・余白の一貫性)は一度も評価対象になって
  いなかった。さらに実装(`forge_ai/core/compiler.py`・
  `forge_ai/core/ir/forge_language_compiler.py`)を読むと、
  `design_tokens`という仕組み自体はFORGE v1.0 Product Quality
  Sprint1で**既に実装・Flutter Runtime側の描画対応も完了済み**
  だったが、`ForgeLanguageCompiler`(Curated Domain Library、
  実機到達可能なのはfishing_log/household_budget/habit_tracking/
  inventory/diaryの5 Domainのみ、TD39参照)だけが使っており、
  legacy`Compiler`(それ以外の10 Domain: shopping・hospital・
  attendance・task_management・survey・schedule・child_growth・
  study・travel・generic——実際に生成されるアプリの大半)は
  `design_tokens`を一度も出力していなかった。つまり「アプリストア
  レベルの品質」に一番効くはずの、**既に作った資産(4種のプリセット
  配色)を、対象の大半に配れていなかった**というのが実際の状況
  だった(新しいWidgetを増やすでも、AIの賢さを底上げするでもなく、
  「既存の高品質な仕組みを取りこぼしなく適用する」ことが最も
  レバレッジの高い改善、という結論に至った)。

**実装**: `_DESIGN_TOKEN_PRESETS`(4プリセット: calm/warm/vibrant/
neutral)を`forge_language_compiler.py`から`compiler.py`(元々前者が
後者をimportしているため、循環importを避けるにはこちらが単一の
定義元になる必要がある)へ移動し、`design_tokens_for_style()`・
`design_tokens_for_domain()`という2つの公開関数として再構成した。
`design_tokens_for_domain()`は、`_VISUAL_STYLE_BY_DOMAIN_CATEGORY`
という新設のDomain→visual_styleマップ(Curated Domain Library分は
`ir_generator.py`の`_ENTITY_DEFINITIONS[...].visual_style`と意図的に
一致させ、残り10 Domainは新たに割り当てた)を経由してプリセットを
選ぶ。`Compiler.compile()`のChecklist経路・Form Template経路の両方が、
`ForgeIRDocument`構築時にこれを呼ぶよう変更した。

**副作用として必要だったversion引き上げ**: `design_tokens`は
Validator(`schema_validator.py`)がv1.5以降でのみ許可するフィールド
のため、Checklist経路の`version="1.0"`・Form経路の`version="1.2"`を
いずれも`"1.5"`へ引き上げた。使用するWidget/Action/State型自体は
いずれもv1.0〜v1.2の範囲内のままで、v1.5はその上位互換のため、
実際の画面構成・挙動は一切変わらない。

**Frontend側の変更は不要だった**: Flutter Runtime
(`forge_document.dart`・`forge_renderer.dart`)は元々
`design_tokens`キーの有無だけを見てテーマを切り替える設計になって
おり(Sprint1で実装済み)、versionやDomainには依存しないため、
Dart側のコード変更は一切不要だった。

**確認**: `forge_ai/tests/test_compiler.py`に新規テストクラス
`TestCompilerDesignTokensByDomain`(4件、全15 DomainCategoryが空でない
design_tokensを持つこと・Domainによって実際に異なる配色になること・
未知Domainは"calm"へ安全にフォールバックすること・Form Template
経路にも適用されることを検証)を追加。既存の`version`固定値アサーション
(10箇所)を、"1.0"/"1.2"→"1.5"へ理由を添えて更新した。forge_ai/側
451件・Backend側645件、全てgreen。実際にuvicorn+curlで
`/api/v1/ai/generate`を叩き、「買い物リストを作りたい」(shopping、
以前は無配色)が`#D68C45`(warm)、「満足度アンケートを作りたい」
(survey、以前は無配色)が`#5C6470`(neutral)という異なる配色で、
実際のSchema Validatorを通過して返ることをライブ確認した。

**やらなかったこと・今後の検討事項**: 今回はプリセット配色の
「取りこぼしを無くす」ことに絞り、以下は意図的にスコープ外とした。
* `QualityEngine`/`DesignCritic`へ視覚的仕上がりを評価する軸を
  追加すること(「配色が適用されているか」を機械的にチェックする
  軸自体は追加できるはずだが、この変更で全Domainに配色を適用した
  今、緊急度は下がった)。
* プリセットを4種から増やすこと、またはAIにセマンティックな
  visual_style選択(例: 「几帳面な人向けの日記」→neutral、
  「楽しい家計簿」→vibrant)をさせること(現状は`domain_category`
  という粗い単位でしか選べない。指示書3.4節の「無限に多様な配色を
  AIが自由に生成するのではなく、少数の選択肢から選ぶ」という制約は
  維持しつつ、選ぶ粒度をDomain単位からもう少し細かくできる余地は
  ある)。

## TD45. 「作れるアプリの種類」の上限が、人手でテーブルに書いたDomain数と完全に一致していた → **解消(2026-08-12)、AIによるEntity合成を導入**

CEO「つくれるアプリの自由度をあげたい。トップレベルまで」への対応。

**天井の正体**: `IRGenerator.generate()`は、記録するデータの型
(Entity・Field・型・選択肢)を`_ENTITY_DEFINITIONS`という**手書きの
dictテーブル**から`.get(domain_category)`で引いていた。テーブルに
載っている7 Domain(うち実機で到達可能なのはTD39により5つ)だけが、
型付きCRUDアプリ——タブ構成・record_list_view・日付ピッカー・
選択肢ドロップダウン・スライダー・棒グラフ・編集・削除・
design_tokens——になり、**それ以外の全ての依頼は例外なく
`compiler.py`のChecklist**(文字列が縦に並ぶだけ、型も編集も削除も
無い)へ落ちていた。

つまり「Forgeで作れるアプリの種類」の上限は、Widget語彙の数でも
Geminiの賢さでもなく、**人間が`ir_generator.py`に手で書いた
Domainの数(5)そのもの**だった。新しい領域に対応するには、毎回
人手でEntity定義を書き足す以外に方法が無かった——これが自由度の
天井であり、CEOの言う「トップレベルまで上げたい」対象そのものである。

**実装**: `forge_ai/core/ir/entity_synthesizer.py`(新規)。
Curated Domain Libraryに無いDomainについて、「このアプリが繰り返し
記録する1件分のデータ」の構造をAIに設計させ、手書きテーブルと
**まったく同じ表現**(`EntitySpec`/`FieldSpec`、今回`_`付きの
private名から公開名へ改名)を組み立てて`IRGenerator.
build_from_spec()`(今回`_build_ir()`から公開)へ渡す。以降の経路
——IR構築、`ForgeLanguageCompiler`によるForge Language化、Widget選択、
Design Token適用、Validator——は、**合成された定義と手書きの定義を
一切区別しない**。

新設した`entity_synthesis` stageの周辺:
* `PromptBuilder.build_entity_synthesis_prompt()`(新規)。
* `MockProvider._handle_entity_synthesis()`(新規、決定的)。Mockは
  依頼内容を理解できないため`<概念名>`+`date`という同じ形しか
  返さないが、**合成経路そのもの**(検証・IR生成・Forge Language化・
  Validator通過)がMockだけで一通り実行されることを保証する。
* `ForgeAIProviderBridge._RESPONSE_SCHEMAS["entity_synthesis"]`(新規)。
  **この登録は必須**である: 未登録stageは`{"type": "object"}`
  (propertiesなし)へ落ち、TD40で実機確認したとおりGeminiは黙って
  空dict`{}`を返す。その場合、合成は常に失敗して全Domainが
  Checklistへ戻るが、**エラーにはならないため気付けない**。

**AIの出力を一切信用しない設計**(このモジュールの要点):
`synthesize()`は応答を`_sanitize_*`群で決定的に検証・整形し、
使える形にできなければ`None`を返す。`None`なら
`pipeline_orchestrator.py`は従来のChecklistへ落ちる——つまり
**この機能が失敗しても以前より悪くなることはない**。主なルール:
* entity名・Field名は`identifier`パターンへ機械的に整形(大文字→
  小文字、空白/ハイフン→`_`)。整形しても無理なら諦める。
* 未知の型名(`text`・`integer`等)は項目ごと捨てずにSTRINGへ倒す。
* 選択肢が2件未満のchoiceはSTRINGへ降格する(「根拠のない選択肢を
  発明しない」既存方針を合成経路でも守る)。
* `records`/`selected`/`id`は`ForgeLanguageCompiler`が固定で使う
  State IDと衝突するため予約語として弾く。
* Field数は8件で打ち切る(Validator上限は20/30だが、毎回20項目を
  入力させるフォームは使われない、というUX判断)。
* requiredが1つも無ければ先頭を強制的にrequiredにする(空レコードが
  無限に増えるのを防ぐ)。
* min/maxはNUMBER型かつ両方数値かつmin<maxのときだけ採用
  (`isinstance(True, int)`がTrueになるため、bool を明示的に除外)。

**`CognitiveDependencies.entity_synthesizer`の既定を`None`にしている
理由**: 必須フィールドにすると、このdataclassを直接構築している
既存テストフィクスチャが全て壊れる。`None`なら合成を一切試みず
従来どおりの挙動になる——つまりこの機能は純粋な追加であり、
注入しなければ以前と1バイトも変わらない。

**確認**: forge_ai/側489件(新規34件、`test_entity_synthesizer.py`)・
Backend側645件、全green。Golden fileは7件更新した(差分を1件ずつ
確認済み: 6件は新設の`entity_source` Decision Traceが増えただけ、
1件(04_survey)は2画面→1画面。後者は「Form送信→サンクス画面へ遷移
してデータは**保存されない**」から「回答をrecord_listへ蓄積し、
一覧・編集・削除できる」への変化であり、意図した改善である)。

実機Gemini(`/api/v1/ai/generate`, provider=gemini)でのライブ確認:
* 「スーパーで買うものをメモしておきたい」→ `shopping_item`
  (item_name:string必須 / quantity:number / estimated_price:number /
  store_name:string / is_purchased:boolean)
* 「会議の議事録を残したい」→ `meeting_minutes`
  (title:string必須 / meeting_date:date必須 / participants:string /
  summary:string / action_items:string)、3タブ構成
  (追加・一覧・編集)、date_field・form・section_header・
  record_list_viewを使用。
いずれも以前はChecklist(文字列の羅列)にしかならなかった依頼である。

**Frontend側の変更は不要**: Flutter Runtimeは既に19種のWidgetと
record_list/record_schemas/design_tokensへ対応済み(Curated Domain
5つが同じ形を出力していたため)。合成経路は同じ形を出すだけなので、
Dart側のコードは一切変更していない。

**ライブ確認中に見つかった、未解消の別問題(重要)**: 「毎日の血圧を
記録したい」を投げると、Domain分類が`diary`(Curated)と判定し、
**Curatedが合成より優先される**ため、手書きのdiary定義
(title/content/mood/date)がそのまま使われた。血圧記録としては
明らかに不適切(収縮期/拡張期/脈拍が無い)であり、合成に任せた方が
良い結果になったはずである。つまり「分類器がゆるくCurated Domainへ
寄せてしまうと、合成より**悪い**結果になる」という経路が存在する。

今回この優先順位は変更していない。Curated 5 Domainは人手で丁寧に
調整され、Golden Testで固定されており、優先順位を変えると
それらを回帰させるリスクがあるためである。次の一手としては
(a)分類の確信度が低い場合のみ合成を優先する、(b)合成結果と
Curated定義を比較して依頼文との適合度が高い方を選ぶ、といった
案が考えられるが、いずれも「どちらが良いか」を機械的に判定する
基準が要るため、独立した検討が必要である。

**その他、今回スコープ外としたこと**:
* 複数Entity(例: 「買い物リスト」と「店舗マスタ」)の合成。
  `ForgeLanguageCompiler`が単一Entityしか受け付けない
  (`len(ir.entities) != 1`で例外)という既存の制約があり、
  Compiler側の設計変更を伴うため。
* TD39(todo/reading_logがDomainCategory enumに存在せず、分類から
  到達不可能)は未解消のまま。ただし影響は小さくなった——到達
  できなくても、合成経路が同等のアプリを生成するようになったため。

## TD46. Conversation Engineが「分からなくても作る」設計になっていた → **解消(2026-08-12、FORGE-CONVERSATION-READY-001)**

CEO指示書「Conversation Readiness / CONFIRM / 『はい、どうぞ』体験 改修」
への対応。監査で見つけた問題は7件あり、いずれも「どこまで聞いたら
作るのか」という製品の核心の判断が弱いことに起因していた。

**発見した問題と対応**:

1. **ターン数による強制BUILD**(指示書1章が名指しした問題)。
   `force_ready = (not unknown_important) or (user_turn_count >= MAX_CONVERSATION_TURNS)`。
   → ターン上限をBUILD条件から外し、**質問戦略を変える閾値**へ変更。
2. **LLMの`next_action="build"`が無条件でBUILDを起こしていた**
   (監査で発見した、1より深刻な経路)。
   `if force_ready or llm_action in ("build","update")`という条件により、
   未知の有無に関わらずLLMの一言でBUILDしていた。指示書3章
   (LLM Proposal < System Facts)に真っ向から反する。
   → Readinessによる決定的判断へ置き換え。
3. **空の質問文がBUILDへ倒れていた**。`ask`なのに`question`が空だと
   BUILDしていた。これも「分からなくても作る」である。
   → 未知のkeyから質問文を組み立てて、必ず聞く。
4. **CONFIRMが型としてしか存在しなかった**(発火経路ゼロ)。
   → `requires_confirmation()`を新設し、会話の1ターンとして返す。
5. **未知・仮定に理由が無かった**(単なる文字列のリスト)。
   → `UnknownItem`(key/impact/reason/status)・`SafeAssumption`
   (key/value/reason)へ格上げ。
6. **繰り返し質問の抑止が無かった**。
   → `ConversationSession.asked_question_keys`とPolicy側のフィルタ、
   さらにプロンプトへの明示の三重で抑止。
7. **BUILD失敗が「作れませんでした」で終わっていた**。
   → `classify_build_failure()`で、理解段階の失敗のみASKへ戻す。

**設計上の判断(なぜ1モジュールにまとめたか)**: 指示書12章は
`readiness_policy`/`question_policy`/`confirmation_policy`への分離を
許可しつつ「空の抽象化は作らない」とも指示していた。3つはいずれも
同じ入力(NeedModel + DecisionContext)を共有し、互いに参照し合う
(Readiness判定がConfirm判定を呼ぶ)。ファイルを3つに割ると、共有型と
定数を行き来するだけの薄いモジュールが増えるため、
`conversation_policy.py`1つの中でセクションを明確に分ける形にした。

**MAX_CONVERSATION_TURNSの新しい意味**: 到達時に変わるのは質問の
仕方だけである——`high`はSafe Assumptionへ回し、残る質問は二択にする。
`blocking`は到達後も質問し続ける。「質問しすぎない」と「分からなくても
作る」は別の問題であり、前者はQuestion Policyで、後者はReadinessで解く。

**BLOCKINGが解消しない場合に無限ループしないのか**: `blocking`が
質問済みでも未解消なら`INSUFFICIENT_INFORMATION`となり、BUILDはしないが
質問の仕方は変わる(二択化)。指示書16章の完了条件を優先し、
「ターン数だけを理由にBUILDする」ことは一切しない設計とした。
利用者が答えられない場合は会話を離脱できる(既存のセッションTTLで
30分後に破棄される)。

**ライブ確認(実機Gemini)**:
* 「買い物リストを作って、できたら家族にも共有したい」→ `status: confirm`
  (reason: 「Forgeの外(他の人・外部サービス)へ影響が及ぶため」)。
* 「買い物行くと、いつも何買うか忘れるんだよね」→ `status: ask`。
  Geminiが`share_type`をhigh(理由: 「一人で使うか家族・同居人と共有
  するかでデータ構造やアクセス権限が変わるため」)、
  `item_repeatability`をlowと分類し、**highの1問だけ**聞いた。

**未確認(Gemini無料枠の上限に到達したため)**: 実機Geminiでの
「ASK → 回答 → BUILD」の完走。Policy側はGolden Test・Integration Test
(いずれもLLM非依存)で検証済みであり、残るのはGemini応答の質のみ。

## TD47. `/converse`のbuild_briefが長いため、生成タイトルがValidatorの80文字制限を超えていた → **解消(2026-08-12)**

TD46のライブ確認中に発見した、**実際に生成を失敗させていた**バグ。

**症状**: `/converse`で「読んだ本の感想を記録したい。自分だけで使う。」
と話すと、`validation_error`「Repair(2回)後もValidatorに合格しません
でした」で失敗する。利用者からは原因が全く分からない。

**原因**: `/converse`が導入されて以降、Cognitive Pipelineへ渡るのは
ユーザーの短い一言ではなく、**会話全体を要約した自己完結型の
`build_brief`**(この例では113文字)になった。`ApplicationPlan.title`は
この入力から導出されるため、80文字を超えるタイトルが生成され、
`app.title`・`screen.title`の`string_length`制約に違反していた。
Repairはこの種のエラーを直せないため、2回試して諦めていた。

つまり、`/generate`(短いユーザー入力)では滅多に起きなかった問題が、
`/converse`(長いbrief)の導入によって**常態化**していた。

**修正**: `forge_ai/core/compiler.py`に`clamp_title()`を新設し、
legacy Compiler経路・ForgeLanguageCompiler経路の両方で必ず通す。
単純な先頭80文字ではなく、**最初の句点まで**を優先して切り出す
(「〜アプリ。入力および管理機能として、〜」という説明文から、
意味の通る「〜アプリ」を取り出すため)。実際、113文字のbriefから
36文字の妥当なタイトルが得られることを確認した。

**この種のバグが今後も起きうる箇所**: `build_brief`は他にも
`natural_language`(2000文字上限)としてPipelineへ入る。タイトル以外に
文字数制約を持つフィールドがある場合、同じ経路で違反しうる。今回は
タイトルのみを修正した(Validatorの`string_length`制約を持つ他の
フィールドは、いずれもCompilerが固定文字列を入れており、入力長に
依存しないことを確認済み)。
