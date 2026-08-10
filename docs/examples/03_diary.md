# Example 3: 日記

## User Input
「毎日の気分と出来事を記録できる日記アプリ」

## Normalized Input
raw_inputと同一。

## Ambiguities
| category | severity | evidence |
|---|---|---|
| missing_data | LOW | 「気分」の表現形式(数値/絵文字/自由記述)が未指定だが、自由記述を
  既定値にして安全に継続可能 |

overall_severity: LOW。

## Intent
```
primary_goal: "日々の記録(気分・出来事)"
required_actions: ("記録", "閲覧", "編集")
required_data: ("日付", "気分", "本文")
constraints: ("1日1エントリが基本",)
success_conditions: ("過去の記録を日付で振り返れる",)
confidence: 0.85
```

## Domain
`primary_domain: diary`(confidence 0.92)。

## World Model
```
Actors: 本人
Entities: entry(記録), date(日付), mood(気分)
Relationships: entryが特定のdateに属する
Rules: 同一日付に複数entryを許容するか(仕様上は許容、UIでは日付ごとに
  グルーピング表示)
Events: entry作成, entry編集
States: entries一覧
```

## Requirements(抜粋)
- Functional(must): entryの作成・閲覧・編集。
- Data(must): 日付・気分・本文。
- Accessibility(should): 長文本文の入力・閲覧がしやすいこと。

## Template Candidates
| template | score | 主な理由 |
|---|---|---|
| memo | 0.85 | 自由記述本文+日付という構造に合致 |
| tracker | 0.45 | 気分の推移を継続記録する点は近いが、本文中心の記録にはmemoが適する |
| checklist | 0.10 | 完了/未完了という概念が無く不適合 |

## Selected Template
`memo`(決定的スコアで確定)。

## Application Plan(抜粋)
```
screens: (main: entry一覧, edit: entry編集/新規作成)
state_requirements: ("entries: 構造化リスト(日付+気分+本文)", "current_entry_text: string")
action_requirements: ("save_entry", "navigate")
empty_state_requirements: ("entryが無い場合の案内文",)
```

## Critic Findings
`overall_score: 0.88`、`release_ready: true`。

## Revision
不要。

## Decision Trace(抜粋)
```
decision: "Template = Memo"
reason: "自由記述本文が中心で、完了状態の管理が不要"
alternatives: [{option: "Tracker", reason_rejected: "気分の数値推移グラフ化は今回のIntentに明示されていない"}]
confidence: 0.85
```
