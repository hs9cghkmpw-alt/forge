# Example 5: 福祉支援記録

## User Input
「利用者の支援記録を管理するアプリを作りたい」

## Normalized Input
raw_inputと同一。

## Ambiguities
| category | severity | evidence |
|---|---|---|
| missing_data | **HIGH** | 「利用者」の記録範囲(氏名のみか、健康・家族状況等の機微情報を
  含むか)が完全に未指定。welfare_support Domainの`forbidden_assumptions`
  (「対象者の同意なく第三者と記録を共有してよいと仮定しない」「氏名以外の
  識別情報を必須項目にしない」)に直接抵触しうる領域のため、安全な既定値で
  推定を進めることはできない |
| missing_actor | MEDIUM | 「caseworker(支援員)」「supervisor(責任者)」の権限差が未指定。
  Domain既定のPermission構造を仮案としつつ、確認を推奨 |

overall_severity: **HIGH**。**4.3節の基準(Privacy要件に影響する曖昧さ)
に該当するため、Forgeはこの時点でユーザーへの確認を要求し、推定して
Application Planを確定させない。**

## Intent(確認前の暫定値、confidence低め)
```
primary_goal: "支援記録の管理"
actors: ("利用者", "支援員")
required_actions: ("記録", "閲覧")
required_data: ("記録内容(範囲未確定)",)
open_questions: (
  "記録する情報の範囲(健康情報を含むか)",
  "第三者との共有可否",
  "支援員間の閲覧権限の範囲"
)
confidence: 0.35
```

confidence 0.35は、旧版では14.2節の独自閾値(現在は廃止)で「Generic
フォールバック」に近い帯域だったが、**本改訂(2026-07-15)で統一した
4.3節の優先順位に従うと、Priority1(Privacy/Safety/Permission関連の
HIGH ambiguity)が最初に評価され、confidenceの値を見るまでもなく
確認要求(Human Confirmation/Escalation、3.12節)が確定する**。
Priority2(confidence 0.5未満で原則確認)・Priority3(低リスク時のみ
Generic仮設計)は、Priority1に該当しない場合にのみ評価される、という
順序を本例が示す。

## Domain
`primary_domain: welfare_support`(confidence 0.75)。

## World Model(仮案、確認待ちのため未確定と明記)
```
Actors: recipient(利用者), caseworker(支援員), supervisor(責任者、仮)
Entities: case(案件), record(記録), service(提供サービス)
Rules: (仮)同一利用者の記録は同一caseへ集約
Permissions: (仮、確認待ち)caseworkerは担当利用者のみ閲覧可、
  supervisorは全件閲覧可
Constraints: (確認待ち)記録範囲・共有範囲
```

## Requirements
- Privacy(must、confirmation_required): 記録する情報の範囲、共有範囲。
  **この2点は`mandatory=True`かつ`priority="must"`だが、値そのものが
  未確定のため、Application Planningへは進めない。**
- 他の要件は、Privacy確認が完了するまで暫定扱い。

## Template Candidates(参考、確定ではない)
| template | score(暫定) | 備考 |
|---|---|---|
| crud | 0.70 | 案件ごとの記録追加・編集・閲覧という構造には合致しそうだが、
  権限モデル確定前のため暫定 |
| detail_list | 0.55 | 同上 |

## Selected Template
**未選択。** Privacy要件確認前にTemplate・Application Planを確定しない
(2.6節 Human Override原則)。

## Application Plan
**生成しない。** Ambiguity DetectionのHIGH判定により、Application
Planningの前段でパイプラインが停止し、ユーザーへの確認質問
(例:「支援記録には、健康状態等の機微な情報を含めますか?」「支援員は
互いの担当利用者の記録を閲覧できるようにしますか?」)を提示する。

## Critic Findings
該当なし(Application Plan自体が生成されていないため、Design Criticは
未実行)。

## Revision
該当なし。

## Decision Trace(抜粋)
```
decision: "Application Planningを保留し、ユーザー確認を要求"
reason: "記録範囲・共有範囲がPrivacy要件に直結し、Domainのforbidden_assumptions
  に抵触するリスクがあるため、推定せず確認する"
stage: "ambiguity_detection"
confidence: null  # 確認要求自体は「確定」ではないためconfidenceを付与しない
rule_used: "privacy_high_ambiguity_escalation"
```

この例は、6例のうち唯一「Application Planまで到達しない」ケースであり、
2.6節(Human Override)・4.3節(HIGH判定基準)が実際にパイプラインの
制御フローへ影響することを示す目的で選定した。
