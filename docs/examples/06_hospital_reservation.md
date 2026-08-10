# Example 6: 病院予約

## User Input
「患者が診療科と時間枠を選んで予約できるアプリ。同じ時間枠に重複予約は
できないようにしたい」

## Normalized Input
raw_inputと同一。

## Ambiguities
| category | severity | evidence |
|---|---|---|
| missing_actor | LOW | 「医師」「管理者」の明示は無いが、reservation Domainの既定Actorから
  安全に補える |
| missing_data | LOW | キャンセル・変更操作の明示は無いが、common_actionsから安全に補える |

overall_severity: LOW(「重複予約不可」という明示的なRuleがあるため、
Domain Ruleとの整合性が高くAmbiguityは低い)。

## Intent
```
primary_goal: "診療予約の管理"
actors: ("患者",)
required_actions: ("予約作成", "診療科選択", "時間枠選択")
required_data: ("診療科", "時間枠")
constraints: ("同一時間枠の重複予約不可",)
success_conditions: ("患者が予約を確認できる",)
confidence: 0.87
```

## Domain
`primary_domain: reservation`(confidence 0.85)。
candidate_domains: `(schedule: 0.4)`(却下理由: 個人スケジュールではなく
患者・医師間の予約という多者間関係が中心のため)。

## World Model
```
Actors: 患者, 医師, 管理者
Entities: 予約, 診療科, 時間枠
Relationships: 患者が予約を持つ / 医師が時間枠を提供する
Rules: 同一時間枠へ重複予約不可
Events: 予約作成, 予約キャンセル, 予約変更
States: 予約ステータス(仮予約/確定/キャンセル済み)
Permissions: 患者は自分の予約のみ閲覧可、管理者は全予約閲覧可
Constraints: 時間枠は診療科の営業時間内のみ
```

(9章の例と同一内容。World Modelの再現性を示すため同じDomainを使用。)

## Requirements(抜粋)
- Functional(must): 診療科選択、時間枠選択、予約作成、重複チェック。
- Validation(must): 選択した時間枠が既に予約済みでないこと。
- Data(must): 予約一覧、診療科一覧、時間枠一覧。

## Template Candidates
| template | score | 主な理由 |
|---|---|---|
| calendar | 0.75 | 時間枠という時間軸に基づく選択が中心 |
| form | 0.60 | 診療科・時間枠の選択+送信という側面もあるが、時間軸の可視化(calendar)がより本質的 |
| wizard | 0.50 | 診療科→時間枠という段階的選択はwizard的だが、画面数が少なく単純なcalendar+formの組み合わせで十分 |

## Selected Template
`calendar`(僅差のためLLM tie-breakを実施。「時間枠の空き状況を
視覚的に把握できることが患者にとって重要」という理由でcalendarを選択、
formは予約確定画面の一部として併用)。

## Application Plan(抜粋)
```
screens: (main: 診療科選択+時間枠カレンダー, confirm: 予約確認)
navigation_edges: (("main", "confirm"),)
state_requirements: ("selected_department: string", "selected_slot: string", "reservations: 構造化リスト")
action_requirements: ("select_slot", "submit_form(予約確定)", "navigate")
validation_requirements: ("selected_slotが既存予約と重複しないこと",)
error_state_requirements: ("満枠の時間枠を選択不可にする表示",)
```

## Critic Findings
`overall_score: 0.86`、`release_ready: true`。minor issue:
`{severity: minor, recommended_fix: "予約キャンセル機能がApplication Planに
明示されていない(Domain Ruleにはあるがrequired_actionsに未反映)",
auto_fixable: false}`。

## Revision
1回目: `action_requirements`へ`cancel_reservation`を追加。
再評価: `overall_score: 0.90`。

## Decision Trace(抜粋)
```
decision: "Template = Calendar(Formではなく)"
reason: "時間枠という時間軸中心の選択体験が本質的"
alternatives: [{option: "Form", reason_rejected: "時間軸の可視化ができない"}]
confidence: 0.75  # 僅差だったためLLM tie-breakを経た旨も記録
provider_used: "mock"
```
