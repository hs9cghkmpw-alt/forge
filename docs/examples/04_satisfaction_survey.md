# Example 4: 満足度アンケート

## User Input
「イベント参加者向けの満足度アンケートを作りたい。5段階評価と自由記述の
感想欄がほしい」

## Normalized Input
raw_inputと同一。

## Ambiguities
| category | severity | evidence |
|---|---|---|
| missing_actor | LOW | 「管理者」の存在は明示されていないが、Survey Domainの既定Actor
  (respondent, administrator)から安全に補える |
| missing_data | LOW | 質問項目数は「5段階評価」「自由記述」の2種のみ明示。追加質問は
  Open Questionとして保持 |

overall_severity: LOW。

## Intent
```
primary_goal: "イベント満足度の収集"
actors: ("参加者",)
required_actions: ("回答", "送信")
required_data: ("5段階評価", "自由記述感想")
constraints: ("匿名回答を前提とするか未確定",)
success_conditions: ("回答が確実に送信・保存される",)
open_questions: ("匿名性の要否", "追加質問項目の有無")
confidence: 0.80
```

## Domain
`primary_domain: survey`(confidence 0.93)。

## World Model
```
Actors: respondent(参加者), administrator(主催者、集計者)
Entities: question(質問: 5段階評価, 自由記述), response(回答), respondent(回答者)
Relationships: responseがrespondentとquestionに紐づく
Rules: 1回答者につき1回答が基本(重複送信の扱いは未確定、Open Question)
Permissions: administratorのみ集計結果を閲覧可能(参加者は自分の回答のみ)
```

## Requirements(抜粋)
- Functional(must): 5段階評価の入力、自由記述の入力、送信。
- Validation(must): 5段階評価は選択必須、自由記述は任意。
- Privacy(must): 個人を特定する情報を必須項目にしない(匿名性が
  Open Questionのため、既定で氏名等は要求しない、安全側)。

## Template Candidates
| template | score | 主な理由 |
|---|---|---|
| form | 0.90 | 複数質問項目+送信という構造そのもの |
| checklist | 0.05 | 完了状態管理ではないため不適合 |
| wizard | 0.35 | 質問数が少ないため単一画面のformで十分、多段階化は過剰 |

## Selected Template
`form`(決定的スコアで確定)。

## Application Plan(抜粋)
```
screens: (main: 質問フォーム, complete: 送信完了)
navigation_edges: (("main", "complete"),)
state_requirements: ("rating: number", "comment: string")
action_requirements: ("submit_form",)
validation_requirements: ("ratingは1〜5の範囲で必須", "commentは任意")
empty_state_requirements: ("該当なし(単一フォームのため)",)
unassigned_requirements: ("匿名性要件(Open Question)", "追加質問項目(Open Question)")
```

## Critic Findings
`overall_score: 0.83`、`release_ready: true`。minor issue:
`{severity: minor, affected_component: "main画面", recommended_fix:
"送信完了画面に戻る操作(go_back)がないため、複数回答時のフローを検討",
auto_fixable: true}`。

## Revision
1回目: complete画面へgo_back相当の「別の回答をする」導線を追加する
提案を反映。再評価: `overall_score: 0.89`。

## Decision Trace(抜粋)
```
decision: "Template = Form(Wizardではなく)"
reason: "質問数が少なく単一画面で完結可能"
alternatives: [{option: "Wizard", reason_rejected: "質問数がwizardを正当化するほど多くない"}]
confidence: 0.90
```
