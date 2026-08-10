# FORGE-RUNTIME-003 実施レポート — Infinite Width Button Constraint Fix

**Ref:** FORGE-RUNTIME-003　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11

CEO実機で得られた完全なスタックトレース(`BoxConstraints forces an infinite width`)
により、根本原因を確定できた。今回は前回(FORGE-RUNTIME-002)と異なり、
**推測ではなく確定した事実として**報告する。

---

## 1. 根本原因(確定)

`frontend/lib/core/theme/forge_theme.dart` の `elevatedButtonTheme` が、

```dart
minimumSize: const Size.fromHeight(56),
```

を指定していた。Flutter公式実装上、`Size.fromHeight(height)` は
`Size(double.infinity, height)` を返す(`Size.fromHeight(double height) : this(double.infinity, height);`)。
つまりアプリ全体の`ElevatedButton`は「最小幅=無限大、最小高さ=56」という
制約を暗黙に要求していた。

**なぜColumnでは問題が起きず、Rowでだけ「BoxConstraints forces an infinite width」に
なったか**(RenderFlexの主軸/交差軸の違い):

- `Row`の主軸(main axis)は横方向。RenderFlexは非flex(`Expanded`/`Flexible`を
  使っていない)子に対し、主軸方向は本来のサイズを測るためunboundedな制約を
  与える。Buttonの`minimumSize.width = infinity`という要求と、Row自身が
  与える「横方向unbounded」が組み合わさり、定義不能な制約になって
  `BoxConstraints forces an infinite width`で描画が失敗する。
- `Column`の主軸は縦方向。横方向はcross axisであり、`crossAxisAlignment`
  (既定は`center`)によって「0〜Columnの確定した横幅」という**有限の**
  loose制約になる。Buttonの無限幅要求はこの有限最大値へ単純にクランプされ、
  結果的に「全幅ボタン」に見えていた(たまたま安全な組み合わせだった)。

`ElevatedButton ← Row ← Column ← Padding ← SingleChildScrollView ← Scaffold`
というCEO報告のWidget構造は、Mock Generatorが出力する`add_row`
(text_field + button のRow)と完全に一致する。

**一次例外と二次例外の区別**: 最初に発生した例外は上記の
`BoxConstraints forces an infinite width`である。CEOが報告した以下の
エラー群は、いずれもこの一次例外が起きた後にレイアウト・描画パイプラインが
不整合な状態のまま処理を続けようとして生じる**二次障害**であり、
別々の原因ではない。

- `RenderBox was not laid out`(無限幅の制約でレイアウトが失敗したまま、
  後続の処理がそのRenderBoxを使おうとする)
- `Cannot hit test a render box that has never been laid out`
  (レイアウトされていないRenderBoxに対してタップ判定が走る)
- `mouse_tracker assertion` / `semantics assertion`(レイアウト未完了の
  RenderBoxに対して、マウス追跡やアクセシビリティ情報の更新が走る)
- `RenderTransform hasSize assertion`(サイズが確定していないRenderBoxを
  前提とする変換処理が失敗する)

したがって、一次例外(本節の無限幅制約)だけを修正すれば、二次障害群は
連鎖的に解消するはずである(ただし実機での確認が必要。9章参照)。

---

## 2. 修正内容

### 2.1 `core/theme/forge_theme.dart`(根本原因の修正)

```dart
// 修正前
minimumSize: const Size.fromHeight(56),
// 修正後
minimumSize: const Size(0, 56),
```

幅の最小値を`0`にすることで「無限幅を要求する」性質を除去した。高さは56を
維持している(禁止事項「Buttonの高さ48を失うこと」に対し、56は48を上回るため
問題ない。48という数値はCEOの例示であり、元のデザイン値56を尊重しそのまま残した)。

### 2.2 `features/app_generation/presentation/screens/home_screen.dart`(stretch責務の移動)

テーマ側の暗黙の全幅化が無くなったため、HomeScreenの送信ボタンだけ
明示的に全幅化した(Task 2の推奨パターンそのまま)。

```dart
SizedBox(
  width: double.infinity,
  child: ElevatedButton(
    onPressed: canSubmit ? _onSubmit : null,
    child: const Text('これで作る'),
  ),
),
```

`confirm_screen.dart`は元々`crossAxisAlignment: CrossAxisAlignment.stretch`を
使っており、Columnのcross-axis方向がtight制約になるため、Button自身の
`minimumSize`に関わらず安全に全幅になる。**コード変更は不要だった。**

### 2.3 Runtime側(`widget_registry.dart`)は無変更

`_buildButton`・`_buildRow`は今回変更していない。原因はテーマ(グローバル設定)
にあり、Runtimeのbutton/row組み立てロジック自体に問題は無かった。

---

## 3. Task 3: Forge Language上の幅指定propの有無

`shared/schemas/ui_schema.v1.json` の `widget_button` 定義を確認した。
`fullWidth`/`expand`/`stretch`/`width`/`size`いずれも存在しない
(`additionalProperties: false`、必須項目は`type`/`id`/`label`/`action`のみ)。

**指示書の方針通り、Language仕様への追加は行っていない。** 代わりに、
「明示指定が無い場合の安全なデフォルト」を「内容幅(content-sized)」に統一した。
これはRow・Column・ScrollViewのいずれの文脈でも安全に動作する
(2章・4章参照)。全幅にしたい場合は、呼び出し側(Screen固有のコード)で
`SizedBox`または`stretch`を使う、という責務分離にした。

---

## 4. Task 4: Renderer全体のInfinity監査

`frontend/lib/`全体を以下のパターンで検索した。

| 検索対象 | 結果 |
|---|---|
| `Size.fromHeight(` | `forge_theme.dart`の1箇所のみ(2章で修正済み) |
| `double.infinity` | 0件(修正後、コメント以外に無し) |
| `width: double.infinity` | `home_screen.dart`の1箇所(2.2節、意図的な全幅化) |
| `minWidth`/`maxWidth` | 0件 |
| `fixedSize`/`minimumSize`/`maximumSize` | `forge_theme.dart`の`minimumSize`のみ(修正済み) |

**同種の事故を起こしうる箇所は他に無かった。**

---

## 5. Task 7: FORGE-RUNTIME-002の3修正の整理

| 修正 | 今回の判断 |
|---|---|
| 内側Columnの`mainAxisSize: MainAxisSize.min` | **原因外**。非flex子のみのColumnは`mainAxisSize`に関わらずクラッシュしない。ベストプラクティスとして妥当なため維持する(付随改善) |
| ListTileへの`ValueKey`付与 | **原因外**。今回のクラッシュ(Button幅制約)とは無関係。動的リストのKey付与は一般的なFlutterのベストプラクティスであり維持する(付随改善) |
| `GestureDetector`→`IconButton`化 | **原因外**。leadingアイコンの実装であり、Button自体の幅制約とは無関係。標準的なMaterialウィジェットへの統一として妥当なため維持する(付随改善) |

3つとも無条件に元へ戻す必要は無いと判断し、そのまま維持した
(`docs/DECISIONS.md` D26追記・D29参照)。

---

## 6. 新規テスト(Task 5)

`test/json_ui/button_layout_regression_test.dart`(8件)。すべて`ForgeTheme.theme`を
明示的に適用した状態で検証する(既定のMaterialAppテーマでは今回のバグを
再現しないため、意味のあるテストにならない)。

1. Button単体
2. ButtonをColumn内へ配置
3. ButtonをRow内へ配置(**根本原因が実際に発生していた組み合わせ**)
4. ButtonをSingleChildScrollView内へ配置
5. Row→Column→ScrollViewの構造(`add_row`と同一の入れ子構造)
6. Buttonを複数個Row内へ配置
7. 800x600 viewport(`flutter test`の既定サイズ。明示指定不要であることを
   `tester.view.physicalSize`で確認する形にした)
8. 狭いviewport(320x600、`tester.view.physicalSize`で明示的に設定)

viewport操作には非推奨API(`tester.binding.window.physicalSizeTestValue`)では
なく、現行の`tester.view.physicalSize`を使用した(Web検索で確認)。

---

## 7. Task 6: 既存E2Eテストの静的確認

`test/e2e/kids_checklist_generation_flow_test.dart`は**削除・変更していない**。
このテストは`find.widgetWithText(ElevatedButton, 'これで作る')`等でボタンの
存在・タップ可能性のみを検証しており、ボタンの**幅**そのものをassertしていない
ため、2章の修正(見た目は変えず、達成方法だけを変更)による影響は無いと判断する。
このテストは生成画面(`add_row`を含む)の描画も経由するため、根本原因が
未修正だった場合はレイアウト例外で失敗していたはずであり、今回の修正の
妥当な回帰テストとしても機能する。

---

## 8. 実際に検証できたこと

- Python: 97件のValidator/Generatorテストを再実行し、合格を再確認。
- `frontend/lib/`全体のInfinity関連パターンをgrepで全件監査(4章)。
- `Size.fromHeight`の実装(`Size(double.infinity, height)`を返す)を
  Flutter公式ドキュメント相当の理解に基づき確認。
- Dartファイル(27ファイル、`lib/`+`test/`)の中括弧・丸括弧対応、import解決:
  機械チェックで問題0件。
- `tester.view.physicalSize`が非推奨API`window.physicalSizeTestValue`に
  代わる現行の正しいAPIであること、既定のテストviewportサイズが800x600で
  あることをWeb検索で確認。

---

## 9. 実際に検証できていないこと

| 項目 | 状態 |
|---|---|
| 修正後の`flutter analyze` | **未検証** |
| 修正後の`flutter test`(既存95件+新規8件=103件) | **未検証** |
| Chrome実機での修正確認(Generated Screenでチェックリストが表示されるか) | **未検証**。2章の修正が実際に不具合を解消するかは、CEO環境での再実行でしか確認できない |
| E2Eテスト(`kids_checklist_generation_flow_test.dart`)が実際に最後まで通るか | **未検証**(7章は静的な確認に留まる) |

---

## 10. 残る技術的負債

`TECH_DEBT.md`(TD1〜TD11)は変更していない。今回の修正はTD11
(レイアウト時例外の汎用的な保護が無い)そのものを解消するものではなく、
今回の具体的な原因(グローバルテーマの無限幅)を直接除去したものである。
TD11は引き続き有効な指摘として残る。

---

## 11. CEO再検証手順

```powershell
cd "C:\forge_verify\runtime003\forge\frontend"
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter run -d chrome
```

完了条件(指示書より):

- `flutter analyze`: `No issues found!`
- `flutter test`: `All tests passed!`(103件)
- Chrome実機: Home→Confirm→Generated Screen→チェックリスト表示→項目タップ成功
- 以下が一度も出ないこと: `BoxConstraints forces an infinite width` /
  `RenderBox was not laid out` / `Cannot hit test a render box that has
  never been laid out` / `RenderTransform hasSize assertion` /
  `mouse_tracker assertion` / `semantics assertion`

**もし今回の修正でも同様のエラーが出る場合**、`frontend/lib/`全体のInfinity監査
(4章)は完了しているため、新たな箇所である可能性は低いと考えているが、
念のため完全なスタックトレースを共有してほしい。
