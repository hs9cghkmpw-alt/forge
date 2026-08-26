# Generated UI Quality Gate v2 — 第1回・第2回・第3回

- Task: Generated UI Quality Gate v2（`docs/spec/GENERATED-UI-QUALITY-GATE-V2.md`）
- Branch: `claude/forge-master-handoff-k46jns`
- Implementation Agent: Claude Code
- 実施日: 2026-08-26
- 環境: Flutter 3.44.9 stable / Chromium (Playwright) / Linux container

---

## 判定

| | Golden Quality Gate |
|---|---|
| 第1回（修正前） | **FAIL** |
| 第2回（崩れを直した） | **FAIL**（改善したが、まだ「使いたい」とは言えない） |
| 第3回（名付けを直した） | **FAIL**（名前は名前になった。**中身が同じことが、かえってはっきりした**） |

「このまま普通のアプリとして使いたいと思えるか」——**まだ思えない。**

崩れているから落ちたのではない。**同じ画面しか出てこないから**落ちた。
第2回でも、そこは変わっていない。

`before/` = 第1回、`after/` = 第2回（修正後の再描画）。

### 第2回で直ったもの

| 軸 | 第1回 | 第2回 |
|---|---|---|
| overflow / clipping | FAIL | **PASS** — `date_field` のラベル貫通を修正 |
| content fit | FAIL | **PASS** — 本文を最大 720px に制限（desktop） |
| long-text resilience | FAIL | **PASS** — 見出しを2行まで許可、省略が消えた |
| empty-state quality | FAIL | **PASS** — 偽の中身をやめ、空状態を出す |

### 第2回でも直っていないもの

**8アプリが3種類の画面にしかならない。** ここが本体である。

---

## 何をしたか

```
scripts/export_quality_gate_fixtures.py   本番の /generate で 8 アプリ生成
  → frontend/lib/forge_quality_gate_visual.dart（同じ Renderer で描く）
  → flutter build web --debug --no-web-resources-cdn
  → scripts/capture_quality_gate_v2.py     4 viewport × 8 = 32 枚
  → **全部開いて目視**
```

Document は**本番が返したもの**であり手書きではない。ハーネスに
アプリごとの分岐は書いていない（書いた時点で測りたいものが測れない）。

---

## 最大の発見: 8 アプリが 3 種類の画面にしかならない

| 生成された画面 | アプリ |
|---|---|
| tracker（form + 一覧 + metric + chart、21 widget型） | finance |
| tracker（同上から choice_field を除く、20 widget型） | map |
| **checklist（7 widget型）** | **worklog / kids / photo / game / analytics / study** |

**6 アプリが構造的に同一である。** widget 型の集合が完全に一致する。

実描画でも同じだった。「部署ごとの売上を月別に集計してグラフで比べたい」
（データ分析）と「子どもが朝の支度をひとつずつチェックできるように
したい」（子ども向け）は、

* 同じチェックリスト2行（`最初の項目` / `2つめの項目`）
* 同じ「追加する」入力欄と「追加」ボタン
* 同じ余白、同じ字送り、同じ密度

で、**違うのは追加ボタンの色だけ**（オレンジ / 青）。

`before/analytics-mobile-390x844.png` と `before/kids-mobile-390x844.png`
を並べて見ると分かる。

### これは「崩れていない」

overlap も overflow も無い。**だから v1 の基準なら通ってしまう。**
Quality Gate v2 が要る理由がここにある。

### Product Direction に照らすと

`docs/GENERATIVE-SOFTWARE-DIRECTION.md` §1:

> Widget / Component / Template は primitive である。
> **Forge が生成できる Software の境界ではない。**

いまの Forge は、境界が **2 template** である。写真アプリにも、
ゲームにも、分析ツールにも、学習アプリにも**チェックリストを出している。**

---

## 見つけた実バグ（修正済み・再描画で確認）

### `date_field` のラベルを枠線が貫通する

`before/finance-desktop-1440x900.png` / `defect-date-field-before.png`

「日付」のラベルが浮いたまま描画され、入力欄の**上枠線が文字を貫通**
していた。

- **全 viewport で再現**（mobile / small / tablet / desktop）
- 原因: `InputDecorator.isEmpty` の既定は `false`。渡していなかったので
  「値が入っている」と見なされ、空でもラベルが浮いた。ForgeTheme の
  `OutlineInputBorder`（角丸 20）と衝突する
- 直し: `isEmpty: currentValue.isEmpty` を渡す。空なら他の入力欄と同じ
  ように内側へ、入力後は notch 付きで浮く
- 確認: `defect-date-field-after.png`（再 build → 再撮影 → 目視）

> **019C の Visual Review では見つからなかった。** あのときは同じ
> 家計簿でも「一覧」タブしか見ておらず、`date_field` を含む「追加」
> タブを描いていなかった。**1画面だけ見て「実描画を確認した」と
> 言っていた**ことになる。

---

## 13 軸の評価

| 軸 | 判定 | 見たこと |
|---|---|---|
| overflow / clipping | **FAIL → 修正済** | `date_field` のラベルを枠線が貫通（全 viewport）。直して再描画で確認 |
| hierarchy | **FAIL** | checklist 6 アプリに階層が無い。見出し＝生の要求文、あとは同列の2行 |
| typography | **FAIL** | 8 アプリすべて同じ字種・同じ大きさ。子ども向けも分析ツールも同一 |
| spacing | PASS | 間隔は一定。崩れは無い |
| density | **FAIL** | 全 viewport で内容が上部 30〜55% に収まり、下が空。desktop で顕著 |
| contrast | PASS（要再測） | 目視では読める。**数値としては測っていない**（UNVERIFIED） |
| empty-state quality | **FAIL** | 空状態が無い。代わりに `最初の項目` / `2つめの項目` という**内部の仮データ**が出ている |
| long-text resilience | **FAIL** | 見出しが `子どもが朝の支度をひとつずつチ…` と省略。**生の要求文をアプリ名にしている** |
| navigation clarity | **FAIL**（desktop） | tab が 1440px に等間隔で散り、関連が読めない。checklist 系は画面1枚で navigation 自体が無い |
| touch target | **PASS（第1回の記載を訂正）** | 第1回は「約 24px で下限割れ」と書いたが**誤り**。実装は `IconButton` であり、Material の既定で **48px の tap 領域**を持つ。**画像で測ったのは字の大きさであって、触れる範囲ではない**——スクリーンショットに写らないものを写真から判定していた。見た目の小ささは残るが、この軸は通る |
| visual identity | **FAIL** | アプリごとの佇まいが**アクセント色1つ**しか変わらない |
| content fit | **FAIL**（desktop） | 入力欄・ボタンが 1950px 幅まで伸びる。金額欄が画面いっぱい |
| accessibility | UNVERIFIED | contrast 比・意味ラベル・screen reader は**測っていない** |

**PASS 2 / FAIL 9 / 要修正 1 / UNVERIFIED 1。**

---

## viewport 別

| viewport | 所見 |
|---|---|
| 390×844 (mobile) | 基準。破綻なし。ただし下半分が空 |
| 320×640 (small) | 破綻なし。`193,000 円` 等も切れない |
| 834×1112 (tablet) | mobile をそのまま引き伸ばした状態。列は増えない |
| 1440×900 (desktop) | **最も悪い。** 単一列のまま全幅へ伸び、フォーム1行が約 1950px |

**どの viewport でもレイアウトが変わらない。** 幅が増えても列は増えず、
最大幅の制限も無い。

---

## 第2回で直したもの（すべて再描画で確認）

### 1. `date_field` のラベルを枠線が貫通する

`InputDecorator.isEmpty` の既定は `false`。渡していなかったので空でも
ラベルが浮き、`OutlineInputBorder`（角丸20）と衝突していた。
`isEmpty: currentValue.isEmpty` を渡した。
→ `defect-date-field-after.png`

### 2. 広い画面で入力欄が 1950px まで伸びる

本文を `maxWidth: 720` で中央寄せにした。**mobile では何も変わらない**
——すでに通っている見た目を壊さずに、広い画面だけ直す。
→ `after-desktop-content-fit.png` / `after/finance-desktop-1440x900.png`

### 3. 見出しが1行で省略される

`AppBar` の既定 maxLines 1 をやめ、2行まで許した（`toolbarHeight: 72`）。
「部署ごとの売上を月別に集計してグラフで比べたい」が全部読める。
→ `after/analytics-mobile-390x844.png`

### 4. 中身が嘘だった

**これが一番たちが悪かった。**

第1回では `最初の項目` / `2つめの項目` という**Forge の内部語**が
2件入った状態でアプリが開いていた。それを直したら、今度は

* 「部署ごとの売上を月別に集計してグラフで比べたい」
* 「植物を育てながら音を組み合わせるゲームを作りたい」
* 「英単語を出題して、正解率の推移を見たい」

の**すべてが牛乳・卵・パンで始まった**。

追ったら、Planner が概念を1つも取り出せなかったときに
`data_needed: ["item"]` を差し込んでおり（`entities: []`）、
Compiler 側の `_EXAMPLE_ITEMS_BY_PRIMARY_CONCEPT["item"]` が
それを「品物 → 牛乳・卵・パン」と解釈していた。

`item` は語彙ではなく、**何も分からなかったときの内部の既定値**である。
それを根拠に食品を並べるのは、分からないものを楽観側へ倒している
（`CLAUDE.md` §3）。

分からないときは例示を出さず、**空状態を見せる**ようにした。

* 「まだ何もありません」＋「追加する」欄 → 次にすることが分かる
* **本物の買い物アプリは牛乳・卵・パンのまま**（`買い物リストを作りたい`
  で確認）——分かるときは今までどおり出す

> これは同じ穴の2度目である。#29「mockの品質: 内部識別子を出さない」で
> 一度直したが、**fallback 経路だけ残っていた**。

## 第3回 — 名付けを生成の一部にした（2026-08-26）

`after/` を撮り直した（32枚）。生成物も入れ替わっている
（`docs/evidence/quality-gate-v2/`）。

### 何を変えたか

`Intent.goal`（＝文）を**そのままアプリ名にしていた**のをやめた。
`forge_ai/core/naming.py` を新設し、compile の2経路
（`compiler.py` / `ir/forge_language_compiler.py`）を通した。

候補を上から順に `is_name_like()` へ通し、最初に通ったものを採る。

1. AI が名付けたもの
2. 取り出せた概念のラベル（「家計簿記録」「釣果記録」）
3. Domain の日本語名（「やること」「買い物」）
4. どれも通らなければ **`新しいアプリ`**——分からなかったと認める

**要求文は検査を通らない**（実測: 8件すべて落ちる）。
逆に「買い物リストを作りたい」→「買い物リスト」のように、
語尾を落とした結果が短い名詞句なら**それは名前なので通す**。
判定するのは出所ではなく**形**である。

### 実測（AppBar に出た文字列）

| Need | 第2回まで | 第3回 |
|---|---|---|
| 毎日の収入と支出を記録して残高を見たい | 要求文そのまま | **家計簿記録** |
| 今日やる作業を登録して、終わったものを… | 要求文そのまま | **やること** |
| 釣った場所を地図に残して魚の種類を記録したい | 要求文そのまま | **釣果記録** |
| 買い物リストを作りたい | 買い物リスト | 買い物リスト（変わらず） |
| 子どもが朝の支度を… | 要求文そのまま | こどもの成長 ← **誤り、下記** |
| 旅行の写真を日付ごとに残してメモを付けたい | 要求文そのまま | 旅行 ← **誤り、下記** |
| 部署ごとの売上を月別に… | 要求文そのまま | **新しいアプリ** |
| 植物を育てながら音を組み合わせるゲーム… | 要求文そのまま | **新しいアプリ** |
| 英単語を出題して、正解率の推移を見たい | 要求文そのまま | **新しいアプリ** |

### 直した結果、見えたもの（2つとも報告する）

#### 1. 名前が**自信を持って間違える**ようになった

「子どもが朝の支度をひとつずつチェックできるようにしたい」は
**朝の支度のチェックリスト**である。しかし Forge は `child_growth`
Domain と判定し、「こどもの成長」という名前で
**体重測定・身長測定**を並べた（`after/kids-mobile-390x844.png`）。

「旅行の写真を日付ごとに残してメモを付けたい」も同じで、
`travel` と判定して「旅行」という名前の**持ち物リスト**
（充電器・着替え・歯ブラシ）になった（`after/photo-mobile-390x844.png`）。

> **これは名付けの失敗ではなく、Domain 判定の失敗である。**
> 第2回までは要求文がタイトルに出ていたので、画面が要求とずれていても
> **タイトルだけは正しく見えていた**。それが誤判定を隠していた。
>
> 名前にした結果、ずれが**画面に出る**ようになった。
> 隠れている不具合より、見えている不具合の方がよい。

#### 2. 3アプリが**ピクセル単位で同一**になった

analytics / game / study の PNG が**全 viewport でバイト単位一致**する。

```
26659 analytics-small-320x640.png
26659 game-small-320x640.png
26659 study-small-320x640.png
```

第2回までは、タイトルに要求文が出ていたぶん**見た目が違って見えた**。
名前を揃えた（どれも「新しいアプリ」）ことで、
**3つの全く違う要求が、同一の1枚の絵になる**ことがはっきりした。

これは第3回で悪化したのではない。**元から同じだったものが、
飾りが取れて見えるようになった**だけである。TD87 の症状であり、
Capability Registry を作り直すまで消えない。

### `新しいアプリ` は逃げではないか

逃げである、とは考えていない。

* Forge はこの3件を**Domain として理解できていない**（`generic` へ落ちる）
* 理解していないのに要求文を名前にすると、**理解しているように見える**
* `CLAUDE.md` §3「分からないものを楽観側へ倒さない」

`UNKNOWN` を既定値にするのと同じ判断である。ここで良い名前が付くように
なるのは、Capability 分解が効くようになったときである。

### 検査（配線破壊試験）

直した配線を1つずつ外して、対応するテストが落ちることを確認した。
**6つ全部が落ちた（置物なし）。**

| | 外したもの | 結果 |
|---|---|---|
| M1 | `compiler.py` が `decide_app_name` を使わない | backend 5件 FAIL |
| M2 | `forge_language_compiler.py` が使わない | backend 4件 + forge_ai 1件 FAIL |
| M3 | `is_name_like()` を常に True | backend 3件 + forge_ai 7件 FAIL |
| M4 | 内部識別子ガードを外す | forge_ai 4件 FAIL（うち1件は本番 pipeline の E2E） |
| M5 | `generic` Domain も名前として使う | backend 1件 + forge_ai 1件 FAIL |
| M6 | GENERIC の代わりに要求文を返す | backend 4件 + forge_ai 2件 FAIL |

M4 だけは HTTP のテストで落ちない（本番の Entity ラベルは日本語なので
識別子経路へ入らない）。ただし `test_pipeline.py` の
`run_cognitive_pipeline` を通す E2E が落とすので、**単体テストだけの
置物ではない**。

### 途中で1つ、自分の書いたテストが間違っていた

最初 `assertNotIn(title, need)`（アプリ名が要求文の部分文字列でないこと）
と書いたが、**正しい名前が落ちた**——「旅行の写真を…」に対する「旅行」は
要求文の部分文字列でありながら良い名前である。

名前が要求と語を共有するのは当たり前であって、欠陥ではない。
見るべきは出所ではなく形なので、この行は消して理由をテストへ書いた。

## 直すべきものの順（提案）

| | 内容 | 状態 |
|---|---|---|
| ~~2~~ | 仮データを空状態にする | ✅ 第2回で完了 |
| ~~3~~ | desktop / tablet の最大幅 | ✅ 第2回で完了 |
| ~~4~~ | touch target | ✅ 元から通っていた（第1回の判定が誤り） |
| ~~1~~ | アプリ名を生の要求文にしない | ✅ 第3回で完了（`naming.py`） |
| **5** | **checklist へ落ちる範囲を狭める** | ⬜ **残っている（本体）** |
| **6** | **Domain 判定が外れる**（新規） | ⬜ 第3回で見えた。8件中2件が別分野と判定された |

### 1 をこのセッションで直さなかった理由

見出しの**省略**は直した（2行まで許した）。しかし
「毎日の収入と支出を記録して残高を見たい」が**アプリ名として出ている**
ことは直っていない。

日本語の願望文（〜したい / 〜できるようにしたい）から名詞句を取り出す
のは、形態素解析なしでは壊れやすい。「残高を見たい」から「たい」だけ
落とすと「残高を見」になる。**半端に壊れた名前は、元の文より悪い。**

推測で直さない（`CLAUDE.md` §3）。

**正しい直し方の候補**は2つある。

1. **命名を生成の一部にする** ← 本筋。名前を付けるのは理解の結果であり、
   AI がやるべき仕事である
2. Domain → 名前の対応表を fallback にする（`household_budget` → 家計簿）。
   Mock Provider は既に `_TOPIC_PROFILES` で似た表を持っている

### 5 が本体である

写真・分析・学習・ゲームが全部 checklist になるのは、Capability 分解が
効いていない証拠であり、`docs/LEARNABLE-LOCAL-AI-VISION.md` §22 の
Capability Registry 作り直しと**同じ根**である。

Renderer をいくら磨いても、**出てくる画面が2種類しかない**限り
Golden Quality Gate は通らない。

---

## この評価の限界（正直な申告）

- **字形は本番と違う。** この container は `fonts.gstatic.com` を拒否
  するので、撮影時だけローカルの IPAGothic を差し替えている。
  配置・重なり・階層は見てよいが、字形と字送りは本番と一致しない
- **contrast と accessibility を数値で測っていない。** 目視のみ。
  UNVERIFIED
- **操作していない。** 静止画のみで、タップ後の挙動・入力後の描画・
  スクロールは見ていない
- **生成は `provider=mock`**（Curated Domain Library）。実 LLM が
  入ると別の結果になりうる（`Real Local Model runs = 0`）
