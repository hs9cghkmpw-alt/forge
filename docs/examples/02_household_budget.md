# Example 2: 家計簿

## User Input
「毎月の支出を記録して、カテゴリごとに集計できる家計簿がほしい」

## Normalized Input
raw_inputと同一。

## Ambiguities
| category | severity | evidence |
|---|---|---|
| missing_data | MEDIUM | 「カテゴリ」の具体的な区分(食費/交通費等)が未指定。ただし後から
  ユーザーが自由入力できる設計にすれば安全に継続可能なためMEDIUM(HIGHへ
  格上げしない) |

overall_severity: MEDIUM(複数案を保持: 「固定カテゴリ一覧を用意する案」
と「自由入力カテゴリ案」の2案でApplication Planを仮生成し、Criticスコアで
自由入力案を採用)。

## Intent
```
primary_goal: "月次支出の記録と集計"
required_actions: ("記録", "集計", "カテゴリ分類")
required_data: ("金額", "カテゴリ", "日付")
constraints: ("月単位の集計",)
success_conditions: ("カテゴリごとの合計が確認できる",)
open_questions: ("カテゴリの初期セットが必要か",)
confidence: 0.78
```

## Domain
`primary_domain: household_budget`(confidence 0.88)。
candidate_domains: `(inventory: 0.1)`(却下: 在庫ではなく金銭記録のため)。

## World Model
```
Actors: 本人
Entities: transaction(取引), category(カテゴリ), budget(予算、任意)
Relationships: 取引がカテゴリに属する
Rules: 金額は正数のみ(支出額として)
Events: 取引記録, カテゴリ別集計表示
States: transaction一覧, カテゴリ別合計(派生値)
Permissions: 単一利用者のみ
```

## Requirements(抜粋)
- Functional(must): 取引の記録(金額・カテゴリ・日付)、カテゴリ別集計表示。
- Data(must): 取引リスト。
- Non-Functional(should): 集計はリアルタイムに近い形で反映。
- Validation(must): 金額が数値であること。

## Template Candidates
| template | score | 主な理由 |
|---|---|---|
| tracker | 0.80 | 継続的な記録+集計という性質に合致 |
| dashboard | 0.55 | 集計表示は該当するが、記録操作自体はtrackerの方が主体 |
| form | 0.40 | 1件の記録操作はform的だが、継続的な履歴管理にはtrackerが適する |

## Selected Template
`tracker`(スコア差はあるが僅差寄りのため、LLM tie-breakでdashboardとの
使い分けを確認: 「記録」が主目的でありtrackerを最終選択)。

## Application Plan(抜粋)
```
screens: (main: 一覧+集計表示, add: 記録入力)
navigation_edges: (("main", "add"), ("add", "main"))
state_requirements: ("transactions: string_list相当の構造", "new_amount: number", "new_category: string")
action_requirements: ("add_transaction", "navigate")
validation_requirements: ("金額は数値かつ0より大きい",)
unassigned_requirements: ("固定カテゴリ一覧の提示(Open Questionのため保留)",)
```

## Critic Findings
`overall_score: 0.74`、`release_ready: false`。
issue: `{severity: major, affected_component: "add画面", recommended_fix:
"カテゴリ入力が自由記述のみだと表記揺れが集計を壊すため、既存カテゴリの
候補表示を追加検討", auto_fixable: false}`。

## Revision
1回目: カテゴリを自由入力+既存入力からの候補提示という設計に変更。
再評価: `overall_score: 0.85`、`release_ready: true`。

## Decision Trace(抜粋)
```
decision: "Template = Tracker(Dashboardではなく)"
reason: "記録行為が主目的、集計は付随的表示"
alternatives: [{option: "Dashboard", reason_rejected: "記録操作の頻度が高く、閲覧より入力が主体"}]
confidence: 0.80
```
