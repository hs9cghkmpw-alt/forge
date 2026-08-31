# 方式B Evidence — 持っているものは組み合わせ、足りないものだけ作り、次から速い

作成: 2026-08-31
Branch: `claude/forge-master-handoff-k46jns`
実行時の Git HEAD: `a53a22e`（この commit の親）
実行ホスト: この Linux コンテナ（Flutter は `/opt/flutter`）

> 用語: **能力**（Forge が持っている作れるものの単位） /
> **生成**（足りない能力の実装を AI に書かせること） /
> **検査**（作ったものを実際に試験・解析・起動して確かめること） /
> **配線破壊試験**（配線を1本ずつ外して、対応するテストが落ちるか確かめる）。

---

## 1. まず簡単な言葉で

### できるようになったこと

* **持っている能力だけで作れる要求は、新しいコードを1行も作らずに即表示する。**
  実測 0.4 ms。AI は1回も呼ばない。
* **足りない能力があるときだけ、その1つだけを作る。** 実測 1062 ms
  （ほぼ全部が、作ったものを実際に試験・解析・起動して確かめる時間）。
* **一度作った能力は、次から作り直さない。** 別の文で頼んでも 0.2 ms。
  AI は1回も呼ばない。
* **検査したコードと、実際に載せるコードが必ず同じになった。**
  以前は検査のあとにもう一度作り直していた（下記 §2）。

### まだできないこと

* **本物のローカル AI に書かせていない。** ここで実装を渡しているのは
  試験用の Test Double である。**Real Local Model runs = 0 のまま。**
* **実機 Chrome で見ていない。** 描画は `flutter test` が動かす本物の
  widget tree で確かめている。ブラウザではまだ見ていない。
* **言い回しによっては要求を読み取れない**（§5）。

### 実際に使ったランダム自由文（seed 20260831）

| | 入力文 | 結果 |
|---|---|---|
| A | うまく言えないけど、釣れた魚を残しておいて、釣れた場所も一緒に並びにしたい。細かい機能はいらない。 | 生成 0 回 / **0.4 ms** |
| B | 働いた時間を記録して、出勤した日を月ごとにまとめて見たい。細かい機能はいらない。 | 生成 **1 回** / **1062.1 ms** |
| C | 出した書類を記録して、出した日を月ごとにまとめて見たい。 | 生成 0 回 / **0.2 ms** |

* **1回目（B、獲得を含む）: 1062.1 ms**
* **2回目（C、再利用）: 0.2 ms** — およそ **5000 倍**速い
* **本当に再生成 0 回だったか: はい。** C の生成回数 0、Provider 呼び出し 0。
  試験全体でも生成は合計 1 回、Provider 呼び出しも合計 1 回だけである。

---

## 2. 直した実バグ — 検査したものと違うものを載せていた

TD94 の E2E は、こうなっていた。

```text
1回目の生成 → 検査 → PROMOTED
2回目の生成 → ← これを Flutter へ載せていた
```

**検査した対象と、実際に動く対象が別物だった。** 同じ Provider が同じものを
返していたので結果は一致していたが、それは偶然に頼っているだけである。

いまは1回だけ生成し、`SynthesizingBuildTimeImplementer.last_verified` に
**検査を通ったそのもの**を残す。`FlutterCapabilityInstaller.install()` は
`VerifiedCapabilityArtifact` **しか受け取らない**——生の生成物を渡す口を
用意していない。用意すると「検査していないものを載せる」経路ができてしまう。

install の直前に digest を照合するので、**1byte でも変わっていれば落ちる。**

---

## 3. 保存先の衝突と、古いファイルの残留

* 保存先には `capability_provenance.json` を置く。別の能力が同じ保存先名を
  取ろうとしたら**落とす**（黙って上書きしない）
* 素性の分からないファイルが既に置かれていたら**落とす**
* install のたびにディレクトリを**作り直す**。前回の生成物を残さない
* `verify_installed_capability()` が、載っているファイルの中身を記録した
  digest と突き合わせる——**「Flutter 側だけ直す」抜け道を塞ぐ**

---

## 4. ランダム自由文と再現性

`forge_ai/testing/free_text_requests.py`

* 分野は15種（家計・予定・在庫・釣果・勤怠・タスク・申請・健康・売上・
  学習・予約・持ち物・読書・練習・修理）
* 言い回し・前置き・語尾を毎回変える
* **Forge の内部語彙を入力文へ入れない。**
  `capability` / `widget` / `registry` / `view.` / `_view` / `forge` などを
  含む文は、生成時に**その場で落とす**（`assert_no_internal_vocabulary`）
* 英字の識別子らしい語も落とす

**同じ seed なら同じ文。** CI が落ちたらログに出た seed を
`--seed` へ渡せば完全に同じ試験を再実行できる。

```bash
python3 scripts/reuse_first_e2e.py --seed 20260831
FORGE_E2E_SEED=20260831 python -m pytest forge_ai/tests/test_reuse_first_pipeline.py
```

---

## 5. ランダム自由文で見つかった、要求理解の取りこぼし

**固定文をやめた瞬間に出てきた。** これは Forge の実力であって、
テストの都合ではない。

### 5.1 直したもの

| 取りこぼし | 直し方 |
|---|---|
| 「月ごと」「月単位」「月別」と書かれても月表示の要求だと分からない | Catalog の検出語へ追加（宣言表。分岐ではない） |
| 「出勤した日」「使った日」「釣りに行った日」を日付だと分からない | 「〜た日 / 〜の日」という**日本語の形**で受ける（語を1つずつ足すと分野の数だけ増える） |

日付の欄が立たないと記録の型が組めず、**画面がまったく作れない**。
実際に seed 20260831 の B はこれで落ちていた。

### 5.2 まだ取りこぼすもの（TD96）

* 「どの月に何回あったか分かるようにしたい」——月表示の要求だと読み取れない
* 「会う日」「行く日」のような**動詞の終止形＋日**——日付だと読み取れない

200 通りのランダム自由文で測った**読み取り率**:

| | 読み取れた |
|---|---|
| A（既存能力だけ） | **200 / 200** |
| B（月ごとに見たい） | **117 / 200** |

E2E は読み取れる言い方に当たるまで seed から**決定的に**探し、
**取りこぼした文はログへ残す**（`comprehension_misses`）。
無かったことにしない。

---

## 6. 配線破壊試験

ログ: `logs/forge-reuse-first-guard-break-20260831.log`

| # | 外した配線 | 結果 | 落ちたテスト |
|---|---|---|---|
| R1 | 足りていても常に生成する（方式Bを壊す） | DETECTED | 再利用・既存能力の2件 |
| R2 | 検査を通ったものではなく作り直したものを載せる | DETECTED | `test_the_installed_bytes_are_the_inspected_bytes` |
| R3 | install 前の digest 照合を外す | DETECTED | 1文字変更・すり替えの2件 |
| R5 | 保存先名の衝突検査を外す | DETECTED | `test_a_slug_collision_between_capabilities_is_detected` |
| R6 | 古いファイルを消さない | DETECTED | `test_reinstalling_removes_files_the_new_artifact_does_not_have` |
| R7 | 載せたあとの中身の照合を外す | DETECTED | `test_editing_the_installed_flutter_side_is_detected` |

R4 / R8 は「外しても落ちない」が、**置物ではなく下層と重なった検査**である
（同じ不変条件を守る別の検査があり、そちらは実際にテストされている）。
ログの末尾に理由を書いた。

一方、`SynthesizingBuildTimeImplementer` へ重ねて書いた digest 照合は
**到達しないコード**だったので**削除した**。外しても何も落ちないものは、
テストだけでなくコードでも置物である。

---

## 7. 実行結果

```text
$ python3 scripts/reuse_first_e2e.py --seed 20260831
A  生成 0 回 / Provider 0 回 / 0.4 ms
B  生成 1 回 / Provider 1 回 / 1062.1 ms
   検査した生成物 = 載せた生成物: 9b7a53ec7f6bc370…
C  生成 0 回 / Provider 0 回 / 0.2 ms
合計 生成 1 回 / Provider 1 回

$ cd forge_ai && python -m pytest tests -q
744 passed, 10 skipped

$ cd backend && python -m pytest tests -q
1998 passed, 16 skipped

$ cd frontend && flutter analyze          # 獲得を載せた状態
No issues found!

$ cd frontend && flutter test
00:50 +562: All tests passed!

$ cd frontend && flutter test test_acquired
00:02 +7: All tests passed!

$ cd frontend && flutter build web --debug
✓ Built build/web
```

ログ: `logs/forge-reuse-first-e2e-seed20260831.log` / `.json`

### CI（canonical）

run **33447252973** / head `85e50b776b55ae707b01e6c62cd84e32f493ea1c` /
**4 jobs すべて success**。

frontend job の step 9「自由文 E2E（既存能力なら生成0回 / 足りない分だけ1回 /
2回目は再利用）」が**実際に走って success**（skip ではない）。
CI 上の seed は毎回変わる——**固定文へ最適化していないことを、CI 自身が
毎回確かめている。**

---

## 8. 各工程の時間（B、獲得を含む1回目）

| 工程 | 時間 |
|---|---|
| 要求を読む | 0.1 ms |
| 持っている能力で足りるか調べる | 0.0 ms |
| 実装を作る + 実際に試験・解析・起動して確かめる | 1059.6 ms |
| Forge へ組み込む | 1.6 ms |
| 画面を組み立てる | 0.8 ms |
| **合計** | **1062.1 ms** |

ほぼ全部が「本当に動くか確かめる」時間である。**そこは削らない。**

---

## 9. まだ証明していない境界（推測で埋めない）

1. **実 Model が実装を書いたこと。** Provider は Test Double である。
   **Real Local Model runs = 0 のまま。**
2. **実機 Chrome での表示。**
3. **要求理解の取りこぼし**（§5.2、TD96）。
4. **process を跨いだ再利用。** いまの Registry は process ローカルである。
   同じ process の中では再生成しないことを確かめたが、Forge を再起動しても
   獲得済みのままかどうかは別の話であり、**確かめていない**。

## 10. 秘密情報

本作業で API キー・token・password は一切使用・出力していない。
ログにも含まれない。実 API を呼んでいない。
