# TD94 Evidence — 獲得した Capability が Forge の Flutter アプリで実際に描かれる

作成: 2026-08-31
Branch: `claude/forge-master-handoff-k46jns`
実行時の Git HEAD: `123e9376c11374edfa3bfc43740fa68a1e5c3497`（この commit の親）
実行ホスト: この Linux コンテナ（Flutter は `/opt/flutter`）

> 用語: **Parser**（生成 Document を読んで内部の木にする仕組み） /
> **Widget Registry**（型名から実際の描き方を引く表） /
> **install**（生成された Dart を Forge アプリのビルド対象へ置くこと） /
> **配線破壊試験**（配線を1本ずつ外して、対応するテストが落ちるか確かめる） /
> **fail-closed**（分からないものは通さない側へ倒すこと）。

---

## 1. 何が閉じたか

020F では次の2つを**別々に**閉じた。

| 区間 | 020F の状態 |
|---|---|
| 獲得 capability → Validator | CLOSED |
| Validator → 実 Flutter widget runtime | CLOSED |
| 生成 Dart → 実 `dart` で試験・解析・起動確認 | CLOSED |
| **生成 Dart → Forge アプリへ載せて実描画** | **NOT CLOSED（TD94）** |

TD94 でその最後の区間を閉じた。**1本の経路として**次が通る。

```text
未知の要求
  → Capability Plan が gap を名指しする        （view.calendar が missing）
  → 実装を生成する                              （Dart）
  → 隔離 workspace で実 dart による試験・解析・起動確認
  → PROMOTED
  → Forge の Flutter アプリへ install            ← TD94
  → 本番 compiler が生成 Document へ widget を出す
  → Parser → document model → Registry → 実 Widget
```

---

## 2. CEO が要求した10項目

| # | 要求 | 結果 | 根拠 |
|---|---|---|---|
| 1 | 生成 Dart が Forge Flutter app のビルド対象へ入る | **PASS** | `lib/json_ui/acquired/view_calendar/{capability_impl,forge_binding}.dart` が置かれ、`flutter build web` に含まれる。E2E test 1 |
| 2 | acquired widget type が Parser に認識される | **PASS** | E2E test 2（`ForgeAcquiredWidgetNode`、`rawType='calendar_view'`、Unknown は0件） |
| 3 | `forgeAcquiredWidgetTypes` へ登録される | **PASS** | E2E test 3。**テストは自分では登録しない**——本番の `ensureAcquiredCapabilitiesRegistered()` が生成された登録表を読む |
| 4 | Widget Registry がその型を実 Widget へ解決する | **PASS** | E2E test 4 と `registry_without_parsing_test.dart` |
| 5 | generated document からその Widget が生成される | **PASS** | E2E test 5/6。本番 compiler が出した JSON を `ForgeDocumentView` で描画 |
| 6 | `flutter analyze` が通る | **PASS** | 獲得を載せた状態で `No issues found!` |
| 7 | `flutter test` が通る | **PASS** | `test/` 562 passed、`test_acquired/` 7 passed |
| 8 | `flutter build web` が通る | **PASS** | 獲得を載せた状態で `✓ Built build/web` |
| 9 | 配線破壊試験で適切に FAIL する | **PASS** | 7件すべて検出（§5） |
| 10 | CI で skip なしに実行される | **PASS** | frontend job に step を追加（§6） |

---

## 3. 何を足したか

### 3.1 Dart 側の着地点

`frontend/lib/json_ui/acquired/`

| ファイル | 役割 |
|---|---|
| `acquired_capability.dart` | `ForgeAcquiredCapability`（能力id + Parser 側の宣言 + 描き方）と登録関数 |
| `acquired_capabilities.dart` | `ensureAcquiredCapabilitiesRegistered()`（何度呼んでも安全） |
| `acquired_registrations.g.dart` | **生成される登録表。** 出荷状態は空 |

`ForgeAcquiredCapability` は宣言と描き方を**両方**持つ。片方だけの値は
型として作れない。

### 3.2 忘れられない場所へ置く

「呼び出し側が忘れずに呼ぶ」設計にしない（`CLAUDE.md` §3。同じ失敗を
8回以上している）。登録は**本番が必ず通る2箇所**から呼ばれる。

* `ForgeWidgetNode.fromJson` が未知の型を見たとき
* `buildDefaultForgeRegistry()` が Registry を組むとき

### 3.3 Python 側の installer

`forge_ai/core/orchestration/flutter_capability_installer.py`

* 生成 binding を `lib/json_ui/acquired/<slug>/` へ書く
* 登録表を**丸ごと作り直す**（追記ではない）。installer を通っていない
  能力が表に残り続ける形にしない
* 隔離 workspace 用の harness（テスト・probe）は**載せない**
* binding を持たない artifact は**落とす**（描けないものを載せない）
* 書き込み先は獲得用の1ディレクトリだけ。出荷済み source は触らない

### 3.4 言語ごとの build plan の拡張

`LanguageBuildPlan` へ `harness_files` と `host_prefix` を足した。
**能力ごとの表ではない。** 行が増えるのは対応言語を足したときだけである。

`flutter/` 以下は Flutter を要るので隔離 workspace では解析しない
（あちらに Flutter は無い）。install 後の `flutter analyze` /
`flutter test` / `flutter build web` が見る。**2つは別の事実である。**

---

## 4. 途中で直した実バグ

### 4.1 生成 Document の属性は平ら

Parser の獲得分岐は `json['properties']` を読んでいたが、Forge の生成
Document は widget の属性を**平らに**持つ（出荷済みの型と同じ）。

```json
{"type": "calendar_view", "id": "record_calendar", "state_ref": "records", "date_field": "date"}
```

`type` と `id` 以外を属性として読むよう直した。直す前は必須 property が
欠けている扱いになり、**獲得 widget が永久に parse で落ちていた。**

### 4.2 「表が空である」を期待していたテスト

`既定では何も登録されていない` は、実際に能力を獲得した checkout で
**獲得を壊れたことにしてしまう**。「**この型が**入っていない」を見る形へ
直した。

---

## 5. 配線破壊試験（7件すべて検出）

ログ: `logs/forge-td94-guard-break-20260831.log`

| # | 外した配線 | 結果 | 落ちたテスト |
|---|---|---|---|
| T1 | Registry へ獲得の描き方を入れる行を削除 | DETECTED | 4件 |
| T2 | Registry 側の登録呼び出しを削除 | DETECTED | `parse していなくても Registry は獲得 widget を解決する` |
| T3 | Parser 側の登録呼び出しを削除 | DETECTED | E2E 2/3 |
| T4 | 登録表を読む本体を空にする | DETECTED | 4件 |
| T5 | widget 型の持ち主検査を削除 | DETECTED | `別の能力が同じ widget 型を奪えない` |
| T6 | installer が binding 無しでも載せる | DETECTED | `test_an_artifact_without_a_binding_is_refused` |
| T7 | installer が登録表を作り直さない | DETECTED | 4件 |

### 5.1 置物テストを1本見つけて潰した

**初回、T2 は素通りした。** `buildDefaultForgeRegistry()` から登録呼び出しを
外しても、どのテストも落ちなかった——同じファイル内で先に走ったテストの
parse が既に登録を済ませていたためである。

Flutter はファイルごとに別 isolate で走るので、
`test_acquired/registry_without_parsing_test.dart` を独立させ、
**parse を一切せずに Registry を最初に組む**経路を作った。
これで T2 が検出されるようになった。

---

## 6. CI（skip なしで実行）

`.github/workflows/ci.yml` の frontend job へ次を追加した。

```yaml
- name: 獲得 Capability を Forge アプリへ載せる
  run: python3 scripts/acquired_capability_flutter_e2e.py
- name: flutter analyze（獲得 Capability を載せた状態）
- name: flutter test（獲得 Capability が実際に描かれる）
  run: flutter test test_acquired
- name: flutter build web        # 獲得を載せたまま build する
```

`test_acquired/` を `test/` の外へ置いてある。`test/` に置くと素の checkout で
`flutter test` が落ちる。かといって「生成物が無ければ skip」にすると
**skip が PASS として数えられる**——それは何も証明しない。
生成物が無ければ **skip ではなく失敗**する。

生成物は commit しない（`.gitignore`）。commit すると「出荷済み source」に
なってしまい、**生成したものと出荷したものの区別が消える**。
`acquired_registrations.g.dart` だけは出荷状態（空）を commit する。

---

## 7. 実行結果

```text
$ python3 scripts/acquired_capability_flutter_e2e.py
  missing : ('view.calendar',)
  test           exit=0
  build          exit=0
  runtime_probe  exit=0
  PROMOTED  build_id=build-...
  installed  lib/json_ui/acquired/view_calendar/capability_impl.dart
  installed  lib/json_ui/acquired/view_calendar/forge_binding.dart
  calendar_view is in the compiled document

$ cd frontend && flutter analyze          # 獲得を載せた状態
No issues found!

$ cd frontend && flutter test test_acquired
00:01 +7: All tests passed!

$ cd frontend && flutter build web --debug
✓ Built build/web

$ cd frontend && flutter test             # 素の状態
00:33 +562: All tests passed!

$ cd forge_ai && python -m pytest tests -q
736 passed

$ cd backend && python -m pytest tests -q
1998 passed, 16 skipped
```

ログ: `logs/forge-td94-e2e-20260831.log`

### 7.1 CI（canonical）

run **33409772751** / head `a89ea7f4cc93a803efb28098edadf6555db2e60c` /
**4 jobs すべて success**。frontend job の step 8〜12（生成 Dart の実ビルド
経路 / install / analyze / test_acquired / build web）が**すべて実際に走って
success**。**skip は1件も無い。**

commit SHA（この作業）: `a89ea7f4cc93a803efb28098edadf6555db2e60c`

---

## 8. 避けたこと（CEO の指示どおり）

* **capability ごとの専用 if 分岐** — 無い。増えるのは対応言語の行だけ
* **テンプレートでの疑似対応** — Widget も Template も足していない
* **shipped widget の再利用を「新規生成」と数える** — `calendar_view` は
  出荷済みの widget 型に**存在しない**。`view.map` は使っていない
  （あれは activation であって生成ではないと判定済み）
* **Parser を通さず直接 Widget を生成する近道** — E2E は
  `ForgeDocument.fromJson` を通す。Unknown が0件であることも見ている
* **Registry 登録だけで描画可能と判定する** — Parser 側の宣言が無ければ
  描かれないことを 020F のテストが固定している
* **test 専用配線で本番経路を迂回する** — E2E テストは自分では登録しない。
  本番の `ensureAcquiredCapabilitiesRegistered()` が生成された表を読む
* **skip を PASS 扱いする** — §6 のとおり

---

## 9. まだ証明していない境界（推測で埋めない）

1. **実 Model が capability の実装を書いたこと。**
   この E2E の Provider は **Test Double** である。
   **Real Local Model runs = 0 のまま。**
2. **実機 Chrome での表示。** 描画を確かめたのは `flutter test` が動かす
   本物の widget tree であり、ブラウザではない。次の作業である。
3. **未知の要求からの完全 E2E。** 要求文・契約・宣言はこの script が
   固定している。自然言語から契約を機械的に引くところは別の段である。
4. **ぱすとらる PC (Windows) の Puro 問題。** このホストでは再現しない。

## 10. 秘密情報

本作業で API キー・token・password は一切使用・出力していない。
ログにも含まれない。実 API を呼んでいない。
