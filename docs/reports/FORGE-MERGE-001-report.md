# FORGE-MERGE-001 統合監査・再構築レポート

**Ref:** FORGE-MERGE-001　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11
**対象:** `Prototype_v0.1.3`（添付ZIP）× `forge-foundation`（添付ZIP、`forge-foundation_2.zip`として受領)

本レポートは指示書23章の「添付ファイルを確認せず、推測だけで設計する」ことを禁じる方針に従い、
**2つのZIPを実際に展開し、全208ファイルを分類・監査した上で**作成している。監査の詳細な生ログ
(コマンドと出力)はこのレポートには含めていないが、すべての主張は実ファイルの内容に基づく。

---

## 1. Executive Summary

### 何が分かったか
- `Prototype_v0.1.3` は実際に動くFlutter UI(Home→Confirm→Tool)を持つが、JSON Schema・
  Validator・Rendererに相当するものは一切無い。生成ロジックはDartのキーワード判定のみ。
- `forge-foundation` は91ファイル中49ファイル(54%)が`.gitkeep`のみの空ディレクトリで、
  実コードはDart 1ファイル(`main.dart`、"Forge foundation ready."を表示するだけ)・
  Python 1ファイル(`main.py`、`/health`のみ)・JSON Schema 1ファイル(`screen: object`の
  ドラフト)の合計3ファイルのみだった。
- 直前に共有された「forge-foundationには既にValidatorテスト13件・19件のチェック(全Widget・
  深いネスト・Fallback・クラッシュ耐性含む)が合格している」という趣旨の内容は、**実ファイルの
  どこにも根拠が見つからなかった**。`backend/tests/`・`frontend/test/`はいずれも`.gitkeep`のみ、
  `.dart`ファイルはリポジトリ全体で1つ、コード中にテスト・assertパターンは0件だった
  (機械的なgrep検索で確認)。`docs/ROADMAP.md`自体も「JSON UI Schemaの初版を定義」
  「レンダラーと最小Widget Registryを実装」等をすべて未完了(`[ ]`)としており、
  リポジトリの自己申告とも一致する。本レポートは以降、この実ファイルベースの現在地を
  唯一の前提として扱う。

### 何を決めたか
`forge-foundation`を統合先とし、`Prototype_v0.1.3`のUX(Home→Confirm→Toolの導線・
Inspiration Cards・テーマ)を移植する。Architectとして12件の技術判断を行った
(`docs/DECISIONS.md`)。CEO確認が必要な事項は4件のみ(13章)。

### 何を変更したか
Forge Language v1(JSON Schema)を確定・実装し、Validator・Mock Generator・FastAPI
router・Flutter Runtime(Registry/Renderer/State)・Prototypeの3画面移植までを実装した。
詳細は10章 Implementation Report。

### 現在どこまで動くか
- **Python側(Validator・Mock Generator)**: Claudeの環境で実際に`python -m unittest`を
  実行し、**26/26件合格**を確認済み(生成→検証の結合テスト込み)。
- **Backend HTTPルーター・Dart側全体**: 書いたが**未実行**。Claudeのサンドボックスに
  Dart SDK・fastapi/pydanticパッケージが無く(ネットワークも無く追加導入不可)、
  `flutter analyze`・`flutter test`・`flutter run`・`uvicorn`のいずれも実施できていない。
  代わりに、相対import 23件の解決確認とカスタム型の定義-参照突合を機械チェックし、
  その過程で2件の実装ミス(未定義メソッド呼び出し・switch文のフォールスルー)を発見し
  修正した。詳細は11章 Test Report。

### 次の最大リスク
Dartコードが一度も`flutter analyze`を通っていないこと。機械チェックで防げる種類の誤りは
潰したが、型不整合等コンパイラでしか検出できない誤りが残っている可能性はゼロではない。
15章 Immediate Next Task の最初の一歩はこれの解消に充てている。

---

## 2. Repository Audit

208ファイルすべてを監査した。個別ファイルの1行ずつの列挙ではなく、モジュール単位の
集計として示す(全リストは`find`コマンドで機械的に再現可能)。

### 2.1 forge-foundation（統合前、91ファイル）

| 分類 | 該当 | 件数 |
|---|---|---|
| 完成 | なし | 0 |
| 部分実装 | `backend/app/main.py`(`/health`のみ、router無し)/ `frontend/lib/main.dart`(プレースホルダー文言のみ) | 2 |
| 雛形 | `.gitkeep`のみのディレクトリ | 49 |
| 設計文書のみ | `docs/*.md`・各層の`README.md`・`.ai/`・`.agents/`・`PROMPTS/*` | 33 |
| 重複 | なし(`PROMPTS/`と`docs/prompts/`は目的が異なると明記されており重複ではない) | 0 |
| 矛盾 | `docs/AI.md`のJSON例(`screen`単数+`type:screen`)が実装方針と食い違い、`docs/ROADMAP.md`の一部チェックボックスが実ファイル存在と非同期 | 2件(3.2/3.3節で詳述) |
| 不要 | なし(空ディレクトリ群は「将来のために構造だけ示す」という明確な意図がdocs/tasks/task001.mdに記録されており、現時点では不要ではなく意図的) | 0 |
| 移植対象 | (Prototype側からの移植先として機能する) | — |
| 作り直し | `shared/schemas/ui_schema.v1.json`(ドラフトの中身は破棄し、v1として作り直し) | 1 |
| 保留 | Supabase接続・認証・CRUD・Marketplace/Plugin本体(意図的に未着手、ROADMAP.md/README.md 6章に明記) | — |

### 2.2 Prototype_v0.1.3（13ファイル）

| 分類 | 該当 | 件数 |
|---|---|---|
| 完成 | `main.dart`・`theme.dart`・`home_screen.dart`・`confirm_screen.dart`・`tool_screen.dart`(いずれもUXとして機能。STATUS.mdにより実機確認記録あり) | 5 |
| 部分実装 | `tool_generator.dart`(動くが対応カテゴリが8種中3種のみ。3.4節) | 1 |
| 矛盾 | `confirm_screen.dart`の音声入力コメント(実装は既に削除済みなのにコメントが残存) | 1 |
| 設計文書のみ | `README.md`・`INSTALL.md`・`STATUS.md`・`KNOWN_ISSUES.md`・`CHANGELOG.md` | 5 |
| 移植対象 | 上記「完成」5ファイルすべて(UXとして) + `KNOWN_ISSUES.md`/`STATUS.md`/`CHANGELOG.md`の運用形式 | — |
| 作り直し | `tool_generator.dart`(Dart→Python、`GeneratedTool`→Forge JSON) / `tool_screen.dart`(固定UI→Runtime描画) | 2 |

### 2.3 特記: KNOWN_ISSUES.mdの自己申告の正確さ

`Prototype_v0.1.3/KNOWN_ISSUES.md`は「このZIPは単体で`flutter run`できない
(作成環境にFlutter/Android SDKが無いため)」と明記していた。これはClaudeが今回
置かれている制約と全く同種であり、`Prototype`の作者(人間かAIかを問わず)も
誠実に「未検証」を申告していたことの確認できる証拠になっている。本レポートは
この基準を踏襲し、11章で同様の区別を徹底する。

---

## 3. Conflict Report

### 3.1 直前に共有された「既存実装済み」という趣旨の内容と実ファイルの不一致

前節の通り、Validatorテスト13件・19件のチェック合格・Dart Runtime Renderer・
Widget Registry等の主張に対応する実体はforge-foundation内に存在しなかった。
本レポートではこの食い違いをこれ以上追跡せず(原因の推測はしない)、**実ファイルを
唯一の根拠として以降の設計を進める**という運用で対処した。

### 3.2 `docs/AI.md` のJSON例と、あるべきSchemaの形の不一致

`docs/AI.md`の「想定する最小構造(例、確定ではない)」は`"screen"`が単数・
`"type": "screen"`付きだった。これは実装のしやすさの観点で問題がある
(`screen`自体をWidget Registryで解決するのか、それとも構造体として特別扱いするのか
が曖昧になる)。Task003で確定したv1は`screens`配列+`initial_screen_id`とし、
`docs/AI.md`の例をこれに合わせて更新した(6章)。

### 3.3 `docs/ROADMAP.md` のチェックボックスと実ファイル存在の非同期

Phase 1「FastAPIヘルスチェックエンドポイントのみ実装」は`[ ]`のままだったが、
`backend/app/main.py`には`/health`が既に実装済みだった。矛盾ではなく
「実装はされたが動作確認(チェックを倒す条件)が満たされていない」状態と解釈し、
ROADMAP.md側の意味を「コードの存在」ではなく「Claudeまたは人間が実際に実行して
確認したこと」に統一する形で更新した(該当箇所に注記を追加)。

### 3.4 Inspiration Cards(8種) と `tool_generator.dart` のキーワード判定(3種)の不一致

`home_screen.dart`の`_inspirationCards`は8種類(🍳🛒✈️💰📅👶🐶🎁)だが、
`tool_generator.dart`の`generateToolFrom`は3種類(買い物/todo/旅行)しか
専用分岐を持たず、残り6種類は無関係な汎用Fallback(「最初のアイテム」1件のみの
リスト)に落ちていた。ユーザーが🍳「今日のご飯」カードをタップしても、
実際には空同然のリストが返る状態だった。Task003で8種類全てに対応するよう
Mock Generatorを拡張した(`docs/DECISIONS.md` D10、回帰テスト`test_mock_generator.py`
の`TestAllEightInspirationCardsMapCorrectly`)。

### 3.5 `confirm_screen.dart` の音声入力コメント

コメント「音声/テキストどちらで入力しても」は、v0.1.3で既にマイクボタン機能が
削除された後も残っていた(`CHANGELOG.md`のv0.1.3項目に削除の記録がある)。
移植時に削除した。

---

## 4. Keep / Migrate / Rewrite / Delete

| 区分 | 対象 | 理由 |
|---|---|---|
| **Keep(そのまま維持)** | forge-foundationのディレクトリ構成・Clean Architecture方針・`docs/*`の設計原則群・`.ai/`/`.agents/`/`PROMPTS/`の運用規約・`pubspec.yaml`/`requirements.txt`の依存選定 | 監査の結果、設計自体に構造的欠陥は無かった。空ディレクトリが多いのは未実装なだけで、設計判断としては妥当(docs/tasks/task001.md/task002.mdに理由が明記されている)。 |
| **Migrate(移植)** | Home画面・Confirm画面・Inspiration Cards・テーマ(`ForgeTheme`)・空状態表示・「生成前に確認・修正できる」体験 | Prototypeで実際に検証済みのUX資産。5.2節「残すもの」の指示通り。 |
| **Rewrite(作り直し)** | `tool_generator.dart`(→Python `mock_generator.py`)・`tool_screen.dart`(→Runtime描画に置き換え)・`shared/schemas/ui_schema.v1.json`(ドラフト→v1) | Dartオブジェクト直接生成という設計そのものがForgeの原則(AIはコードを書かない/JSONのみ)と両立しないため。ドラフトSchemaは「確定ではない」と自己申告されていた。 |
| **Delete(削除)** | 無し | Prototype・foundationとも、削除すべき「価値のないファイル」は見つからなかった。空ディレクトリは2.1節の通り意図的なプレースホルダーであり削除対象ではない。 |

---

## 5. Final Architecture

`docs/ARCHITECTURE.md`の設計原則(Clean Architecture、`json_ui/`の独立、
AIはコード非生成、Validator分離)はそのまま維持し、変更していない。Task003で
「空だったモジュールに初めて実体が入った」というのが今回の変更の性質である。

```
[Home画面(Flutter/native)]
        │ テキスト入力
        ▼
[Confirm画面(Flutter/native)]
        │ 確定テキスト
        ▼
[GeneratedAppScreen] --watch--> [appGenerationProvider(Riverpod)]
        │                              │
        │                              ▼
        │                    POST /api/v1/ai/generate (Dio)
        │                              │
        │                              ▼
        │                  [backend/app/routers/ai.py]
        │                              │
        │                    generate_forge_document()  (Mock Generator, Python)
        │                              │
        │                    validate_forge_document()  (Validator, Python)
        │                              │
        │                  合格 → {success:true, data:{document}}
        │                  不合格 → {success:false, error:{...}}
        ▼                              │
[ForgeDocumentView] <--- raw JSON ------┘
        │  ForgeDocument.fromJson()(パース、失敗時はFallback画面)
        ▼
[ForgeScreenView] --uses--> [ForgeWidgetRegistry] --uses--> [ForgeRuntimeState]
        │
        ▼
   実際のFlutter Widgetツリー(操作可能なチェックリスト)
```

Home/Confirmは意図的にForge JSONで駆動しない(1章参照)。AIが生成するのは
「作られるアプリの中身」であって、Forgeというアプリ自体のUIではないため。

---

## 6. Forge Language v1

`shared/schemas/ui_schema.v1.json`(JSON Schema Draft 2020-12)として確定。

**トップレベル**: `version`(const "1.0") / `app.title` / `initial_screen_id` / `screens`(配列)

**Widget(6種類。`checklist_item`は独立Widgetにしない。D2/D3参照)**:
`text` / `text_field` / `button` / `column` / `row` / `checklist`

**Action(4種類。toggle_item/delete_itemはchecklist Widgetの組み込み挙動とし、
独立Actionにしない。D3参照)**: `navigate` / `go_back` / `set_value` / `add_item`

**State(4型)**: `string` / `boolean` / `string_list` / `checklist`

**共通ルール**: 全Widget/Screenに安定ID必須(`^[a-z][a-z0-9_]{0,63}$`)。Widget IDは
文書全体でグローバルに一意(D11)。`additionalProperties: false`を全objectに適用。
再帰深度上限12・画面あたりWidget数上限200・配列長上限は用途ごとに規定。

---

## 7. Validation Contract

`backend/app/ai/validators/schema_validator.py`。4層構成、エラー形式は
`{path, category, severity, rule, message}`で統一(FORGE-MERGE-001 11章準拠)。

| 層 | 内容 | 実装方式 |
|---|---|---|
| syntax | JSON構文として解析可能か | `json.loads`の例外捕捉 |
| schema | 型・必須項目・additionalProperties・列挙値 | 手書きの構造検査(D9参照) |
| semantic | ID重複・initial screen存在・navigate先存在・state_ref存在+型一致 | ツリー走査 |
| runtime_safety | 再帰深度・Widget数上限 | ツリー走査 |

severityは`blocking`(不合格)と`warning`(合格するが指摘あり)を区別する。
「initial screen以外でgo_back/navigateが一つも無い(行き止まり)」は意図的に
`warning`にした(D12: UX品質はCriticの領分であり、構造的正しさとは分離する判断)。

---

## 8. Runtime Design

`frontend/lib/json_ui/`配下、3ファイル構成。

- `schema/forge_document.dart`: パース層。sealed classによる型安全なモデル
  (`ForgeDocument`/`ForgeScreen`/`ForgeStateValue`系4種/`ForgeWidgetNode`系7種/
  `ForgeAction`系4種)。不正な構造は`ForgeParseException`を投げ、Renderer側で
  捕捉してFallbackへ倒す(素通りクラッシュさせない、方針4.4/4.5節に対応)。
- `widget_registry/widget_registry.dart`: `"type"`文字列→Flutter Widget構築関数の
  辞書(`ForgeWidgetRegistry`)。6種類の組み込みWidgetを登録。未知typeは
  `ForgeFallbackWidget`(development: 理由を表示 / production: 空スペース。方針12章)。
- `renderer/forge_renderer.dart` + `forge_runtime_state.dart`: 画面描画・
  状態管理・画面遷移。`ForgeRuntimeState`(ChangeNotifier)がAI生成アプリの
  動的な状態を保持する。Riverpodではなくこれを使う理由はD7参照
  (Riverpod providerはコンパイル時に型・個数が決まっている前提の設計であり、
  実行時にキー集合が決まる状態には向かないため)。

freezed/json_serializable/riverpod_generator/go_routerは今回使わず、手書き
コード・素のNavigatorにした(D5・D6。build_runnerというコード生成ステップを
挟まずにこのまま`flutter run`できるようにするため)。

---


## 9. Migration Plan（ここから先）

`docs/ROADMAP.md`の既存フェーズ番号を維持し、今回完了/着手した部分を反映した
(詳細はROADMAP.md本体、検証状況の注記つき)。次に着手すべき順序:

| 順序 | 内容 | 依存 | 完了条件 |
|---|---|---|---|
| 1 | Dart/Backend実行環境での検証(15章) | 無し | `flutter analyze`エラー0件、`pytest`合格、E2E手動確認 |
| 2 | Phase 3残: `apps`/`app_versions`テーブル(Supabase) | 1 | 生成結果が永続化され、アプリ再起動後も残る |
| 3 | Phase 4残: Repair Engine(最小版) | 1 | Validator不合格時、即エラーでなく最大2回の自動修復を試みる |
| 4 | 本物のAI接続(Mock Generatorの`InferenceProvider`化) | 1〜3 | `ai/generators/`の実装だけ差し替え、router以降は無変更で動く |
| 5 | Phase 5: CRUD(アプリ一覧・編集・削除) | 2 | `_template_feature/`を複製して実装 |

Phase 6以降(AI Memory/Improve/Template/Marketplace/Plugin/Team)は指示書20章の
禁止事項(Marketplace/Plugin/Trainerを今回実装しない)により対象外のまま。

---

## 10. Implementation Report

### 新規作成ファイル(25件)
```
shared/schemas/ui_schema.v1.json                                       [書換]
backend/app/ai/validators/schema_validator.py                          [新規・検証済み]
backend/app/ai/generators/mock_generator.py                            [新規・検証済み]
backend/app/schemas/ai.py                                              [新規・未検証]
backend/app/routers/ai.py                                              [新規・未検証]
backend/tests/test_schema_validator.py                                 [新規・検証済み]
backend/tests/test_mock_generator.py                                   [新規・検証済み]
frontend/lib/json_ui/schema/forge_document.dart                        [新規・未検証]
frontend/lib/json_ui/widget_registry/widget_registry.dart              [新規・未検証]
frontend/lib/json_ui/renderer/forge_renderer.dart                      [新規・未検証]
frontend/lib/json_ui/renderer/forge_runtime_state.dart                 [新規・未検証]
frontend/lib/core/theme/forge_theme.dart                               [新規(Prototypeから移植)・未検証]
frontend/lib/core/network/dio_client.dart                              [新規・未検証]
frontend/lib/core/di/network_providers.dart                            [新規・未検証]
frontend/lib/features/app_generation/domain/repositories/app_generation_repository.dart  [新規・未検証]
frontend/lib/features/app_generation/domain/usecases/generate_app_usecase.dart           [新規・未検証]
frontend/lib/features/app_generation/data/datasources/ai_generation_api.dart             [新規・未検証]
frontend/lib/features/app_generation/data/repositories/app_generation_repository_impl.dart [新規・未検証]
frontend/lib/features/app_generation/presentation/providers/app_generation_provider.dart [新規・未検証]
frontend/lib/features/app_generation/presentation/screens/home_screen.dart               [新規(移植)・未検証]
frontend/lib/features/app_generation/presentation/screens/confirm_screen.dart            [新規(移植)・未検証]
frontend/lib/features/app_generation/presentation/screens/generated_app_screen.dart      [新規・未検証]
docs/DECISIONS.md                                                      [新規]
docs/tasks/task003.md                                                  [新規]
KNOWN_ISSUES.md                                                        [新規(リポジトリ直下)]
```

### 変更ファイル(4件)
```
backend/app/main.py     — ai routerを追加
frontend/lib/main.dart  — プレースホルダー画面をHomeScreenへ差し替え
docs/ROADMAP.md         — 検証済み/未検証を区別して反映
docs/AI.md              — Schema例を実装したv1に合わせて修正(3.2節)
docs/ARCHITECTURE.md    — 冒頭に実装状況メモを追加
```

### 削除ファイル
無し(Prototype/foundationとも、削除すべきものは4章の通り無かった)。

---

## 11. Test Report

### 実行できたテスト(Claude環境、`python -m unittest`)

```
$ cd backend && python -m unittest discover -s tests -p "test_*.py" -v
...
----------------------------------------------------------------------
Ran 26 tests in 0.005s

OK
```

- `test_schema_validator.py`: 19件。正常系4件(単一画面/複数画面+navigate/state_ref
  参照/テキストへのstate_ref)、異常系15件(不正JSON/version欠損/未知Widget/未知Action/
  Screen ID重複/Widget ID重複/存在しないState参照/型不一致State参照/存在しないNavigation先/
  initial_screen_id不整合/過剰ネスト/button.action欠損/screen.body欠損/余分な属性/
  行き止まり画面の警告)。
- `test_mock_generator.py`: 7件 + Inspiration Cards8種類の回帰テスト。**Mock Generatorの
  出力を実際にValidatorへ通す統合テストを含む**(Flutterが無い環境でも、生成→検証という
  経路そのものは実質的にEnd-to-End検証できている)。

全ファイルに対し`python -m py_compile`による構文チェックも実施し、fastapi/pydantic
依存ファイル(`routers/ai.py`・`schemas/ai.py`)を含め全件合格。

### 実行できなかったテスト(理由: Dart SDK・fastapi/pydantic・ネットワークが環境に無い)

| コマンド | 目的 | 状態 |
|---|---|---|
| `flutter analyze` | Dart静的解析 | 未実施。CEO環境で必須(15章) |
| `flutter test` | Widgetテスト(今回は未作成) | 未実施・テスト自体も未作成 |
| `flutter pub get` / `flutter run` | 依存解決・実機/Chrome確認 | 未実施 |
| `pip install -r requirements.txt` | fastapi/pydantic等の導入 | 未実施(ネットワーク不可) |
| `pytest` | CI相当のテスト実行 | 未実施(pytest未導入。ただし`unittest`で同一テストを実行し合格) |
| `uvicorn app.main:app --reload` + `curl` | HTTP経由でのE2E確認 | 未実施 |

代替として実施した検証(11章冒頭のPython実行に加えて):
- 全Dartファイルの相対import(23件)がファイルとして実在するかの機械チェック → 0件破損
- 独自クラス/型名の定義箇所と使用箇所の突合 → 誤検知(文字列・コメント内の一致)以外の
  未定義参照は0件
- 上記チェック中に発見し修正した実装ミス2件: (1) `ForgeDocument`に存在しないメソッドの
  呼び出し、(2) switch文でのcase句フォールスルー(コンパイルエラーになりうる書き方)

---

## 12. Decision Log

Architectが決定した12件は `docs/DECISIONS.md` に記録済み(D1〜D12)。要点:
Foundationを統合先とする(D1)/ checklistは専用Widget(D2)/ toggle・deleteはAction化しない(D3)/
差分編集方式の決定は保留(D4)/ freezed・riverpod_generator見送り(D5)/ go_router見送り(D6)/
AI生成アプリの状態はRiverpodでなくChangeNotifierで持つ(D7)/ Mock GeneratorはBackend設置(D8)/
Validatorは標準ライブラリのみで実装(D9)/ キーワード判定を3→8カテゴリへ拡張(D10)/
Widget IDはグローバル一意(D11)/ 行き止まり画面はエラーでなく警告(D12)。

---

## 13. CEO Decisions

指示書19章の基準(外部送信・個人情報保存・課金・認証方式・破壊的変更・公開/配布方針)に
該当する判断は、**今回のスコープには一件も存在しない**(本物のAI呼び出し無し、
永続保存無し、課金無し、認証無し、公開前のためユーザー影響無し)。

ただし、以下はCEOの意向を確認したい(必須ではないが、次工程の前提が変わるため):

1. **D10(キーワード8カテゴリ化)を意図通りとして良いか。** 各カテゴリの項目内容
   (例: 家計簿→「今月の収入を記録する」等)はClaudeが今回新規に作成した文言であり、
   Prototypeの実績があるのは買い物/todo/旅行の3カテゴリのみ。
2. **D5/D6(freezed・go_router見送り)を承認するか。** pubspec.yamlには両方とも
   依存として残したままにしている(削除はしていない)。将来使う前提であれば
   このままでよいが、「使わないなら依存から外す」方針であれば別途整理が必要。
3. **開発機のGPU/VRAM有無・Flutter/Python実行環境の状況。** 15章の検証作業を
   CEO側で行う前提になっているため、詰まった場合はエラーメッセージを共有してほしい。
4. **添付いただいた元のZIP(`Prototype_v0.1.3`・`forge-foundation_2.zip`)は、
   統合後も別途保管するか、削除して統合リポジトリのみを正とするか。**

---

## 14. Known Issues

詳細は`KNOWN_ISSUES.md`(リポジトリ直下、新規)。要点7件: Dart未検証 / Backend未実行 /
ruff未実行 / GitHub Actions未確認 / アイテムIDがタイムスタンプ由来で理論上衝突しうる /
状態がアプリ再起動で消える(永続化未着手) / Repair Engine未実装(Mock生成物は
テストで26/26合格しているため実害は小さい) / Androidエミュレータの接続先設定
(`localhost`ではなく`10.0.2.2`が必要)。

---

## 15. Immediate Next Task

**今すぐ着手できること(所要時間の目安つき)**:

1. **Backend起動確認(5分)**
   ```powershell
   cd backend
   python -m venv venv
   venv\Scripts\activate
   pip install -r requirements.txt
   pytest -v
   ```
   `pytest`が26件合格すれば、Claudeが検証した内容がCEO環境でも再現されたことになる。

2. **Backendサーバー起動 + 手動疎通確認(5分)**
   ```powershell
   uvicorn app.main:app --reload
   ```
   別ターミナルで:
   ```powershell
   curl.exe -X POST http://localhost:8000/api/v1/ai/generate -H "Content-Type: application/json" -d "{\"text\": \"買い物メモを作って\"}"
   ```
   `"success": true` とチェックリストのJSONが返れば、11章で「未実行」だった
   ルーター層が実際に動くことが初めて確認できる。

3. **Flutter側の静的解析(5分)**
   ```powershell
   cd frontend
   flutter pub get
   flutter analyze
   ```
   エラーが出た場合はその内容を共有してほしい。11章の機械チェックで防げなかった
   誤りがあれば、この時点で特定・修正する。

4. **実際に動かす(5分)**
   ```powershell
   flutter run -d chrome
   ```
   Home画面で🛒「買い物」カードをタップ→「これで作る」→確認画面→
   「この内容で作ります」→チェックリストが表示されるか確認。8種類のカードのうち、
   最低でも🍳(今日のご飯)のような今回新規対応したカードを1つ試してほしい
   (3.4節で修正した部分の実地確認になる)。

5. 上記がすべて通れば、`docs/ROADMAP.md`のPhase 3該当箇所を`[x]`に更新してよい
   (Claude側では実行できず`[ ]`のままにしてある)。

6. 次の依頼としては、9章 Migration Plan の順序2〜3(Supabase永続化 / Repair Engine)
   を想定している。
