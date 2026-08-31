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
| Validator → real Flutter/Dart runtime | **CLOSED（実 Flutter widget runtime まで）** | §8。`test/json_ui/widget_registry/acquired_widget_renders_test.dart`（7 tests）+ 配線破壊 4 件 |

§4 で後半が**未達であること**を実測して記録し、§8 でその穴（TD93）を開けた。
この文書は「Chrome 上の Forge アプリで、自律生成された能力が描かれた」という
主張では**ない**。閉じたのは**実 Flutter widget runtime**（`flutter test` が
動かす本物の Dart VM・本物の widget tree・本物の描画）までである。
その境界を §9 に明記する。

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

**この節は §8 の作業前に測った事実である。** 穴を開けた後の状態は §8 を見ること。

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

---

## 8. 後半を開けた — Parser 側の受け口（TD93 解消）

### 8.1 何を足したか

`frontend/lib/json_ui/schema/acquired_widget_types.dart`

* `ForgeAcquiredWidgetSpec` — 獲得 widget 型の**宣言**（型名＋必須 property 名）
* `ForgeAcquiredWidgetTypeRegistry` / `forgeAcquiredWidgetTypes` — process-local な表
* `ForgeAcquiredWidgetNode`（`forge_document.dart`）— 型名と properties を
  持ち回るだけの**汎用**ノード。capability ごとの専用クラスを作らない

`ForgeWidgetNode.fromJson` の `default:` は、Unknown へ倒す**前に**この表を引く。

### 8.2 緩めていないこと

| 不変条件 | 確かめ方 |
|---|---|
| 既定は空。何も獲得していなければ何も通らない | `既定では何も登録されていない` |
| **Parser の宣言だけ**では描かない（描き方が無い） | `Parser だけ登録して描き方が無ければ描かない（fail-closed）` |
| **Registry の登録だけ**では描かない（宣言が無い） | `Registry だけ登録して Parser の宣言が無ければ描かない` |
| 必須 property が欠ければ **parse で落ちる** | `必須 property が欠けていれば parse で落ちる` |
| 出荷済み型は**乗っ取れない**（`switch` が先に一致） | `出荷済みの型は、この表では乗っ取れない` |
| 空の型名は登録できない | `空の型名は登録できない` |

**両方登録して初めて描かれる。** 獲得能力の生成コードが、載るときに自分で
両方へ登録する。**Forge 本体に `if capability_id == ...` の分岐は無い。**

### 8.3 配線破壊試験（Dart 側・4件すべて検出）

ログ: `logs/forge-020f-dart-guard-break-20260831.log`

| # | 外した配線 | 結果 | 落ちたテスト |
|---|---|---|---|
| D1 | Parser 側の受け口を無効化 | DETECTED | `両方登録すれば…` / `必須 property が…` |
| D2 | 必須 property 検査を削除 | DETECTED | `必須 property が欠けていれば parse で落ちる` |
| D3 | `typeNameOf` の獲得ノード対応を削除 | DETECTED（compile error） | sealed class の非網羅 switch。**型として載っている証拠** |
| D4 | Registry 未登録でも Fallback にしない（fail-open 化） | DETECTED | `Parser だけ登録して描き方が無ければ描かない` |

### 8.4 実行結果

```text
$ cd frontend && flutter analyze
No issues found!

$ cd frontend && flutter test
00:38 +557: All tests passed!   # 546 → 550 → 557
```

`mock_generator_renderer_contract_test.dart` が持つ `_typeNameOf` の複製にも
獲得ノードの case を足した（sealed class の非網羅 switch でコンパイルが
落ちたため。この複製は過去にも同じ失敗を検出しており、今回も効いた）。

---

## 9. どこまでを「閉じた」と言っているか（過大主張の防止）

**言っていること**

* 獲得 widget 型が backend Validator を通る（実測・破壊試験9件）
* その型が**実 Flutter widget runtime で実際に描画される**
  （`flutter test` は本物の Dart VM と widget tree を動かす。実測・破壊試験4件）
* 片方だけの登録では描かれない（fail-closed）

**言っていないこと**

* Chrome 上の Forge アプリで描いた — **していない**。本番起動経路へ
  架空の capability を登録するのは偽装なので行わない
* 自律生成された Dart source を実際にビルドして載せた — **していない**
* Real Local Model が capability の source を書いた — **していない。
  Real Local Model runs = 0 のまま**

### 9.1 次に必要な最後の一手 → §10 で半分を埋めた

`forge_ai` の BUILD_TIME 自己拡張（`SynthesizingBuildTimeImplementer`）は
Python 用の build plan しか持っていなかった。§10 で Dart 用の plan を足し、
**生成された Dart が実 `dart` で試験・解析・起動確認を通る**ところまでを
閉じた。残るのは「その Dart を Forge の Flutter アプリへ載せて描く」段である。

---

## 10. 生成 Dart の実ビルド経路（TD94 の半分）

### 10.1 何を足したか

`_LANGUAGE_COMMAND_PLANS` へ `dart` の行を足した。**能力ごとの表ではない**
——行が増えるのは対応言語を足したときだけである。

| kind | コマンド |
|---|---|
| test | `dart run capability_test.dart` |
| build | `dart analyze .` |
| runtime_probe | `dart run probe.dart` |

`dart pub get` を挟まない構成にしてある。挟むと外向き通信が要り、
**ネットワークの都合が build の成否に化ける**。依存無しの素の Dart で書く。

### 10.2 併せて直した実バグ

Python の plan は `probe.py` を名指しで実行していたが、**その名前を
生成側へ要求していなかった**。Model が別の名前を返せばコマンドが
ファイル不在で落ち、**生成の失敗が build の失敗に化ける**。

`LanguageBuildPlan.entry_files` を足し、
(a) prompt でその名前を要求し、(b) 生成後に不足していれば
`CapabilityImplementationUnavailable` として落とすようにした。

### 10.3 実測（実 subprocess）

```text
$ cd forge_ai && FORGE_REQUIRE_DART_BUILD=1 python -m pytest tests/test_dart_build_plan.py -q
9 passed in 2.94s
```

* `test` の stdout に `tests ok`、`runtime_probe` の stdout に
  `runtime probe ok` が出ていることを確かめている
  （**本当にその Dart が動いた**ことを出力で見る）
* Negative proof: テストを落とす／`dart analyze` が通らない Dart にする／
  probe を落とす — いずれも **PROMOTED されず activation も出ない**

### 10.4 配線破壊試験（4件すべて検出）

ログ: `logs/forge-020f-dart-plan-guard-break-20260831.log`

| # | 外した配線 | 結果 |
|---|---|---|
| P1 | `dart analyze` を削除 | DETECTED（5件 FAIL） |
| P2 | entry file の要求を削除 | DETECTED（2件 FAIL） |
| P3 | `runtime_probe` を削除 | DETECTED（5件 FAIL） |
| P4 | `test` コマンドを削除 | DETECTED（5件 FAIL） |

### 10.5 CI で skip させない

Python job には `dart` も `flutter` も無いので、この経路はあちらでは
**skip される**。skip されたテストは何も証明しないので、
`dart` を持つ frontend job で走らせる step を `.github/workflows/ci.yml`
へ足した。`FORGE_REQUIRE_DART_BUILD=1` は
**「dart が無ければ skip ではなく失敗させる」**指定である。

実測（このホスト）:

```text
dart 不在 + FORGE_REQUIRE_DART_BUILD=1  → 7 failed, 2 passed  （静かに素通りしない）
dart 不在 + 指定なし                     → 2 passed, 7 skipped
dart 有り + FORGE_REQUIRE_DART_BUILD=1  → 9 passed
```

### 10.6 CI で実際に走ったことの確認

CI run **33387417433** / head `442ba87` / 4 jobs すべて success。
frontend job の step 8「生成 Dart の実ビルド経路」が
**success（skip ではない）**。所要 6 秒。

### 10.7 これでもまだ言えないこと

隔離 workspace は **Flutter を持たない**。したがって
「生成 Dart が Forge の Flutter アプリで描かれる」ことは、
この経路では**証明していない**。描画側は §8 のテストが別に押さえている。
**2つは別の事実であり、片方でもう片方を語らない。**
