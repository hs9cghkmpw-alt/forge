# FORGE-MILESTONE-003 実施レポート — Stateful Runtime Foundation

**Ref:** FORGE-MILESTONE-003　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11

依頼書の方針(途中報告不要、重大な仕様衝突がない限り最善の判断で完成状態まで
進める)に従い、一括で完遂した。作業順序(10章)・依存方向(8章)は指示書の
通りに守った。CEO承認が必要な事項(2.3節「JSONは宣言」という原則からの逸脱、
Dependency追加、Directory全面変更等)には抵触していないため、途中停止はしていない。

**最重要事項**: 今回追加・変更した全コードについて、Claude環境では
`flutter analyze`・`flutter test`・`flutter build web`のいずれも実施できていない
(12章)。「おそらく通る」という推測を完了扱いにはしていない。

---

## 1. Milestone 002からの前提

CEO実機で以下が確認された状態を凍結基準とした(依頼書冒頭)。

- `flutter analyze`: PASS(No issues found)
- `flutter test`: 166/166 PASS
- `flutter build web --debug`: PASS

この基準を壊していないことは、12章の「未検証項目」に照らして正直に申告する
(Claude環境では検証不能。CEO環境での再実行が必要)。

---

## 2. 変更ファイル一覧

| ファイル | 変更内容 |
|---|---|
| `backend/app/ai/validators/schema_validator.py` | v1.0/v1.1/v1.2の3バージョン対応へ拡張 |
| `backend/app/ai/generators/templates/form_template.py` | Survey Templateへvalidation追加、version 1.1→1.2 |
| `backend/tests/test_mock_generator_v2.py` | version期待値を1.1→1.2へ更新(1箇所) |
| `frontend/lib/json_ui/schema/forge_document.dart` | number State、5新規Action、validation プロパティを追加 |
| `frontend/lib/json_ui/renderer/forge_runtime_state.dart` | Runtime層への委譲に全面リファクタリング(公開APIは無改変) |
| `frontend/lib/json_ui/renderer/forge_renderer.dart` | navigationDepth・診断ログ配線を追加 |
| `frontend/lib/json_ui/widget_registry/widget_registry.dart` | text_fieldへvalidation error表示を追加 |
| `frontend/lib/json_ui/widget_registry/widget_registry_v1_1.dart` | checkbox(toggle_state経由)・form(submit_form経由)を変更 |
| `frontend/lib/features/app_generation/data/datasources/templates.dart` | Dart版Survey Templateへvalidation追加、version 1.1→1.2 |
| `frontend/test/features/app_generation/data/datasources/mock_generation_datasource_v2_test.dart` | version期待値を1.1→1.2へ更新(1箇所) |
| `TECH_DEBT.md` / `docs/DECISIONS.md` / `CHANGELOG.md` | 記録更新 |

---

## 3. 新規ファイル一覧

| ファイル | 内容 |
|---|---|
| `shared/schemas/ui_schema.v1.2.json` | Language v1.2定義 |
| `backend/tests/test_schema_validator_v1_2.py` | v1.2 Validatorテスト(32件) |
| `frontend/lib/json_ui/runtime/forge_state_store.dart` | State Store |
| `frontend/lib/json_ui/runtime/forge_action_dispatcher.dart` | Action Dispatcher |
| `frontend/lib/json_ui/runtime/forge_form_validator.dart` | Form Validator |
| `frontend/test/json_ui/runtime/forge_state_store_test.dart` | State Storeテスト(14件) |
| `frontend/test/json_ui/runtime/forge_action_dispatcher_test.dart` | Action Dispatcherテスト(14件) |
| `frontend/test/json_ui/runtime/forge_form_validator_test.dart` | Form Validatorテスト(12件) |
| `frontend/test/json_ui/state_binding_test.dart` | State Bindingテスト(5件) |
| `frontend/test/e2e/survey_form_validation_flow_test.dart` | E2Eテスト(1件) |
| `docs/spec/RUNTIME_CONTRACT_V1_2.md` | State/Action/Validation/Navigation設計書 |
| `docs/tasks/task014.md` | 本Task記録 |

---

## 4. 削除ファイル一覧

**無し。** 既存ファイルはすべて維持・更新のみで、削除は行っていない
(禁止事項「既存テストの削除・無効化」を厳守)。

---

## 5. Schema変更内容

`shared/schemas/ui_schema.v1.2.json`を新設(v1.0・v1.1は無改変のまま凍結維持、
`docs/spec/LANGUAGE_FREEZE.md`のMinor定義に従った)。

- **State型**: `number`を追加(既存4型: string/boolean/string_list/checklistは
  無改変)。
- **Action型**: `set_state`/`toggle_state`/`reset_state`/`submit_form`/
  `composite`の5種を追加(既存4種: navigate/go_back/set_value/add_itemは
  無改変。`set_value`は廃止せず維持)。
- **Widget**: 新規Widget型の追加は無し(text_field/checkboxへ任意の
  `validation`プロパティを追加しただけ)。
- **後方互換性**: v1.0/v1.1文書はそのまま合格し続ける(Python既存135件
  ―無改変のまま―全合格で確認済み)。v1.0/v1.1文書がv1.2専用の
  State型/Action型を使った場合は不合格になる(version gatingを実装、
  テストで確認済み)。
- **Migration**: 不要(v1.0/v1.1文書をv1.2へ変換する必要は無い。そのまま
  動き続ける)。

---

## 6. State設計説明

単一の[ForgeStateStore](`json_ui/runtime/forge_state_store.dart`)が実データを
保持する。汎用API(`read`/`write`/`contains`)と型別便利メソッド
(`toggleBoolean`/`reset`/`addChecklistItem`等)を両方提供する。

既存の[ForgeRuntimeState]が持っていたAPI(`getString`/`setString`等、
Widget Builderが直接使うもの)は、シグネチャ・挙動を変えずに、内部実装だけを
`ForgeStateStore`への委譲へ置き換えた。既存Widget Builderのコードは
1行も変更していない。

`reset_state`は「画面初期化時点の値」へ戻す(直近の値ではない)。State全体の
一括resetは今回導入していない(個別resetと明確に区別するという指示書の
方針に従った)。詳細設計は`docs/spec/RUNTIME_CONTRACT_V1_2.md` 2章参照。

---

## 7. Action設計説明

[ForgeActionDispatcher.execute()]が9種類(v1.0/v1.1の4種+v1.2の5種)すべての
唯一の入口。Widget Builderは`if (action.type == ...)`のような分岐を書かない。
戻り値`ActionResult`で成功/失敗を呼び出し元が判定できる。

`composite`は最大10 Action・ネスト最大3段。途中のstepが失敗すると、それ以降の
stepは実行しない(ロールバックはしない、という設計判断をTECH_DEBT.md TD13に
記録した)。詳細設計は`docs/spec/RUNTIME_CONTRACT_V1_2.md` 3章参照。

---

## 8. Validation設計説明

`required`/`min_length`/`max_length`/`min`/`max`/`pattern`の6種
(`email`/`integer`/`non_empty_list`は「必要以上の機能追加は禁止」の方針に従い
見送った)。

`form`の送信ボタンは、JSON上の`submit_action`を直接dispatchするのではなく、
`SubmitFormAction(formRef: 自分のid, successAction: submit_action)`でラップして
dispatchするよう変更した(DECISIONS.md D41)。これがValidationが実際に
実行されるようになった核心の変更である。エラーメッセージは
`InputDecoration.errorText`(text_field)・`CheckboxListTile.subtitle`
(checkbox)でWidget付近に表示する。詳細設計は
`docs/spec/RUNTIME_CONTRACT_V1_2.md` 4章参照。

---

## 9. Navigation設計説明

`navigate`/`go_back`は[ForgeActionDispatcher]から`onNavigationAction`
コールバックへ委譲され、実際の`Navigator`操作は`forge_renderer.dart`が担う
(Dispatcher自体は`BuildContext`を持たない、依存方向を守るため)。

無限遷移防止として、`ForgeScreenView`に`navigationDepth`(現在何画面目か)を
持たせ、MAX_SCREENS(20)を超えて遷移しようとした場合は拒否する。JSON
Widgetツリー自体は構造上ループを作れないため、この対策は主に
composite×navigateの組み合わせに対する多重防御という位置づけ。
詳細設計は`docs/spec/RUNTIME_CONTRACT_V1_2.md` 5章参照。

---

## 10. テスト一覧と件数

### Python(実行・合格を確認済み、167件)

既存135件(無改変)+ 新規32件(`test_schema_validator_v1_2.py`: version
gating・number State・5新規Action・validation rules・composite深度制限)。

### Dart(静的カウント、211件。実行はCEO環境待ち)

既存165件(無改変)+ 新規46件:

| ファイル | 件数 | 内容 |
|---|---|---|
| `forge_state_store_test.dart` | 14 | 指示書5章State Storeの8項目全て |
| `forge_action_dispatcher_test.dart` | 14 | 指示書5章Action Dispatcherの全項目 |
| `forge_form_validator_test.dart` | 12 | 指示書5章Validationの全項目 |
| `state_binding_test.dart` | 5 | 指示書5章State Bindingの5項目全て |
| `survey_form_validation_flow_test.dart` | 1 | E2E(8ステップ、実際のMock Generator使用) |

---

## 11. 実行結果

| コマンド | 結果 |
|---|---|
| `cd backend && python -m unittest discover` | **実行済み。167/167 PASS** |
| `python -m py_compile`(全.pyファイル) | **実行済み。構文エラー0件** |
| Dart brace/import整合性チェック(機械的) | **実行済み。0件不一致**(文字列リテラル内の括弧を除外する改良版チェッカーを使用) |
| `flutter analyze` | **未実行**(次章) |
| `flutter test` | **未実行**(次章) |
| `flutter build web` | **未実行**(次章) |

---

## 12. 未検証項目

| 項目 | 状態 |
|---|---|
| 修正後の`flutter analyze` | **未検証**。sealed classの非網羅switchバグ(過去に発見した実例)が今回無いか、手動で全switch文を洗い出して確認したが、実際のコンパイラでの確認ではない |
| Dartテスト211件の実際の合否 | **未検証**。静的カウントであり、CEO環境での`flutter test`実行でしか確定しない |
| `flutter build web` | **未検証** |
| Survey Form ValidationのE2Eテストのタイミング(`pump`秒数指定) | **未検証**。650msの人工遅延に対し700ms分`pump`しているが、実機での余裕は未確認 |
| CheckboxListTileのFinder(`find.widgetWithText(CheckboxListTile, ...)`) | **未検証**。パターンとしては標準的だが、実際にビルドして確認していない |

---

## 13. 既知の制限

- `number` State型を実際に編集するWidgetが無い(TECH_DEBT.md TD12)。
- `composite`は途中失敗時にロールバックしない(TD13)。
- `form`の中に`form`がネストされた場合、Action Dispatcherは内側のformを
  辿らない(TD14)。
- Mock Generatorの二重管理(Python/Dart、TD10)は今回も継続。Survey
  Templateの変更は両方に反映したが、今後も変更のたびに両方を更新する
  運用が必要。

---

## 14. 技術的負債

`TECH_DEBT.md`(TD1〜TD14)。今回追加したのはTD12(number編集Widget不在)・
TD13(composite非ロールバック)・TD14(form-in-form未対応)の3件。

優先度が高いと考えるもの:
1. **flutter analyze/test/build未実行**(12章)。次の作業より前に、
   CEO環境での実行結果を確認することを最優先とする。
2. **TD10(Mock Generator二重管理)**。Survey Templateの変更で、
   同期を保つ手間が実際に発生した(今回は正しく両方更新したが、
   今後も同じ注意が必要)。

---

## 15. 次マイルストーン候補

依頼書2.1節の通り、AI接続(Intent Planner・Prompt Builder・LLM Adapter等)は
Runtime契約が固まった後に着手すべきフェーズである。今回State/Action/
Validationの契約が一通り揃ったため、次の候補としては:

1. **CEO環境でのMilestone 003検証**(最優先。16章のコマンド)。
2. **AI Foundation(FORGE-MILESTONE-002 PHASE6で設計済みのインターフェース)を
   実際のProvider実装へつなぐ**。ただし依頼書2.1節の理由(Runtime契約を
   先に固める)は今回のMilestoneで一定達成されたと考えられるため、
   CEOの判断を仰ぎたい。
3. **number State型を使う実際のTemplate/カテゴリの追加**(TD12の解消)。
4. **JSON Patch vs Semantic Operationの決定**(DECISIONS.md D4、未決事項)。
   本物のRepair Engineを作る前に必要。

---

## 16. CEO実機検証コマンド

```powershell
cd frontend
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter build web --debug
```

確認してほしい追加項目(依頼書の完了定義に対応):

1. `flutter analyze`: 警告0件。
2. `flutter test`: 既存166件を含む全件PASS(今回の静的カウントでは211件)。
3. `flutter build web`: 成功。
4. Chrome上で、Home画面のText Fieldへ「アンケートを作って」と手入力し、
   生成→Checkbox操作→コメント入力→送信→送信完了画面への遷移→戻る→
   チェック状態が保持されていることを確認する(今回のE2Eテストと同じ操作)。
5. 既存のMock生成アプリ(買い物・旅行等のChecklist)が引き続き動作すること。
6. Buttonレイアウト回帰・Fallback Widget回帰・Home画面回帰が無いこと。

---

## 17. ZIP内容監査結果

再提出ZIPを展開し、以下を直接確認した。

```
forge/                                   最上位(余計な親フォルダ無し)
forge/frontend/web/index.html            存在確認済み(Milestone 002.2から継続)
forge/frontend/web/manifest.json         存在確認済み
forge/frontend/lib/json_ui/runtime/      新設3ファイルの存在確認済み
forge/backend/tests/test_schema_validator_v1_2.py   存在確認済み
forge/shared/schemas/ui_schema.v1.2.json 存在確認済み(有効なJSONとして解析済み)
```

`flutter create .`をCEO側で実行しなくてもWeb Buildできる状態
(`frontend/web/`)は、今回変更しておらずそのまま維持されている。

---

## 18. 事実と推測の分離(総括)

**事実(実行して確認済み)**: Python 167件全合格。全.pyファイルの構文正当性。
Dart全ファイルの中括弧・丸括弧整合性(文字列リテラル内を除外した改良版
チェックで確認)・import解決。sealed class(ForgeStateValue・ForgeAction)の
switch文を全箇所手動で洗い出し、新規追加した5 Action・1 State型が
網羅されていることを確認(この過程で、既存の契約テストファイルではなく
今回のテストファイル自体には非網羅switchの問題が無いことを確認済み)。

**推測(CEO環境でのみ確定する)**: Dart 211件の実際の合否。
`flutter analyze`が0警告になること。`flutter build web`の成功。
E2Eテストのタイミング(`pump`秒数)が実機でも十分であること。

これらを明確に区別して報告した。
