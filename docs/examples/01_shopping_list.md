# Example 1: 買い物リスト

## User Input
「家族で使える買い物リストを作って」

## Normalized Input
`raw_input` と同一(表記揺れ・誤字なし)。`applied_rules: ()`。

## Ambiguities
| category | severity | evidence |
|---|---|---|
| missing_data | LOW | 「何を買うか」の初期項目が無いが、空リストから開始できるため既定値で継続可能 |
| missing_action | LOW | 「削除」「共有」の明示は無いが、Shopping Domainのcommon_actionsから安全に補える |

overall_severity: LOW(確認要求なし、既定値で継続)。

## Intent
```
primary_goal: "共有買い物管理"
secondary_goals: ("価格の記録",)
actors: ("本人", "家族")
required_actions: ("追加", "完了", "削除", "共有")
required_data: ("品目", "数量")
constraints: ("複数利用者", "簡単操作")
success_conditions: ("家族全員が同じリストを見て更新できる",)
prohibited_behaviors: ()
open_questions: ("価格を記録するか未確定",)
confidence: 0.82
evidence: ("家族で使える" → actors/constraints, "買い物リスト" → primary_goal/required_data)
```

## Domain
`primary_domain: shopping`(confidence 0.9、"買い物"がcommon_actions/
entitiesと直接一致)。candidate_domains: `(household_budget: 0.2)`
(却下理由: 「買い物」は支出記録ではなく品目管理が主目的のため)。

## World Model
```
Actors: 本人, 家族
Entities: item(品目), price(価格、任意), store(店舗、任意)
Relationships: 本人が家族とitemリストを共有する
Rules: 同一itemの重複追加を許容する(買い忘れチェックのため)
Events: item追加, item完了, item削除
States: item.done(boolean)
Permissions: 家族全員が追加・完了・削除可能(権限差なし)
Constraints: なし
```

## Requirements(抜粋)
- Functional(must): 品目の追加・完了マーク・削除ができる。
- Data(must): 品目テキスト、完了フラグ。
- Interaction(should): 複数人が同時に更新しても矛盾しない(簡易な最終更新優先で可)。
- Privacy(must): 家族以外への共有が既定でオフ。
- Open Questions: 価格記録の要否。

## Template Candidates
| template | score | 主な理由 |
|---|---|---|
| checklist | 0.88 | 項目ごとに独立した完了状態、追加/削除が中心操作 |
| form | 0.15 | 単一送信の性質が薄いため不適合 |
| tracker | 0.30 | 価格記録が確定すれば候補になるが、現時点はOpen Question |

## Selected Template
`checklist`(スコア差が大きく決定的に確定、LLM tie-break不要)。

## Application Plan(抜粋)
```
app_goal: "家族で使える買い物リスト"
screens: (main画面のみ)
screen_responsibilities: { main: "品目一覧の表示・追加・完了・削除" }
state_requirements: ("items: checklist", "new_item_text: string")
action_requirements: ("add_item", "toggle_state(完了)", "delete_item")
validation_requirements: ("new_item_textは空文字での追加を無視",)
empty_state_requirements: ("項目が無い場合のメッセージ表示",)
error_state_requirements: ("追加失敗時の非クラッシュ",)
unassigned_requirements: ("価格記録(Open Question、今回のPlanには含めない)",)
design_rationale: "checklistは既存forge_ai/実装(ChecklistTemplate)と一致し、
  実績のあるTemplateであるため採用"
```

## Critic Findings
`overall_score: 0.91`、`release_ready: true`。issue無し
(empty_state_requirements・error_state_requirementsが明示されているため)。

## Revision
不要(Critic初回評価で合格)。

## Decision Trace(抜粋)
```
decision: "Template = Checklist"
reason: "項目ごとに独立した完了状態を管理する用途"
alternatives: [{option: "Form", reason_rejected: "単一送信の性質が無い"}]
confidence: 0.88
```
