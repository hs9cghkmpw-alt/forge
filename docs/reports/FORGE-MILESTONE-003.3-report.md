# FORGE-MILESTONE-003.3 実施レポート — add_item_regression_test.dart 誤検知修正

**Ref:** FORGE-MILESTONE-003.3　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-13

CEO実測(backend Python 192 PASS・forge_ai Python 80 PASS・`flutter analyze`
警告0・`flutter build web` PASS・Chrome起動PASS)を前提とする。今回の変更は
`frontend/test/json_ui/add_item_regression_test.dart`**のみ**。Runtime
コード・JSON生成・Mock Generatorは一切変更していない。

---

## 1. なぜ旧テストが誤っていたか

### 旧テストのコード

```dart
await tester.enterText(find.byType(TextField), '   ');
await tester.pump();
await tester.tap(find.widgetWithText(ElevatedButton, '追加'));
await tester.pump();

expect(find.text('   '), findsNothing);
```

### 誤りの構造

1. `ForgeStateStore.addChecklistItem()`は、source文字列をtrimして空なら
   `AddChecklistItemOutcome.emptySource`を返す。この場合、**チェックリストへの
   追加は行わないが、入力欄(source State)自体もクリアしない**
   (クリアするのは`added`の場合のみ、という既存仕様。
   `forge_state_store.dart`のコメント参照)。
2. そのため、`"   "`を入力して追加ボタンを押した**後も**、TextFieldの
   `EditableText`は`"   "`を表示し続ける。
3. Flutterの`find.text(String text)`は、静的な`Text`ウィジェットだけでなく、
   **`EditableText`(TextField/TextFormFieldの内部実装)の現在のテキストとも
   マッチする**、というFlutter Test Framework自体の仕様がある。
4. したがって`expect(find.text('   '), findsNothing)`は、「チェックリストに
   `"   "`という項目が追加されていないこと」を検証しているつもりが、
   実際には「画面のどこにも`"   "`というテキストが無いこと」を検証しており、
   **TextField自身が表示し続けている`"   "`にヒットして失敗する**。

Runtimeは`emptySource`を正しく返し、チェックリストへの追加も正しく
行っていない(CEO報告の通り)。**失敗していたのはテストの判定方法**であり、
Runtime・生成JSON・Mock Generatorのいずれにも問題は無い。

---

## 2. 修正内容(差分)

### 修正前

```dart
await tester.enterText(find.byType(TextField), '   ');
await tester.pump();
await tester.tap(find.widgetWithText(ElevatedButton, '追加'));
await tester.pump();

expect(find.text('   '), findsNothing);
expect(tester.takeException(), isNull);
```

### 修正後

```dart
final listTileCountBefore = find.byType(ListTile).evaluate().length;
expect(listTileCountBefore, 4, reason: '操作前のチェックリスト項目数は4件のはず');

await tester.enterText(find.byType(TextField), '   ');
await tester.pump();
await tester.tap(find.widgetWithText(ElevatedButton, '追加'));
await tester.pump();

final listTileCountAfter = find.byType(ListTile).evaluate().length;
expect(
  listTileCountAfter,
  listTileCountBefore,
  reason: '空白のみの入力ではチェックリスト項目が増えないはず(trim判定によりemptySource扱いになる)',
);

const expectedItemTexts = <String>['今月の収入を記録する', '固定費を確認する', '今日の支出を記録する', '来月の予算を立てる'];
for (final expectedText in expectedItemTexts) {
  expect(
    find.descendant(of: find.byType(ListTile), matching: find.text(expectedText)),
    findsOneWidget,
    reason: '項目「$expectedText」が壊れずに残っているはず',
  );
}

expect(tester.takeException(), isNull);
```

### 修正方針の説明

- **チェックリスト項目数(`ListTile`の件数)を操作の前後で比較する形へ変更した。**
  `ListTile`は本Repository内で唯一、checklist Widgetのみが使用するため
  (`grep`で確認済み、`widget_registry.dart`の1箇所のみ)、この件数は
  「チェックリスト項目数」と一対一に対応する。`TextField`(`EditableText`)は
  `ListTile`の子孫ではないため、この判定方法は入力欄の内容と混同しない。
- CEOが提示した候補(ListTile数・CheckboxListTile数・items.length・
  StateStore内容)のうち、**ListTile数**を採用した。`items.length`・
  StateStore内容は、`ForgeRuntimeState`/`ForgeStateStore`がWidget Test側から
  直接参照できるAPIとして公開されていない(`_ForgeScreenViewState`内部の
  privateフィールド)ため、Runtimeへ新しいテスト用の公開APIを追加しない限り
  使えない。「Runtimeコードは変更禁止」という条件のもと、ウィジェット構造から
  判定できるListTile数を選んだ。
- 追加で、元の4項目それぞれが`ListTile`の子孫として存在することも
  `find.descendant()`で確認するようにした(項目の中身自体が壊れていないことの
  追加確認。この4つの項目テキストは`"   "`と異なるため今回のバグの再発では
  ないが、同じ安全な検索方法へ統一した)。

---

## 3. 影響範囲の確認

- 変更したのは`add_item_regression_test.dart`の3番目の`testWidgets`ブロックのみ。
  同ファイル内の他3つのテスト、および他のテストファイルは変更していない。
- Runtimeコード(`forge_state_store.dart`・`forge_action_dispatcher.dart`等)・
  Mock Generator(Python/Dart)・Forge Language Schemaは一切変更していない。
- `flutter analyze`/`flutter build web`に影響する変更(import追加・型変更等)は
  無い(既存のimportのみを使用。`ListTile`は`package:flutter/material.dart`
  経由で既にimport済み)。

---

## 4. 検証できたこと・できていないこと

| 項目 | 状態 |
|---|---|
| ソースコードの静的レビュー(import解決・括弧の対応・型の整合性) | ✅ 実施済み、問題無し |
| `ListTile`がchecklist Widget以外で使われていないことの確認 | ✅ `grep`で全文検索し確認済み(1箇所のみ) |
| `flutter test`の実際の実行 | **未実施**。Claude環境にDart SDKが無いため |

**ご指示の通り、Pythonの再実行、`flutter analyze`/`flutter build web`の
再実行は行っていません。** CEO環境での`flutter test`実行結果をお待ちします。

---

## CEO再検証手順

```powershell
cd "C:\forge_verify\<展開先>\forge\frontend"
flutter test --reporter expanded
```

または`.\scripts\verify.ps1 -SkipPython -SkipBuild`でも同等の確認ができる
(Python・Web Buildをスキップし、analyze/testのみ実行)。
