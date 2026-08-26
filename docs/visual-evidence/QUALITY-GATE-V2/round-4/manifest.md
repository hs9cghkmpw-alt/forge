# Generated UI Quality Gate v2 — 第4回（Round 4）

- Task: GENERATED-UI-QG-V2-R4（CEO指示、2026-08-26）
- 詳細: `docs/reports/FORGE-020A1-QG-V2-R4-report.md`
- 第1〜3回: `../manifest.md`（`before/` = 第1回、`after/` = 第2・3回）
- 環境: Flutter 3.44.9 stable / Chromium (Playwright) / Linux container

---

## 判定

| | 置き場 | Golden Quality Gate |
|---|---|---|
| 第1回 | `../before/` | **FAIL**（8アプリが3種類の画面） |
| 第2回 | `../after/` | **FAIL**（崩れは直った） |
| 第3回 | `../after/`（上書き） | **FAIL**（名前は名前になった） |
| **第4回** | **`round-4/`** | **FAIL**（**理由が変わった**） |

> 第3回までが `after/` を共用しているのは記録上の弱点である。
> Round 4 から versioned path にした。**上書きしない。**

---

## TD87 は解消した

**32枚に重複が1枚も無い**（`md5sum | awk '{print $1}' | sort | uniq -d`
が 0 件）。

第3回では analytics / game / study が**全 viewport でバイト単位一致**
していた。3つの全く違う要求が1枚の絵になっていた。

widget 型数の比較:

| | 第3回 | 第4回 |
|---|---|---|
| finance | 21 | 21 |
| worklog | 7 | 7 |
| kids | 7 | 7 |
| photo | **7** | **17** |
| map | 20 | 20 |
| game | **7** | **16** |
| analytics | **7** | **19** |
| study | **7** | **19** |

---

## TD89 も解消した（画像で確認）

| 画像 | 第3回 | 第4回 |
|---|---|---|
| `kids-mobile-390x844.png` | 「こどもの成長」＋ 体重測定・身長測定 | **「支度」＋空状態** |
| `photo-mobile-390x844.png` | 「旅行」＋ 充電器・着替え・歯ブラシ | **「写真記録」＋ 写真 / 日付 / メモ** |
| `study-mobile-390x844.png` | 「新しいアプリ」＋ チェックリスト2行 | **「単語」＋ 単語 / 正解率** |
| `analytics-mobile-390x844.png` | 「新しいアプリ」＋ チェックリスト2行 | **「売上記録」＋ 部署 / 金額** |

---

## それでも FAIL — 3つの理由

### 1. ゲームがゲームではない（最大）

「植物を育てながら音を組み合わせるゲーム」は、実際には
**植物と音を記録する CRUD** である（`game-desktop-1440x900.png`）。

Capability Plan は `simulate.loop` と `media.compose` を `MISSING` と
**正しく名指ししている**。しかし**その事実が利用者に一切見えない**。
Forge は知っているのに黙っている。

> これが次に直すべきものである。「作れない」と分かっているなら、
> 画面か会話でそう言う。

### 2. record_log 系4本の入口が似ている

photo / map / game / analytics / study はどれも
**3タブ CRUD + フォーム**で始まる。Shape は違う（record_log /
+group_compare / +trend）が、**第1画面の見た目が同じ**である。

Shape の違いは一覧タブ側に出るので、入口だけ見ると区別が付かない。

### 3. 集計・推移の画面を撮れていない

`analytics.json` には `bar_chart` と `metric_view(aggregate=sum)` が
**実在する**。しかし一覧タブにあるので、静止画では写らない。

**「撮れていない」と「無い」は違う。** ここは前者である。
撮影ハーネスがタブを操作できないという**この評価の限界**であって、
生成物の欠落ではない。

---

## Golden Gate の判定（人が全部開いて見た）

「このまま普通のアプリとして使いたいと思えるか」

| アプリ | 判定 |
|---|---|
| 支度（kids） | ○ 思える |
| やること（worklog） | ○ 思える |
| 家計簿記録（finance） | ○ 思える |
| 釣果記録（map） | ○ 思える |
| 単語（study） | △ 惜しい（推移が入口で見えない） |
| 写真記録（photo） | △ 惜しい（写真が文字入力） |
| 売上記録（analytics） | △ 惜しい（グラフが入口で見えない） |
| 植物（game） | ✗ **ゲームではない** |

**1つでも「ゲームだと言われたものがゲームでない」なら FAIL。**
結果を先に決めない、という約束どおり FAIL のままにする。

---

## この評価の限界（正直な申告、据え置き）

- **字形は本番と違う。** `fonts.gstatic.com` を拒否するので、撮影時だけ
  ローカルの IPAGothic を差し替えている
- **contrast / accessibility を数値で測っていない。** 目視のみ。UNVERIFIED
- **操作していない。第1タブしか写っていない**（上の 3.）
- **生成は `provider=mock`。** 実 LLM が入ると別の結果になりうる
  （**Real Local Model runs = 0**）
