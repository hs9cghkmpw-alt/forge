# FORGE-018 — Growing AI Learning Event Foundation（commit E）

2026-08-25 / branch `claude/forge-master-handoff-k46jns`

start HEAD `7f31aa46785d6db7fbcc4bbf7097b9bd889c927e`

final HEAD: このreportを含むcommit（Git log先頭）

## 再現した欠落 / 原因

017Aの語彙はあったが、`LearningEvent`本体、Projector、Consent、Sanitizer、
Retention、Outbox、Dataset lineageは実コードに存在せず、HTTPからEvidenceを
作ってもLearning Eventは0件だった。commit E用に契約だけ先行し、Production
wiringが未着手だったことが原因である。

## Architecture判断

- Existing Evidenceが唯一のSource of Truth。置換・並列体系化しない
- 全Storeの`record/append`直後を単一Projectorへ接続
- Local LearningEventとCloudLearningEnvelopeは別型
- Local Eventにcross-session contributor identityを持たせない
- Consentは6カテゴリ、既定ALL OFF
- 中央`TrainingEligibilityPolicy`で判断
- client app_idは`UNTRUSTED`のままGlobalへ流さない
- server-issued identityやCloud送信を捏造しない

## 変更ファイル

`backend/app/ai/gateway/learning_events.py`、`learning_contract.py`、
`learning_foundation.py`、`generation_evidence.py`、`revision_evidence.py`、
`artifact_feedback.py`、`backend/tests/test_learning_events.py`、本report、
`docs/HANDOFF.md`、ROADMAP/Architecture/Spec、`TECH_DEBT.md`、`CHANGELOG.md`。

## 実装 / Production path

`LearningEvent`は仕様の構造fieldを持ち、取得不能値はNone/unknown。
ProjectorはExperience→AI_CALL、Generation→GENERATION、Feedback→FEEDBACK、
Revision→REVISIONを変換する。Production emit済みと呼ぶのは最初の3種のみ。

```
POST /generate (mock)
  → ExperienceStore → AI_CALL
  → GenerationEvidenceStore → GENERATION
POST /feedback accepted  → append sequence=1 → FEEDBACK
POST /feedback corrected → append sequence=2 → FEEDBACK
```

HTTP focused runではAI Call 1件、Generation 1件、Feedback 2件、Dataset
Candidate 4件、Cloud Outbox 0件を実測。別入力やPipeline変更でcall数は
変わりうるため一般的な固定公称にはしない。Generationには
`knowledge_references`と永続artifact evidence IDが残る。

## Consent / Privacy / Sanitizer

ConsentSnapshotはusage statistics / AI feedback / semantic corrections /
sanitized artifacts / code diff / runtime crashを別々に保持し既定全OFF。
withdrawalは未送信Outboxを消し、将来exportを止める。既学習weightの
unlearningは実装しない。

LearningEvent型にraw utterance/conversation/provider response/Document/
secret/handleは無い。SanitizerはAPI key、Bearer、JWT、private key、secret
env、email、phone、address-like値を拒否するが、PII検出100%とはしない。

## Dataset lineage / Retention / Artifact

全Eventから`DatasetCandidate`を作りsource event/artifact IDsを保持。不適格
でもREJECTEDとして系譜を失わない。Training Dataset昇格やTrainingはしない。
RetentionはLocal/Cloud Candidate/Rejected/Artifactを中央Policyで分離し、
expired Local Event削除をテストした。LearningArtifactは別契約のみ。

## Cloud / Supabase

Production Cloud送信: **未実装・0件・blocked**。trusted server identity、
Supabase Auth/RLS/migration、Consentを利用者へ安全に結ぶ境界が無いため。
Test Double identityではEnvelope/Outbox 1件を実証したがnetwork送信ではない。

## Tests / Intentional break

- focused: 18 passed
- backend full: 1424 passed, 17 skipped
- forge_ai full: 521 passed
- ruff: All checks passed
- Flutter test: 508 passed
- flutter analyze: No issues found
- flutter build web: 成功（CupertinoIcons font warningあり、build自体は成功）
- CI: push後確認

13 mutation: Projector配線、Consent default、UNKNOWN/FORBIDDEN、TEST_DOUBLE、
Feedback時系列、raw field、LOCAL_ONLY、Sanitizer、Knowledge refs、artifact handle、
server identity、app trust、expiryを1つずつ壊し、全てFAILを確認して復元した。

## Flutter判断

配置先は`GeneratedAppHostShell`だが、Frontend parserがartifact handle/version
tokenを捨てる。世代照合なしのボタンは誤対象へ書くため、FORGE-019でDomain
entity/API parser/host shellを一緒に接続する。Backend contractは今回固定。

## 未検証 / Risk / 次

Outbox durable化、Supabase/Auth/RLS/server identity、実Cloud送信、実Local
Model（0回）、Artifact永続化、完全PII検出は未検証/未実装。

Product Direction 7問: Golden回帰を維持し、Local AI用lineageを作り、生成軸を
後退させず、Template依存を増やさず、HTTP Production Pathを実測し、Evidenceを
残し、未実装領域を縮小せず明記した。

次はFORGE-019 Semantic Design Revision。Target resolution → typed operation →
local patch → Validator/Critic → Revision Evidence → Feedback → Learning Event。
