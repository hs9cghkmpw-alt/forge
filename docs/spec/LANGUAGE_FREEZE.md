# Forge Language — Freeze & Versioning Policy

FORGE-MERGE-002 Task 5。Forge Languageを「今後数年変更しない土台」として扱うための
バージョニング方針を定義する。対象は`shared/schemas/ui_schema.v1.json`と、それに
対応する`backend/app/ai/validators/schema_validator.py`。

---

## 1. 現在のFreeze状況(事実)

**v1はまだFreeze宣言できる状態ではない。** 以下がFreeze条件(2章)であり、
現時点の充足状況を偽らず記す。

| 条件 | 状況 |
|---|---|
| Validatorが全Widget/Action/State型を正常系・異常系両方でカバーしている | **充足**(97件、FORGE-MERGE-002 Task 4) |
| 少なくとも1つの実Runtime実装が`flutter analyze` エラー0件でビルドできる | **未充足**(Dart SDKが無い環境で実装されたため未検証。Test Report参照) |
| 少なくとも1つの実Runtime実装が全Widget種別を実際に描画できることを確認済み | **未充足**(同上) |
| Widget/Action/Stateの「形」を変える必要がある既知の未解決課題が無い | **一部未充足**(3.4節: `string_list`型を消費するWidgetが存在しない、という設計上の空白が残っている) |

したがって本ドキュメントは「Freezeする」という宣言ではなく、**Freezeする際に
従うべき規約**として先に整備する。実際のFreeze宣言は、CEO環境での
`flutter analyze`/`flutter test`確認(Immediate Next Task)が完了し、
3.4節の`string_list`の扱いが決定してから行う。

---

## 2. Freeze条件(今後、v1確定を宣言する基準)

1. Validator: 正常系・異常系のテストが全Widget(6)・全Action(4)・全State型(4)を
   最低1件ずつカバーしている。
2. Runtime: 少なくとも1つの実装(現状はFlutter/Dart)が対象環境で
   `flutter analyze`エラー0件、全Widget種別の描画テストに合格している。
3. Mock Generatorまたは実AIが、少なくとも数種類の現実的な入力から
   Validator合格文書を生成できることを確認済み。
4. 既知のスキーマ設計上の空白(3.4節参照)について、少なくとも方針が
   決まっている(実装は後回しでもよいが「保留」であることが明記されている)。

この4条件が揃った時点でFreeze宣言し、本ドキュメントの3章以降の規約が
正式に発効する。

---

## 3. バージョン区分の定義

Forge Languageのバージョン文字列(`version`フィールド)は`"MAJOR.MINOR"`とする
(現在は`"1.0"`。Patchレベルの変更はドキュメント上の管理のみとし、`version`
文字列自体は変えない。理由: Validatorの`version_const`検査は完全一致であり、
Patchのたびに全既存文書が検証エラーになるのは本末転倒なため)。

### 3.1 Breaking Change(MAJOR、例: 1.x → 2.0)

以下のいずれかに該当する変更。

- 既存Widget/Action/Stateの必須フィールドを削除・改名する。
- 既存フィールドの型を変更する(例: `value`をstringからobjectへ)。
- 既存の列挙値(`style`の`title`/`body`/`caption`等)を削除する。
- 検証の上限値を**厳しくする**方向に変更する(例: `MAX_NESTING_DEPTH`を12→8)。
  既存の合格文書が新バージョンで不合格になりうるため。
- Widget/Actionの意味(挙動)を変更する(例: `add_item`が末尾追加ではなく
  先頭追加になる)。

### 3.2 Minor(例: 1.0 → 1.1)

以下のいずれかに該当し、**かつ**既存の全合格文書が新バージョンでも
合格し続ける変更。

- 新しいWidget/Action/State型を追加する。
- 既存Widget/Action/Stateへ新しい**オプショナル**フィールドを追加する。
- 検証の上限値を**緩める**方向に変更する(例: `MAX_SCREENS`を20→30)。

Minorの追加によって生じる非対称性(4章)を必ず理解した上で行うこと:
新バージョンの文書を、更新していない旧Runtimeに渡すと、Fallback表示
(`ForgeFallbackWidget`)になる。これはクラッシュではなく想定内の劣化として
許容する(方針12章)。

### 3.3 Patch

- Validatorのバグ修正(仕様上は不正なはずの文書が誤って合格していた/
  仕様上は合格すべき文書が誤って不合格になっていたものを直す)。
- エラーメッセージ・ドキュメントの改善。
- `version`文字列は変更しない。

---

## 4. Backward Compatibilityの保証内容

**保証すること**: v1.0で合格した文書は、将来のすべてのv1.xでも合格し続ける
(3.2節Minorの定義そのもの)。

**保証しないこと**: v1.xの新機能を使った文書が、より古いv1.0時点のValidator/
Runtimeで動くこと(Validatorは`unknown_widget`/`unknown_action`等で拒否し、
Runtimeは`ForgeFallbackWidget`で劣化表示する。いずれも安全側に倒れるため、
「動かないこと」自体は許容し、「クラッシュすること」だけを禁止する)。

---

## 5. Migration(MAJOR間の移行)

v2以降を作る場合、以下を最低限用意すること(v1時点では未着手・v2は今回のスコープ外)。

1. **Validatorのバージョン分岐**: 現在の`_check_schema()`は`version == "1.0"`を
   固定で要求しており、複数バージョンを同時に検証できない。v2を作る時点で、
   `version`の値に応じて検証ロジックを分岐させる(または`validators/v1.py`・
   `validators/v2.py`のようにファイルごと分離する)リファクタリングが必要になる
   ことをあらかじめ記録しておく。
2. **移行ユーティリティ**: 可能な範囲でv1文書をv2形状へ自動変換するスクリプトを
   用意する(全項目が自動移行できるとは限らない。手動移行が必要な差分は
   一覧化する)。
3. **並行運用期間**: v1文書を持つ既存ユーザーが、v2 Runtimeへ強制的に
   移行させられることが無いよう、最低1 Minorサイクルはv1 Validatorも
   稼働させ続ける。

---

## 6. Deprecation(非推奨化)

フィールド・Widget・Actionを削除する場合、以下の手順を踏む。

1. 対象を「Deprecated」として本ドキュメントの7章に追記し、代替手段を明記する。
2. Deprecated化した時点のMinorから数えて、最低1 Minorサイクルは
   Validatorが引き続き合格させる(警告(`severity: warning`)を出してよい)。
3. 次のMAJORで初めて削除してよい。

現時点でDeprecatedな項目は無い。

---

## 7. 既知の設計上の空白(Freeze前に方針だけ決めておくべき事項)

### 7.1 `string_list` State型を消費するWidgetが存在しない

`shared/schemas/ui_schema.v1.json`には`string_list`型のStateを定義できるが、
v1の6 Widget種別(`text`/`text_field`/`button`/`column`/`row`/`checklist`)の
どれもこれを表示・編集する手段を持たない。宣言はできるが誰も使えない状態。

今回はWidget追加が禁止されているため実装では対応しないが、方針だけ決めておく。
**選択肢は2つ**:

- (a) 将来Widgetを追加する際、`string_list`表示用Widget(例: タグ表示、
  シンプルな箇条書き)を追加し、この空白を埋める。
- (b) 実際に使われる見込みが無いなら、次のMinorで`string_list`をDeprecated化し、
  次のMajorで削除する。

**推奨**: (a)。Mock Generator/将来のAIが「タグ」「カテゴリ一覧」のような
軽量な文字列リストを表現したくなる場面は具体的に想像でき、`checklist`ほど
重い(done状態を持つ)Widgetを使わせるのは過剰である可能性が高い。ただし
これはCEO確認事項として次フェーズ提案に含める(実施レポート参照)。
