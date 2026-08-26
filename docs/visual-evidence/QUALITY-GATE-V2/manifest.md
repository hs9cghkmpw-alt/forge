# Generated UI Quality Gate v2 — 第1回

- Task: Generated UI Quality Gate v2（`docs/spec/GENERATED-UI-QUALITY-GATE-V2.md`）
- Branch: `claude/forge-master-handoff-k46jns`
- Implementation Agent: Claude Code
- 実施日: 2026-08-26
- 環境: Flutter 3.44.9 stable / Chromium (Playwright) / Linux container

---

## 判定

> ## Golden Quality Gate: **FAIL**
>
> 「このまま普通のアプリとして使いたいと思えるか」——**思えない。**

崩れているから落ちたのではない。**同じ画面しか出てこないから**落ちた。

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
| touch target | **要修正** | チェック丸・削除 ✕ が約 24 CSS px。44px 下限を下回る |
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

## 直すべきものの順（提案）

1. **アプリ名を生の要求文にしない** — 見出しの省略はこれが原因。
   命名は生成の一部である
2. **仮データを空状態にする** — `最初の項目` はアプリの中身ではない
3. **desktop / tablet の最大幅と列** — 単一列全幅をやめる
4. **touch target 44px 下限**
5. **checklist へ落ちる範囲を狭める** — 写真・分析・学習・ゲームが
   全部 checklist になるのは、Capability 分解が効いていない証拠。
   `docs/LEARNABLE-LOCAL-AI-VISION.md` §22 の Registry 作り直しと同じ根

1〜4 は Renderer / Design Language の話で、**今の土台のまま直せる**。
5 は生成側の話であり、**Capability Registry の作り直し**が要る。

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
