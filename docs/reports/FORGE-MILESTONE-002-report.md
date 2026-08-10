# FORGE-MILESTONE-002 実施レポート — Forge Language v0.3 + AI Foundation

**Ref:** FORGE-MILESTONE-002　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11

依頼書の方針(途中報告不要、CEO判断が必要な事項のみ停止)に従い、PHASE1〜9を
一括で完遂した。CEO承認が必要な6項目(Language思想変更・UX変更・
ブランド変更・Plugin思想変更・Directory全面変更・外部Dependency追加)には
一度も抵触しなかったため、途中停止はしていない。

**最重要事項**: 今回追加した全コードについて、Claude環境では
`flutter analyze`・`flutter test`・Chrome実行のいずれも実施できていない。
8章・9章に断定できない旨を明記する。**最終検証パスで、既存テストファイル
1件にDartのsealed class非網羅switchという実バグ(コンパイルエラーになる状態)を
発見し、修正した(7章末尾・11章参照)。この種の問題を含め、実際に
`flutter analyze`/`flutter test`を実行するまで「問題が無い」とは断定できない。**

---

## 1. 変更概要

| PHASE | 内容 | 状態 |
|---|---|---|
| PHASE1 | Forge Language v1.1(6 Widget追加) | 完了 |
| PHASE2 | Runtime再編(Registry機構とWidget実装の分離) | 完了 |
| PHASE3 | Validator拡張(v1.0/v1.1 2バージョン対応) | 完了・Python側検証済み |
| PHASE4 | Template System(Checklist/Memo/Form) | 完了 |
| PHASE5 | Mock Generator v2(12カテゴリ) | 完了・Python側検証済み |
| PHASE6 | AI Foundation(インターフェースのみ) | 完了(実装はしていない、意図通り) |
| PHASE7 | Repository整理 | 実施(軽微。7章参照) |
| PHASE8 | Documentation | 完了(本レポート含め9ファイル新設・更新) |
| PHASE9 | Testing | Python 135件実行・合格。Dart 165件(静的予測、D36のバグ修正後)は未実行 |

新規ファイル: Python 8件・Dart 8件・ドキュメント 6件・テスト Python 3件/Dart 4件。
詳細な一覧はCHANGELOG.md Task011エントリを参照。

---

## 2. 設計判断

`docs/DECISIONS.md` D31〜D35に記録。要点:

- **D31**: v1.1はMinorバンプとし、v1.0は無変更で凍結を維持した。
  Validatorのversion gatingにより、旧文書が新Widgetを使えないことを保証した。
- **D32**: checkboxのトグルもchecklistと同じくWidget組み込み挙動とし、
  新Actionは追加しなかった(タップ対象は実行時にしか決まらないため)。
- **D33**: Card Widgetは実装・テストは完了させたが、単独の自然なCategory
  トリガーを見つけられなかった。Form Template内での実演にとどめ、
  正直にその旨を記録した(将来の拡張点)。
- **D34**: AI Foundationは`Protocol`のみで実装クラスを書かず、Providerは
  全て`NotImplementedError`スタブにした。「動いたふりをしない」ことを
  テストで保証している。
- **D35**: Dartテストの合計は静的カウントによる予測であり、
  実行確認はCEO環境まで断定しないと明記した。
- **D36**: 最終検証パスで、既存の契約テストファイルにDartのsealed class
  非網羅switch(コンパイルエラーになる実バグ)を発見・修正した。対象カテゴリも
  8→11種類へ拡張し、静的カウントは131→**165件**に更新した(7章参照)。

---

## 3. 追加Language(PHASE1)

`shared/schemas/ui_schema.v1.1.json`(新設、v1.0は無変更)。

| Widget | 必須props | 備考 |
|---|---|---|
| `heading` | `value` | `level`(1/2)。構造的な見出し |
| `checkbox` | `label`, `state_ref` | boolean state、組み込みトグル |
| `card` | `children`(1件以上) | 視覚的なグルーピング |
| `list` | `state_ref` | string_list表示(TECH_DEBT.md TD7を解消) |
| `divider` | (なし) | 区切り線 |
| `form` | `children`, `submit_label`, `submit_action` | 入力の束ね+送信 |

Action・State型の追加は無し(既存4種/4型のまま)。詳細は
`docs/spec/LANGUAGE_SPEC.md`。

---

## 4. 追加Template(PHASE4)

| Template | 新規/既存 | 使用Widget | version |
|---|---|---|---|
| Checklist | 既存を関数として切り出し | column/checklist/row/text_field/button | 1.0 |
| Memo | **新規** | column/heading/text_field | 1.1 |
| Form | **新規** | column/heading/card/form/checkbox/text_field/button/text | 1.1 |

新規カテゴリ3件(家事→Checklist、アンケート→Form、メモ→Memo)を追加し、
計12カテゴリになった。既存9カテゴリの出力は1バイトも変更していない
(回帰テストで確認済み)。詳細は`docs/spec/TEMPLATE_SPEC.md`。

---

## 5. 追加Runtime(PHASE2)

- `widget_registry_core.dart`(新設): Registry機構(`ForgeWidgetRegistry`・
  `buildForgeWidget`・`ForgeFallbackWidget`)を分離。
- `widget_registry_v1_1.dart`(新設): 6新Widgetの構築関数
  (`CheckboxListTile`・`Card`・`Divider`等、実績のあるMaterial標準Widgetを使用)。
- `widget_registry.dart`: v1.0の6 Widget実装はロジック無変更、
  `buildDefaultForgeRegistry()`から両バージョンを登録する形に再編。
- `forge_document.dart`: sealed classへ6新規ノード型を追加(同一ファイル内。
  Dartのsealed class制約による)。
- `forge_runtime_state.dart`: `getBoolean`/`setBoolean`/`getStringList`を追加。

**開発中に発見・修正した実装ミス**: 当初`ForgeWidgetRegistry`への`extension`
として`static withBuiltins()`を追加しようとしたが、Dartの`extension`は
静的ファクトリメソッドを外部から追加する機構ではない(コンパイルエラーに
なる)。トップレベル関数`buildDefaultForgeRegistry()`として定義し直し、
呼び出し元(`forge_renderer.dart`)を含め全箇所を修正した。詳細は
`docs/spec/RUNTIME_SPEC.md`。

---

## 6. 追加Validator(PHASE3)

`schema_validator.py`をv1.0/v1.1の2バージョン対応へ書き換えた。

- `WIDGET_TYPES_BY_VERSION`: version文字列 → 許可Widget集合の辞書。
- v1.0文書がv1.1専用Widgetを使うと`widget_not_allowed_in_version`で不合格。
- 新規意味検査: `checkbox`のstate_ref型(boolean)一致確認、`list`の
  state_ref型(string_list)一致確認、`form`のsubmit_action参照解決、
  `form_without_input`警告(入力Widgetが1つも無いform)。
- 既存120件のテストは無改変のまま全て合格を維持(後方互換性の実証)。

---

## 7. 追加テスト(PHASE9)

### Python(実行済み、135件全合格)

| ファイル | 件数 | 内容 |
|---|---|---|
| `test_schema_validator.py` | 19 | v1.0 Validator既存分(無改変) |
| `test_schema_validator_extended.py` | 71 | v1.0 Validator既存分(無改変) |
| `test_schema_validator_v1_1.py` | 23(新規) | version gating・6新規Widgetの正常系・異常系 |
| `test_mock_generator.py` | 33 | 既存9カテゴリ(無改変) |
| `test_mock_generator_v2.py` | 10(新規) | 家事/アンケート/メモ3カテゴリ・12カテゴリ一括検証 |
| `test_ai_foundation.py` | 5(新規) | IR型構築・Providerスタブの「正直な未実装」確認 |

### Dart(未実行、静的カウント165件)

| ファイル | 件数(静的) | 内容 |
|---|---|---|
| `smoke_test.dart` 他既存6件 | 30 | 既存(無改変) |
| `v1_1_widgets_test.dart`(新規) | 8 | 6新規Widgetの個別描画・操作・12種混在描画 |
| `mock_generation_datasource_v2_test.dart`(新規) | 19 | 家事/アンケート/メモ・12カテゴリ一括パース確認 |
| `mock_generator_renderer_contract_test.dart`(修正・拡張) | 99 | 11カテゴリ×9観点。**バグ修正済み(D36)** |

修正の詳細(D36): 契約テストが v1.1 Widgetノード型をswitch式に反映しておらず、
Dartのsealed class非網羅switchとしてコンパイルエラーになる状態だった。
全13派生型を網羅する形に修正し、対象を8→11カテゴリへ拡張、
checklist固有だった検証をテンプレート非依存(存在する場合のみ検証)へ変更し、
checkbox・form(submit_action)の検証を追加した。

---

## 8. flutter analyze結果

**未実施。** Claudeのサンドボックスに Dart SDK が無く、`flutter analyze`を
実行する手段が無い。今回追加・変更した約20ファイルについて、以下の
代替検証を実施した。

- 相対import・`package:forge_app/...`import(全ファイル): 機械チェックで0件破損。
- 中括弧・丸括弧の対応: 機械チェックで全ファイル一致。
- sealed class(`ForgeWidgetNode`)の switch/if 網羅性: 手動で全箇所を洗い出し、
  7章で報告した1件のバグを発見・修正した。
- 独自クラス・関数の定義-参照突合: 全件で定義箇所を確認(旧`withBuiltins()`の
  誤り(5章)もこの過程で発見・修正した)。

これらはFlutterの実際のAnalyzer(型検査・lintルール全体)を代替するものではない。
**`flutter analyze`が`No issues found!`になることを断定しない。**

---

## 9. flutter test結果

**未実施。** 7章の165件(静的カウント)がすべて合格するかどうかは、
CEO環境での`flutter test`実行でのみ確定する。**推測で合格と報告しない。**

---

## 10. CEO実機確認事項

```powershell
cd frontend
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter run -d chrome
```

Chrome起動後、Mock Modeのまま(Backend不要)で以下を確認してほしい
(依頼書「CEO実機確認」の指定通り)。

1. Home画面で以下のInspiration Cardから、それぞれ生成できること:
   - 🛒買い物(Checklist) / ✈️旅行(Checklist) / 🏠家事(Checklist、新規)
2. 「アンケートを作って」等、手入力でSurvey(Form Template)を生成し、
   質問への回答→送信→お礼画面への遷移まで確認すること(2画面構成)。
3. 「メモを作って」等、手入力でMemo Templateを生成し、見出し+自由入力欄が
   表示されることを確認すること。
4. いずれの生成でも、Consoleにエラーが出ないこと。
5. 7章で修正したcontract testが実際にコンパイル・合格することを確認すること
   (D36で発見したバグの実地確認)。

---

## 11. 未解決事項

| # | 内容 | 深刻度 |
|---|---|---|
| 1 | 今回追加した全コードが`flutter analyze`/`flutter test`/Chrome実機で未検証 | 高(最優先でCEO確認が必要) |
| 2 | Card Widgetの単独Categoryトリガーが無い(D33) | 低(将来の拡張点として記録済み) |
| 3 | AI Foundationは設計のみで、実際のPlanner/Repair Engineは1行も実装されていない(意図通り、PHASE6の指示に従った結果) | 情報共有のみ(次フェーズの前提) |
| 4 | Mock Generator(Python/Dart)の二重管理は継続(TECH_DEBT.md TD10)。今回12カテゴリへ拡張したことで管理対象がさらに増えた | 中 |
| 5 | 差分編集方式(JSON Patch vs Semantic Operation)は依然未決定(DECISIONS.md D4)。AI Foundationの`RepairEngine` Protocolも、この決定を前提にしていない抽象的な型のみ | 中(本物のRepair Engine実装前にCEO判断が必要) |
| 6 | Dartテスト件数(165件)は静的カウントであり、CEO環境での実行結果と一致する保証は無い | 高(9章と同じ) |

CEOに次に確認いただきたいのは、10章の実機確認と、上記1・6の解消
(実際の`flutter analyze`/`flutter test`結果の共有)である。
