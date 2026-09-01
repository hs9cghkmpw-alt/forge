# 実機の速度 FAIL / 意味判断 FAIL への修正 — 会話入口の決定的な速い道

作成: 2026-09-01
Branch: `claude/forge-master-handoff-k46jns`
修正前の Git HEAD: `bb33274`
実行ホスト: この Linux コンテナ

> 用語: **Conversation Engine**（利用者の言葉を読んで、聞くか作るかを決める仕組み） /
> **capability**（Forge が持っている「作れるもの」の単位） /
> **structured 生成**（決まった形の JSON をモデルに書かせること） /
> **fail-closed**（迷ったら緩い側へ倒さないこと） /
> **配線破壊試験**（配線を1本ずつ外して、対応するテストが落ちるか確かめる）。

---

---

## 0. この数字が何の数字か（2026-09-01 CEO 指摘により明確化）

**73.54 秒 → 0.09 ミリ秒は、Forge 全体の処理時間ではない。**

これは最初の「ASK か BUILD か」を決める判定が、速い道に入って
**LLM 0 回**になった結果である。そのあと `PromptPipeline` が実際に
画面を作る時間は**まだ計測していない**。

```text
利用者の入力
  ├─ ASK / BUILD 判定   ← ここが 73.54 秒 → 0.09 ミリ秒（測った）
  └─ PromptPipeline     ← ここは未計測（TD98）
       └─ 画面生成 / Validator / repair
```

**「高速化完了」ではない。** 判定が速くなっただけである。

### `Real Local Model runs = 0` の意味（同上）

これは「Local Model を動かしていない」という意味では**ない**。

* 実モデル（`qwen2.5:1.5b-instruct`）による**会話経路は実機 PASS 済み**
* HTTP 200 / `simulated=false` も実機で確認済み

**0 なのは**、実 Local Model が

> 新 Capability を生成 → 検証 → 取り込み → 再利用まで**完走した回数**

である。その一連が実モデルで通った実績が 0 という意味であり、
モデルが動いていないという意味ではない。

---

## 1. 実機で確認された事実（丸めない）

| 項目 | 結果 |
|---|---|
| Frontend 表示 | **PASS** |
| Frontend → Backend | **PASS** |
| Backend 起動 | **PASS** |
| Ollama | **PASS** |
| `qwen2.5:1.5b-instruct` 実モデル | **PASS** |
| `/api/v1/ai/converse`（`provider=local`）| **PASS**（HTTP 200 / `simulated=false`）|
| **応答時間** | **73.54 秒 — FAIL** |
| **意味判断** | **FAIL** |
| **Chrome 完走** | **FAIL** |

Flutter 側の `receiveTimeout` は 10 秒だったので、Chrome では先に
「サーバーに接続できませんでした」になり、**画面まで到達しなかった**。

### 意味判断が何を誤ったか

> 「事務所の鍵を誰が持ち出していて、いつ返す予定か記録したい」

に対して Conversation Engine は「誰が持っているか」「返却予定はいつか」を
**利用開始前に確認すべき未知**（blocking unknown）と判定して聞き返した。

**これらは未知ではない。作る管理ツールの入力項目である。**
値は道具ができたあとに利用者が入れる。

### 73 秒の主因

同じモデルの単純な structured 生成は warm 状態で約 **4.02 秒**である。
つまりモデルが遅いのではなく、**Conversation Engine の大きな prompt と
schema を小型 CPU モデルへ丸投げしている構造**が主因である。

---

## 2. まず既存実装を読んで確かめたこと

**reuse-first B は、本番の入口へ繋がっていなかった。**

| | |
|---|---|
| `forge_ai/core/orchestration/reuse_first_pipeline.py` | 存在する（前回実装） |
| `/api/v1/ai/converse` から呼ばれているか | **呼ばれていない** |
| `ConversationEngine.step()` | **毎回** `complete_structured()` を呼ぶ |

`step()` は最初の1行目から大きな prompt を組み立ててモデルへ渡していた。
判定の前に必ず1回、無条件に呼んでいた。**ここが 73 秒である。**

したがって今回やることは「新しい系統を作る」ことではなく、
**既存の資産（capability decomposition と risk 検出）を、本番の入口の
手前へ差し込む**ことである。

---

## 3. 変更した設計

`backend/app/ai/runtime/conversation_fast_path.py`（新規）

```text
利用者の言葉
  ↓
速い道で決められるか（決定的・LLM 0 回）
  ├ 決められる → BUILD へ進む
  └ 決められない → いままでどおり Conversation Engine の LLM 判定へ
```

**再利用した既存資産**（新しい分類器を作らない）:

| 使ったもの | 何のために |
|---|---|
| `plan_capabilities()`（forge_ai の capability decomposition） | 足りない能力があるか / 作る物の形が決まっているか |
| `detect_risk_signals()`（既存 conversation policy） | 外部作用・不可逆操作 |
| `ConversationStepResult` / `NeedModel` / `SafeAssumption`（既存 types） | 戻り値の形を変えない |

**新規コード**は、速い道へ入れてよいかを決める規則だけである。

### 速い道へ入れる条件（**どれか1つでも欠けたら LLM へ渡す**）

1. 1ターン目であり、まだ何も聞いていない
2. 既存ツールへの変更要求ではない
3. 外部作用・不可逆操作の気配が無い
4. 既にある物への変更を頼む言い方ではない（「期限も追加して」）
5. 扱う対象が名指しされている（「何か」「いろいろ」ではない）
6. 複数人で使う前提ではない（保存場所と権限の設計が変わる）
7. **足りない能力が無い**
8. 作る物の形が決まっている（`is_actionable`）**または**
   記録・管理の意図が読み取れる

**fail-closed である。** 迷ったら速い道へ倒さない。

### 「記録項目」と「聞くべき未知」を混同しない

速い道が BUILD を選んだとき、`NeedModel` へ理由を明記して残す。

```text
key    : tool_fields_are_not_unknowns
value  : 記録する項目は、作るツールの入力欄として用意する
reason : 「誰が」「いつ」のような項目は、利用開始前に確定させる未知ではなく、
         利用者が後から入れる値である
```

### 分野の語彙を並べる方向で埋めない

意図は**動詞の側**で受ける（記録・記入・入力・登録・管理・保存・控え・
メモ・残す・付ける・一覧・台帳・見返す・振り返る・把握・確認）。
「鍵」「食事」「在庫」のような**分野ごとの名詞**を並べると、分野の数だけ
増えて追いつかない（TD96 と同じ轍）。

「事務所の鍵を…」が通るのは、**鍵という語を知っているからではない**。
「記録したい」という**やりたいことが明確**だからである。

### 忘れられない場所へ置く

`ConversationEngine.__init__` の既定引数**かつ class 属性**として持たせた。
`__init__` を差し替えるテストが既にあり、そこで属性が生えていないと本番が
落ちるため、class 側にも既定を置いてある。**渡し忘れたら遅い道、という形に
していない。**

---

## 4. 実測 Before / After

### 実機で落ちた文そのもの

| | Before（実機） | After（この修正） |
|---|---|---|
| 応答 | **73.54 秒** | **0.09 ミリ秒** |
| LLM 呼び出し | 1 回（大きな prompt + schema） | **0 回** |
| 判定 | **ASK（誤り）** | **BUILD** |

**これは会話の判定だけの数字である。** Forge 全体の処理時間ではない。
BUILD の先の生成時間は未計測（§0 / TD98）。倍率で語ると全体が速くなったように
読めるので、**倍率ではなく「判定が 0.09 ミリ秒」とだけ言う。**

### ランダム自由文 A / B / C（seed 20260901）

```text
$ python3 scripts/converse_fast_path_e2e.py --seed 20260901

A. いま持っている能力だけで作れる自由文
   入力: 自分用でいいんだけど、読んだ本をためていって、感想つきの一覧を作りたい。続けられる形がいい。
   結果: build   LLM 呼び出し 0 回   0.09 ms

B. 本当に曖昧な自由文 → ASK が妥当
   ask  LLM 1 回  なんとかしてほしいんだけど        （記録・管理の意図を読み取れない）
   ask  LLM 1 回  いい感じのやつ作って              （記録・管理の意図を読み取れない）
   ask  LLM 1 回  いろいろ記録して一覧で見返したい    （何を扱うのかが名指しされていない）

C. 足りない能力が要る自由文
   入力: 自分用でいいんだけど、釣れた魚をメモして、釣りに行った日を月単位で振り返れるようにしたい。
   足りない能力: ('view.calendar',)
   結果: ask   LLM 呼び出し 1 回   （足りない能力がある: view.calendar）
```

**B と C で LLM を呼んでいることが重要である。** 速さのために雑に
分類していない。曖昧なものは聞く。足りないものは自己拡張の判断へ渡す。

ログ: `logs/forge-fast-path-e2e-seed20260901.log` / `.json`

---

## 5. LLM 呼び出し回数 Before / After

| 要求の種類 | Before | After |
|---|---|---|
| 既存能力だけで作れる（記録・一覧・入力・日付…） | 1 回（73 秒級） | **0 回** |
| 本当に曖昧 | 1 回 | 1 回（変えない） |
| 足りない能力がある | 1 回 | 1 回（変えない） |
| 既存ツールへの変更 | 1 回 | 1 回（変えない） |
| 2ターン目以降 | 1 回 | 1 回（変えない） |

**capability 生成回数は 0 のまま**である。この修正は会話の判定を速く
しただけで、生成の経路には触れていない。

---

## 6. 配線破壊試験（10件すべて検出）

ログ: `logs/forge-fast-path-guard-break-20260901.log`

| # | 外した配線 | 結果 |
|---|---|---|
| F1 | 速い道そのものを外す（実機の 73 秒へ戻す） | DETECTED |
| F2 | 足りない能力があっても速い道へ通す | DETECTED |
| F3 | 外部作用・不可逆操作でも通す | DETECTED |
| F4 | 曖昧でも通す | DETECTED |
| F5 | 対象が名指しされていなくても通す | DETECTED |
| F6 | 複数人で使う前提でも通す | DETECTED |
| F7 | 既存物への変更でも新規作成として通す | DETECTED |
| F8 | 2ターン目以降でも通す | DETECTED |
| F9 | 既存ツールがあっても通す | DETECTED |
| F10 | 記録項目を未知として残す（実機の誤判定へ戻す） | DETECTED |

### 置物を1件見つけて直した

F5 は**初回は素通りした**。テストが「家族で何か管理したい」を使っており、
**複数人の規則の方で先に落ちていた**ため、名指しの規則を検査したことに
なっていなかった。「いろいろ記録して一覧で見返したい」へ変えて締め直した。

### Golden Conversation が2件落ちて、設計を直した

最初の実装は「管理したい」だけで速い道へ倒しており、
既存の Golden Case 02 が落ちた。

* 「家族で予定を管理したい」→ 誰が追加できるかで**保存場所と権限が変わる**
* 「家族で何か管理したい」→ **何を**管理するのか未定

どちらも**聞くべき未知**である。テストを緩めず、規則の方を直した
（§3 の条件 5・6）。Golden Case 06「期限も追加して」も同様に、
既存物への変更は新規作成として通さない規則（条件 4）を足した。

---

## 7. 副次的な変更 — Flutter の待ち時間

`frontend/lib/core/network/dio_client.dart` の `receiveTimeout` を
10 秒 → 60 秒にした。

**これは主たる直しではない。** 主たる直しは会話の判定を速くしたことである
（73.54 秒 → 0.09 ミリ秒）。BUILD の先では小型ローカルモデルが実際に
生成するため 10 秒では短い、というだけの理由であり、**遅さを許す値では
ない**。生成が遅いこと自体は別に測る。

`connectTimeout` は 10 秒のまま変えていない（到達可否は 10 秒で分かる）。

---

## 8. 回帰（全部通した）

```text
$ cd backend  && python -m pytest tests -q      2014 passed, 16 skipped
$ cd forge_ai && python -m pytest tests -q       754 passed
$ cd frontend && flutter analyze                 No issues found!
$ cd frontend && flutter test                    562 passed
$ ruff check（変更ファイル）                      All checks passed!
$ python3 scripts/reuse_first_e2e.py --seed 20260831   生成 1 回 / Provider 1 回（変化なし）
```

---

## 8.1 CI を2回落とした（どちらも手順ミス。速い道の不具合ではない）

**丸めない。** この修正を push したあと、CI を2回落とした。

| run | SHA | 落ちた場所 | 原因 |
|---|---|---|---|
| 33469325234 | `e3c4a34` | `flutter test` 48件 | 獲得物を出荷物と一緒に commit した |
| 33470175316 | `0d5415e` | 会話E2Eの step | script の置き場所を間違えた |

### 1回目 — 獲得物を commit した

回帰確認のため `scripts/reuse_first_e2e.py` を走らせたまま `git add -A` した。
E2E は獲得能力を install して登録表を書き換える。獲得した Dart 本体は
`.gitignore` で除外されているので、

```text
lib/json_ui/acquired/acquired_registrations.g.dart:10:8:
  Error when reading 'lib/json_ui/acquired/view_calendar/forge_binding.dart':
  No such file or directory
```

手元（能力あり）では通り、新しい checkout（能力なし）では**コンパイル不能**
という食い違いが生まれた。

### 2回目 — 置き場所を間違えた

会話入口の速い道を測る script を **frontend job** へ置いた。あの job には
Flutter しか入っておらず `backend/requirements.txt` が無い。

```text
ModuleNotFoundError: No module named 'httpx'
```

`ConversationEngine` → `provider_router` → `cloud_provider` → `httpx` と辿る。
手元では依存が全部入っているので通っていた。**Flutter も dart も要らない
試験**だったので、置き場所そのものが誤りだった。backend job へ移した。

### どちらも機械に見させるようにした

「commit 前に restore するのを忘れない」「どの job に何が入っているか覚えて
おく」——**まさに忘れたこと**である。人の注意力に賭けない。

| テスト | 見るもの | 再現時 |
|---|---|---|
| `forge_ai/tests/test_shipped_acquired_registrations.py` | 出荷する登録表が空か / import 先が実在するか / 獲得物が残っていないか | 2件 FAIL |
| `backend/tests/test_ci_job_dependencies.py` | frontend job の script が backend を import していないか / script が実在するか / 速い道の step が消えていないか | 1件 FAIL |

どちらも**CI を落とした状態を再現して落ちることを確認済み**である。

---

### CI（canonical）

run **33471061839** / head `d34ffd6c89c7a5938cafe5dc667acf38f7cf47f8` /
**4 jobs すべて success**。

会話入口の速い道を測る step は **backend job**（Python 3.11 / 3.12 の両方）で
**実際に走って success**。frontend job の 6 step も全部 success である。

| job | step | 結果 |
|---|---|---|
| backend (3.11 / 3.12) | 会話入口の速い道（簡単な要求で LLM 0 回） | success |
| frontend | flutter test | success |
| frontend | 生成 Dart の実ビルド経路 | success |
| frontend | 自由文 E2E | success |
| frontend | 獲得 Capability を Forge アプリへ載せる | success |
| frontend | flutter analyze（獲得を載せた状態） | success |
| frontend | flutter test（獲得 Capability が実際に描かれる） | success |
| frontend | flutter build web | success |

**skip は1件も無い。**

途中経過（丸めない）:

| run | SHA | 結果 |
|---|---|---|
| 33469325234 | `e3c4a34` | **failure**（獲得物を commit した） |
| 33470175316 | `0d5415e` | **failure**（script の置き場所を間違えた） |
| 33470964425 | `22bcd5f` | cancelled（後続 push により中断） |
| **33471061839** | **`d34ffd6`** | **success** |

---

## 12. 段ごとの計測を本番経路へ入れた（2026-09-01 追記）

### なぜ

実機で 73.54 秒かかったとき、**内訳が無かった**。合計しか見えないと
「1つ速くしたから全部速い」と丸めてしまう。次に何を速くすべきかも
決まらない。

### 何を入れたか

`backend/app/ai/runtime/stage_timing.py`。context variable に計測器を置き、
測りたい場所は `with stage("validator"):` と書くだけでよい。引数を通して
回らないので、深いところ（Validator）もそこだけ見て測れる。

**計測していないときは何もしない。** 計測のために本番の形を変えない。

`/api/v1/ai/converse` の応答へ `timings` として載る。

| 出るもの | 中身 |
|---|---|
| `stages_ms` | `fast_path` / `conversation_step` / `conversation_llm` / `build_pipeline` / `validator` |
| `stage_calls` | 段ごとの通過回数（Validator は repair のたびに走る） |
| `counters` | `conversation_llm_calls` / `build_pipeline_runs` |
| `notes` | 速い道を通ったか、その理由 |

### この環境で確かめたこと（**実モデルではない**）

Ollama はこのコンテナに無い。したがって以下は `provider=mock` の数字であり、
**実機の数字ではない**。確かめたのは「計測が本番経路で動き、段が分かれて
返ること」だけである。

```text
$ python3 scripts/measure_real_device_converse.py --provider mock

A. 事務所の鍵を誰が持ち出していて、いつ返す予定なのか記録できるようにしたい
   HTTP 200  status=build   provider_used=mock  simulated=True
   速い道の判定              0.173 ms
   会話ステップ全体            0.197 ms
   会話の LLM 呼び出し        —（0 回）
   生成（PromptPipeline）    3.851 ms
   Validator               0.159 ms
   HTTP 全体                86.2 ms
   Forge Document          返った（画面 1 / Validator PASS=True）

B. 家族で予定を管理したい
   status=needs_confirmation  ← 雑に BUILD せず、確認を求めた
```

**B が BUILD になっていないことが重要である。** 速い道は共有範囲が
未確定な要求を通さない。

### 配線破壊試験（7件すべて検出）

ログ: `logs/forge-stage-timing-guard-break-20260901.log`

| # | 外した配線 | 結果 |
|---|---|---|
| M1 | 計測そのものを止める | DETECTED |
| M2 | 応答へ載せない（測っても見えない） | DETECTED |
| M3 | 生成段を測らない | DETECTED |
| M4 | Validator を測らない | DETECTED |
| M5 | 速い道を測らない | DETECTED |
| M6 | LLM 呼び出しを数えない | DETECTED |
| M7 | 速い道を通ったかを記録しない | DETECTED |

---

## 13. 実機で実行していただく手順

**この環境に Ollama は無い。実機の数字は私には取れない。**
以下は CEO の実機で1コマンドである。

```bash
# Backend を起動した状態で
python3 scripts/measure_real_device_converse.py
```

既定で `provider=local`、`--base-url http://127.0.0.1:8000`。
2件（実機で落ちた文 / 共有範囲が未確定な文）を投げて、段ごとの実測を
画面と `logs/forge-real-device-converse-<日時>.json` へ残す。

**遅かったときに timeout を伸ばして「解決」にしない。**
script は一番遅い段を名指しする。そこを速くする。

### そのあと Chrome で（人が見る）

1. Forge を Chrome で開く
2. 「事務所の鍵を誰が持ち出していて、いつ返す予定なのか記録できるようにしたい」と入力
3. **画面が出るところまで人が見る**
4. 「家族で予定を管理したい」を入力し、**聞き返してくることを人が見る**

**見ていないものを PASS にしない。**

---

## 9. 残る問題

1. **BUILD の先の生成時間を測っていない。** 会話の判定は速くなったが、
   その後 `PromptPipeline` が小型モデルで entity synthesis と検証を回す。
   ここが何秒かかるかは**まだ測っていない**。60 秒で足りるかどうかも
   実機で確かめていない。
2. **実機 Chrome の完走は未確認。** この修正で 10 秒の壁は越えるはずだが、
   **見ていないので PASS と書かない。**
3. **要求理解の取りこぼし（TD96）** は残っている。速い道は
   `plan_capabilities` に乗っているので、あちらが読み取れない言い方は
   こちらでも読み取れない。
4. **Real Local Model runs = 0 のまま。** これは Local Model を動かして
   いないという意味ではない（会話経路は実機 PASS 済み）。0 なのは、
   **実 Local Model が新 Capability を生成 → 検証 → 取り込み → 再利用まで
   完走した回数**である。

---

## 10. 実機で次に確認すべき操作

1. `/api/v1/ai/converse` へ「事務所の鍵を誰が持ち出していて、いつ返す予定か
   記録したい」を `provider=local` で POST し、**応答時間**と
   `status`（`build` になるか）を見る
2. そのまま BUILD が走るので、**生成まで含めた実時間**を測る
   （60 秒で足りるか。足りなければ生成側の速度が次の課題）
3. Chrome から同じ文を入力し、**画面まで到達するか**を見る
4. 「家族で予定を管理したい」を入力し、**ちゃんと聞き返すか**を見る
   （速くするために雑になっていないことの確認）

## 11. 秘密情報

本作業で API キー・token・password は一切使用・出力していない。
ログにも含まれない。実 API を呼んでいない。
