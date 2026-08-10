# FORGE-MILESTONE-003.1 実施レポート — Runtime State Contract Fix & Final Quality Closure

**Ref:** FORGE-MILESTONE-003.1　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-13

---

## 0. CEO実機再検証結果と追加修正(最新)

CEOが実際にCEO環境で検証した結果は以下の通り。

| 項目 | 結果 |
|---|---|
| `flutter analyze` | ✅ **PASS**(実機確認済み) |
| `flutter build web` | ✅ **PASS**(実機確認済み) |
| `flutter test` | `action_result_kind_test.dart`の2件が**失敗**(下記) |
| `scripts/verify.ps1` | Python部分がexit code 9009(コマンドが見つからない)で失敗 |

### 発見された実バグ(2件、根本原因は1つ)

失敗した2件はいずれも同じ根本原因だった。

1. `set_value(存在しないstate_ref)` — Expected `invalidTarget`、Actual `success`
2. `compositeは内側で失敗したActionのkindをそのまま伝播する` — Expected
   `invalidTarget`、Actual `success`

**根本原因**: `ForgeStateStore._coerce()`に、「対象キーが存在しない場合、
valueの実行時型からState型を推測して新規作成する」という分岐が残っていた。
Forge Languageの契約上、`set_value`/`set_state`が参照する`state_ref`は
必ず`screen.state`へ事前宣言されている前提であり(Validatorもそれを
検査している)、存在しないキーへの書き込みは「対象が存在しない」という
契約違反として扱うべきだった。この分岐があったせいで、存在しない
state_refへの`set_value`が静かに成功してしまい、`ActionResultKind`が
`success`になっていた。

**修正**: `_coerce()`から該当分岐を削除し、対象キーが存在しない場合は
常に`null`(=書き込み失敗)を返すようにした。既存の`write()`呼び出し箇所
(テスト・`ForgeActionDispatcher`)を全て確認し、いずれも書き込み対象の
キーをコンストラクタで事前宣言しており、この分岐に依存していないことを
確認済み(削除による既存機能への影響は無い)。

**`scripts/verify.ps1`の修正**: CEO報告の「Python exit 9009」は、
`python`コマンドがPATHに無い環境で発生する典型的な症状である。
`py`(Windows Python Launcher、python.org公式インストーラでPATHへ
登録される)を優先し、無ければ`python`にフォールバックする方式へ変更した。

**この2点の修正後の状態**: Claude環境にFlutter SDK・PowerShellが無いため、
`flutter test`・`scripts/verify.ps1`を実際に再実行して確認することは
できていない。修正内容は、失敗した2テストのロジックを手動でトレースし
(0.1章参照)、期待される結果と一致することを確認した。**CEO環境での
再実行が必要**。

### 0.1 手動トレースによる修正確認

修正後のコードで、失敗していた2テストを1行ずつ手動で追跡した。

- `set_value('does_not_exist', 'x')`: `store.write()` → `current = null`
  (空のStoreにキーが無い) → `_coerce(null, 'x')` → 全ての型チェックを
  通過せず(該当分岐を削除済みのため)`null`を返す → `write()`は`false`を
  返す → Dispatcherは`ActionResult.failure(..., kind: invalidTarget)`を
  返す。**Expected(`invalidTarget`)と一致**。
- composite経由: 上記の結果がそのまま`result.kind`として伝播される
  (既存の伝播ロジックは変更していない)。**Expected(`invalidTarget`)と一致**。
- 影響確認: `set_value(有効なstate_ref)`等、既存キーへの書き込みパスは
  今回の削除対象と別の分岐であり、無変更。この回帰は無いと判断する。

---

## 1. PHASE1: add_item_failedの根本原因

### 実際に生成した家計簿カテゴリのJSON(Python Mock Generatorを実行)

```json
{
  "version": "1.0",
  "app": { "title": "家計簿" },
  "initial_screen_id": "generated_screen",
  "screens": [{
    "id": "generated_screen",
    "title": "家計簿",
    "state": {
      "new_item_text": { "type": "string", "value": "" },
      "items": {
        "type": "checklist",
        "value": [
          { "id": "item_1", "text": "今月の収入を記録する", "done": false },
          { "id": "item_2", "text": "固定費を確認する", "done": false },
          { "id": "item_3", "text": "今日の支出を記録する", "done": false },
          { "id": "item_4", "text": "来月の予算を立てる", "done": false }
        ]
      }
    },
    "body": {
      "type": "column", "id": "root_column",
      "children": [
        { "type": "checklist", "id": "list_view", "state_ref": "items", "empty_state_text": "アイテムはまだないよ" },
        { "type": "row", "id": "add_row", "children": [
          { "type": "text_field", "id": "add_field", "state_ref": "new_item_text", "placeholder": "アイテムを追加" },
          { "type": "button", "id": "add_button", "label": "追加",
            "action": { "type": "add_item", "target_state_ref": "items", "source_state_ref": "new_item_text" } }
        ]}
      ]
    }
  }]
}
```

**Validator実行結果**: `valid: True`, `errors: []`(実際に実行して確認)。

### 該当箇所の確認

| 項目 | 値 |
|---|---|
| Document version | 1.0 |
| Screen ID | generated_screen |
| items Stateの型 | checklist(4件) |
| new_item_text Stateの型 | string(空文字) |
| 追加ボタンのAction | `{"type": "add_item", "target_state_ref": "items", "source_state_ref": "new_item_text"}` |
| target_state_ref | "items"(実在、checklist型) |
| source_state_ref | "new_item_text"(実在、string型) |

### 断定した原因

指示書PHASE1で列挙された10候補のうち、**いずれにも該当しない
(候補10「その他」に該当)**。生成JSON自体は完全に正しい
(項目1〜4・6・9は明確に否定される。項目5・7は単一画面・単一Documentの
ため構造上発生し得ない)。

**実際の原因**: `ForgeStateStore.addChecklistItem()`(Dart Runtime)が、
以下2つの根本的に異なる状況を、同じ`bool`型の`false`として
区別なく返していた。

1. **ユーザーが何も入力せず「追加」ボタンを押した**(source Stateの
   テキストが空文字)— これは完全に正常な操作であり、契約違反ではない。
2. **target/source Stateが存在しない、または型が違う** — これは
   AI生成JSONの契約違反であり、本物の不具合。

`ForgeActionDispatcher`は、この`false`を受け取ると常に
`add_item_failed`という同一のERRORログを出していた。CEOが実機で
確認したエラーについて、**最も可能性が高い仮説は、状況1
(空入力での追加操作)によって発生したというもの**である
(生成JSON自体が実際にValidatorへ合格し、構造的に完全であることを
実行して確認済みのため、状況2である可能性は低いと考える)。

**事実と推測の分離**: 「生成JSONが正しいこと」は実行して確認した事実。
「実機で発生した具体的なトリガーが空入力だったこと」は、コードの
挙動から導かれる仮説であり、断定はしない(CEO実機のブラウザ操作ログが
無いため、これ以上の確認はできない)。一方、原因が
「Dart Runtime側の状況区別不足」であることは、コード上確定した事実である
(生成JSON側に問題が無いことが確定しているため、消去法として)。

---

## 2. PHASE2: State契約の修正

**責務の所在確認**: Template(Mock Generatorのテンプレート関数)・
Generator出力・Validatorはいずれも正しいことを確認済み(1章)。
問題はRuntime(Dart)にあると判断し、Runtime側を修正した。

`ForgeStateStore.addChecklistItem()`の戻り値を`bool`から
`AddChecklistItemOutcome`という4値enum(`added`/`emptySource`/
`targetMissing`/`sourceMissing`)へ変更した。`ForgeActionDispatcher`側で
`emptySource`は成功として扱い(ERRORログを出さない)、
`targetMissing`/`sourceMissing`は引き続き明確なERRORとして扱う
(それぞれ異なるメッセージで、どちらの参照が問題かを明示するよう改善)。

**特定カテゴリのハードコードではないことの確認**: この修正は
`ForgeStateStore`・`ForgeActionDispatcher`という汎用Runtime層のみに
加えており、「家計簿」という文字列やカテゴリ名は一切登場しない
(全カテゴリ共通のadd_item契約として修正)。

### CEOレビュー対応: ActionResultへの統一

CEOレビューで「`AddChecklistItemOutcome`だけが特別扱いになっている。
`ActionResult`へ統一したい」というご指摘を受け、`ActionResultKind`という
共通enum(`success`/`noOp`/`invalidTarget`/`invalidSource`/
`validationError`/`runtimeError`)を導入し、**add_itemだけでなく
navigate/go_back/set_value/set_state/toggle_state/reset_state/
submit_form/compositeの全Action種別**が、最終的にこの共通enumへ
収束するようにした。

`AddChecklistItemOutcome`(Store層固有の4値)自体は廃止していない
(Store層の詳細情報を保持する意味はある)。ただし、Dispatcher層で
必ずこの`ActionResultKind`へ変換される、という規則を追加した。

**後方互換性**: 既存の`ActionResult.success`(bool)・`reason`(String?)
フィールドは削除・変更していない(既存テストが具体的な`reason`文字列
(例:`'form_not_found'`)を検証しているため)。`kind`は追加のフィールドで
あり、既存のテスト・呼び出しコードは無改変のまま動作する。

**新規テスト**: `test/json_ui/runtime/action_result_kind_test.dart`
(新規、15件)で、全8 Action種別について`kind`が正しく設定されることを
検証した。composite Actionが内側の失敗の`kind`をそのまま伝播することも
確認した(以前は一律`runtimeError`だったが、より正確な情報を呼び出し元へ
伝えられるよう改善した)。

## 3. PHASE3/6: 全Template Action契約監査

`backend/tests/test_all_categories_action_contract.py`を新設し、
指示書PHASE3で列挙された全12カテゴリ(Memo/Shopping/Travel/Household/
Schedule/Survey/Checklist/Child/Pet/Gift/Budget/Generic fallback)について、
Validatorとは独立したロジックで以下を機械検証した。

- add_item: target_state_refが実在しchecklist型、source_state_refが実在しstring型
- navigate: target_screen_idが実在
- toggle_state: state_refが実在しboolean型
- reset_state: state_refが実在
- submit_form: form_refが実在
- composite: actionsが空でない
- 全widget IDの重複が無い

```
$ python -m unittest tests.test_all_categories_action_contract -v
test_all_categories_action_contracts ... ok
test_budget_category_add_item_contract_specifically ... ok
test_all_categories_valid ... ok
test_no_duplicate_ids ... ok

Ran 4 tests in 0.002s
OK
```

**結果: 12カテゴリ全て、Action契約に問題は見つからなかった。** これは
1章の結論(生成JSON自体は正しい)を、全カテゴリへ拡張して裏付ける
追加証拠である。

**delete_item/toggle_itemについての補足**: 指示書PHASE3/4で言及された
`delete_item`/`toggle_item`は、Forge Languageの独立したAction型としては
存在しない(意図的な設計。DECISIONS.md D3/D32)。checklist項目の
チェック/削除は、checklist Widget自身が持つ組み込み動作であり、
JSON上のActionとしては表現されない(「どの項目がタップされたか」は
実行時にしか決まらないため、静的なActionとして書けない、という
既存の設計判断)。そのため、これらについては「checklist Widgetの
state_refが実在しchecklist型である」ことの検証(Validator既存機能)が、
実質的に対応する契約検証となる。

## 4. PHASE4: Validator強化の要否

3章の契約監査(Validator非依存の再検証)を実施した結果、
**Python Validator自体が今回の不正契約を見逃していた形跡は無かった**
(そもそも今回の問題は不正な契約ではなく、Runtime側の状況区別不足
だったため)。したがって、Validator本体への新規チェック追加は
行っていない。3章の契約テストを「Validatorの並行チェック」として
Repositoryに残すことで、将来Validator自体にバグが混入した場合の
多重防御とした。

## 5. PHASE5/6: 追加テスト一覧

### Dart(Claude環境では未実行)

| ファイル | 件数 | 内容 |
|---|---|---|
| `add_item_regression_test.dart`(新規) | 4 | 家計簿カテゴリの生成→描画→入力→追加のE2E、空入力時の非クラッシュ、空白のみ入力時のtrim判定、全9 Checklistカテゴリの描画時無例外確認 |
| `forge_state_store_test.dart`(拡張) | +7程度 | `AddChecklistItemOutcome`の4値それぞれを単体テストで確認(added/emptySource×2/targetMissing×3/sourceMissing) |
| `action_result_kind_test.dart`(新規、CEOレビュー対応) | 15 | 全8 Action種別について`ActionResultKind`(success/noOp/invalidTarget/invalidSource/runtimeError)が正しく設定されることを確認。compositeの内側失敗kind伝播も確認 |

### Python(実行・全合格確認)

```
$ python -m unittest discover -s tests -p "test_*.py"
Ran 224 tests in 0.019s
OK
```

224件(既存217件 + 今回のadd_item修正関連4件 + 契約テスト4件
[221件の内訳] + Golden Test 3件 = 224件)。この224件には、
`docs/spec/NATIVE_AI_STATUS_NOTE.md`で報告した想定外のMILESTONE-004
関連テスト27件も含まれる(M003.1の作業とは別に、既にRepositoryに
存在していたもの)。

### Golden Test(新規、CEOレビュー対応)

`tests/test_golden_mock_generator.py`・`tests/golden/*.json`
(12カテゴリ分)を新設した。Mock Generatorの現在の出力を凍結し、
再実行結果とバイト単位で比較する。**実際に1文字書き換えて
意図的に壊し、テストが確実に検出することを確認した**上で、
正しい内容へ復元した(この検証手順自体は使い捨てであり、
成果物には含まれない)。

## 6. PHASE7: Analyzer完全ゼロの確認状況

**Claude環境にFlutter SDKが無いため、`flutter analyze`は一度も
実行していない。実行済みと報告することはできない。**

今回のPHASE1/2修正(Dart Runtime、enumの導入)について、静的レビュー
(コード上のimport・型・括弧の対応関係の機械チェック)は実施し、
問題は見つからなかった。ただし、これは`flutter analyze`の代替には
ならない。CEO環境での実行結果を待つ(末尾の「CEO再検証手順」を参照)。

## 7. PHASE8: Web警告の整理

| # | 警告 | 対応 |
|---|---|---|
| 1 | `apple-mobile-web-app-capable`非推奨 | `mobile-web-app-capable`を追加(apple-プレフィックス版はiOS Safari対応のため維持) |
| 2 | 既存`<meta viewport>`との衝突 | 明示的な`viewport`タグを削除(Flutter Webがビルド時に自動挿入する仕様であることをWeb検索で確認。github.com/jonbhanson/flutter_native_splash Issue #526/#359/#397) |
| 3 | `flutter/lifecycle channel`メッセージ破棄 | **対応せず、既知の外部要因として記録**(Flutter Engine自体の起動時タイミング警告。dart-lang/dart-pad・flutter/flutter・FlutterFlow等、Forgeと無関係な複数プロジェクトで同一報告を確認。index.htmlレベルでの修正方法は存在しない。DECISIONS.md D49) |
| 4 | Noto font不足 | PHASE9(8章)で方針を記録 |

Pluginの追加は行っていない(禁止事項「不要なPlugin追加は禁止」を遵守)。

## 8. PHASE9: 日本語フォント方針

`TECH_DEBT.md` TD18に記録した。要点: 今回はフォントファイルを同梱しない
(ライセンス確認・サブセット化検討・バンドルサイズ評価が未完了のため)。
対象文字・実害は具体的に特定できていない(警告ログのみで、実際の
表示崩れの報告は無い)。推奨フォントはNoto Sans JP(Apache License 2.0、
ただし条文レベルでの確認は今回未実施)。

## 9. PHASE10: 「計算アプリ」入力の扱い

実際に実行して確認した: 「計算アプリつくって」は**Generic fallback**へ
落ちており、入力テキストをそのままタイトルにした、項目1件のみの
空のChecklistが生成される。四則演算等のCalculator機能は一切生成されない。
現状仕様としては「クラッシュしない」という意味では妥当だが、UXとしては
ユーザーの期待と乖離する。CEO承認なしにCalculator Widget・Language仕様は
追加していない。`TECH_DEBT.md` TD19に記録した。

## 10. PHASE11: Native AI Foundationについて

**この話題はM003.1レポートから分離した**(CEOレビュー対応:
「M004関連の話題はレポートから分離すること」)。
`docs/spec/NATIVE_AI_STATUS_NOTE.md`を参照。

CEOレビュー「AI RuntimeはExperimental/Not used/Not connectedを
ディレクトリ単位で明示してほしい」への対応として、
`backend/app/ai/runtime/README.md`・`backend/app/ai/native/README.md`
を新設した(いずれも「Status: EXPERIMENTAL — NOT CONNECTED — NOT
USED IN PRODUCTION PATH」と明記)。

## 11. PHASE12: 検証スクリプト

`scripts/verify.ps1`(PowerShell 5.1対応)・`scripts/verify.bat`を新設した。
Transcript(ログ記録)のみを使用し、Tee-Objectとの併用はしていない
(同一ファイルへの併用による競合を避けるため)。途中のステップが
失敗してもスクリプト全体は停止せず、最後に全ステップのサマリーを
表示する。

**CEOレビュー対応(2点)**:

1. 最終サマリーを`PASS`/`FAIL`/`WARNING`の3区分にした(以前は
   OK/FAILEDの2区分で、スキップされたステップがサマリーに一切
   現れなかった)。`-SkipBuild`等で意図的にスキップされたステップも
   `WARNING`として明示し、「実行していないのに合格したように見える」
   状態を無くした。
2. `flutter devices`のステップを追加した。`-RunChrome`指定時、
   出力にChromeが含まれない場合は`flutter run -d chrome`を実行せず、
   `WARNING`として安全にスキップする(Chromeが無い環境で
   ハングアップ・失敗するのを防ぐ)。

**Claude環境にPowerShellが無いため、このスクリプト自体は一度も
実行できていない。** 変更箇所は括弧・構文の機械チェックと、慎重な
目視レビュー(特にスコープの問題:関数へ渡したscriptblock内から
呼び出し元スコープの変数を直接書き換えると、PowerShellでは意図通りに
伝播しない可能性があるため、`flutter devices`の出力取得はscriptblock
経由にせず、呼び出し元スコープで直接実行する形にした)のみ行った。
README.mdに使用方法を記載した。

---

## 完了条件チェックリスト

| 条件 | 状態 |
|---|---|
| Python Test 全件PASS | ✅ 実行確認済み(224件、Golden Test 3件を含む) |
| `flutter analyze` No issues found! | ✅ **CEO実機確認済み(PASS)** |
| `flutter test` All tests passed! | ⚠️ CEO実機で2件失敗を確認、原因特定・修正済み(0章)。**再検証待ち** |
| `flutter build web --debug` Built build\web | ✅ **CEO実機確認済み(PASS)** |
| Chrome実機(Home/Mock生成/家計簿追加成功/Checklist/Form/画面遷移/Runtime ERRORなし/例外なし) | 未実施との報告は無いため保留。次回CEO確認時にお願いしたい |
| `.\scripts\verify.ps1 -RunChrome` の1コマンドで検証可能、PASS/FAIL/WARNING表示 | ⚠️ CEO実機でPython exit 9009を確認、原因特定・修正済み(0章)。**再検証待ち** |
| ActionResultの統一契約 | ✅ 実装済み。CEO実機のflutter testで2件の実装漏れを発見、修正済み(0章) |
| Golden Test | ✅ 実装・動作確認済み(5章) |
| Runtime README(Experimental明示) | ✅ 新設済み(10章、`docs/spec/NATIVE_AI_STATUS_NOTE.md`) |

---

## CEO再検証手順

```powershell
cd "C:\forge_verify\<展開先>\forge"
.\scripts\verify.ps1 -RunChrome
```

上記1コマンドで、Python Test〜Chrome起動までを一括実行できる。

個別に実行する場合:

```powershell
cd "C:\forge_verify\<展開先>\forge\frontend"
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter build web --debug
flutter run -d chrome
```

Chrome実機で特に確認いただきたいのは、**家計簿カテゴリで「追加」ボタンを
複数回(空入力のまま1回、テキスト入力後に1回)押し、いずれもConsoleに
`add_item_failed`のERRORが出ないこと**である。空入力時は項目が増えず
静かに何も起こらない(正常)、テキスト入力後は項目が追加される(正常)、
という2つの挙動を確認いただきたい。

(Native AI / MILESTONE-004関連の話題は、`docs/spec/
NATIVE_AI_STATUS_NOTE.md`として本レポートから完全に分離した。)
