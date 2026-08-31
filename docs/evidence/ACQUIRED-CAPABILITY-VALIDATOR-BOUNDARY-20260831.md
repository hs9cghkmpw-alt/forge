# 020F Evidence — 獲得した Capability は Validator まで届く / Dart にはまだ届かない

作成: 2026-08-31
Branch: `claude/forge-master-handoff-k46jns`
検証時の Git HEAD: `05c2c60f80c9ae8c99a423bd193a937c30bac33f`（この commit の親）

> 用語: **Validator**（生成物を検査する仕組み） /
> **PROMOTED**（Evidence Gate を通って獲得済みと認められた能力） /
> **activation**（実際にビルドして載せた runtime の実体） /
> **fail-open**（分からないものを「通す」側へ倒すこと。禁止） /
> **配線破壊試験**（配線を1本ずつ外して、対応するテストが落ちるか確かめる）。

---

## 1. 何を閉じたか / 何を閉じていないか

CEO 指示の最優先項目は
**「acquired capability → Validator → real Flutter/Dart runtime」** の closure である。
この鎖のうち、**閉じたのは前半だけ**である。後半は閉じていない。

| 区間 | 状態 | 根拠 |
|---|---|---|
| acquired capability → Validator | **CLOSED** | `tests/test_forge_020f_runtime_attested_widgets.py`（14 tests）+ 配線破壊 9 件 |
| Validator → real Flutter/Dart runtime | **NOT CLOSED** | `test/json_ui/widget_registry/acquired_widget_runtime_boundary_test.dart`（4 tests、実 Flutter で実行） |

**この文書は「Flutter runtime まで閉じた」という主張ではない。**
後半が未達であることを、推測ではなく**実行したテストの結果**として記録する。

---

## 2. 前半（Validator）で何を変えたか

### 2.1 これまでの詰まり

Validator の許可 widget は**版ごとの固定表**だった。

```python
WIDGET_TYPES_V1_16_ADDITIONS = {"map_view"}
```

人が書き足す表なので、Self-Extension で獲得した能力の widget は
**永久に「未知の widget」として弾かれる**。獲得しても検査を通れない。

### 2.2 しかし「宣言したから通す」にはしない

そこを緩めると、**Dart（実際に描く側）が知らない widget を通してしまう。**
Validator は通るのに実行時に描けない。これが fail-open である。

`backend/app/ai/validators/runtime_attested_widgets.py` は、通す条件を
**2つとも**要求する。

| 条件 | 意味 |
|---|---|
| PROMOTED である | Evidence Gate を通って獲得済み |
| **loaded な BUILD_TIME activation を持つ** | **新しい runtime が実際にビルドされ、載っている** |

* `requested`（利用者が欲しいと言っただけ）では**広がらない**
* `DECLARATIVE` な獲得でも**広がらない**（既存 widget の組み替えであり、新しい型を持ち込まない）
* 何も獲得していなければ**空集合**。`forge_ai` が読めない環境でも**空集合**
* 版ごとの出荷表 `WIDGET_TYPES_BY_VERSION` は**書き換えない**（他の検査へ漏れない）

`install` 時に Registry 側も同じ条件を見ているが、
Validator は**その時点の事実を見直す**（install 後に activation が降ろされた／
壊れた場合に、語彙が開いたままにならないようにするため）。

### 2.3 見つけた実バグ

`_check_widget_schema` は `WIDGET_TYPES_ALL`（全版の出荷型の和）を
**先に**見ていたため、獲得した型は `allowed_widgets` に足しても
その手前で `unknown_widget` として落ちていた。判定順を

1. `allowed_widgets` にあれば通す
2. なければ `WIDGET_TYPES_ALL` にあるか見て `widget_not_allowed_in_version`
3. どちらでもなければ `unknown_widget`

へ直した。出荷型に対する挙動は従来と同じである
（従来 `allowed_widgets ⊆ WIDGET_TYPES_ALL` だったため）。

---

## 3. 配線破壊試験（9件すべて検出された）

ログ: `logs/forge-020f-guard-break-20260831.log`

| # | 外した配線 | 結果 | 落ちたテスト |
|---|---|---|---|
| B1 | 両方の呼び出し箇所から `| runtime_attested_widget_types()` を削除 | DETECTED | `test_the_document_now_validates` |
| B2 | unknown/allowed の判定順を元へ戻す | DETECTED | `test_the_document_now_validates` |
| B3 | `BUILD_TIME` route 条件を削除 | DETECTED | `test_a_declarative_promotion_does_not_open_it` |
| B4 | `loaded` 再確認を削除 | DETECTED | `test_a_runtime_that_was_unloaded_stops_being_attested` |
| B5 | `build_id` 再確認を削除 | DETECTED | `test_a_lost_build_id_stops_being_attested` |
| B6 | `runtime_fingerprint` 再確認を削除 | DETECTED | `test_a_lost_runtime_fingerprint_stops_being_attested` |
| B7 | 能力 identity 再確認を削除 | DETECTED | `test_an_activation_for_another_capability_stops_being_attested` |
| B8 | 出力宣言の要求を外し、型名を推測で作る | DETECTED（6 failed） | 上記ほか |
| B9 | 既定を fail-open にする | DETECTED（9 failed） | 上記ほか |

**置物テストは無い。** 初回は B4〜B7 に対応するテストが存在せず素通りしたため、
install 後に activation を壊す test class を追加してから再測した。

---

## 4. 後半（Dart）— 実行して確かめた「まだ描けない」事実

`frontend/test/json_ui/widget_registry/acquired_widget_runtime_boundary_test.dart`
を**実 Flutter** で実行した結果、現在の Dart 側は次のとおりである。

1. 未知の型は例外にならず `ForgeUnknownWidgetNode`（型名は保持）になる
2. 出荷済み Registry は獲得能力の型を知らない
3. Renderer は `ForgeFallbackWidget` へ倒す — **描かれない**
4. **Registry へ後から登録しても描かれない**

4 が重要である。`ForgeWidgetNode.fromJson` の `switch` が
先に `ForgeUnknownWidgetNode` へ倒し、`buildForgeWidget` は
Registry を引く前にそこで短絡する。つまり

> **Dart 側の拡張点は Registry ではなく Parser 側にある。**

Registry だけを拡張点だと思って作業すると必ず外す。これは次のセッションが
最初に踏む穴なので、テストとして固定した。

### 4.1 併せて記録する懸念（未修正）

`ForgeFallbackWidget` は release build では `SizedBox.shrink()` を返す
（`kDebugMode` 分岐）。描けない widget が**無言で消える**。
これは既存の製品方針（方針12章）であり、今回勝手に変えない。
`TECH_DEBT.md` へ記録し、判断を仰ぐ。

---

## 5. 実行したコマンドと結果

```text
$ cd backend  && python -m pytest tests -q
1998 passed, 16 skipped, 1 warning in 29.58s

$ cd forge_ai && python -m pytest tests -q
717 passed in 2.51s

$ ruff check backend/app/ai/validators/
All checks passed!

$ cd frontend && flutter analyze
No issues found!

$ cd frontend && flutter test test/json_ui/widget_registry/acquired_widget_runtime_boundary_test.dart
00:00 +4: All tests passed!

$ cd frontend && flutter test
00:37 +550: All tests passed!   # 546 → 550（今回の4件を追加）
```

Flutter は `/opt/flutter/bin/flutter`（この Linux 実行ホスト）。
ぱすとらる PC (Windows) の Puro（Flutter のバージョン管理ツール）問題は
**このホストでは再現しない**ため、依然として未解決である。

---

## 6. まだ証明していないこと（推測で埋めない）

* 獲得能力の Dart source を実生成して Parser/Registry へ載せ、**実際に描画すること**
* Real Local Model が capability の source を書くこと（Real Local Model runs = 0 のまま）
* 未知の要求からの完全 E2E
* ぱすとらる PC での `flutter run -d chrome` 成功

## 7. 秘密情報

本評価で API キー・token・password は一切使用・出力していない。
ログにも含まれない。
