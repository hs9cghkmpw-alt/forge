# Design Language V1

2026-08-17 / FORGE-R1-ENTRY-AND-DESIGN-LANGUAGE-014
実装: `backend/app/ai/runtime/design_language.py`（唯一の定義）

> この文書は**実装から生成した写し**である。語彙の正は Python 側にある。
> 説明と定義が別々に育ってずれるのを避けるため、`meaning` /
> `use_when` / `avoid_when` は実装のフィールドをそのまま出している。

---

## 1. これは何か

Product Direction §3 の分担を、実際の語彙として書き下したもの。

> **AIは意味を決める。Forgeは品質を保証する。**

```
❌ AIが決める:  font_size: 36 / color: "#23D18B" / padding: 16
✅ AIが決める:  metric.primary / finance.income / surface.elevated
   Forgeが保証: それが実際に何pxで何色になるか
```

## 2. なぜ値ではなく意味か

1. **生成品質** — 値のブレが構造的に消える
2. **Local AIが小さくて済む** — 語彙から1つ選ぶのは、色とサイズを
   整合的に生成するよりはるかに易しい
3. **Evidenceが意味単位で残る** — 「`#23D18B`が選ばれた」ではなく
   「`finance.income`が選ばれ、利用者がACCEPTEDした」が残る

3番目が閉ループの入口である。**見た目の作業が、そのままLocal AIの
学習素材になる。**

## 3. 使い方（Forge Language v1.10）

全Widget共通の任意キー。

```json
{"type": "section_header", "id": "list_header",
 "title": "支出", "style_role": "text.headline"}
```

* **v1.10以降**でのみ使える
* 語彙に無い値は Validator が `unknown_style_role` で落とす
* 自然言語は入らない（`[a-z][a-z0-9]*([._-][a-z0-9]+)*`、64文字以内）

## 4. 語彙（33件）

### typography

| role | 意味 | 使う | 使わない |
|---|---|---|---|
| `text.display` | 画面で最も大きい表示文字。 | アプリ名やオンボーディングの見出し。 | 本文。1画面に2つ以上。 |
| `text.headline` | セクションの主見出し。 | 画面内の大きな区切り。 | リスト項目のタイトル(それはtext.title)。 |
| `text.title` | カードやリスト項目のタイトル。 | 個々の項目の名前。 | 画面全体の見出し。 |
| `text.body` | 本文。既定の可読サイズ。 | 説明文・メモ・自由記述の表示。 | 数値の強調(それはmetric.*)。 |
| `text.label` | 入力欄やボタンに付く短い語。 | フィールド名・タブ名・凡例。 | 文章。 |
| `text.secondary` | 補助情報。本文より弱い。 | 日付・単位・注記・前月比の説明。 | 主要な内容。読めなくてよい情報ではないので、極端に小さくしない。 |
| `metric.primary` | 画面で**最も重要な単一のKPI**。 | 残高・合計・今日の達成率など、利用者が最初に見る1つの数値。 | リスト内の全数値。**同一画面で2つ以上使わない。** |
| `metric.secondary` | 主KPIを補足する数値。 | 前月比・内訳の小計・サブ指標。 | 主KPIと同じ大きさにしたい数値(それはmetric.primary)。 |

### color

| role | 意味 | 使う | 使わない |
|---|---|---|---|
| `color.primary` | アプリの主色。操作の中心。 | 主要CTA・選択状態・アクセント。 | 本文の色。警告の色。 |
| `color.secondary` | 副次的なアクセント。 | 補助的な操作・タグ。 | 主要CTA。 |
| `state.success` | 成功・達成・正常。 | 完了・目標達成・正常稼働。 | 収入(それはfinance.income)。意味が違うものを色で兼用しない。 |
| `state.warning` | 注意。まだ失敗ではない。 | 残量が少ない・期限が近い。 | エラー。 |
| `state.danger` | エラー・危険・不可逆操作。 | 削除・失敗・上限超過。 | 支出(それはfinance.expense)。 |
| `finance.income` | **金銭の増加**という意味。 | 収入・入金・プラスの残高変化。 | 一般的な成功(それはstate.success)。 |
| `finance.expense` | **金銭の減少**という意味。 | 支出・出金・マイナスの残高変化。 | エラー(それはstate.danger)。 |
| `text.primary` | 主要な文字色。 | 本文・見出しの色。 | 補助情報。 |

### surface

| role | 意味 | 使う | 使わない |
|---|---|---|---|
| `surface.background` | 画面全体の地の面。 | Scaffoldの背景。 | カード。 |
| `surface.card` | 情報のまとまりを載せる面。 | KPIカード・リスト項目の箱。 | 画面全体。 |
| `surface.elevated` | 背景より手前にある面。 | 強調したいカード・重ねて見せる領域。 | 全カード。**全部を持ち上げると階層が消える。** |
| `surface.selected` | 選択中であることを示す面。 | 選択されたタブ・行。 | 常時強調。 |

### shape

| role | 意味 | 使う | 使わない |
|---|---|---|---|
| `shape.small` | 小さい角丸。 | チップ・小ボタン。 | 大きなカード。 |
| `shape.medium` | 標準の角丸。 | カード・入力欄。 | 円形にしたいもの。 |
| `shape.large` | 大きい角丸。 | ヒーローカード・シート。 | 小さな要素。 |
| `shape.pill` | 完全な丸み。 | タグ・フィルタチップ。 | 文章を含む広い面。 |

### density

| role | 意味 | 使う | 使わない |
|---|---|---|---|
| `density.compact` | 情報を詰める。 | 一覧・タスクリスト。 | 読ませたい本文。 |
| `density.normal` | 標準の余白。 | 多くの画面の既定。 | — |
| `density.relaxed` | ゆったり見せる。 | 日記・ウェルネスなど落ち着かせたい画面。 | 密度が要る一覧。 |

### component

| role | 意味 | 使う | 使わない |
|---|---|---|---|
| `button.primary` | その画面の主要操作。 | 保存・追加・実行。**画面に1つ。** | 取り消し・戻る。 |
| `button.secondary` | 副次的な操作。 | キャンセル・絞り込み。 | 主要操作。 |
| `card.metric` | KPIを見せるカード。 | 残高・達成率のヒーロー領域。 | 自由記述の表示。 |
| `card.summary` | 内訳・要約を見せるカード。 | カテゴリ別集計・週次まとめ。 | 単一KPI(それはcard.metric)。 |
| `card.list` | 繰り返し項目を並べるカード。 | 記録一覧・タスク一覧。 | 単発の情報。 |
| `navigation.primary` | 画面間の主要な行き来。 | 下部ナビ・主要タブ。 | 画面内の絞り込み。 |

## 5. Local AI との関係

この語彙は「見た目の設定」ではなく、**Local AIが将来選ぶ出力言語の
一部**である。`knowledge_entries()`がRAGへ渡せる形を返す。

**まだAIはroleを選んでいない**（TD69）。現在出ているroleはすべて
Compilerが構造から決めたものである。Conversation/Cognitive Pipelineへ
語彙を渡すのがR2の最初の作業。

## 6. 増やすときの条件

語彙を無制限に増やさない。増やす前に:

* 既存の組み合わせで表現できないか
* Golden App以外にも一般化するか

語彙が増えるほど、AIが選び間違える余地と、Runtimeが保証すべき
組み合わせが増える。
