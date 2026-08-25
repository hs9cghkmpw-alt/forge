# FORGE-018A — Learning Boundary Hardening + Agent Protocol

2026-08-25 / branch `claude/forge-master-handoff-k46jns`

- start HEAD: `166487a02c2a9601f0adb8dacff0603ba4abd478`
- final HEAD: このReportを含むcommit（Git log先頭）
- next task: FORGE-019 Semantic Design Revision

## 再現した問題 / 原因

独立Reviewの指摘を実コードで再現した。

1. `TrainingEligibilityPolicy`がConsent/Sanitizer/Cloud境界まで担当し、
   collection可否とtraining可否が同じ`eligible`になっていた
2. Event由来へModel用`TrainingProvenance`を流用してSpecに違反していた
3. FEEDBACK以外を一律usage statisticsへrouteしていた
4. singleton serviceのmutable `consent/context`が利用者間で共有可能だった
5. withdrawalが同じsnapshot IDを書き換え、判断時点を再現できなかった
6. RetentionはLocal Eventだけを削除していた
7. 全EventをRejectedを含む`DatasetCandidate`にして意味を曖昧にしていた
8. deploymentをprovider/source名からhard-codeし、Curated/MockをLocal扱いした
9. 同期Projector例外がEvidence/生成本体を失敗させ得た
10. root `AGENTS.md`がなく、GitHub/Markdown共有記憶の指示がRepositoryに無かった

## Architecture判断 / 実装

### Local projectionとCloud境界

`LearningEventProjector.project(evidence)`はConsent/App Contextを受け取らない。
既存Evidenceからcontent-free Local Eventだけを生成する。subject-scopedな
`ConsentSnapshot`と`ProjectionContext`は`evaluate_for_export()`へ明示的に
渡す。serviceに利用者単位のmutable consent/contextは存在しない。

```
Existing Evidence
  -> Local LearningEvent projection
  -> explicit subject-scoped export request
     -> CloudExportPolicy (collection rights)
     -> ExportDecision + optional CloudLearningEnvelope outbox
     -> TrainingEligibilityPolicy (training rights)
     -> eligible only: DatasetCandidate
     -> all results: LearningEventEvaluationRecord
```

### Collection rights / Training rights

`CloudExportPolicy`はEvent type別Consent、residency、scope、contribution target、
sanitizer、app trust、server identity、expiryだけを見る。`training_use`は見ない。
`TrainingEligibilityPolicy`はcollection可を前提にtraining use、data provenance、
Cloud provider terms、TEST_DOUBLE、validator/runtime evidenceを見る。

実測testでは`training_use=FORBIDDEN`かつusage statistics consent ONの安全な
Curated metadata EventがCloud Export eligible/outbox 1件となる一方、Training
eligible=false、Dataset Candidate 0件となった。Cloud export可だけではDatasetへ
入らない。

### Provenance / Deployment

Event専用`LearningDataProvenance`を追加した。CURATED / LOCAL_AI_OUTPUT /
CLOUD_AI_OUTPUT / USER_EXPLICIT_FEEDBACK / USER_CORRECTION /
DETERMINISTIC_RUNTIME / TEST_DOUBLE / UNKNOWNの閉じた型である。
`TrainingProvenance`はModel/Knowledge provenance用途のまま変更しない。

Experienceのdeployment/provenanceは`ProviderDefinition` / Registryから決める。
MockはRegistry上LOCALでもtest_onlyを先に弾きTEST_DOUBLE + deployment UNKNOWN。
CuratedはNOT_APPLICABLEでLocal AI実績へ数えない。未登録providerはUNKNOWN。
Cloud outputはprovider termsがTrueと確認されなければDataset Candidateにならない。

### Consent / Routing / Isolation

Consent choicesは`MappingProxyType`でimmutable。変更/withdrawalは新しい
snapshot ID、`previous_snapshot_id`、`effective_at`を持つ追記である。
中央mappingはAI_CALL/GENERATION/Benchmark/Build/Test metadataをusage
statistics、FEEDBACKをAI feedback、REVISIONをsemantic corrections、Crash/
Runtimeをruntime crashへrouteする。未知Eventはfail closed。

Subject A=ON、B=OFFを同じserviceで逐次・ThreadPool並列評価し、Aだけがexport
eligible/outboxに入ることを確認した。BはAのConsentを参照しない。

### Retention / withdrawal / lineage

RetentionをLocal Event、Export Decision/Evaluation、Outbox、Dataset Candidate、
Learning Artifactへ適用した。Rejected評価は
`LearningEventEvaluationRecord`へ残し、Dataset CandidateはTraining eligibleな
Eventだけ作る。withdrawalは未送信Outboxを削除し、同じsnapshot由来の未学習
CandidateをREVOKED + revoked_atへ変更し、旧snapshotの将来再利用も拒否する。
既学習weightのunlearningは未実装。

### Safe observation / Production wiring

Experience/Generation/Revision/Feedback Store直後の単一hookは維持した。
`observe_evidence()`はProjector例外をcatchし、content-freeなfailure countと
error typeへ記録してEvidence本体を成功させる。Projectorを故意にraiseさせ、
ExperienceRecordが保存されdiagnosticが増えることを確認した。正常時の
AI_CALL/GENERATION/FEEDBACK production wiring testも残る。

## 変更ファイル

- `AGENTS.md`（新規） / `CLAUDE.md`
- `backend/app/ai/gateway/learning_events.py`
- `backend/tests/test_learning_events.py`
- `docs/HANDOFF.md`
- 本Report、Learning Event Spec、Growing AI Architecture、Roadmap
- `TECH_DEBT.md`、`CHANGELOG.md`

## Tests / Regression

- FORGE-018A focused: 19 passed
- backend full: 1425 passed, 17 skipped
- forge_ai full: 521 passed
- Ruff: All checks passed
- Flutter test: 508 passed（Golden/E2E含む）
- Flutter analyze: No issues found
- Flutter build web: success（Wasm dry-run advisoryのみ）
- CI: push後確認（Python 3.11 / 3.12 / backend smoke / Flutter）

## Intentional break

以下10 roundを1件ずつ壊し、すべて対応testのFAILを確認して復元した。

1. CloudExportPolicyへTrainingUse判定を混入
2. TrainingEligibilityからtraining_useを除去
3. REVISIONをusage statisticsへ誤routing
4. Event provenanceをTrainingProvenanceへ戻す
5. subject AのConsentをBへ共有
6. withdrawal後もDataset CandidateをCANDIDATEのまま残す
7. Dataset retention配線を外す
8. provider名hard-codeへ戻す
9. CURATEDをLOCAL_AIとして数える
10. root AGENTS.mdを削除

復元後focused 19件PASS、`MUTATION`/`False and`痕跡なし。

## AGENTS.md proof

root ProtocolへGitHub Source of Truth、開始時の文書/Git監査、未commit差分保護、
Implementation Agent 1つ、commit/pushで交代、独立ReviewerによるHEAD/diff/
code/tests/CI確認、UNVERIFIED表記、Production wiring + mutation + MD + push + CI
を完了条件として記録した。CLAUDE.md冒頭からroot Protocolを参照する。

## 未検証 / Risk / Technical Debt

- Cloud network送信、Supabase、Auth/RLS、durable outboxは未実装
- Production server-issued identityは未実装。Test Doubleのみ
- Consent/Retention/Evaluationはin-memoryで再起動に耐えない
- Cloud provider termsを取得するProduction経路は未実装
- Learning observer diagnosticsはprocess-local counterで再処理queueなし
- Learning Artifactはin-memory契約/retentionのみ
- 実Local Model生成0回。実Training/Weight unlearningは未実装
- Sanitizerは既知patternのみでPII 100%検出ではない

## Product Direction 7問

1. 生成品質: Learning障害が生成成功を壊さないため後退を防ぐ
2. Local AI: 権利・由来が正しいDataset Candidateだけを残す構造になった
3. 両軸: Flutter Golden 508件を維持しLearning側をhardeningした
4. Template依存: 追加なし
5. Production Path: 既存Store/HTTPからLocal Eventまで実測、Cloudは未送信
6. Evidence: Evaluation/Consent/Dataset lineageを保持する
7. 最終目標: 縮小なし。未実装Cloud/Trainingは明示した

## 次に行うこと

FORGE-018AのCIがgreenになった後、FORGE-019 Semantic Design Revisionへ進む。
Target resolution -> typed operation -> local patch -> Validator/Critic -> Revision
Evidence -> Feedback -> Learning EventをProductionで閉じる。
