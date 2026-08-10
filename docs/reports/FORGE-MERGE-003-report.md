# FORGE-MERGE-003 実施レポート — Flutterプロジェクトとしての成立性

> **【FORGE-MERGE-004による訂正あり・2026-07-11】**
> 本レポート1.3節の優先順位付き候補のうち、以下がCEO環境での実測(FORGE-MERGE-004)
> により訂正された。**本文は原文のまま保存し、削除・改変していない。**
> 訂正の詳細は `docs/reports/FORGE-MERGE-004-report.md` 6章「過去の原因仮説の訂正」
> を参照。要点のみ:
> - 候補1(`.dart_tool/package_config.json`のパス解決エラー)を裏付ける証拠は
>   得られなかった。
> - Analysis Server crashは、ASCIIパス(`C:\forge_verify`)+ `cmd.exe`経由の実行で
>   再現しなくなった。原因はパスの文字種・実行シェルの一方または両方の可能性が高いが、
>   確定はしていない。
> - `flutter create`未実施は、Web/Windowsビルド不可の直接原因として引き続き有効。
>
> ここから下は、FORGE-MERGE-003作成時点の原文である。

---

**Ref:** FORGE-MERGE-003　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11

CEO環境での実測結果(PASS: `flutter clean`/`flutter pub get`、FAIL: `flutter analyze`/
`flutter test`/`flutter build windows`)を唯一の事実として扱い、そこから調査を始める。
「Analyzerは通るはず」という推測は用いない(指示書の最重要事項に基づく)。

---

## 0. 前提として確定した事実

`frontend/`の実際のファイル構成を確認した結果、以下が判明した。**これは推測ではなく、
現物のディレクトリ一覧から直接確認した事実である**。

| 項目 | 状態 |
|---|---|
| `android/`・`ios/`・`windows/`・`linux/`・`macos/`・`web/` | **すべて存在しない** |
| `analysis_options.yaml` | **存在しなかった**(今回作成。1章) |
| `.metadata` | **存在しない** |
| `test/` | 存在するが`.gitkeep`のみ(今回テストを追加。2章) |
| `.dart_tool/` | 存在しない(CEO環境で`pub get`実行時に生成される想定通りのビルド成果物であり、これ自体は異常ではない) |

**結論**: `frontend/`は一度も`flutter create`を通っていない。`lib/`と`pubspec.yaml`
だけを手作業で用意した状態であり、これは`Prototype_v0.1.3/KNOWN_ISSUES.md`が
自己申告していた制約(「作成環境にFlutter/Android SDKが無く、`flutter create`を
実行できない」)と同じ性質のものである。forge-foundationの`frontend/`も、
実は同じ制約下で作られていたことが、今回のCEO実測で初めて確定した。

---

## 1. Task 1: Analysis Server Crash(FormatException)の調査

### 1.1 確認した項目と結果

| 確認対象 | 結果 |
|---|---|
| `analysis_options.yaml` | 存在しなかった(1.3節で新設) |
| `pubspec.yaml` | YAML構文として正常(PyYAMLで実際にパース確認済み)。タブ文字無し。BOM無し。全ファイルUTF-8として正常 |
| `dart define` | 使用箇所なし(grep 0件) |
| `tool/` | 存在しない |
| VSCode設定(`.vscode/`) | 存在しない |
| LSP設定 | 該当ファイル無し |
| JSON生成箇所(`part 'x.g.dart'`等) | **0件**。`build_runner`関連の生成コードへの依存は無い(DECISIONS.md D5により意図的に不使用) |
| `build_runner`設定(`build.yaml`) | 存在しない |

上記のうち「ファイルが存在しないので中身を確認しようがない」ものが大半であり、
**Claudeが持っている材料だけでは、FormatExceptionの直接の原因を1つに断定できない**。
これは調査を怠ったのではなく、事実として断定材料が無いためである。

### 1.2 実施した調査: 類似事例の確認

Web検索で、同種の症状(Dart Analysis Serverが`FormatException`で異常終了する事例)を
確認した(2026年7月時点)。

もっとも症状が一致した事例は、`dart-lang/sdk`のissue #41322で報告された
`FormatException: The resolved 'packageUri' must be inside the rootUri...`
というエラーで、`.dart_tool/package_config.json`の解決処理
(`analyzer/src/context/package_config_json.dart`)内で例外が発生し、
Analysis Serverごと落ちるというものだった。

一方、`.metadata`ファイルの欠落については、別の実例(DEV Community記事)で
「`.metadata`が無くても`flutter run -d chrome`・`flutter build web`は問題なく動いた」
という報告があり、`.metadata`単独の欠落が直接の原因である可能性は相対的に低いと判断した
(ただし`flutter analyze`固有の挙動までは確認できていない)。

### 1.3 優先順位付き候補

| 優先度 | 候補 | 根拠 | 確度 |
|---|---|---|---|
| 1 | `.dart_tool/package_config.json`のパス解決エラー | 症状(FormatException+Analysis Server crash+パッケージ解決)が完全一致する実例あり(dart-lang/sdk#41322)。非標準的なプロジェクト配置(flutter create未経由)がこの種のエラーを誘発しやすいと推測される | 中(実例との類似はあるが、本件で再現・確認はできていない) |
| 2 | `analysis_options.yaml`不在による未定義動作 | `flutter_lints`が依存に入っているのに読み込まれておらず、Analysis Serverが暗黙のデフォルト設定で動く状態だった。デフォルト動作の中に本件のような非標準プロジェクトで問題を起こす経路が無いとは言い切れない | 低〜中(明確な実例は見つからず) |
| 3 | `flutter analyze`の実行ディレクトリ | `forge/`ルート(pubspec.yaml無し)から実行された場合、`frontend/`から実行された場合と挙動が異なりうる。**CEOに確認が必要**(1.4節) | 未確認(要ヒアリング) |
| 4 | Flutter/Dart SDKのバージョン | `pubspec.yaml`の`environment: sdk: '>=3.3.0 <4.0.0'`と、CEO実機にインストールされているSDKバージョンの組み合わせ。CI(`ci.yml`)は3.22.0を指定しているが、CEO実機のバージョンは未確認のまま(FORGE-MERGE-001 CEO確認事項3で既に一度質問し、まだ回答を得ていない) | 未確認(要ヒアリング) |
| 5 | Platformフォルダの完全欠如 | 単独では致命的でない実例(pluginプロジェクトでは正常運用されるケースがある)があるが、`.metadata`・`analysis_options.yaml`の同時欠如と組み合わさった際の挙動は確認できていない | 低(単独では説明力が弱い) |

### 1.4 CEOに提供いただきたい追加情報(最重要)

**「FormatException」というカテゴリ名だけでは、上記5候補のどれが正しいか
確定できない。** 以下のいずれかを共有いただければ、原因を大きく絞り込める。

1. `flutter analyze`実行時に表示された**エラーメッセージの全文**(スタックトレースを含む)。
2. `flutter analyze -v`(verboseモード)で再実行した際の出力。
3. `flutter analyze`をどのディレクトリから実行したか(`forge/`直下か`forge/frontend/`か)。
4. `flutter --version`の出力(Dart SDKバージョンを含む)。

### 1.5 今回実施した修正(1.3節の候補2への対応)

`frontend/analysis_options.yaml`を新設した。`flutter_lints`パッケージは以前から
依存に入っていたが、この設定ファイルが無かったため実際には一度も有効になっていなかった。
この修正が1.3節優先度1のクラッシュそのものを直接解消するとは断定していない
(1.4節の情報が無い限り断定は不可能)が、それとは独立して正当な修正である。

**明記しておくこと**: `.metadata`は今回作成していない。理由は、実際のFlutter SDK
リビジョン・チャンネル情報を持たない状態で捏造した`.metadata`を置くと、
「本当は`flutter create`していないのに、したかのような情報」を記録することになり、
事実と異なる記録を残すことになるため。`.metadata`を正しく用意する方法は、
CEO環境で(今回は禁止されている)`flutter create .`を実行するか、CEOが
実際のSDKチャンネル・リビジョンを把握した上で手動で追記するかのいずれかであり、
どちらもClaude単独では実施できない。

---

## 2. Task 2: Flutter Test整備

CEOの実測で「Flutter Testが存在しない」と報告された通り、`frontend/test/`は
`.gitkeep`のみだった(現物確認済み)。以下を新設した。

| ファイル | 内容 | テスト数 |
|---|---|---|
| `test/smoke_test.dart` | アプリ全体(`ForgeApp`)が例外を投げずにHomeScreenまで起動するか | 1 |
| `test/features/app_generation/presentation/screens/home_screen_test.dart` | 送信ボタンの有効/無効切り替え、Inspiration Cardタップで自動送信されないこと、8種のカードが全て表示されること | 4 |
| `test/json_ui/widget_registry/forge_fallback_widget_test.dart` | ForgeFallbackWidget(Runtime層で最も依存の少ないWidget)が理由テキストを表示し、任意の文字列でクラッシュしないこと | 2 |

**合計7件**。いずれも`package:forge_app/...`形式のimportが実在するlib/配下の
ファイルを指していることを機械チェックした(4件、全件解決)。**Dart SDKが無いため
`flutter test`そのものは実行できていない**(5章 Test Report)。

これらはRiverpod(`ProviderScope`)を必要としない範囲(HomeScreen・
ForgeFallbackWidget)のみを対象にした。`GeneratedAppScreen`(Riverpod経由でBackend
HTTPを呼ぶ画面)のテストは、Dioのモック化が必要でありClaude側で動作検証できないため、
今回は見送った(4章で候補として記録)。

---

## 3. Task 3: Desktop Project構成調査

### 3.1 事実

`windows/`ディレクトリは存在しない。同様に`android/`・`ios/`・`linux/`・`macos/`・
`web/`もすべて存在しない(0章参照)。`pubspec.yaml`にも`flutter: plugin: platforms:`
のような明示的なプラットフォーム宣言は無い。

### 3.2 意図の切り分け(調査結果、断定はしない)

以下の2つの可能性のどちらであるか、リポジトリの記録だけからは判別できなかった。

- **(a) flutter create実施前提**: `docs/tasks/task001.md`・`task002.md`
  (Foundation初期構築時の記録)を確認したが、「`flutter create`を実行した」
  という記述も「あえて実行しなかった」という記述も見当たらなかった。
  `Prototype_v0.1.3/KNOWN_ISSUES.md`が同じ制約を明示的に自己申告していたことから
  類推すると、forge-foundationも同様に「本来は`flutter create`する前提だったが、
  作成環境にFlutter SDKが無かったため実行できなかった」可能性が高い。
- **(b) Repository方針**: `.gitignore`(リポジトリ直下)を確認したが、
  プラットフォームフォルダを意図的に除外する記述(例: `windows/`を`.gitignore`に
  含める等)は無かった。方針として除外しているなら通常`.gitignore`に痕跡が残るはずだが、
  それが無い。

**現時点の判断**: (a)の可能性が高いと考えるが、確証は無い。**勝手に生成しない**
という指示に従い、`windows/`等のプラットフォームフォルダはClaude側では一切作成していない。

### 3.3 CEOへの確認事項

`flutter create .`(禁止事項に抵触するため今回不可)を、次のいずれかのタイミングで
CEO環境で実行してよいか。

1. 今すぐ(Task 1のFormatException原因特定と同時に検証できる可能性があるため)。
2. Task 1の原因が(候補1: package_config.json由来と)確定してから。
3. Windows Desktop対応が本当に必要になったタイミングまで保留
   (`flutter run -d chrome`によるWeb動作確認だけで当面はよい、という判断もありうる)。

---

## 4. Task 4: Analyzerが動作した場合に想定されるError候補の事前レビュー

`flutter analyze`が一度も成功していないため、実際の指摘事項は不明。以下は
`flutter_lints`(pubspec.yamlの依存)の代表的なルールに対して、コードを手動で
突き合わせた**予測**である。

### 4.1 手動チェックで「問題なし」と確認できたもの

| ルール | 確認方法 | 結果 |
|---|---|---|
| `prefer_single_quotes` | 全`.dart`ファイルをgrep | コード中の二重引用符は0件(ドキュメントコメント内の1件のみで対象外) |
| `sort_child_properties_last` | `child:`/`children:`を含む全箇所を個別に文脈確認 | 全箇所で`child`/`children`が最後の名前付き引数になっている |
| `avoid_print` | grep | 0件 |
| `use_super_parameters` | 全コンストラクタを確認 | `super.key`で統一済み |
| コード生成への依存 | `part`宣言をgrep | 0件(freezed/json_serializable関連のコードは一切無い) |

### 4.2 手動チェックでは断定できず、`flutter analyze`実行を待つべきもの

- **型推論の細部**: `strict-casts`/`strict-inference`を今回`analysis_options.yaml`で
  有効にしたため(1.5節)、暗黙のdynamic化・暗黙キャストが無いかは実際にanalyzerを
  通すまで確定できない。特に`ForgeStateValue`/`ForgeWidgetNode`/`ForgeAction`の
  `switch`式・sealed classパターンマッチング周辺は、Dart 3の比較的新しい構文であり、
  手動レビューだけでは網羅的確認ができない。
- **未使用のprivateメンバー**(`unused_element`等): importの要不要は機械チェック済み
  だが、private methodやprivate fieldの「宣言されているが使われていない」は
  ファイル横断の網羅チェックをしていない。
- **`flutter_lints`のうち今回明示的に確認していないルール**: `prefer_final_locals`
  等、細部の慣習ルール。

### 4.3 このレビューの位置づけ

「Analyzerは通るはず」という楽観的な推測はしない。4.1は実際に確認できた事実、
4.2は確認できていない事項として明確に分けている。`flutter analyze`が実行できた
時点で、この予測が正しかったかどうかも検証対象にしてほしい(答え合わせをすることで、
今後Claudeが同種の手動レビューを行う際の精度向上に使える)。

---

## 5. Test Report(検証できた/できなかった)

| 項目 | 状態 |
|---|---|
| Python: 97件のValidator/Generatorテスト | **検証済み**(前回から変更なし、再実行して合格を再確認) |
| `analysis_options.yaml`のYAML構文 | **検証済み**(PyYAMLで実際にパース、タブ文字無し) |
| 新設したDartテストファイル3件のimport解決(4件) | **検証済み**(機械チェック、全件解決) |
| 新設したDartテストファイルの中括弧・丸括弧対応 | **検証済み**(機械チェック、不一致0件) |
| `flutter analyze` | **未検証**(Dart SDK無し。CEO実測が今回の情報源) |
| `flutter test`(新設した7件を含む) | **未検証**(同上) |
| `flutter build windows` | **未検証・対象外**(3章の意図確認待ち、Desktop Project生成禁止のため) |
| Task 4の予測内容 | **予測であり、確認ではない**(4.3節で明記) |

---

## 6. CEO確認事項

1. **Task 1の原因特定に必要な追加情報(1.4節)を共有いただけるか。**
   `flutter analyze`の生エラーメッセージ・スタックトレース、実行ディレクトリ、
   `flutter --version`の出力。これが無いと、これ以上の絞り込みはClaude単独では困難。
2. **`windows/`等プラットフォームフォルダの意図(3.3節)。** flutter create実施前提と
   考えてよいか、それとも別の方針があったか。
3. **`flutter create .`を実行するタイミング(3.3節の3択)。**
4. **FORGE-MERGE-001から未回答のまま残っている確認事項の状況。**
   開発機のGPU/VRAM有無、Flutter/Python実行環境。今回の実測でFlutter環境は
   存在することが分かったが、正確なバージョン(`flutter --version`)はまだ未共有。
5. **`.metadata`を今回作成しなかった判断(1.5節)への同意。** 捏造を避けるため
   意図的に見送ったが、別の対応(例: CEOが実際の値を教えてくれれば、それを使って
   Claudeが作成することは可能)を希望する場合は伝えてほしい。

---

## 7. 次のステップ

1. **最優先**: 6章の確認事項1(`flutter analyze`の生ログ)を共有いただくこと。
   これが無いと、Task 1は「候補止まり」から先に進めない。
2. ログを受け取り次第、Claude側で原因を再特定し、可能なら追加の修正を行う
   (`analysis_options.yaml`の調整、または`.dart_tool`関連の問題であれば
   `flutter clean && flutter pub get`のやり直しを提案する等)。
3. Task 1が解消した後、`flutter test`を実行し、今回追加した7件のテストの
   合否を共有いただきたい。落ちるものがあれば、それはClaudeが実行環境無しで
   書いたことによる実装ミスの可能性が高く、その場で修正する。
4. 3章の意図確認の結果を踏まえ、`windows/`(または他のプラットフォーム)の
   scaffold生成に進めるかどうかを次回改めて判断する。
