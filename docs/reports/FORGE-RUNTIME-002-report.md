# FORGE-RUNTIME-002 実施レポート — Generated Screen Rendering Fix & Navigation E2E Verification

**Ref:** FORGE-RUNTIME-002　**担当:** Principal Engineer / Architect（Claude）　**日付:** 2026-07-11

CEO実機での確認結果(Mock Modeナビゲーション成功、Generated Screen本文が空白、
RenderBox関連の例外らしきログ)を唯一の事実として扱う。完全なスタックトレースは
共有されていないため、根本原因を1つに断定はしない。

---

## 1. 根本原因

**断定はできない。以下を優先順位付きの判断として報告する。**

完全なスタックトレース(どのファイル・どの行で例外が発生したか)が共有されて
いないため、「これが原因である」と断定することはできない。ただし、以下は
実際にコードを追跡して確認した事実である。

- JSON生成・パース・State格納の各段階(3章)を実際に追跡した結果、
  **チェックリスト項目のデータは一切失われていない**(5項目とも最後まで
  保持されている)。したがって原因はデータ層ではなく、描画(レイアウト/
  hit-test)層にあると判断した。
- Renderer全体で「チェックリスト部分」だけが、他と比べて明確に非標準的な
  実装だった: `AnimatedBuilder`による動的リスト構築、Key無しの`ListTile`、
  `GestureDetector`で素の`Icon`を包む(他の場所では`IconButton`を使っている
  のに、ここだけ違う実装だった)、内側`Column`の`mainAxisSize`が外側と
  不整合(外側は`min`明示、内側は既定値の`max`のまま)。
- 「hit test a render box that has never been laid out」というエラーメッセージは、
  一般にジェスチャー検出Widget(タップ判定を行うWidget)まわりの実装不整合で
  発生することが多い、という一般的な傾向がある(Web検索で確認した実例には、
  今回と完全一致する事例は無かった)。

これらを踏まえ、**最も疑わしい3箇所**を特定し、根本原因を1つに絞れないまま
3点まとめて修正した(5章)。原因の完全な特定には、CEO環境での完全な
スタックトレース(またはブラウザのDevTools Consoleの全文)が必要であり、
これを次回の最優先確認事項とする(12章)。

---

## 2. 実際の生成JSON

「子どもの持ち物チェックを作って」を、実際にPython Mock Generator
(Dart版と機械比較で完全一致を確認済み。8章参照)を実行して取得したもの。
省略せず全文を掲載する。

```json
{
  "version": "1.0",
  "app": {
    "title": "子どもの持ち物チェック"
  },
  "initial_screen_id": "generated_screen",
  "screens": [
    {
      "id": "generated_screen",
      "title": "子どもの持ち物チェック",
      "state": {
        "new_item_text": {
          "type": "string",
          "value": ""
        },
        "items": {
          "type": "checklist",
          "value": [
            { "id": "item_1", "text": "着替え", "done": false },
            { "id": "item_2", "text": "オムツ", "done": false },
            { "id": "item_3", "text": "水筒", "done": false },
            { "id": "item_4", "text": "タオル", "done": false },
            { "id": "item_5", "text": "お気に入りのおもちゃ", "done": false }
          ]
        }
      },
      "body": {
        "type": "column",
        "id": "root_column",
        "children": [
          {
            "type": "checklist",
            "id": "list_view",
            "state_ref": "items",
            "empty_state_text": "アイテムはまだないよ"
          },
          {
            "type": "row",
            "id": "add_row",
            "children": [
              {
                "type": "text_field",
                "id": "add_field",
                "state_ref": "new_item_text",
                "placeholder": "アイテムを追加"
              },
              {
                "type": "button",
                "id": "add_button",
                "label": "追加",
                "action": {
                  "type": "add_item",
                  "target_state_ref": "items",
                  "source_state_ref": "new_item_text"
                }
              }
            ]
          }
        ]
      }
    }
  ]
}
```

**この文書は、実際にPython Validatorで検証し合格することを確認済み**
(`valid: True`, `errors: []`)。checklist項目は5件、いずれも空配列になっていない。

---

## 3. データが失われていた段階

**結論: どの段階でも失われていない。** Task 2で指定された7段階のうち、
実行して確認できた段階と、コード追跡のみで確認した段階を分けて報告する。

| # | 段階 | 確認方法 | item数 |
|---|---|---|---|
| 1 | Mock Generator生成直後 | **実行して確認**(Python版。Dart版は構造が機械比較で完全一致と確認済みのため同一と判断) | 5 |
| 2 | Repository返却直前 | コード追跡(`MockAppGenerationRepository.generate()`は`_dataSource.generate()`の戻り値をそのまま返すのみで加工していない) | 5(変化なし) |
| 3 | `ForgeDocument.fromJson`直後 | コード追跡(`ForgeStateValue.fromJson`のchecklist分岐は`rawItems.asMap().entries.map(...)`で全件変換しており、フィルタや先頭要素だけ取る処理は無い) | 5(変化なし) |
| 4 | Confirm画面受け取り時 | 該当なし(Confirm画面はJSONを受け取らない。テキストのみを次画面へ渡す設計) | - |
| 5 | Rendererへ渡す直前 | コード追跡(`GeneratedAppScreen`は`document`を`ForgeDocumentView(rawJson: document)`へそのまま渡すのみ) | 5(変化なし) |
| 6 | Registryで該当Widget解決時 | コード追跡(`checklist`typeは`_buildChecklist`へ正しく解決される。type名の不一致は無い、8章の機械比較で確認) | 5(変化なし) |
| 7 | 各Widget Builderへchildren/props | コード追跡(`_buildChecklist`は`state.getChecklist(n.stateRef)`でState全件を取得しており、途中でのフィルタ・truncateは無い) | 5(変化なし) |

**したがって、「本文が空白」だった原因はデータ消失ではなく、5件のデータが
正しく`Column`+`ListTile`のWidgetツリーとして構築された"後"、それが
画面に実際に描画される段階(レイアウト/hit-test)で問題が起きていたと判断する。**

---

## 4. 修正ファイル一覧

| ファイル | 変更内容 |
|---|---|
| `frontend/lib/json_ui/widget_registry/widget_registry.dart` | `_buildChecklist`の3点修正(5章) |
| `frontend/test/e2e/kids_checklist_generation_flow_test.dart` | 新規(7章) |
| `frontend/test/features/app_generation/data/datasources/mock_generator_renderer_contract_test.dart` | 新規(8章) |
| `docs/spec/MOCK_GENERATOR_CONTRACT.md` | 新規(8章) |
| `TECH_DEBT.md` | TD10更新(解消済みにはしていない)・TD11新規追加(11章) |
| `docs/DECISIONS.md` | D26〜D28追加 |
| `docs/tasks/task009.md` | 新規 |
| `CHANGELOG.md` | Task009エントリ追加 |

---

## 5. 修正前・修正後

`frontend/lib/json_ui/widget_registry/widget_registry.dart` の `_buildChecklist` 内、
チェックリスト項目が1件以上ある場合の描画部分。

**修正前:**
```dart
return Column(
  children: [
    for (final item in items)
      ListTile(
        leading: GestureDetector(
          onTap: () => state.toggleChecklistItem(n.stateRef, item.id),
          child: Icon(item.done ? Icons.check_circle_rounded : Icons.circle_outlined),
        ),
        title: Text(
          item.text,
          style: TextStyle(decoration: item.done ? TextDecoration.lineThrough : null),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.close_rounded, size: 18),
          onPressed: () => state.deleteChecklistItem(n.stateRef, item.id),
        ),
      ),
  ],
);
```

**修正後:**
```dart
return Column(
  mainAxisSize: MainAxisSize.min, // (1) 外側Columnとの不整合を解消
  children: [
    for (final item in items)
      ListTile(
        key: ValueKey('checklist_item_${item.id}'), // (2) 安定したKeyを付与
        leading: IconButton( // (3) GestureDetector+Icon から IconButton へ統一
          icon: Icon(item.done ? Icons.check_circle_rounded : Icons.circle_outlined),
          onPressed: () => state.toggleChecklistItem(n.stateRef, item.id),
        ),
        title: Text(
          item.text,
          style: TextStyle(decoration: item.done ? TextDecoration.lineThrough : null),
        ),
        trailing: IconButton(
          icon: const Icon(Icons.close_rounded, size: 18),
          onPressed: () => state.deleteChecklistItem(n.stateRef, item.id),
        ),
      ),
  ],
);
```

各修正の個別の根拠:

1. **`mainAxisSize: MainAxisSize.min`**: 外側の`_buildColumn`(root_column用)は
   既にこれを明示している。`SingleChildScrollView`配下という高さ無制限の
   文脈で、内側だけ既定値(`max`)のままなのは一貫性を欠いており、
   Flutterのベストプラクティス(スクロール可能領域内のColumnは`min`を
   明示するのが定石)にも反していた。
2. **`ValueKey`**: チェック/追加/削除で要素数が変わりうるリストにKeyが
   無いのは、Flutter公式ドキュメントでも明確に非推奨とされているパターン。
   `item.id`という安定した識別子が既に存在するため、それをそのまま使った。
3. **`IconButton`化**: 同じListTile内のtrailing(削除ボタン)は元々`IconButton`で
   実装されており、動作報告上の問題は出ていなかった。leadingだけが
   `GestureDetector`+素の`Icon`という、リポジトリ内で唯一の非標準的な
   組み合わせだった。「hit test」関連のエラーが一般にジェスチャー検出
   Widgetまわりで起きやすいことを踏まえ、実績のある実装パターンへ統一した。

---

## 6. Rendererへの影響

- 変更は`_buildChecklist`関数の内部のみ。関数シグネチャ・呼び出し方法・
  Registry登録方法は変更していない。
- 見た目(視覚的なデザイン)は変更していない。leading/trailingとも
  「丸いアイコンをタップする」という操作感は同じ(IconButtonは標準で
  タップ範囲を確保するため、むしろタップしやすくなる可能性がある)。
- 他の5 Widget種(text/text_field/button/column/row)の実装は変更していない。
- Registry登録・type解決ロジック(`buildForgeWidget`)は変更していない。

---

## 7. 新規テスト一覧

### `test/e2e/kids_checklist_generation_flow_test.dart`(1件、E2E相当)

Home画面起動 → 「子ども」カードタップ → 入力欄確認 → 「これで作る」→
Confirm画面 → 入力内容確認 → 「この内容で作ります」→ (人工遅延を明示的に
`pump`で進める) → Generated Screen表示確認 → チェックリスト5項目の表示確認 →
最初の項目(item_1)をタップ → チェック状態変化の確認 → 例外0件の確認、を
1つのテストで通す。

実装上の注意: ローディング中に`CircularProgressIndicator`(無期限アニメーション)
が表示されるため、その区間では`pumpAndSettle()`を使わず、`pump(Duration)`で
明示的に時間を進めている(`pumpAndSettle()`は無期限アニメーション中は
タイムアウトするため)。

使用文字列('確認'・'これで作る'・'この内容で作ります'・'子ども'・
5項目のテキスト等)は、すべて実際のソースファイルとプログラムで
突き合わせ、1文字も違わないことを確認済み。

### `test/.../mock_generator_renderer_contract_test.dart`(8カテゴリ×8観点=64件)

8章で詳述。

---

## 8. 8カテゴリ契約テスト結果

`docs/spec/MOCK_GENERATOR_CONTRACT.md`を新設し、以下を実施した。

### Python版とDart版の機械比較(実際に実行して比較)

Python側は`_CATEGORIES`を実際にimportして値を取得し、Dart側はソースコードを
正規表現で解析して`MockCategory(...)`ブロックを抽出、9カテゴリ全件について
キーワード・タイトル・アイテムをフィールド単位で比較した。

**結果: 9カテゴリ全件、完全一致。差分0件。**(実行結果。推測ではない)

### 8カテゴリ×8観点のRenderer契約テスト(Dart、未実行)

各カテゴリについて以下8項目を検証するテストを新設した(実行はできていない)。

1. `ForgeDocument.fromJson`が成功しrootが存在する
2. bodyのchildrenが空でない
3. 使用されている全Widget typeがRegistryに登録済み(6種類の範囲内)
4. Widget IDがドキュメント内で重複しない
5. checklist Widgetのstate_refが実在するchecklist型stateを指している
6. add_itemのtarget/source_state_refが両方とも実在するstateを指している
7. 表示可能な主要コンテンツ(チェックリスト項目)が1件以上存在する
8. チェックリスト項目のIDが重複しない

8カテゴリ×8項目=64件。Registry登録type一覧(`text`/`text_field`/`button`/
`column`/`row`/`checklist`)は、`widget_registry.dart`の実装と手動で
同期させたものであり(private APIのため直接参照できないため)、
この同期がずれていないことは目視で確認した。

---

## 9. 実際に検証できたこと

- Python: 97件のValidator/Generatorテストを再実行し、合格を再確認。
- Python Mock Generatorを実際に実行し、「子どもの持ち物チェック」の
  実JSON(5項目)を取得、Validatorで合格することを確認(2章)。
- Python版・Dart版Mock Generatorの9カテゴリを実際にプログラムで機械比較し、
  差分0件を確認(8章)。
- Dartファイル(26ファイル、`lib/`+`test/`)の中括弧・丸括弧対応、
  `package:forge_app/...`import解決: 機械チェックで問題0件。
- 新規E2Eテストで使用する全文字列(画面タイトル・ボタンラベル・
  チェックリスト項目テキスト)を、実際のソースファイルとプログラムで
  1文字単位まで突き合わせ、完全一致を確認。
- Task 4で指定された各種レイアウト誤用パターン(`Expanded`をFlex外で使用・
  `ListView`・`Flexible`・`Positioned`・`LayoutBuilder`・`Offstage`/
  `Visibility`・`Stack`)について、リポジトリ全体をgrepで監査し、
  `Expanded`は2箇所とも正しくRow内で使われていること、他のWidgetは
  そもそも使われていないことを確認。
- データ消失箇所の切り分け(3章): JSON生成からRenderer直前まで、
  コード追跡により5項目が失われていないことを確認。

---

## 10. 検証できていないこと

| 項目 | 状態 |
|---|---|
| 修正後の`flutter analyze` | **未検証** |
| 修正後の`flutter test`(既存30件+新規65件=95件) | **未検証** |
| Chrome実機での修正確認(チェックリストが実際に表示されるか) | **未検証**。今回の修正が実際に不具合を解消するかは、CEO環境での再実行でしか確認できない |
| RenderBox例外の完全なスタックトレースとの突き合わせ | **未実施**(共有されていないため)。1章の根本原因判断はこの情報が無い状態での最善の推測である |
| E2Eテストのタイミング(`pump`の秒数指定)が実機と一致するか | **未検証**。650msの人工遅延に対し700ms分`pump`しているが、実際のCI/実機環境での余裕は未確認 |

---

## 11. 残る技術的負債

`TECH_DEBT.md`(TD1〜TD11)。今回追加したのはTD11
(Rendererの例外保護が構築時のみでレイアウト時例外を捕まえない)。
TD10(Python/Dart二重管理)は、8章の機械比較により差分が無いことは
確認したが、**解消済みとは扱っていない**(指示書の禁止事項に従う)。

優先度が高いと考えるもの:
1. **1章の根本原因の完全特定**: 完全なスタックトレースが得られ次第、
   3点修正のうちどれが(あるいは複合要因か)実際の原因だったかを確定させる。
2. **TD11**: 将来Widgetが追加されるタイミングで、レイアウト時例外の
   汎用的な保護(`ErrorWidget.builder`等)を検討する。

---

## 12. CEO再検証手順

```powershell
cd "C:\forge_verify\runtime002\forge\frontend"
flutter clean
flutter pub get
flutter analyze
flutter test --reporter expanded
flutter run -d chrome
```

Chrome起動後、Task検証環境の「CEO実機確認項目」17項目を再確認してほしい。
特に以下を優先で見てほしい。

1. 「子ども」カードから生成した画面で、チェックリスト項目(着替え・オムツ・
   水筒・タオル・お気に入りのおもちゃ)が実際に表示されるか。
2. 項目をタップしてチェック状態が変わるか。
3. Console(ブラウザDevTools)に「Cannot hit test...」等のエラーが
   出ていないか。

**もし今回の修正でも本文が空白のままの場合**、ブラウザのDevTools Console
(F12)に出ている**エラーメッセージの全文とスタックトレース**を共有してほしい。
1章で述べた通り、これが無いままでは根本原因の完全な特定ができない。
