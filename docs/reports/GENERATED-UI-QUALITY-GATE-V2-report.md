# Generated UI Quality Gate v2 — 第1回・第2回 report

- Task: Generated UI Quality Gate v2（CEO指示、2026-08-26）
- 仕様: `docs/spec/GENERATED-UI-QUALITY-GATE-V2.md`
- 証拠: `docs/visual-evidence/QUALITY-GATE-V2/manifest.md`（**全文はこちら**）
- Branch: `claude/forge-master-handoff-k46jns`
- 実施日: 2026-08-26

---

## 結論を先に

> ### Golden Quality Gate: **第1回 FAIL / 第2回 FAIL**

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

## 残っている2件

| | 内容 | 状態 |
|---|---|---|
| **1** | アプリ名を生の要求文にしている | ⬜ **残っている（最優先）** |
| **5** | checklist へ落ちる範囲が広すぎる | ⬜ **残っている（本体）** |

### なぜ 1 を今回直さなかったか

見出しの**省略**は直した。しかし「毎日の収入と支出を記録して残高を見たい」
が**アプリ名として出ている**ことは直っていない。

日本語の願望文（〜したい / 〜できるようにしたい）から名詞句を取り出すのは
形態素解析なしでは壊れやすい。「残高を見たい」から「たい」だけ落とすと
**「残高を見」**になる。**半端に壊れた名前は、元の文より悪い。**

推測で直さない（`CLAUDE.md` §3）。正しい直し方の候補:

1. **命名を生成の一部にする** ← 本筋。名前を付けるのは理解の結果であり、
   AI がやるべき仕事である
2. Domain → 名前の対応表を fallback にする（`household_budget` → 家計簿）。
   Mock Provider は既に `_TOPIC_PROFILES` で似た表を持っている

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
backend  : 1739 passed, 16 skipped
forge_ai :  521 passed
flutter  : analyze No issues found / 514 passed
ruff     : 変更した3ファイルは clean
           （repo 全体の 17 件は既存の E402/F401。CI は ruff を実行しない）
```
