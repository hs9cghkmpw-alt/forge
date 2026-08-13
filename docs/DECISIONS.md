# DECISIONS.md

Architectが可逆な範囲で決定した事項の記録(共通指示書19章・FORGE-MERGE-001 19章に基づく)。
CEO確認が必要な事項は別途 `docs/tasks/task003.md` および統合レポートの
「CEO Decisions」章を参照。ここは「決めたこと」と「その理由」のみを記録する。

---

## D1. forge-foundationを統合先とし、Prototypeはそこへ移植する

Prototype v0.1.3とforge-foundationの現物監査の結果、以下を確認した(統合レポート
Repository Audit参照): Prototypeは動くUXを持つがJSON Schema/Validatorを持たず、
Foundationは構造・原則(AIはコードを書かない、Renderer/Validator分離等)を持つが
実装がほぼ無い(`.gitkeep`のみのディレクトリが49件、実コードはDart 1ファイル・
Python 1ファイルのみ)。したがってFoundationを土台とし、PrototypeのUX
(Home→Confirm→Toolの導線、Inspiration Cards、テーマ、空状態)を移植する。

---

## D2. checklistは専用Widgetにする(汎用list+テンプレート機構にしない)

FORGE-MERGE-001 9章が明示的に比較を求めていた論点。Prototypeの
`tool_screen.dart` のコメントが既に「買い物メモ/Todo/旅行の持ち物チェックは
構造としてはすべて『タイトル+チェック可能な項目リスト』なので同じWidgetで表現する」
と書いており、これは実際に検証済みのUXパターンである。汎用list+テンプレート機構
(state配列の要素ごとにWidgetツリーを繰り返す仕組み)は、AIが生成するJSONの
検証・Repair双方を複雑にする割に、v1で必要な具体的ユースケースが無い。
初版の複雑化を避ける(FORGE-MERGE-001 9章)ため、専用Widgetを採用した。

反転する条件: チェックリスト以外の「繰り返しリスト」UI(例: 検索結果一覧)が
実際に必要になった時点で、汎用list機構を再検討する。

---

## D3. toggle_item / delete_itemはActionとして独立させない

section 9はtoggle_item/delete_itemをAction候補として挙げていたが、これらは
「どの項目がタップされたか」という実行時にしか分からない情報(item_id)を
必要とする。AIが生成時にitem_idを静的に書けないため、汎用Actionとして
JSONに含める設計は成立しない。代わりに、checklist Widget自体の組み込み挙動
(行ごとのタップ・×ボタン)として実装した。add_itemだけは「どの状態を読んで
どこに足すか」が生成時に決まるため、通常のAction(button.action)として残した。

---

## D4. JSON Patch vs Semantic Operationの比較は今回実施しない

FORGE-MERGE-001 12章より。今回の縦の一本(Home→Confirm→Mock Generator→
Forge JSON→Validator→Renderer)は既存文書の編集を含まない(Mock Generatorは
毎回新規文書を生成する)ため、差分編集方式はどちらを選んでも縦の一本の
完成に影響しない。12章が明示的に許可している「比較設計とADRまでで止める」
を適用し、実装は見送った。次に「生成済みアプリをAIが修正する」機能に着手する時点で、
本file(D4)を更新し、4方式(RFC 6902 / JSON Merge Patch / Widget IDベースの
Semantic Operation / 全体再生成+構造差分)を実際に5パターンの編集ケースで
比較してから決定する。

---

## D5. freezed / json_serializable / riverpod_generator を今回は使わない

pubspec.yamlには両方とも依存として既に入っているが、本統合作業では
手書きのDartクラス・手書きのRiverpod Providerを使った。

理由:
- 両方とも `build_runner` によるコード生成(`.freezed.dart` / `.g.dart`)を
  必要とし、生成を1回実行しないと `flutter run` すら通らない。
- Claudeのサンドボックスに Dart SDK が無く、コード生成の実行はおろか
  生成されたコードの構文確認すらできない。生成ステップに依存しないコードの方が、
  現時点で「CEOがすぐ試せる」「Claudeが誠実に検証できる」の両方を満たす。

反転する条件: Widget種別が増えて手書きモデルの保守負担が増した時点、または
`build_runner` を含めたセットアップ手順自体をINSTALL.mdで確立した時点で、
freezedへの移行を再検討する。

---

## D6. go_router を今回は使わない(素のNavigatorを使う)

pubspec.yamlには依存として入っているが、Prototypeが素の`Navigator.push`で
既に実機確認済み(STATUS.md参照)であり、今回の画面数(Home/Confirm/
GeneratedApp + Forge JSON側の動的画面)でNamed Route/Deep Linkが必要になる
場面が無い。導入する場合のconfig面のリスクをClaude側で検証できない
(Dart SDK無し)ため、実績のある方式を維持した。

反転する条件: Deep Link・Web URLでの画面共有・複雑な画面遷移が必要になった時点。

---

## D7. AI生成アプリの内部状態はRiverpodで持たない

Riverpodのproviderはコンパイル時に型・個数が決まっている設計を前提とする。
AIが生成するJSONの `state` はキー・型の集合が実行時にしか決まらないため、
Riverpod providerとしての表現に向かない。そこで:
- Studioアプリ自体の状態(生成リクエストの成功/失敗/ローディング、認証、
  プロジェクト一覧等) → 引き続きRiverpod(`appGenerationProvider`等)。
- AI生成アプリの内部状態(チェックリストの中身、入力欄の値等) →
  `ForgeRuntimeState`(ChangeNotifier)。json_ui/renderer/ 配下。

この2つの状態管理の境界は `json_ui/` と `features/` の境界(ARCHITECTURE.md 2章)
とも一致しており、責務分離として一貫している。

---

## D8. Mock GeneratorはBackend(Python)に置く。Flutter側には置かない

Prototypeの`generateToolFrom`はDart(クライアント側)にあったが、本番のAI生成は
Backend(`backend/app/ai/generators/`)で行う設計(docs/AI.md・docs/ARCHITECTURE.md)
のため、Mock Generatorも同じ場所に置いた。理由: 本物のAIへ差し替える際、
呼び出し側(Flutter)のコードを一切変更しなくて済む
(`POST /api/v1/ai/generate` というインターフェースは変わらない)。

---

## D9. Validatorは標準ライブラリのみで実装した(jsonschemaパッケージ不使用)

backend/requirements.txtには`jsonschema`が含まれておらず、Claudeのサンドボックスは
ネットワーク不可のため追加インストールもできなかった。標準ライブラリのみで
`shared/schemas/ui_schema.v1.json` と等価な検査を手書きした。

副次的な利点: `backend/app/domain/README.md` の「フレームワーク非依存」原則
(domain/usecasesはFastAPI/Pydantic等に依存しない)と自然に合致する。

既知のトレードオフ: `.json`のSchema定義と`.py`の検査ロジックを手動で同期する
必要がある。CEO環境で`pip install jsonschema`が可能であれば、
`_check_schema()`の中身を`jsonschema.validate()`呼び出しに置き換えることで
この二重管理を解消できる(その場合もエラー形式は維持すること)。

---

## D10. Mock Generatorのキーワード判定を3カテゴリから8カテゴリへ拡張した

監査で判明: Prototypeの`_inspirationCards`は8種類だが、`generateToolFrom`の
キーワード判定は3種類(買い物/todo/旅行)にしか対応しておらず、残り6種類
(🍳🍳今日のご飯/💰家計簿/📅今日の予定/👶子ども/🐶ペット/🎁プレゼント)は
無関係な汎用Fallback(「最初のアイテム」1件のみ)に落ちていた。移植と同時に
8種類全てへ対応を広げた。低リスクな機械的拡張(既存パターンの延長)と判断し、
CEO確認は求めず実施した。「子どもの持ち物チェック」が「持ち物」キーワードで
旅行カテゴリに誤分類される衝突を発見し、判定順序で回避した(テストで固定済み)。

---

## D11. Widget IDはドキュメント全体でグローバルに一意とする

画面ごとの一意性ではなく、ドキュメント全体での一意性を要求する。理由:
将来のJSON Patch/Semantic OperationがWidget IDで対象を指す際、
画面をまたいだ一意性が保証されている方が安全(画面移動を伴うRepair・編集で
IDの取り違えが起きない)。実装コストもほぼ変わらないため、より安全な方を採用した。

---

## D12. 「戻る手段が無い画面」はエラーではなく警告(warning)にした

Validatorの意味検査に追加した `no_back_navigation` ルールは、initial screen
以外の画面にgo_back/navigateが無い場合に警告を出す。ブロッキングエラーにしなかった
理由: これはUX品質(Criticの領分)であり、文書として「壊れている」わけではない
(将来的にはあえて行き止まり画面を作るケースもありうる)。品質基準17章の
「JSON構文成功率100%」等の対象は構造的正しさであり、UXの巧拙とは分離すべきと判断した。

---

## D13. Row内でExpandedにするのはtext_fieldのみとする(FORGE-MERGE-002)

`_buildRow`が全childrenを一律`Expanded`で包んでいたため、button等の本来
コンパクトであるべきWidgetまで横幅いっぱいに引き伸ばされていた
(Prototype v0.1.3のtool_screen.dartが持っていた見た目との回帰)。
text_fieldだけをExpandedにする実装へ修正した。汎用的な`flex`/`grow`ヒントを
Schemaに持たせる設計は、Language変更を伴うため今回は見送った(TECH_DEBT.md TD6)。

---

## D14. Task 1(flutter analyze/test実行)は未達成のまま報告する

FORGE-MERGE-002の「最重要事項: 実際に確認できたものだけを完了とする」に従い、
Dart SDKが無い環境的制約により`flutter analyze`/`flutter test`を実施したと
偽ることはしない。代替として、手動レビューによるハードニング(D13や
const付与漏れの修正)と、機械的に検証可能な範囲の再チェック(import解決・
識別子突合)を実施し、実施できなかった部分は統合レポートで明確に区別した。

---

## D15. `string_list`型Widgetの欠落は、方針だけ決めて実装は見送る

`docs/spec/LANGUAGE_FREEZE.md` 7.1節の判断をここにも記録する。Widget追加が
今回禁止されているため、`string_list`型のStateを表示する手段が無いという
既知のギャップ(TECH_DEBT.md TD7)は今回解消しない。次にWidgetを追加する
タイミングで、専用Widgetを追加するか、`string_list`自体を非推奨化するかを
CEOに確認する(実施レポート CEO確認事項参照)。

---

## D16. `.metadata`を捏造せず、未作成のまま報告する(FORGE-MERGE-003)

`.metadata`はFlutter SDKの実際のリビジョン・チャンネル情報を記録するファイルであり、
Claudeはこれを知る手段を持たない。実在しない値で作成すると「flutter createを
実行したかのような偽の記録」を残すことになるため、作成しなかった。CEOが実際の
SDK情報を共有すれば、その値を使って作成することは可能。

---

## D17. `analysis_options.yaml`を新設した(根本原因への効果は未確定のまま)

FormatExceptionの直接原因を断定できないまま(FORGE-MERGE-003-report.md 1章)、
`flutter_lints`を実際に有効化する`analysis_options.yaml`を作成した。理由:
これ自体は依存関係として既に宣言されていた意図を実現するものであり、
FormatExceptionの原因究明とは独立に正当な修正だから。「原因かもしれないものを
直したから解決したはず」という推測はレポートに書かず、CEOの再実測を待つ形にした。

---

## D18. CIのFlutterバージョン指定をCEO実機の実測値へ更新した(FORGE-MERGE-004)

`ci.yml`の`flutter-version: '3.22.0'`は、根拠のない暫定値だった。FORGE-MERGE-004で
CEO環境の実測値(Flutter 3.44.5)が判明したため、これに合わせて更新した。
Dependencyの一括アップグレードやパッケージのメジャーアップグレードとは異なり、
CI設定内の1バージョン文字列を事実に合わせて修正しただけであり、指示書の
禁止事項には該当しないと判断した。

---

## D19. `withOpacity`を`withValues(alpha:)`へ置換した(FORGE-MERGE-004)

CEO実機での実測(`dart analyze`/`flutter analyze`)により、`withOpacity`が
Flutter 3.27以降非推奨であることが確認された(info 1件)。公式移行ガイド
(docs.flutter.dev/release/breaking-changes/wide-gamut-framework)に基づき
`withValues(alpha: 0.6)`へ置換した。内部的には量子化(255段階への丸め)を
経なくなる分、むしろ精度がわずかに向上する変更であり、見た目の透明度は
変わらない。

補足: FORGE-MERGE-002時点では「CI(旧: 3.22.0)ではwithOpacityの方が安全」という
理由でこのまま残す判断をしていたが、CEO実機の実際のバージョンが3.44.5と
判明した今、その判断の前提(3.22.0が実際のターゲット環境)は誤りだったことになる。
古い判断を上書きするのではなく、ここに訂正として記録する(過去の判断そのものは
D13以前の記述を参照すれば経緯が追える)。

---

## D20. 過去のレポート(FORGE-MERGE-001〜003)を削除せず、リポジトリへ保存した

`docs/reports/`配下に過去3件のレポートをそのまま保存し、FORGE-MERGE-003-report.md
の冒頭には「FORGE-MERGE-004で一部訂正された」という注記を追加した(本文は
削除・改変していない)。理由は指示書の「過去のレポートを削除せず、追記または
訂正文として履歴を残すこと」に従うため。

---

## D21. Mock GeneratorをDartへも移植した(Python版との二重管理を受け入れる)

FORGE-RUNTIME-001 Task 3。D8(Mock GeneratorはBackendに置く)は「本物のAIへ
差し替える際にFlutter側を変更しなくて済む」という理由だったが、今回の
要求(Backend非依存で動くMock Mode、Chrome/Web上でPythonは実行できない)は
D8の前提と両立しない。そのためHTTP経由のPython版(`HttpAppGenerationRepository`
が使う)はそのまま残し、Dart版(`MockGenerationDataSource`、
`MockAppGenerationRepository`が使う)を新設した。キーワード・カテゴリ・
出力JSON構造は完全一致させ、Dart側のテストでPython版と同じ回帰ケース
(子ども×持ち物の判定順衝突)を検証している。二重管理の負担はTECH_DEBT.md
TD10として記録した。

---

## D22. Mock Modeに意図的な遅延(650ms)を入れた

Task 6「ユーザーから見るとAIが生成したように見える」を満たすため。
即座に返すとLoading Indicator(Task 4)がほぼ表示されず、不自然に感じられる。
遅延はコメントで明示しており、隠していない。

---

## D23. Mock Modeでは構造上エラー画面を出さない(if分岐で出し分けない)

Task 5「Mock Modeでは絶対に表示しない」を、`if (mockMode) hide error`の
ような特殊分岐で実現するのではなく、`MockAppGenerationRepository`自体が
例外を投げない設計(決定的なMap構築のみ、外部通信なし)にすることで、
自然に満たした。HTTP Mode側(`HttpAppGenerationRepository`)は例外時の
ユーザー向けメッセージを簡潔化し(「接続できませんでした」)、生の例外文字列は
`ForgeLogger`へのみ出力するようにした。

---

## D24. ロギングは新規パッケージを追加せず、debugPrintを内部で使う薄いLoggerにした

Task 9。`logging`パッケージ等の追加は「禁止事項: Dependency更新」に抵触する
リスクがあると判断し、`ForgeLogger`という薄いラッパークラスを自作した。
呼び出し側は常に`ForgeLogger.start/request/success/error`を通すため、
生の`debugPrint`が散らばる状態は解消される。

---

## D25. MOCK/LIVE BadgeはFlutter標準の`Banner`ウィジェットを流用した

Task 8。新規Widgetを作らず、既定のDEBUGリボンと同じ`Banner`を
`MaterialApp.builder`で全画面に適用する形にした(禁止事項「Widget追加」を
回避しつつ要件を満たす)。`debugShowCheckedModeBanner`の設定はそのまま
変更していない。

---

## D26. チェックリスト描画の3点修正(内側Column/Key/IconButton化)

FORGE-RUNTIME-002 Task 3/4。CEO実機で確認された「本文が空白」
「Cannot hit test a render box that has never been laid out」への対応として、
以下3点を修正した(詳細はFORGE-RUNTIME-002-report.md参照)。
1. `_buildChecklist`内側のColumnに`mainAxisSize: MainAxisSize.min`を明示
   (外側Columnとの不整合を解消)。
2. 各ListTileに`ValueKey('checklist_item_${item.id}')`を付与
   (Key無しでの動的リスト構築はFlutterの既知のアンチパターン)。
3. leadingのタップ領域を`GestureDetector`+素の`Icon`から`IconButton`へ変更
   (trailingで既に問題なく動いている実装パターンへ統一)。

**重要な限界の記録**: 実機での完全なスタックトレースが無いため、
上記3点のうちどれが実際の原因だったか、あるいは複合要因だったかは
断定していない。3点とも独立して正当化できる改善であり、まとめて適用した。

**【FORGE-RUNTIME-003による追記】** その後CEO実機で完全なスタックトレースが
得られ、根本原因は本DECISIONSのD29(`ForgeTheme`の`ElevatedButton`
`minimumSize`が無限幅を要求していたこと)であり、上記3点はいずれも
**原因ではなかった**ことが確定した。3点は「付随改善」として整理し、
「原因修正」ではないと明記する(FORGE-RUNTIME-003-report.md Task 7参照)。

---

## D27. Widget typeとRegistry整合性を、機械比較テストで固定した

FORGE-RUNTIME-002 Task 7/8。`docs/spec/MOCK_GENERATOR_CONTRACT.md`を新設し、
Python版・Dart版のMock Generator出力(9カテゴリ全件)を実際にプログラムで
突き合わせ、差分0件であることを確認した(推測ではなく実行結果)。
今後この2つのファイルを変更する際は、必ずこのcontractドキュメントも
更新することをTECH_DEBT.md TD10に明記した。

---

## D28. Rendererの例外保護が「構築時」のみである限界を明文化した

TECH_DEBT.md TD11。今回の修正は具体的な症状への対処であり、
「レイアウト/hit-test時の例外を汎用的に捕まえる」という根本的な保護は
まだ実装していない。ErrorWidget.builderのカスタマイズ等は将来検討事項として
残し、今回は「Widget追加禁止」の制約もあり見送った。

---

## D29. 根本原因: ForgeThemeのElevatedButton `minimumSize`が無限幅を要求していた

FORGE-RUNTIME-003。CEO実機のスタックトレース(`BoxConstraints forces an
infinite width`、`ElevatedButton ← Row ← Column ← ... ← Scaffold`)により
確定。`core/theme/forge_theme.dart`の`elevatedButtonTheme`が
`minimumSize: const Size.fromHeight(56)`を指定していたが、
`Size.fromHeight(h)`はFlutter公式実装上`Size(double.infinity, h)`を返す
(`this(double.infinity, height)`)。

**なぜColumnでは問題にならずRowでだけ問題になったか**: RenderFlexの
主軸(main axis)は、Rowでは横(width)、Columnでは縦(height)にあたる。
Flexは非flex(Expanded/Flexible以外)の子に対し、主軸方向は
unboundedな制約で本来のサイズを測ろうとする。Rowの場合、主軸=横のため、
Buttonの`minimumSize.width = infinity`という「無限を要求する」性質と、
Row自体が非flex子に与える「unboundedな横制約」が組み合わさり、
定義不能な制約になって描画に失敗する。Columnの場合、横(width)は
cross axisであり、`crossAxisAlignment`(既定は`center`)によって
「0〜Columnの確定した横幅」という有限のloose制約になるため、
Buttonの無限幅要求はこの有限最大値へ単純にクランプされ、
結果的に「全幅ボタン」に見えていた(実際にはクラッシュせず正しく
動作していたわけではなく、たまたま安全な制約の組み合わせだった)。

FORGE-RUNTIME-002での3つの修正(内側Columnのmain AxisSize・Key付与・
IconButton化)は、この根本原因とは無関係だったと判断する(Task 7参照)。
無条件に元へ戻す必要は無いと判断し、そのまま残した(理由はTECH_DEBT.mdの
該当箇所、および本DECISIONSのD26参照。ValueKeyと`mainAxisSize:min`は
一般的なFlutterのベストプラクティスとして、IconButton化はGestureDetector
より標準的な実装として、それぞれ独立に妥当と判断する)。

---

## D30. Button全幅化の責務をButton自身からSizedBox/stretchへ移した

FORGE-RUNTIME-003 Task 2。テーマのButtonから`minimumSize`の無限幅を除去した
結果、HomeScreenの送信ボタン(元々テーマ任せで全幅になっていた)は
`SizedBox(width: double.infinity, child: ElevatedButton(...))`で
明示的に全幅化するよう変更した。ConfirmScreenは元々
`crossAxisAlignment: CrossAxisAlignment.stretch`を使っていたため、
コード変更は不要だった(Columnのcross-axis方向のtight制約により、
Button自身のminimumSizeに関係なく安全に全幅になる)。Forge Language側の
Widget定義(`button`)には元々`fullWidth`等の幅指定propは存在せず、
今回も追加していない(Task 3の判断)。

---

## D31. Language v1.1はMinorバンプとし、v1.0は一切変更しなかった(FORGE-MILESTONE-002)

新Widget6種の追加にあたり、既存の`ui_schema.v1.json`は1バイトも変更せず、
新規ファイル`ui_schema.v1.1.json`を追加した。Validatorも
`WIDGET_TYPES_BY_VERSION`でversion別にWidget許可リストを分岐させ、
v1.0文書がv1.1専用Widgetを使うと明示的に不合格にする(`widget_not_allowed_in_version`)。
これにより「v1.0で合格した文書は将来のv1.xでも合格し続ける」という
LANGUAGE_FREEZE.mdの約束を、実装レベルで裏付けた(既存120件のテストが
無改変のまま合格し続けることで検証済み)。

---

## D32. checklist/checkboxのトグルはWidget組み込み挙動のまま、新Actionは追加しなかった

D3(checklistのtoggle/deleteをAction化しない)と同じ理由をcheckboxにも適用した。
「どのWidgetがタップされたか」は実行時にしか決まらないため、AIが静的な
Actionとして書けない。Widget自身の組み込み挙動として実装した。

---

## D33. Card Widgetの標準的な単独カテゴリを見つけられなかった

Templateとして実装した3つ(Checklist/Memo/Form)のうち、Card自体を
主役とする自然なCategoryトリガーを設計時点で見つけられなかった
(既存8ドメインカテゴリはいずれもChecklist・Form・Memoのいずれかで
無理なく表現できた)。Form Template内でCardを実際に使い(質問群を
視覚的に囲む)、Language/Validator/Runtime全層での実装・テストは
完了させたが、単独トリガーは今回設けなかった。将来の拡張点として
`docs/spec/LANGUAGE_SPEC.md`に記録している。

---

## D34. AI Foundationは`Protocol`(構造的部分型)で定義し、実装クラスを1つも書かなかった

指示書PHASE6「AIはまだ実装しない。Interfaceのみ」を文字通り実行した。
Providerスタブ(OpenAI/Claude/Gemini/OSS/ForgeAI)は「型としては存在するが
呼ぶと`NotImplementedError`」という状態にし、「動いたふりをする」ことを
明示的に避けた(テストでも「全Providerが正直に未実装を表明すること」自体を
検証している)。

---

## D35. Dartテストの正確な合計件数は静的カウントで131件と算出したが、実行確認はCEO環境まで未確定と明記する

Python側は実行して135件と確定できた。Dart側は新規4ファイル分を含め、
ループで生成されるテスト(カテゴリ判定8×8=64件等)まで正確に数え上げると
**131件**になる(既存30件+新規101件)。ただしこれは静的なコード読解による
予測であり、実際に`flutter test`を実行して得られた数字ではない
(事実と推測の分離。FORGE-MILESTONE-002-report.mdで確定値をCEOへ確認する)。

---

## D36. 検証パスで発見: 契約テストの非網羅switchバグを修正し、12カテゴリへ拡張した

FORGE-MILESTONE-002の最終検証パスで、`mock_generator_renderer_contract_test.dart`
(FORGE-RUNTIME-002由来)が、v1.1で追加した6 Widgetノード型を`_typeNameOf`の
switch式に反映しないまま残っていたことを発見した。これはDartのsealed class
非網羅switchとしてコンパイルエラーになる実バグである(このテストが検証する
8カテゴリはいずれもv1.1 Widgetを生成しないため、テスト内容自体は成立して
いたが、コンパイル自体が通らない状態だった)。

修正内容: `_typeNameOf`を全13派生型(12 Widget種+Unknown)を網羅する形に修正し、
`kRegisteredWidgetTypes`を12種類へ拡張し、`_flatten`をcard/formの子要素も
辿るよう修正し、対象カテゴリを8種類(旧)から11種類(家事・アンケート・メモを
追加、todoは元々Inspiration Card経由では到達しないため対象外)へ拡張した。
また、Memo/Formカテゴリはchecklistを持たないため、checklist固有の検証を
「存在する場合のみ検証する」形(テンプレート非依存)へ変更し、新たに
checkbox・form(submit_action)の検証を追加した(1カテゴリあたり8→9件)。

この結果、Dartテストの静的カウントはD35時点の131件から165件へ変わった
(実行はできていないため、いずれも推測値であることに変わりはない)。

---

## D37. flutter analyze 3件の修正はいずれも意味・挙動を変えない型/const注釈のみ

FORGE-MILESTONE-002.1。CEO実機実測(Flutter Test 166/166 PASS済み)により、
実装自体は正しく動作していることが確認された上での、純粋な静的解析対応。
3件とも「型を明示する」「const化する」だけで、Mock生成結果・遅延時間・
実行順序のいずれも変更していない。Task 4監査で見つけた4件目
(`forge_document.dart`の`?? const []`)も同様に、`List<String>?`という
左辺の型からDartが正しく推論できる可能性が高いと判断しつつも、
確実性を優先し明示的型引数を追加した(念のための対応であり、
これも意味・挙動を変えない)。

---

## D38. `web/`プラットフォームファイルに限り、方針を変更してClaude側で追加した

FORGE-MILESTONE-002.2。従来(FORGE-MERGE-004以来)「プラットフォームファイルは
CEO環境で生成する、Claude側では捏造しない」としてきた方針を、`web/`にのみ
例外的に変更した。

**理由**: `.metadata`はFlutter SDKの実際のgitリビジョンハッシュ等、Claudeが
知りようのない不透明な情報を含むため、引き続き作成しない。一方
`web/index.html`・`web/manifest.json`はFlutter公式ドキュメントで
バージョンごとに公開されている比較的単純で安定したテンプレートであり、
Web検索で現行(Flutter 3.44系)の正しい内容を確認できたため、再現の確実性が
`.metadata`とは質的に異なると判断した。アイコン画像はPillowで実際に生成し、
有効なPNGファイルであることを確認済み。

**残る限界**: 実際に`flutter build web`が成功するかはClaude環境で検証できて
いない。`android/`・`ios/`・`windows/`・`linux/`・`macos/`は、プラットフォーム
固有のビルド設定(Gradle・Xcode project等)が`web/`よりもはるかに複雑で
Claudeが正確に再現する自信を持てないため、引き続きCEO環境での生成が必要とした。

---

## D39. `set_value`と`set_state`を同じDartクラスへ写像した

FORGE-MILESTONE-003。指示書Task 3は`set_state`を新Action名として提示したが、
v1.0/v1.1で確定していた`set_value`と意味論が完全に同じ(state_ref + valueを
設定する)ため、2つの別クラスを作らず、Dart側は`SetValueAction`1つで
両方のJSON typeを受理する設計にした。Schema側は`action_set_value`
(互換維持用)と`action_set_state`(v1.2正式名称)を別定義として残しつつ、
中身の制約は同一にしている。

---

## D40. Runtime層(State Store/Action Dispatcher/Validator)を新設し、
既存ForgeRuntimeStateはそこへ委譲する形にリファクタリングした

FORGE-MILESTONE-003 Task 1/4。「単一のState Store」「一元化されたAction
Dispatcher」という要求を満たすため、`json_ui/runtime/`配下に3つの新クラス
(`ForgeStateStore`・`ForgeActionDispatcher`・`ForgeFormValidator`)を作った。
既存の`ForgeRuntimeState`(Widget Builderが直接使ってきたAPI)は、シグネチャ・
挙動を変えずに内部実装だけをこれらへ委譲する形にした。これにより、
既存のWidget Builderコード(FORGE-MERGE-001〜FORGE-MILESTONE-002で書いたもの)を
1行も変更せずに新しいRuntime契約を導入できた。

`dispatch()`の戻り値を`void`から`ActionResult`へ変更したが、Dartの言語仕様上
`void Function()`コンテキストで非void値を返す関数を使うことは許容されるため
(呼び出し元が戻り値を無視できる)、既存の`onPressed: () => state.dispatch(action)`
という呼び出し方は変更せずに動作する。

---

## D41. form送信ボタンは常にSubmitFormActionでラップしてdispatchする

FORGE-MILESTONE-003 Task 2/4/5。`form` Widgetの送信ボタンが、JSON上の
`submit_action`を直接dispatchするのではなく、`SubmitFormAction(formRef: 自分の
id, successAction: submit_action)`でラップしてdispatchするよう変更した。
これにより、Validationが実際に実行されるようになった。JSON契約自体
(`form.submit_action`の形)は変更していない — ラップはDart Runtime内部だけの
挙動であり、既存のMock Generator出力(validation無しのform)は、検証対象
フィールドが0件になるため、常に成功する(=以前と同じ挙動)。

---

## D42. checkboxの操作をtoggle_state Action経由に統一した

FORGE-MILESTONE-003 Task 2/4。以前は`buildCheckbox`が`state.setBoolean()`を
直接呼んでいたが、`state.dispatch(ToggleStateAction(...))`を呼ぶよう変更した。
`CheckboxListTile.onChanged`が渡す新しい値は常に「現在値の反転」なので、
意味論上の差異は無い。他のAction同様Dispatcherを経由することで、診断ログ・
将来の拡張(例: toggle操作の監査ログ)が一元化される。

---

## D43. Composite/Navigation深度の上限値

FORGE-MILESTONE-003 Task 4/6。`composite`のネスト上限を3段
(`ForgeActionDispatcher.maxCompositeDepth`)、画面遷移の段数上限を20
(`ForgeScreenView._maxNavigationDepth`、既存のMAX_SCREENS制約と同じ値)とした。
根拠のない数値ではなく、それぞれ「compositeが実用上必要になるネストの深さは
通常1〜2段程度」「1つの文書が持てるscreen数の上限(20)より深く遷移するのは
明らかにループ」という理由で設定した。

---

## D44. `backend/app/ai/runtime/`を`foundation/`の置き換えではなく追加とした

FORGE-MILESTONE-003(v2)。既存の`backend/app/ai/foundation/interfaces.py`
(FORGE-MILESTONE-002)と、今回要求された`backend/app/ai/runtime/`は
概念的に重複する。型(`Intent`/`Plan`/`AIProvider`等)は`foundation/`の
既存型(`IntentIR`/`PlanIR`/`LLMAdapter`)をエイリアスとして再利用し、
重複定義を避けた。`RepairResult`・`PromptContext`・`ProviderRouter`・
`PromptPipeline`のみ、既存に無い責務として正当に新規追加した。
`foundation/`は削除していない(既存テスト5件を無改変のまま維持)。
詳細は`docs/spec/AI_RUNTIME.md`。

## D45. `ProviderRouter`のルーティングロジックは実装し、Provider本体は実装しない

「AI実装したふり」の境界線を、「AI推論そのもの」と「どのProviderを
使うかを決める処理(推論を含まない)」の間に引いた。前者は全てStub
(`NotImplementedError`)、後者(`ProviderRouter.resolve()`)は実際に
動作する。この区別により、PHASE7「実装は禁止」を守りつつ、
オーケストレーション層(PromptPipeline)を実際にテスト可能にした。

## D46. `LanguageGenerator`(Plan→JSON)を新規Protocolとして定義しなかった

PHASE7は`AIProvider`/`AIPlanner`/`AICritic`/`AIRepair`/
`AIContextBuilder`の5つを要求したが、「Plan→JSON」の変換を担う
Protocolは要求リストに無かった。`foundation/interfaces.py`に既に
`LanguageGenerator`という同じ責務のProtocolが存在したため、
新規追加せずそのまま`prompt_pipeline.py`から再利用した(D44と同じ、
重複定義を避ける原則)。

## D47. Flutter Analyzer警告3件を自動検出ツールで発見した

FORGE-MILESTONE-003(v2) PHASE1。CEOから正確なfile:line:colの指定が
無かった(「Unused import・List inference・Map inference 計3件」という
カテゴリ名のみ)ため、Pythonで簡易的な静的検出スクリプトを書いて
Repository全体を機械的に監査した。手作業の目視確認だけでは見落とした
可能性が高い(実際、`forge_runtime_state.dart`の未使用importは、
ツールでの検出まで気づかなかった)。この監査スクリプト自体は
成果物には含めていない(使い捨てのワンオフスクリプトのため)が、
検出ロジックはFORGE-MILESTONE-003-report.mdに記録した。

---

## D48. add_itemの「空入力」と「契約違反」を明確に区別するenumを導入した

FORGE-MILESTONE-003.1。CEO実機で発見された`add_item_failed`の根本原因を
調査した結果、生成JSON自体は完全に正しいことを実際にGeneratorを実行して
確認した(本文書と同じ日付のFORGE-MILESTONE-003.1-report.md 1章参照)。
問題は`ForgeStateStore.addChecklistItem()`が単一の`bool`で成功/失敗を
表現しており、「ユーザーが未入力のまま追加ボタンを押した」という完全に
正常な操作と、「target/sourceのState参照が存在しない・型が違う」という
本物の契約違反を、同じ`false`として区別なく扱っていたことだった。

`AddChecklistItemOutcome`という4値の列挙型を新設し、`emptySource`
(正常操作、ERRORログ無し)と`targetMissing`/`sourceMissing`
(契約違反、ERRORログあり)を明確に分離した。「エラーを握り潰す」
「LoggerのERRORを非表示にする」という禁止事項に抵触しないよう、
契約違反は引き続き確実にERRORとしてログされることを維持した
(握り潰したのではなく、そもそも「エラーではない場合」を正しく
分類し直しただけである)。

## D49. flutter/lifecycle channel警告は対応しない、と明示的に判断した

Web検索で、Flutter Engine自体の既知の起動時タイミング問題であり、
Forge固有の実装ミスではないことを複数の無関係プロジェクトの報告で
確認した(dart-pad, FlutterFlow等)。「警告を隠すだけの対応は禁止」
「不要なPlugin追加は禁止」という制約の下、コードレベルでの対策は
存在しない(または存在してもPlugin追加等の副作用を伴う)と判断し、
`docs/spec`ではなく`TECH_DEBT.md`ではなく、対応不要な既知の外部要因として
`FORGE-MILESTONE-003.1-report.md`にのみ記録することとした
(TECH_DEBT.mdは「将来変更コストを増やしうる、意図的な近道」を記録する
場所であり、この警告は近道でも設計判断でもないため対象外と判断した)。

---

> **【2026-07-14 注記、Architecture Freeze】** 以下D50〜D55は、当時
> 「FORGE-MILESTONE-004: Native AI Phase-1」という名前の依頼として
> 記録されたものである。この名前は現在「**M005: Backend AI
> Integration**」として正式に読み替えられている(M004は
> `forge_ai/`のみを指す)。番号整理・責務境界の正典は
> `docs/spec/FORGE_AI_ARCHITECTURE_V1.md`を参照すること。
> 以下の記録内容そのものは変更していない(歴史的記録として保持)。

## D50. IntentIRを拡張し、新しいIntent型は作らなかった(→ M005)

FORGE-MILESTONE-004 PHASE1。「Goal/Entities/Constraints/Platform/
Complexity/Category/OutputType」というIntent IRの要求に対し、
既存の`IntentIR`(foundation/interfaces.py、FORGE-MILESTONE-002由来)へ
5フィールド(entities/platform/complexity/category/output_type)を
追加する形で対応した。新しい`Intent`型は作っていない。既存フィールド
(purpose/target_users/required_features/constraints/open_questions/
privacy_notes/accessibility_notes)は変更していない。全ての新規
フィールドに既定値を持たせ、既存の`IntentIR(purpose="x")`という
呼び出し方(test_ai_foundation.py・test_ai_runtime.py)を壊さないことを
実際にテスト実行して確認した(194件全合格)。

## D51. IntentParserをAIPlannerとは別に新設し、AIPlannerは変更しなかった(→ M005)

FORGE-MILESTONE-004 PHASE2。既存の`AIPlanner`(runtime/planner.py、
FORGE-MILESTONE-003由来)は「自然言語→Intent」と「Intent→Plan」の
2段階を1つのProtocolにまとめていた。今回の指示書は、この2段階を
PHASE1(Intent IR設計)→PHASE2(IntentParser)→PHASE3(Planner)と
明示的に3段階として要求している。既存の`AIPlanner`を分割・削除すると
既存21件のテストが壊れるため、`AIPlanner`はそのまま残し、
「自然言語→Intent」だけを担当する新しい`IntentParser`
Protocolを追加した。将来の実装時、`AIPlanner.interpret()`が内部で
`IntentParser`へ委譲する形にすることを想定しているが、今回は両方
Stubのため委譲関係自体は実装していない。

## D52. Template Engineは既存3 Templateのカタログ化のみ行い、新規実装は追加しなかった(→ M005)

FORGE-MILESTONE-004 PHASE4。「Template」を構造化する、という要求に対し、
新しいTemplateを追加するのではなく、既存の3つ(checklist/memo/form、
FORGE-MILESTONE-002/003で実装・テスト済み)を、Category/Priority/
Capabilities/Required Widgets/Optional Widgets/Tagsという構造化
メタデータでカタログ化した。`Template.builder`は既存の
`build_checklist_template`等への薄い委譲であり、実際に呼び出して
本物のForge Language互換JSON(Validator合格)が返ることをテストで
確認した。

## D53. ProviderRouterへ'native'/'local'エイリアスを追加し、既存5名前は維持した(→ M005)

FORGE-MILESTONE-004 PHASE8。指示書が要求した語彙
(Native/Claude/OpenAI/Gemini/Local)に合わせ、'native'→既存'forge_ai'と
同一インスタンス、'local'→既存'oss'と同一インスタンス、という
エイリアスを追加した。新しいProvider実装は増やしていない。この変更で
`test_all_five_providers_registered`(5件ちょうどを期待する既存テスト)が
壊れるため、`test_all_seven_provider_names_registered`
(7件を期待する形)へ更新した。加えて、エイリアスが正しく同一
インスタンスを指すことを検証する新規テストを2件追加した(単なる
期待値の弱体化ではなく、カバレッジの拡張と判断した)。

## D54. NativeAIRuntimeに`is_fully_stubbed()`という自己検証メソッドを持たせた(→ M005)

FORGE-MILESTONE-004 PHASE9。「動いたふりは禁止」という原則を、
ドキュメントの記述だけでなく、実行可能なテストとして機械的に
検証できるようにするため、`NativeAIRuntime.is_fully_stubbed()`を
追加した。既定構築(`NativeAIRuntime()`)がこのメソッドで`True`を
返すことを実際にテストで確認しており、将来誰かが誤って
「実装済みのふり」をするコードを混入させた場合、このテストが
検出できる。

---

## D55. 「Pythonのみ変更/Flutterのみ変更」という区別をやめ、毎回verify.ps1による(→ M005で提起、以降全体へ適用)
     完全な品質ゲート通過をもって完了とする運用へ統一した

FORGE-MILESTONE-004完了時、CEOより方針変更の指示があった。従来、
Claude側は「今回はFlutter/Dartを変更していないため、追加のCEO実測は
不要」といった判断を各マイルストーンの報告に含めていた
(例: FORGE-MILESTONE-004レポート2章)。この判断自体が誤っている
可能性(見落とし・環境差異等)を排除するため、今後は**変更範囲に
関わらず、毎回`scripts/verify.ps1`(Python Test + flutter analyze +
flutter test + flutter build web)をCEO環境で実行し、通過したことを
もって完了とする**運用へ統一する。

Claude側は今後、「今回は◯◯を変更していないため再検証不要」という
趣旨の記述をレポートへ含めない。完了条件は常に「CEO環境での
verify.ps1通過」の1つに統一する。

---

## D56. ActionResultを共通enumへ統一しつつ、既存フィールドは変更しなかった

FORGE-MILESTONE-003.1、CEOレビュー対応。`ActionResultKind`という
6値enum(success/noOp/invalidTarget/invalidSource/validationError/
runtimeError)を追加し、全Action種別の結果がこの共通語彙へ収束する
ようにした。`AddChecklistItemOutcome`(Store層固有の4値)は廃止せず、
Dispatcher層で必ずこの共通enumへ変換される、という規則を追加する形にした。

既存の`ActionResult.success`(bool)・`reason`(String?)フィールドは、
具体的な文字列値も含めて一切変更していない。既存テストが
`result.reason == 'form_not_found'`のような具体的な文字列を検証して
おり、フィールドの意味・値を変えると「期待値の弱体化」になりかねない
ため、`kind`を追加フィールドとして導入する方が安全と判断した。

## D57. composite Actionの失敗kindは、内側の失敗をそのまま伝播させる

以前は`composite`内のいずれかのActionが失敗すると、一律
`'composite_step_failed_at_N'`という文字列reasonだけを返していた。
`kind`導入にあたり、内側で実際に失敗したActionの`kind`(例:
`invalidTarget`)をそのまま呼び出し元へ伝播させるよう変更した。
これにより、composite経由で失敗した場合でも、呼び出し元が
「target参照の問題だったのか、validationの問題だったのか」を
`kind`から正確に判定できるようになった。

---

## D58. CEO実機のflutter testが実際に不具合を発見した(ActionResultKind導入の副作用)

FORGE-MILESTONE-003.1。CEOがCEO環境で実際に`flutter test`を実行し、
`action_result_kind_test.dart`の2件の失敗を報告した。原因は
`ForgeStateStore._coerce()`に残っていた「存在しないキーへの書き込みを
新規作成として扱う」という、`ActionResultKind`導入前から存在していた
古い挙動だった。この分岐を削除し、存在しないキーへの`set_value`/
`set_state`は常に`invalidTarget`として失敗するよう修正した。

この一件は、Claude環境で不可能な「実際にコンパイル・実行して確認する」
ことの価値を裏付けている。静的なコードレビューだけでは、この分岐が
`ActionResultKind`の意図(存在しない対象は必ず`invalidTarget`にする)と
矛盾していることに気づけなかった。

---

## D59. M004↔M005 Adapter ContractをM005実装より前に固定した

FORGE-MILESTONE-005(設計フェーズ)。CEOの提案するロードマップ
(M005 Adapter Contract → M005実装 → M006 Pipeline → M007 LLM Adapter
→ M008 Repair → M009 Quality → M010 Native AIβ)に従い、実装着手前に
`docs/spec/ADAPTER_CONTRACT_V1.md`としてAdapter Contractを固定した。

**最も重要な発見**: forge_ai.RepairEngine(内部でmax_iterations=2の
リトライループを持つ)を、そのままM005のAIRepair実装として接続すると、
M005側のPromptPipelineが持つ外側リトライループ(MAX_REPAIR_ATTEMPTS=2)
と掛け合わさり、実質最大4回の修復試行が発生する「二重ループ問題」を、
設計段階で発見した。これは共通指示書6.5節「修正回数には上限を設ける。
推奨は最大2回」という原則を、実装者が気づかないまま静かに破ってしまう
可能性が高い箇所だった。対応方針(forge_ai.RepairEngineをM005経由で
使う際はmax_iterations=1で構築し、M005の外側ループにリトライ制御を
一本化する)を、Adapter Contract(2.4節)に明記した。

**型統合の判断基準**: forge_ai/(M004)とbackend/app/ai/foundation/
(M005が使う型)の間で、概念的に対応する5組の型(Intent/Plan/
ScreenPlan/RepairResult/QualityScore↔CriticResult)を比較した結果、
Forge IR(dict)以外は全てAdapterで変換する方針とした。理由は、
M005側の型が既にBackend運用(プライバシー・アクセシビリティ・
プラットフォーム別出力・UX方針)を前提にしたフィールドを持っており、
これをforge_ai/へ統合するとM004のスタンドアロン性(Backend/Runtime/
実LLMに依存しない)という既存の設計原則(D1〜D7)が壊れるため。

---

## D60. CEO実コード監査により、Adapter ContractをFacade方式へ設計変更した

FORGE-MILESTONE-005。v1.0のAdapter Contractは、M005がforge_ai/の
個別コンポーネント(MeaningExtractor/IntentBuilder/Planner/Compiler)を
段階ごとに呼び出す設計だった。CEOが実コードと突き合わせた結果、
`forge_ai.core.compiler.Compiler.compile()`が`ApplicationPlan`型しか
受け取れず(`PlanIR`型は受け取れない)、v1.0の設計通りに実装すると
型エラーで即座に停止することが判明した。

対応として、既存の`forge_ai.core.pipeline.run_pipeline()`
(自然言語→PipelineResultを1回で返す、既に実装済みの関数)を
「M004↔M005間の唯一の呼び出し境界(Facade)」として採用する設計へ
変更した。これにより、M004内部では`Intent`・`ApplicationPlan`・
`ForgeIRDocument`という固有の型が最後まで維持され、型不整合が
起こり得なくなる。副次的に、`forge_ai/core/pipeline.py`と
`backend/app/ai/runtime/prompt_pipeline.py`の両方がオーケストレーション
責務を持つという重複も解消された(前者が認知パイプラインの唯一の
所有者、後者はHTTP/Provider/Validator/Repair制御に限定)。

この設計変更は、実装着手前の設計監査(Adapter Contract作成)という
プロセスが機能した具体例である。実コードとの突き合わせを行わなければ、
M005実装の初期段階で型エラーに直面し、手戻りが発生していた可能性が高い。

---

## D61. HTTPテストファイルの重複を統合し、発見した実装ミスを修正した

FORGE-MILESTONE-005実装。並行して作成されていた`test_http_api.py`と、
自分が新規作成した`test_http_ai_generate.py`が、同じ`TestGenerateEndpoint`
という内容でほぼ完全に重複していた。比較の結果、`test_http_api.py`の
`test_unsupported_engine_returns_error_envelope`が「HTTP 200(bodyの
statusフィールドで判定)」を期待していたが、実際のルーター実装
(`app/routers/ai.py`)は`ProviderError`以外の`ForgeAIPipelineError`を
一律422で返す設計になっており、この期待値は誤りだった(指示書8章
「未実装Provider指定時: HTTP 503」等、エラー種別ごとに異なるHTTP
Statusを使うことが明示されているため、実装側が正しい)。

対応: `test_http_api.py`の該当アサーションを422へ修正し、自分の
`test_http_ai_generate.py`は重複のため削除した(同じ内容を二重に
持つことに実質的な価値が無いため。既存テストの「弱体化」ではなく、
同一ラウンド内で作成された重複ファイルの統合)。

## D62. `request_error`という、Error Contract 5分類に含まれない
      6番目のcategory値を導入した

`docs/spec/ADAPTER_CONTRACT_V1.md` 3.1節は「リクエスト自体の形式不正は
本Error Contractの対象外とする」と明記しており、5分類
(validation_error/planning_error/provider_error/runtime_error/
unexpected_error)のいずれにも、HTTPリクエストレベルの不正
(JSON構文エラー・スキーマ不正)を無理に当てはめるべきではないと
判断した。`ErrorDetailDTO.category`を`Literal`で制限せず自由な
文字列にしていたため、`"request_error"`という6番目の値を追加する形で
対応した。ADRの5分類を変更するものではなく、ADRが「対象外」と
明示した領域を補う追加的な値である。

## D63. `verify.ps1`へ`pip install -r requirements.txt`ステップを追加した

`backend/tests/test_http_api.py`はfastapi/pydanticが無い環境で
自己スキップする設計(`_FASTAPI_AVAILABLE`チェック)にしている。
CEO環境でこれらのパッケージが未インストールだと、CEOの実行結果でも
HTTPテストが「スキップ」のままになり、実質検証されない懸念があった。
`scripts/verify.ps1`のPython Testステップの直前に
`pip install -r requirements.txt`を追加し、CEO環境で実際にHTTPテストが
実行される可能性を高めた。

---

## D64. HTTP公開APIとRouter内部で、Provider名の許可範囲を意図的に分離した

FORGE-MILESTONE-005実物監査(2回目)。`ProviderRouter`は後方互換のため
8つの名前(`openai`/`claude`/`gemini`/`oss`/`forge_ai`/`native`/`local`/
`mock`)を引き続き解決できるが、HTTP公開APIの`GenerationOptionsDTO`は
`engine: Literal["forge_ai"]`・`provider: Literal["mock", "openai",
"claude", "gemini", "oss"]`という、より狭い許可リストに制限した。
Router内部の柔軟性(エイリアス解決等)と、外部公開契約の厳格さ
(Engine/Providerの混同を防ぐ)を、あえて別の層で扱う設計とした。

---

## D65. Conversation Engineは既存Cognitive Pipelineの「外」に立つ、薄い意思決定層とした

FORGE-PRODUCT-VISION-002(2026-08-11、CEO「『アプリを作るAI』から
『困りごとを話すと道具が生まれるAI』への製品思想更新」)。詳細な
Context/Alternatives/ConsequencesはADR-014に記録した。ここでは要旨のみ:
複数ターンの会話から「聞くか作るか」を判断する新機能を、既存の
Cognitive Pipeline(`forge_ai/core/orchestration/pipeline_
orchestrator.py`)自体には一切追加せず、`backend/app/ai/runtime/
conversation_engine.py`という新規の薄い層として実装した。BUILDと
判定した場合は、会話全体を要約した1つの自然文を既存の`PromptPipeline.
run()`へそのまま渡す。理由: Cognitive Pipelineは「1回の自然文入力→
1回のIR」というステートレスな契約の上に複数のADR(005/007/009)が
積み上がっており、この契約自体を会話向けに拡張すると影響範囲が広すぎる
(指示書26章「既存実装を大量に壊して一気に全面改修しない」)。新規
エンドポイント`POST /api/v1/ai/converse`は追加のみで、既存の`/generate`・
`/generate/confirm`は無変更(後方互換)。

反転する条件: `build_brief`という1本の自然文への要約だけでは、
Cognitive Pipeline側のDomain分類・Ambiguity Detectionの精度が実運用で
不足すると判明した場合(ADR-014のRevisit Conditions参照)。

## D66. ターン数はBUILD条件ではなく、質問戦略を変える閾値である

**背景**: `ConversationEngine`は当初、
`force_ready = (not unknown_important) or (user_turn_count >= MAX_CONVERSATION_TURNS)`
という式でBUILDを決めていた。「無限に質問し続けない」ことが狙いだった。

**問題**: これは「質問しすぎない」ではなく「**分からなくても作る**」で
あった。解を左右する重要な未知が残っていても、3ターン経過しただけで
BUILDへ倒れる。製品の核心である「どこまで聞いたら作るのか」の判断を、
単なるカウンタへ委ねていたことになる。

さらに監査で、より深刻な経路が見つかった:
`if force_ready or llm_action in ("build", "update")`——**LLMが
`next_action="build"`と言えば、未知の有無に関わらず常にBUILDしていた**。
ターン上限は2つある premature-BUILD 経路のうちの1つに過ぎなかった。

**決定**: ターン上限をBUILD条件から完全に外す。到達時に変わるのは
質問の仕方だけとする(`high`はSafe Assumptionへ回す、残る質問は
二択にする)。`blocking`な未知は、ターン数に関わらず質問し続ける。
BUILDの可否は`ConversationReadiness`が決定的に決める。

**根拠**: 「質問しすぎない」と「分からなくても作る」は別の問題であり、
別の手段で解くべきである。前者はQuestion Policy(impactによる絞り込みと
繰り返し質問の抑止)で解き、後者はReadinessで解く。

## D67. Conversation判断において、LLMの自己申告は単独では根拠にしない

**決定**: `next_action`・`confidence`は「提案」として受け取るのみとし、
実際のActionはForge側が事実として知っていること(`DecisionContext`:
既存Toolの有無・ターン数・質問済みkey・外部作用・不可逆操作)から
決定的に導出する。

この思想自体は既に`wants_update = llm_action == "update" and
has_existing_tool`という形で1箇所だけ実装されていた(存在しないツールを
更新させない)。これをConversation Engine全体へ広げた。

**帰結**: `conversation_policy.py`はLLMを一切知らない純粋関数群となり、
「LLMが誤った提案をしてもPolicyが正す」ことをLLM無しで直接テストできる
(`test_conversation_policy.py`・`test_conversation_golden.py`)。

## D68. CONFIRMは専用画面ではなく、会話の1ターンとして返す

**決定**: 外部作用(送信・共有・公開・通知)や不可逆操作(削除・金銭・
権限変更)を含む依頼に対しては`ConversationAction.CONFIRM`を返し、
`/converse`は`status: "confirm"`をASKと同じ形(session_id + question)
で返す。セッションは破棄せず、ユーザーの返事は通常どおり`/converse`へ戻る。

**却下した案**: 独立したConfirm Screenの復活。会話の流れを断ち切り、
「話していたら急に契約書が出てきた」ような体験になるため。

**安全側の非対称性**: 外部作用・不可逆操作の検出は、LLMの申告と
Forge側のキーワード検出の**OR**を取る。LLMが「無い」と言っても
Forge側が検出したならCONFIRMする。一方、単なるローカルTool生成では
毎回CONFIRMしない(キーワード表には「記録したい」「管理したい」の
ようなローカルに閉じた語を決して入れない)。

## D69. Curated Domainは「存在するから」ではなく「Needを満たせるから」採用する

**背景**: `domain_category in SUPPORTED_DOMAIN_CATEGORIES`という条件
だけでCurated定義を採用していた。「毎日の血圧を記録したい」が`diary`
と分類され、手作りの日記定義(タイトル/本文/気分/日付)で血圧記録アプリが
作られていた(TD45)。

**決定**: 分類時に**そのDomainの概念語が実際に一致したか**
(`matched_concepts`)を見る。動詞だけで選ばれたDomainのCurated定義は
使わず、発話から合成する。

**新しい閾値を導入していない**: `domain_classifier.py`には既に
`_ACTION_ONLY_CONFIDENCE_CAP = 0.5`(Concept一致0件ならconfidenceを
制限)という仕組みがあった。判定に必要な情報は最初からあり、
Orchestratorがそれを見ていなかっただけである。

**却下した案**: Curatedと合成の両方を生成して比較する(ADAPT_CURATED
含む)。妥当性の測定のためだけにLLM呼び出しが毎回1回増え、「どちらが
良いか」を機械判定する基準も別途必要になる。既存の信号だけで誤解決を
止められることが実測で確認できたため、複雑な比較機構は入れなかった。

## D70. 委任(「任せる」)は段を止めるのではなく、段を飛ばす

**背景**: 「分からない」「任せる」を検出したら`OFFER_DEFAULT`を返す、
という実装にしていた。Scripted Conversation Set 50件を実際に流したところ、
**段が永久に上がらず**、同じ既定提示を繰り返し続けることが判明した
(15セッションで繰り返し質問、縮退は一度も発動せず、2セッションが
未決着)。

**決定**: 委任は`REPHRASE`を1段飛ばすものとして扱い、
`ask_count`による進行はそのまま続ける。これにより
`ASK → OFFER_DEFAULT → SHRINK_SOLUTION`と進み、必ず決着する。

**併せて修正した2点**(いずれも同じデータセットが検出):

* BUILD経路で`strategy`を渡しておらず、縮退した事実が記録に残らな
  かった(`solution_shrink_count`が常に0)。
* 委任の判定が最新発話のみだったため、「任せる」→「うん」で委任が
  忘れられていた。一度「決めて」と言われた事実は、その後の相槌で
  取り消されない——会話全体のユーザー発話を見る。

## D71. Model Gatewayは既存のLLMAdapterを置き換えず、その上に載る

**背景**: 指示書は`generate(task, input, context, constraints)`という
Provider非依存契約を例示していた。

**決定**: `LLMAdapter.complete_structured(prompt, response_schema)`を
そのまま活かし、Gatewayは`(task, prompt, response_schema)`を受ける。

**理由**: 監査の結果、既存契約は既にProvider非依存であり、上位ロジックは
Provider実装を知らなかった。抽象的な`input`/`context`/`constraints`へ
作り変えると、既存の全呼び出し側とMockの契約を同時に壊す一方、得られる
のは概念的な綺麗さだけである。実際に足りなかったのはTask概念・計測・
Fallback・Routingの4点であり、Gatewayはそれだけを足している
(指示書4章「既存抽象化が十分なら作り直さない」)。
