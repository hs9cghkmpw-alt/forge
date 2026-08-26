# Generated UI Quality Gate v2 — 第1回・第2回・第3回 report

- Task: Generated UI Quality Gate v2（CEO指示、2026-08-26）
- 仕様: `docs/spec/GENERATED-UI-QUALITY-GATE-V2.md`
- 証拠: `docs/visual-evidence/QUALITY-GATE-V2/manifest.md`（**全文はこちら**）
- Branch: `claude/forge-master-handoff-k46jns`
- 実施日: 2026-08-26

---

## 結論を先に

> ### Golden Quality Gate: **第1回 FAIL / 第2回 FAIL / 第3回 FAIL**

「このまま普通のアプリとして使いたいと思えるか」——**まだ思えない。**

**崩れているから落ちたのではない。同じ画面しか出てこないから落ちた。**

第2回で崩れは4件直した（すべて再描画で確認）。それでも判定は変わらない。
**Renderer を磨いても、出てくる画面が2種類しかない限り通らない。**

---

## 何をやったか

| | 第1回 | 第2回 |
|---|---|---|
| 生成 | 本番 `/generate` で 8 アプリ | 同じ 8 アプリを再生成 |
| 撮影 | 4 viewport × 8 = **32 枚** | 同じ条件で **32 枚** |
| 評価 | 13 軸 + Golden Gate、**全部人が開いて見た** | 同じ |
| 置き場 | `before/` | `after/` |

viewport: mobile 390×844 / small 320×640 / tablet 834×1112 /
desktop 1440×900。

8 アプリ（性格を散らした）: finance / map / worklog / kids / photo /
game / analytics / study。

**撮影ハーネスにアプリごとの分岐を書かない。** 書いた時点で
「Forge が作ったもの」ではなく「私が作ったもの」を測ることになる。

---

## 最大の発見: 8 アプリが 3 種類の画面にしかならない

| 画面 | widget 型数 | アプリ |
|---|---|---|
| tracker | 21 | finance |
| tracker | 20 | map |
| **checklist** | **7** | **worklog / kids / photo / game / analytics / study** |

**6 アプリが構造的に同一。** 実描画でも、データ分析アプリと子ども向け
アプリが**同じチェックリスト2行**になり、違うのは追加ボタンの色だけ
だった。

### これは「崩れていない」

overlap も overflow も無い。**v1 の基準なら通ってしまう。**
Quality Gate v2 が要る理由がここにある。

### Direction に照らすと

`docs/GENERATIVE-SOFTWARE-DIRECTION.md` が禁じている
「有限 Widget Builder」そのものである。`LEARNABLE-LOCAL-AI-VISION.md`
§22 の Capability Registry 作り直しと**同じ根**であり、実描画が独立に
同じ結論へ着いた。

---

## 第2回で直した4件（すべて再描画で確認）

| # | 軸 | 第1回 | 第2回 | 直した場所 |
|---|---|---|---|---|
| 1 | overflow / clipping | FAIL | **PASS** | `frontend/lib/json_ui/widget_registry/widget_registry_v1_7.dart` |
| 2 | content fit | FAIL | **PASS** | `frontend/lib/json_ui/renderer/forge_renderer.dart` |
| 3 | long-text resilience | FAIL | **PASS** | 同上 |
| 4 | empty-state quality | FAIL | **PASS** | `backend/app/ai/foundation/providers.py` + `forge_ai/core/compiler.py` |

### 1. `date_field` のラベルを枠線が貫通していた

`InputDecorator.isEmpty` の既定は `false`。渡していなかったので空でも
ラベルが浮き、`ForgeTheme` の `OutlineInputBorder`（角丸20）と衝突して
いた。全 viewport で再現。`isEmpty: currentValue.isEmpty` を渡した。

証拠: `defect-date-field-before.png` / `defect-date-field-after.png`

**019C の Visual Review では見つからなかった。** あのときは同じ家計簿でも
「一覧」タブしか描いておらず、`date_field` を含む「追加」タブを見ていな
かった。**1画面だけ見て「実描画を確認した」と言っていた**ことになる。

### 2. 広い画面で入力欄が 1950px まで伸びていた

desktop(1440px) で、金額1つ入れる欄が画面幅いっぱいまで伸びていた。
広いのではなく**読めない**。本文を `maxWidth: 720` で中央寄せにした。

**mobile では何も変わらない**（1440 未満）——すでに通っている見た目を
壊さずに、広い画面だけ直す。

証拠: `after-desktop-content-fit.png`

### 3. 見出しが1行で省略されていた

`AppBar` の既定 maxLines 1 で「子どもが朝の支度をひとつずつチ…」と
切れ、**何のアプリか分からない**状態になっていた。2行まで許し
（`toolbarHeight: 72`）、全部読めるようにした。

### 4. 中身が嘘だった（**一番たちが悪かった**）

第1回では `最初の項目` / `2つめの項目` という **Forge の内部語**が2件
入った状態でアプリが開いていた。利用者から見れば、開いた瞬間に知らない
データが2件入っている。

`_DEFAULT_EXAMPLES` を空にしたら、今度は

* 「部署ごとの売上を月別に集計してグラフで比べたい」
* 「植物を育てながら音を組み合わせるゲームを作りたい」
* 「英単語を出題して、正解率の推移を見たい」

の**すべてが牛乳・卵・パンで始まった**。

追ったら、Planner が概念を1つも取り出せなかったときに
`data_needed: ["item"]` を差し込んでおり（`entities: []`）、Compiler の
`_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT["item"]` がそれを「品物 → 牛乳・卵・
パン」と解釈していた。

**`item` は語彙ではなく、何も分からなかったときの内部の既定値である。**
それを根拠に食品を並べるのは、分からないものを楽観側へ倒している
（`CLAUDE.md` §3「分からないものを楽観側へ倒さない」）。

直し方: Compiler で `["item"]` を「不明」として扱い、不明なら例示せず
**空状態を見せる**。`checklist` は `empty_state_text` を持っており、
「まだありません。追加してください」と**次にすることを言える**。

実測（再描画で確認）:

| 要求 | 第1回 | 第2回 |
|---|---|---|
| 部署ごとの売上を… | 牛乳・卵・パン | 空状態「まだ何もありません」 |
| 植物を育てながら… | 牛乳・卵・パン | 空状態 |
| 英単語を出題して… | 牛乳・卵・パン | 空状態 |
| **買い物リストを作りたい** | 牛乳・卵・パン | **牛乳・卵・パン（正しい）** |
| 写真 / 作業記録 / 子ども向け | 意味のある例 | 意味のある例（維持） |

**分かるときは今までどおり出す。** 分からないときだけ黙る。

> これは同じ穴の2度目である。#29「mockの品質: 内部識別子を出さない」で
> 一度直したが、**fallback 経路だけ残っていた**。

`forge_ai/tests/test_compiler.py` の4件は `item` = 食料品を前提に書かれて
いたので書き直した（3件は本物の `task` 概念へ差し替えて provider fallback
を確かめる意図を保存、1件は「空になる」ことを主張する意図へ変更）。

---

## 自分の判定を1件撤回した

第1回で **「touch target が約24px」と書いたのは誤り**である。

`IconButton` の既定タップ領域は **48px** あり、私が測ったのは
**グリフの大きさ**だった。**スクリーンショットに写らないものを写真から
判定していた。**

manifest に訂正を残した。「直すべきものの順」の4番は
「元から通っていた（第1回の判定が誤り）」へ書き換えている。

---

## 第3回 — 名付けを生成の一部にした

### やったこと

`Intent.goal`（＝文）を**そのままアプリ名にしていた**のをやめた。
`forge_ai/core/naming.py` を新設し、compile の2経路
（`forge_ai/core/compiler.py` / `forge_ai/core/ir/forge_language_compiler.py`）
の**両方**を通した。名付けが1か所に集まる。

候補を上から順に `is_name_like()` へ通し、最初に通ったものを採る。

| | 出所 | 例 |
|---|---|---|
| 1 | AI が名付けたもの | — |
| 2 | 取り出せた概念のラベル | 家計簿記録 / 釣果記録 |
| 3 | Domain の日本語名 | やること / 買い物 |
| 4 | **どれも通らない** | **新しいアプリ** |

`is_name_like()` が落とすもの: 句読点を含む / 願望・依頼の語尾を含む
（したい・ほしい・して・できるように…）/ 14文字超 / **英小文字の
内部識別子**（`item`・`fish_record`）。

> **要求文は出所で弾いていない。形で弾いている。**
> 「買い物リストを作りたい」→「買い物リスト」のように、語尾を落とした
> 結果が短い名詞句なら、それは名前なので通す。
> 出所で弾くと、この正しい名前まで落ちる。

### 実測（AppBar に出た文字列）

| Need | 第2回まで | 第3回 |
|---|---|---|
| 毎日の収入と支出を記録して残高を見たい | 要求文そのまま | **家計簿記録** |
| 今日やる作業を登録して、終わったものを… | 要求文そのまま | **やること** |
| 釣った場所を地図に残して魚の種類を記録したい | 要求文そのまま | **釣果記録** |
| 買い物リストを作りたい | 買い物リスト | 買い物リスト（変わらず） |
| 子どもが朝の支度を… | 要求文そのまま | こどもの成長 ← **誤り** |
| 旅行の写真を日付ごとに残してメモを付けたい | 要求文そのまま | 旅行 ← **誤り** |
| 部署ごとの売上を月別に… | 要求文そのまま | **新しいアプリ** |
| 植物を育てながら音を組み合わせるゲーム… | 要求文そのまま | **新しいアプリ** |
| 英単語を出題して、正解率の推移を見たい | 要求文そのまま | **新しいアプリ** |

### 直した結果、見えたもの（2つとも報告する）

#### (a) 名前が**自信を持って間違える**ようになった

「子どもが朝の支度をひとつずつチェックできるようにしたい」は
朝の支度のチェックリストである。Forge は `child_growth` と判定し、
「こどもの成長」という名前で**体重測定・身長測定**を並べた。

「旅行の写真を…」も `travel` と判定し、「旅行」という名前の
**持ち物リスト**（充電器・着替え・歯ブラシ）になった。

**これは名付けの失敗ではなく Domain 判定の失敗である。**
第2回までは要求文がタイトルに出ていたので、画面が要求とずれていても
**タイトルだけは正しく見えていた**。それが誤判定を隠していた。
名前にした結果、ずれが画面へ出るようになった。
**隠れている不具合より、見えている不具合の方がよい。**

新しい項目としてこの report と `TECH_DEBT.md` に残す（TD89）。

#### (b) 3アプリが**ピクセル単位で同一**になった

analytics / game / study の PNG が全 viewport でバイト単位一致する。

```
26659 analytics-small-320x640.png
26659 game-small-320x640.png
26659 study-small-320x640.png
```

第3回で悪化したのではない。**元から同じだったものが、飾り（要求文の
タイトル）が取れて見えるようになった**だけである。TD87 の症状。

### `新しいアプリ` は逃げではないか

逃げではない。Forge はこの3件を Domain として理解できていない
（`generic` へ落ちる）。理解していないのに要求文を名前にすると、
**理解しているように見える**。`UNKNOWN` を既定値にするのと同じ判断で
ある（`CLAUDE.md` §3）。

### 配線破壊試験（6件すべて落ちた。置物なし）

| | 外したもの | 結果 |
|---|---|---|
| M1 | `compiler.py` が `decide_app_name` を使わない | backend 5件 FAIL |
| M2 | `forge_language_compiler.py` が使わない | backend 4件 + forge_ai 1件 FAIL |
| M3 | `is_name_like()` を常に True | backend 3件 + forge_ai 7件 FAIL |
| M4 | 内部識別子ガードを外す | forge_ai 4件 FAIL（うち1件は本番 pipeline の E2E） |
| M5 | `generic` Domain も名前として使う | backend 1件 + forge_ai 1件 FAIL |
| M6 | GENERIC の代わりに要求文を返す | backend 4件 + forge_ai 2件 FAIL |

M4 は HTTP のテストでは落ちない（本番の Entity ラベルは日本語なので
識別子経路へ入らない）。ただし `test_pipeline.py` の
`run_cognitive_pipeline` を通す E2E が落とすので、単体テストだけの
置物ではない。**正直に区別して書く。**

### 「作ったが本番から呼ばれない」を作らないための配線

`backend/tests/test_generated_app_naming.py` は**本番の HTTP**
（`POST /api/v1/ai/generate`）を叩き、返ってきた Document の
`app.title` と `screen.title` を見る。撮影対象と**同じ8つの Need**を
使う——絵とテストが別の入力を見ていると、絵で見つけた問題を
テストで固定できない。

### 途中で1つ、自分の書いたテストが間違っていた

最初 `assertNotIn(title, need)`（アプリ名が要求文の部分文字列でないこと）
と書いたが、**正しい名前が落ちた**——「旅行の写真を…」に対する「旅行」は
要求文の部分文字列でありながら良い名前である。名前が要求と語を共有する
のは当たり前であって欠陥ではない。この行は消し、理由をテストへ書いた。

---

## 残っているもの

| | 内容 | 状態 |
|---|---|---|
| ~~1~~ | アプリ名を生の要求文にしている | ✅ 第3回で完了 |
| **5** | checklist へ落ちる範囲が広すぎる（TD87） | ⬜ **残っている（本体）** |
| **6** | Domain 判定が外れる（TD89、新規） | ⬜ 8件中2件 |

### 1 を第2回で直さなかった理由（記録として残す）

見出しの**省略**は直した。しかし「毎日の収入と支出を記録して残高を見たい」
が**アプリ名として出ている**ことは直っていない。

日本語の願望文（〜したい / 〜できるようにしたい）から名詞句を取り出すのは
形態素解析なしでは壊れやすい。「残高を見たい」から「たい」だけ落とすと
**「残高を見」**になる。**半端に壊れた名前は、元の文より悪い。**

推測で直さない（`CLAUDE.md` §3）。

第3回では**文から名詞句を取り出すのをやめ**、名付けを段階のある選択に
した。願望文を削る処理は1つも足していない——**削らずに、落とす**。

### 5 が本体である

写真・分析・学習・ゲームが全部 checklist になるのは Capability 分解が
効いていない証拠である。`LEARNABLE-LOCAL-AI-VISION.md` §22。

---

## 足したもの / 直した撮影基盤

- `scripts/export_quality_gate_fixtures.py` — **本番から**撮影対象を作る
- `scripts/capture_quality_gate_v2.py` — 4 viewport × N アプリ撮影
- `frontend/lib/forge_quality_gate_visual.dart` — 撮影ハーネス。
  未知のキーは**赤い MISSING FIXTURE** を描く（白紙と区別するため）

撮影基盤で踏んだ穴:

- CanvasKit を CDN から取れず engine が起動せず、**真っ白な PNG** が
  出ていた → `flutter build web --no-web-resources-cdn`
- Google Fonts が拒否され、字が出ないうえ **engine 初期化がフォントの
  timeout(~15s) を待つ**ので固定待ちの撮影が白紙になった →
  `flutter-view` セレクタを待ち、`fonts.gstatic.com` をローカルの
  IPAGothic へ回す
- 二重挿入ガードが `canvasKitBaseUrl` の**部分一致**で minify 済みコードに
  当たり、**一度も挿入されないまま**白紙を作っていた → 挿入する文字列
  そのものを印にした

> **白紙の PNG を「実描画の証拠」として出す寸前だった。** manifest に
> 記録した。

---

## この評価の限界（正直な申告）

- **字形は本番と違う。** この container は `fonts.gstatic.com` を拒否する
  ので、撮影時だけローカルの IPAGothic を差し替えている。配置・重なり・
  階層は見てよいが、字形と字送りは本番と一致しない
- **contrast と accessibility を数値で測っていない。** 目視のみ。UNVERIFIED
- **操作していない。** 静止画のみ。タップ後の挙動・入力後の描画・
  スクロールは見ていない
- **生成は `provider=mock`**（Curated Domain Library）。実 LLM が入ると
  別の結果になりうる（**Real Local Model runs = 0**）

---

## 検証

```
backend  : 1744 passed, 16 skipped   （+5: test_generated_app_naming.py）
forge_ai :  537 passed               （+16: test_naming.py）
flutter  : analyze No issues found / 514 passed
ruff     : 変更したファイルは clean
           （repo 全体の 17 件は既存の E402/F401。CI は ruff を実行しない）
```
