# Forge 申し送り（最新）

**最終更新:** 2026-08-25

- branch: `claude/forge-master-handoff-k46jns`
- start HEAD: `166487a02c2a9601f0adb8dacff0603ba4abd478`
- implementation HEAD: `3c5a5f53e95000154625681e4c48bc9ae3494f1a`
- final HEAD: このCI実測追補を含むcommit（Git log先頭）
- current phase: Growing AI / Learning Boundary Hardening
- current task: FORGE-018A — 実装・push・CI確認完了
- next task: FORGE-019 Semantic Design Revision

## 継続中のCEO依頼

- 過去にチャットへ貼られたOpenAI API keyは使用・保存していない。失効と
  再発行が必要で、新keyはチャットでなく`backend/.env`へ直接設定する
- CEO環境でCORS障害が続く場合はブラウザconsoleの実エラーが必要

## 現在地 / 実装内容

FORGE-018独立Reviewで見つかったBlocking設計問題を修正した。Local Learning
Event projectionはConsent/App Contextを読まない。Cloud境界でsubject-scopedな
`ConsentSnapshot`と`ProjectionContext`を明示的に渡すため、A利用者の同意が
B利用者へ漏れるprocess-global mutable stateは無い。

```
Existing Evidence
  -> Local LearningEvent
  -> scoped CloudExportPolicy (collection rights)
  -> ExportDecision / optional in-memory outbox
  -> TrainingEligibilityPolicy (training rights)
  -> eligible only: DatasetCandidate
     all results: LearningEventEvaluationRecord
```

Collection RightsとTraining Rightsは分離した。`training_use=FORBIDDEN`でも明示的
usage statistics consent等を満たす安全なmetadata EventはCloud collection候補に
できるが、Dataset Candidateにはならない。Cloud export可だけではTraining可に
ならない。

Event provenanceはModel用`TrainingProvenance`から独立した
`LearningDataProvenance`へ変更。Cloud AI outputはprovider training termsが
明示TrueでなければTraining不可。Provider deploymentはRegistryをSource of
Truthとし、Mock/CuratedをLocal AI実績へ数えない。

## Consent / Privacy / Retention

- Consentは6カテゴリ・既定ALL OFF・immutable choices
- 変更/撤回はnew snapshot ID + previous snapshot ID + effective_atの追記
- Event Type別中央routing。REVISIONはsemantic corrections、未知はfail closed
- withdrawal後は未送信Outbox削除、Dataset Candidate REVOKED、旧snapshot再利用拒否
- RetentionをLocal Event、Export Decision/Evaluation、Outbox、Dataset Candidate、
  Learning Artifactへ適用
- LearningEventにraw発話/会話/response/Document/secret/handle/tokenなし
- 既学習weightのunlearning、完全PII検出は未実装

## Production wiring

Experience/Generation/Revision/Feedback Store直後の単一Projector配線を維持。
AI_CALL / GENERATION / FEEDBACKはHTTP/Store経路でLocal Eventをemitする。
Learning projector障害はfailure counter/error typeを残すが、Evidence/生成成功を
壊さない。配線を外すと正常wiring testはFAILする。

Production既定では自動Cloud評価を行わず、Local Eventだけ残る。Cloud network
送信、durable outbox、Supabase、Auth/RLS、Production server-issued identityは
未実装。Test Double identityでEnvelope boundaryだけを確認した。

## Agent Protocol

root `AGENTS.md`を新設。GitHub/MarkdownをSource of Truthとし、開始監査、
未commit差分保護、Implementation Agent 1つ、commit/pushで交代、Reviewer独立
確認、UNVERIFIED、Production wiring + mutation + MD + push + CIを恒久Rule化。
`CLAUDE.md`冒頭もroot Protocolを正として読むよう更新した。

## Tests

- FORGE-018A focused: **19 passed**
- backend full: **1425 passed, 17 skipped**
- forge_ai full: **521 passed**
- Ruff: **All checks passed**
- Flutter test: **508 passed**
- Flutter analyze: **No issues found**
- Flutter build web: **success**
- CI run `32806619017`: **success**（implementation HEAD `3c5a5f5`）
  - backend + forge_ai (Python 3.11): success
  - backend + forge_ai (Python 3.12): success
  - backend smoke (起動 + CORS): success
  - frontend (Flutter): success

## Intentional break / mutation

10 roundすべてFAIL確認後に復元:

1. Collection PolicyへTrainingUseを混入
2. Training Policyからtraining_useを除去
3. REVISIONをusage statisticsへ誤routing
4. Event provenanceをTrainingProvenanceへ戻す
5. AのConsentをBへ共有
6. withdrawal後もCandidateを残す
7. Dataset retentionを無効化
8. provider名hard-codeへ戻す
9. CURATEDをLOCAL_AIとして数える
10. AGENTS.mdを削除

## 未検証 / Technical Debt

- 全Learning Store/Consent/diagnosticはin-memory、再起動で失われる
- Cloud network/Supabase/Auth/RLS/server identity未実装、実Cloud送信0件
- Cloud provider terms取得経路なし。UNKNOWNはTraining不可
- 実Local Model生成0回、実Training 0回
- Learning ArtifactのProduction保存/送信なし
- Sanitizerは既知patternのみ
- Flutter Feedback UIとRevision HTTP wiringはFORGE-019

詳細は`docs/reports/FORGE-018A-LEARNING-BOUNDARY-HARDENING-report.md`。

## 次のTask / 次の3手

FORGE-018Aのpush/CIがgreenになってからFORGE-019 Semantic Design Revisionへ進む。

1. artifact handle/version tokenをFlutter Domain層へ安全に通しFeedback UIを接続
2. Semantic target resolution/typed operation/local patchを`/update`へ接続
3. Revision Evidence -> Feedback -> Learning EventをValidator/Critic込みで閉じる
